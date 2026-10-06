from engine.game_state import GameState
from engine.pieces import Rock


class GameManager:
    def __init__(self):
        self.game = GameState()

    # ==================== HELPERS ====================

    def _get_status(self):
        player = self.game.current_player
        if self.game.is_checkmate(player):
            return "checkmate"
        elif self.game.is_stalemate(player):
            return "stalemate"
        elif self.game.is_in_check(player):
            return "check"
        elif self.game.is_draw():
            return "draw"
        else:
            return "ongoing"

    def _state_response(self):
        return {
            "success": True,
            "current_player": self.game.current_player,
            "board": self.game.get_board_state().board,
            "status": self._get_status(),
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
