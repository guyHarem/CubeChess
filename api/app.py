"""
Flask API for CubeChess game engine.
Provides HTTP endpoints for game management.
"""

import json
import os
import sys

# Make the project root importable so `python api/app.py` works from any directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, jsonify, g
from flask_cors import CORS
from api.rooms import Rooms
from api.utils import convert_response
from engine.pieces import Queen, Rook, Bishop, Knight

app = Flask(__name__)
CORS(app)

# Every game lives in its own room (api/rooms.py), chosen with ?game=<room id>. POST /api/games
# opens a new one. Two rooms always exist for the developer test bench and the tests:
# "main" (used when a request names no game) and "practice".
rooms = Rooms()
game_manager = rooms.get("main").manager
practice_manager = rooms.get("practice").manager


@app.before_request
def choose_game():
    if request.path == '/api/games':
        return None
    room = rooms.get(request.args.get("game", "main"))
    if room is None:
        return jsonify({"success": False, "gone": True, "error": "This game no longer exists"}), 404
    g.room = room
    g.manager = room.manager
    # The secret key a seated player sends with every request; None for anyone else
    g.color = room.color_of(request.headers.get("X-Seat"))
    room.seen(g.color)
    return None


def reply(response, **extra):
    """Send a game-manager answer to the page, with the room's details added"""
    room = g.room
    status_code = 200 if response.get("success") else 400
    response = convert_response(response)
    response.update(extra)
    if "board" in response:
        response["game_id"] = room.id
        response["kind"] = room.kind
        response["stamp"] = room.stamp()
        response["online"] = room.describe(g.color) if room.kind == "online" else None
    return jsonify(response), status_code


def refuse(message, status_code=400):
    return jsonify({"success": False, "error": message}), status_code


def online():
    return g.room.kind == "online"


def not_online():
    return refuse("That is not available in an online game") if online() else None


def parse_coord(value):
    """Convert a JSON [x,y,z] list to an (x,y,z) tuple, or raise ValueError"""
    if (not isinstance(value, list) or len(value) != 3 or
            not all(type(n) is int for n in value)):
        raise ValueError("Coordinate must be [x, y, z] integers")
    return tuple(value)


# ==================== GAME SETUP ====================

def start(manager, data):
    """Begin a game in a room from the options the page sent"""
    response = manager.new_game(rocks=bool(data.get("rocks", True)), move_limit=data.get("move_limit", 50),
                                clock=data.get("clock"), computer=data.get("computer"))
    if response.get("success") and response.get("computer") and hasattr(manager._think, "warm_up"):
        manager._think.warm_up()
    return response


@app.route('/api/games', methods=['POST'])
def open_game():
    """Open a new room and start a game in it. Body: {"kind": "local" | "computer" | "online" | "practice"}
    plus the options of /api/game/new. An online game also takes "side": the color the
    creator plays ("white" by default); the answer then carries the creator's secret "seat" key.
    The answer's "game_id" is the room: pass it as ?game=<game_id> from then on."""
    data = request.get_json(silent=True) or {}
    kind = data.get("kind", "local")
    side = data.get("side", "white")
    if kind == "online" and side not in ("white", "black"):
        return refuse('side must be "white" or "black"')
    if (kind == "computer") != (data.get("computer") is not None):
        return refuse("A computer game needs the computer's color and level, and only a computer game takes them")
    try:
        room = rooms.create(kind)
    except ValueError as e:
        return refuse(str(e))
    g.room, g.manager, g.color = room, room.manager, None
    response = start(room.manager, data)
    if not response.get("success"):
        return reply(response)
    if kind == "online":
        seat = room.sit(side)
        g.color = side
        return reply(response, seat=seat)
    return reply(response)


@app.route('/api/game/new', methods=['POST'])
def new_game():
    """Start a new game in the same room. Optional body:
    {"rocks": true, "move_limit": 50, "clock": {"initial": 600, "increment": 5},
     "computer": {"color": "black", "level": "hard"}} (clock in seconds; omit clock or computer for none)"""
    return not_online() or reply(start(g.manager, request.get_json(silent=True) or {}))


@app.route('/api/game/join', methods=['POST'])
def join_game():
    """Open an online game's link: take the free seat if there is one. The answer carries
    "seat" (your secret key) when you are a player; without it you are watching."""
    if not online():
        return refuse("Only online games are joined")
    seat, g.color = g.room.join(request.headers.get("X-Seat"))
    g.room.seen(g.color)
    return reply(g.manager.get_state(), seat=seat)


