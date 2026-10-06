from engine.game_state import GameState
from engine.pieces import King, Queen, Rook, Bishop, Knight, Pawn, Rock

PIECE_CLASSES = {
    "King": King,
    "Queen": Queen,
    "Rook": Rook,
    "Bishop": Bishop,
    "Knight": Knight,
    "Pawn": Pawn
}


class GameManager:
    def __init__(self):
        self.game = GameState()

    # ==================== HELPERS ====================

    def _get_status(self, draw_reason):
        player = self.game.current_player
        if self.game.is_checkmate(player):
            return "checkmate"
        elif draw_reason == "stalemate":
            return "stalemate"
        elif draw_reason is not None:
            return "draw"  # a draw ends the game even if the player is in check
        elif self.game.is_in_check(player):
            return "check"
        else:
            return "ongoing"

    def _state_response(self):
        draw_reason = self.game.get_draw_reason()
        return {
            "success": True,
            "current_player": self.game.current_player,
            "board": self.game.get_board_state().board,
            "status": self._get_status(draw_reason),
            "draw_reason": draw_reason,
            "halfmove_clock": self.game.halfmove_clock,
            "move_limit": self.game.move_limit,
            "pending_promotion": self.game.pending_promotion,
            "move_history": self.game.move_history
        }

    def _error_response(self, error):
        response = self._state_response()
        response["success"] = False
        response["error"] = str(error)
        return response

    # ==================== GAME SETUP ====================

    def new_game(self):
        self.game = GameState()
        return self._state_response()

    # ==================== QUERIES (READ-ONLY) ====================

    def get_state(self):
        return self._state_response()

    def get_legal_moves(self, from_coord):
        try:
            piece = self.game.get_board_state().get_piece(from_coord)

            # Only the player to move has legal moves, and none while a promotion is pending
            if (piece is None or isinstance(piece, Rock) or
                    piece.color != self.game.current_player or
                    self.game.pending_promotion is not None):
                moves = []
            else:
                moves = self.game.get_legal_moves(from_coord)

            return {
                "success": True,
                "legal_moves": moves,
                "current_player": self.game.current_player
            }
        except ValueError as e:
            return {
                "success": False,
                "error": str(e),
                "current_player": self.game.current_player
            }

    # ==================== MOVES (STATE-CHANGING) ====================

    def make_move(self, from_coord, to_coord):
        try:
            self.game.make_move(from_coord, to_coord)
            return self._state_response()
        except ValueError as e:
            return self._error_response(e)

    def promote_pawn(self, coord, new_piece):
        try:
            self.game.promote_pawn(coord, new_piece)
            return self._state_response()
        except ValueError as e:
            return self._error_response(e)

    # ==================== RECOVERY ====================

    def undo_move(self):
        if not self.game.undo_move():
            return self._error_response("No moves to undo")
        return self._state_response()

    # ==================== SANDBOX (TESTING ONLY) ====================
    # Edit the position directly to test move/capture behavior. Every edit
    # starts a fresh position: move history and undo are cleared.

    def _create_piece(self, piece_type, color, coord):
        if piece_type not in PIECE_CLASSES:
            raise ValueError(f"Invalid piece type: {piece_type}")
        if color not in ("white", "black"):
            raise ValueError(f"Invalid color: {color}")

        piece = PIECE_CLASSES[piece_type](color)

        # Only pieces on their starting squares keep double-step / castling rights
        x, y, z = coord
        home_rank = 0 if color == "white" else 7
        pawn_rank = 1 if color == "white" else 6
        if isinstance(piece, Pawn):
            piece.has_moved = not (y == pawn_rank and z == 0)
        elif isinstance(piece, King):
            piece.has_moved = (x, y, z) != (4, home_rank, 0)
        elif isinstance(piece, Rook):
            piece.has_moved = (x, y, z) not in ((0, home_rank, 0), (7, home_rank, 0))
        return piece

    def _set_square(self, coord, piece):
        board = self.game.get_board_state()
        if board.get_piece(coord) is not None:
            board.remove_piece(coord)
        if piece is not None:
            board.set_piece(piece, coord)

    def setup_position(self, pieces, current_player="white", rocks=True):
        """Replace the whole position. pieces: list of {"coord", "type", "color"}"""
        try:
            if current_player not in ("white", "black"):
                raise ValueError(f"Invalid color: {current_player}")

            game = GameState()
            game.board.board = {}
            if rocks:
                game.board.init_rocks()
            for item in pieces:
                coord = item["coord"]
                game.board.is_valid_coordinate(coord)
                game.board.board[coord] = self._create_piece(item["type"], item["color"], coord)
            game.current_player = current_player
            game.reset_tracking()

            self.game = game
            return self._state_response()
        except ValueError as e:
            return self._error_response(e)

    def place_piece(self, coord, piece_type, color):
        try:
            self._set_square(coord, self._create_piece(piece_type, color, coord))
            self.game.reset_tracking()
            return self._state_response()
        except ValueError as e:
            return self._error_response(e)

    def remove_piece(self, coord):
        try:
            self._set_square(coord, None)
            self.game.reset_tracking()
            return self._state_response()
        except ValueError as e:
            return self._error_response(e)

    def set_turn(self, player):
        try:
            if player not in ("white", "black"):
                raise ValueError(f"Invalid color: {player}")
            if self.game.pending_promotion is not None:
                raise ValueError("Promote the pawn before changing the turn!")
            self.game.current_player = player
            self.game.restart_draw_tracking()
            return self._state_response()
        except ValueError as e:
            return self._error_response(e)

    def set_rocks(self, enabled):
        board = self.game.get_board_state()
        for coord, piece in list(board.board.items()):
            if isinstance(piece, Rock):
                board.remove_piece(coord)
        if enabled:
            board.init_rocks()  # overwrites any piece standing on a rock square
        self.game.reset_tracking()
        return self._state_response()
