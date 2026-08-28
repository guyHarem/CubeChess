from engine.game_state import GameState


class GameManager:
    def __init__(self):
        self.game = GameState()

    # ==================== GAME SETUP ====================

    def new_game(self):
        try:
            self.game = GameState()
            return {
                "success": True,
                "current_player": self.game.current_player,
                "board": self.game.get_board_state().board,
                "status": "ongoing",
                "move_history": self.game.move_history
            }
        except Exception as e:
            return {
                "success": False,
                "current_player": self.game.current_player,
                "error": str(e)
            }

    # ==================== QUERIES (READ-ONLY) ====================

    def get_state(self):
        try:
            player = self.game.current_player
            board = self.game.get_board_state().board

            if self.game.is_checkmate(player):
                game_status = "checkmate"
            elif self.game.is_stalemate(player):
                game_status = "stalemate"
            elif self.game.is_in_check(player):
                game_status = "check"
            elif self.game.is_draw():
                game_status = "draw"
            else:
                game_status = "ongoing"

            return {
                "success": True,
                "current_player": player,
                "board": board,
                "status": game_status,
                "move_history": self.game.move_history
            }

        except ValueError as e:
            return {
                "success": False,
                "error": str(e),
                "current_player": self.game.current_player,
                "board": self.game.get_board_state().board,
                "move_history": self.game.move_history
            }

    def get_legal_moves(self, from_coord):
        try:
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
            return {
                "success": True,
                "current_player": self.game.current_player,
                "board": self.game.get_board_state().board,
                "move_history": self.game.move_history
            }
        except ValueError as e:
            return {
                "success": False,
                "error": str(e),
                "current_player": self.game.current_player,
                "board": self.game.get_board_state().board,
                "move_history": self.game.move_history
            }

    def promote_pawn(self, coord, new_piece):
        try:
            self.game.promote_pawn(coord, new_piece)

            # Determine game status after promotion
            player = self.game.current_player
            if self.game.is_checkmate(player):
                game_status = "checkmate"
            elif self.game.is_stalemate(player):
                game_status = "stalemate"
            elif self.game.is_in_check(player):
                game_status = "check"
            elif self.game.is_draw():
                game_status = "draw"
            else:
                game_status = "ongoing"

            return {
                "success": True,
                "current_player": self.game.current_player,
                "board": self.game.get_board_state().board,
                "status": game_status,
                "move_history": self.game.move_history
            }
        except ValueError as e:
            return {
                "success": False,
                "error": str(e),
                "current_player": self.game.current_player,
                "board": self.game.get_board_state().board,
                "move_history": self.game.move_history
            }

    # ==================== RECOVERY ====================

    def undo_move(self):
        try:
            success = self.game.undo_move()
            if not success:
                return {
                    "success": False,
                    "error": "No moves to undo",
                    "current_player": self.game.current_player,
                    "board": self.game.get_board_state().board
                }

            player = self.game.current_player
            if self.game.is_checkmate(player):
                game_status = "checkmate"
            elif self.game.is_stalemate(player):
                game_status = "stalemate"
            elif self.game.is_in_check(player):
                game_status = "check"
            elif self.game.is_draw():
                game_status = "draw"
            else:
                game_status = "ongoing"

            return {
                "success": True,
                "current_player": self.game.current_player,
                "board": self.game.get_board_state().board,
                "status": game_status,
                "move_history": self.game.move_history
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "current_player": self.game.current_player,
                "board": self.game.get_board_state().board,
                "move_history": self.game.move_history
            }
                    