# ==================== QUERIES ====================

@app.route('/api/game/state', methods=['GET'])
def get_state():
    """Get current game state (board, player, status). A page that asks every second adds
    ?since=<the "stamp" of its last answer>: if nothing has changed it gets a short answer
    with just the clock and who is connected."""
    response = g.manager.get_state()
    if request.args.get("since") == g.room.stamp():
        return jsonify({"success": True, "unchanged": True, "stamp": g.room.stamp(), "clock": response["clock"],
                        "online": g.room.describe(g.color) if online() else None})
    return reply(response)


@app.route('/api/game/legal-moves', methods=['GET'])
def get_legal_moves():
    """Get legal moves for a piece at given coordinate"""
    # Extract coordinate from query string: ?from=[0,1,0]
    from_str = request.args.get('from')
    
    if not from_str:
        return jsonify({"success": False, "error": "Missing 'from' parameter"}), 400
    
    try:
        # Parse JSON array string to list, then to tuple: "[0,1,0]" → (0,1,0)
        from_coord = parse_coord(json.loads(from_str))
        
        return reply(g.manager.get_legal_moves(from_coord))
    except ValueError:
        return jsonify({"success": False, "error": "Invalid coordinate format"}), 400


# ==================== MOVES ====================

@app.route('/api/game/move', methods=['POST'])
def make_move():
    """Execute a move"""
    data = request.get_json(silent=True)
    
    if not data or 'from' not in data or 'to' not in data:
        return jsonify({"success": False, "error": "Missing 'from' or 'to' in body"}), 400
    
    try:
        # Convert lists to tuples
        from_coord = parse_coord(data['from'])
        to_coord = parse_coord(data['to'])
        
        with g.manager.lock:
            refusal = not_your_move()
            if refusal:
                return refusal
            response = g.manager.make_move(from_coord, to_coord)
            if response.get("success"):
                g.room.clear_offer()   # moving on answers a pending offer with "no"
            return reply(response)
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "Invalid coordinate format"}), 400


def not_your_move():
    """In an online game only the player whose turn it is may move"""
    if not online():
        return None
    if g.color is None:
        return refuse("You are watching this game", 403)
    if g.color != g.manager.game.current_player:
        return refuse("It is not your move", 403)
    return None


@app.route('/api/game/computer-move', methods=['POST'])
def computer_move():
    """Let the computer think and play. The page calls this when it is the computer's turn."""
    return reply(g.manager.computer_move())


# ==================== SPECIAL MOVES ====================

@app.route('/api/game/promote', methods=['POST'])
def promote_pawn():
    """Promote a pawn to a new piece"""
    data = request.get_json(silent=True)
    
    if not data or 'coord' not in data or 'piece_type' not in data:
        return jsonify({"success": False, "error": "Missing 'coord' or 'piece_type' in body"}), 400
    
    try:
        coord = parse_coord(data['coord'])
        piece_type_str = data['piece_type']  # e.g., "Queen", "Rook", etc.
        
        # Map string to piece class
        piece_classes = {
            'Queen': Queen,
            'Rook': Rook,
            'Bishop': Bishop,
            'Knight': Knight
        }
        
        if piece_type_str not in piece_classes:
            return jsonify({"success": False, "error": f"Invalid piece type: {piece_type_str}"}), 400
        
        # Get piece class and create instance with current player's color
        PieceClass = piece_classes[piece_type_str]
        # The turn only passes once the promotion is done, so it's the current player's piece
        with g.manager.lock:
            refusal = not_your_move()
            if refusal:
                return refusal
            new_piece = PieceClass(g.manager.game.current_player)
            return reply(g.manager.promote_pawn(coord, new_piece))
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "Invalid coordinate format"}), 400


# ==================== ENDING THE GAME BY CHOICE ====================

@app.route('/api/game/resign', methods=['POST'])
def resign():
    """Resign. Optional body: {"color": "white"}; without it the player to move resigns.
    In an online game you resign for yourself, whatever the body says."""
    data = request.get_json(silent=True) or {}
    if online():
        if g.color is None:
            return refuse("You are watching this game", 403)
        response = g.manager.resign(g.color)
        if response.get("success"):
            g.room.clear_offer()
        return reply(response)
    return reply(g.manager.resign(data.get("color")))


