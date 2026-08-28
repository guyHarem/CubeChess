"""
Flask API for CubeChess game engine.
Provides HTTP endpoints for game management.
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from game_manager import GameManager
from utils import convert_response
from engine.pieces import Queen, Rook, Bishop, Knight

app = Flask(__name__)
CORS(app)

# Global game instance (shared across all requests)
game_manager = GameManager()


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
        # Parse JSON array string to list, then to tuple
        from_list = eval(from_str)  # "[0,1,0]" → [0,1,0]
        from_coord = tuple(from_list)  # [0,1,0] → (0,1,0)
        
        response = game_manager.get_legal_moves(from_coord)
        return jsonify(convert_response(response))
    except (ValueError, SyntaxError):
        return jsonify({"success": False, "error": "Invalid coordinate format"}), 400


# ==================== MOVES ====================

@app.route('/api/game/move', methods=['POST'])
def make_move():
    """Execute a move"""
    data = request.json
    
    if not data or 'from' not in data or 'to' not in data:
        return jsonify({"success": False, "error": "Missing 'from' or 'to' in body"}), 400
    
    try:
        # Convert lists to tuples
        from_coord = tuple(data['from'])
        to_coord = tuple(data['to'])
        
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
    data = request.json
    
    if not data or 'coord' not in data or 'piece_type' not in data:
        return jsonify({"success": False, "error": "Missing 'coord' or 'piece_type' in body"}), 400
    
    try:
        coord = tuple(data['coord'])
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
        # Promotion happens AFTER the pawn moves, so it's the OTHER player's piece
        promoting_color = "black" if game_manager.game.current_player == "white" else "white"
        new_piece = PieceClass(promoting_color)
        
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
    app.run(debug=True, port=5000)
