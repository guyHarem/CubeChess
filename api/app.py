"""
Flask API for CubeChess game engine.
Provides HTTP endpoints for game management.
"""

import json
import os
import sys

# Make the project root importable so `python api/app.py` works from any directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, jsonify
from flask_cors import CORS
from api.game_manager import GameManager
from api.utils import convert_response
from engine.pieces import Queen, Rook, Bishop, Knight

app = Flask(__name__)
CORS(app)

# Global game instance (shared across all requests)
game_manager = GameManager()


def parse_coord(value):
    """Convert a JSON [x,y,z] list to an (x,y,z) tuple, or raise ValueError"""
    if (not isinstance(value, list) or len(value) != 3 or
            not all(type(n) is int for n in value)):
        raise ValueError("Coordinate must be [x, y, z] integers")
    return tuple(value)


# ==================== GAME SETUP ====================

@app.route('/api/game/new', methods=['POST'])
def new_game():
    """Start a new game"""
    response = game_manager.new_game()
    return jsonify(convert_response(response))


# ==================== QUERIES ====================

@app.route('/api/game/state', methods=['GET'])
def get_state():
    """Get current game state (board, player, status)"""
    response = game_manager.get_state()
    return jsonify(convert_response(response))


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
        
        response = game_manager.get_legal_moves(from_coord)
        status_code = 200 if response.get("success") else 400
        return jsonify(convert_response(response)), status_code
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
        
        response = game_manager.make_move(from_coord, to_coord)
        
        # Return 400 if move failed, 200 if succeeded
        status_code = 200 if response.get("success") else 400
        return jsonify(convert_response(response)), status_code
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "Invalid coordinate format"}), 400


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
        new_piece = PieceClass(game_manager.game.current_player)
        
        response = game_manager.promote_pawn(coord, new_piece)
        
        status_code = 200 if response.get("success") else 400
        return jsonify(convert_response(response)), status_code
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "Invalid coordinate format"}), 400


# ==================== UNDO ====================

@app.route('/api/game/undo', methods=['POST'])
def undo_move():
    """Undo the last move"""
    response = game_manager.undo_move()
    
    status_code = 200 if response.get("success") else 400
    return jsonify(convert_response(response)), status_code


# ==================== SERVER ====================

if __name__ == '__main__':
    # macOS reserves port 5000 for AirPlay Receiver, so default to 5001
    app.run(debug=True, port=int(os.environ.get("PORT", 5001)))