@app.route('/api/game/draw', methods=['POST'])
def agree_draw():
    """Both players agreed to a draw (two players on one screen), or a draw offer to the
    computer. Online games use /api/game/offer."""
    return not_online() or reply(g.manager.agree_draw())


# ==================== OFFERS BETWEEN ONLINE PLAYERS ====================

def offer_reply(action):
    if not online():
        return refuse("Only online games have offers")
    try:
        action()
    except ValueError as e:
        response = g.manager.get_state()
        response["success"] = False
        response["error"] = str(e)
        return reply(response)
    return reply(g.manager.get_state())


@app.route('/api/game/offer', methods=['POST'])
def make_offer():
    """Offer a draw or ask to take your last move back: {"kind": "draw" | "takeback"}.
    The opponent sees it in the game's "online" details and answers with /api/game/answer."""
    data = request.get_json(silent=True) or {}
    return offer_reply(lambda: g.room.make_offer(g.color, data.get("kind")))


@app.route('/api/game/answer', methods=['POST'])
def answer_offer():
    """Answer the pending offer: {"accept": true | false}. The player who made the offer can
    withdraw it with {"accept": false}."""
    data = request.get_json(silent=True) or {}
    return offer_reply(lambda: g.room.answer(g.color, bool(data.get("accept"))))


# ==================== UNDO ====================

@app.route('/api/game/undo', methods=['POST'])
def undo_move():
    """Undo the last move. Online games ask the opponent instead (/api/game/offer)."""
    return not_online() or reply(g.manager.undo_move())


# ==================== SANDBOX (TESTING ONLY) ====================
# Position editing for the test bench frontend. Not part of the game API.

def sandbox_response(response):
    return reply(response)


@app.before_request
def no_sandbox_online():
    """Positions cannot be edited in a game between two remote players"""
    if request.path.startswith('/api/debug/') and online():
        return refuse("That is not available in an online game")
    return None


@app.route('/api/debug/setup', methods=['POST'])
def debug_setup():
    """Replace the whole position: {"pieces": [{"coord", "type", "color"}], "current_player", "rocks",
    "size", "z_min", "z_max"}. The board defaults to the full 8, -2, 2; lessons use 5, -1, 1."""
    data = request.get_json(silent=True) or {}
    try:
        pieces = [{"coord": parse_coord(item["coord"]), "type": item["type"], "color": item.get("color")}
                  for item in data.get("pieces", [])]
    except (TypeError, KeyError, ValueError, AttributeError):
        return jsonify({"success": False, "error": "Invalid pieces list"}), 400
    
    return sandbox_response(g.manager.setup_position(
        pieces, data.get("current_player", "white"), bool(data.get("rocks", True)),
        size=data.get("size", 8), z_min=data.get("z_min", -2), z_max=data.get("z_max", 2)))


@app.route('/api/debug/place', methods=['POST'])
def debug_place():
    """Put a piece on a square (replacing whatever is there): {"coord", "type", "color"}"""
    data = request.get_json(silent=True) or {}
    try:
        coord = parse_coord(data.get("coord"))
    except ValueError:
        return jsonify({"success": False, "error": "Invalid coordinate format"}), 400
    
    return sandbox_response(g.manager.place_piece(coord, data.get("type"), data.get("color")))


@app.route('/api/debug/remove', methods=['POST'])
def debug_remove():
    """Empty a square: {"coord"}"""
    data = request.get_json(silent=True) or {}
    try:
        coord = parse_coord(data.get("coord"))
    except ValueError:
        return jsonify({"success": False, "error": "Invalid coordinate format"}), 400
    
    return sandbox_response(g.manager.remove_piece(coord))


@app.route('/api/debug/turn', methods=['POST'])
def debug_turn():
    """Choose who moves next: {"player"}"""
    data = request.get_json(silent=True) or {}
    return sandbox_response(g.manager.set_turn(data.get("player")))


@app.route('/api/debug/rocks', methods=['POST'])
def debug_rocks():
    """Add or remove the dungeon rocks: {"enabled"}"""
    data = request.get_json(silent=True) or {}
    return sandbox_response(g.manager.set_rocks(bool(data.get("enabled"))))


# ==================== SERVER ====================

if __name__ == '__main__':
    # The computer player thinks in a worker process so the server stays responsive
    from api.thinker import ProcessThinker
    rooms.set_thinker(ProcessThinker())
    # macOS reserves port 5000 for AirPlay Receiver, so default to 5001
    app.run(debug=True, port=int(os.environ.get("PORT", 5001)))
