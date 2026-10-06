import time

from api.clock import ChessClock
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


def other(color):
    return "black" if color == "white" else "white"


class GameManager:
    def __init__(self):
        self.game = GameState()
        self.clock = None         # ChessClock, or None for an untimed game
        self.result = None        # an ending the rules engine doesn't know: resignation, agreed draw, timeout
        self._clock_stack = []    # clock snapshot before each turn, so undo can put the time back
        self._now = time.monotonic

    # ==================== HELPERS ====================

    def _get_status(self, draw_reason):
        player = self.game.current_player
        if self.result is not None:
            return self.result["kind"]  # "resigned", "agreed_draw" or "timeout"
        elif self.game.is_checkmate(player):
            return "checkmate"
        elif draw_reason == "stalemate":
            return "stalemate"
        elif draw_reason is not None:
            return "draw"  # a draw ends the game even if the player is in check
        elif self.game.is_in_check(player):
            return "check"
        else:
            return "ongoing"

    def _check_flag(self):
        """End the game if the player to move has run out of time"""
        if self.clock is not None and self.result is None:
            flagged = self.clock.flagged()
            if flagged is not None:
                self.result = {"kind": "timeout", "winner": other(flagged)}
                self.clock.stop()

    def _state_response(self):
        self._check_flag()
        draw_reason = None if self.result is not None else self.game.get_draw_reason()
        status = self._get_status(draw_reason)

        winner = None
        if self.result is not None:
            winner = self.result["winner"]
        elif status == "checkmate":
            winner = other(self.game.current_player)

        # Nobody's time runs once the game is decided
        if self.clock is not None and status not in ("ongoing", "check"):
            self.clock.stop()

        board = self.game.get_board_state()
        return {
            "success": True,
            "current_player": self.game.current_player,
            "board": board.board,
            "board_size": {"size": board.size, "z_min": board.z_min, "z_max": board.z_max},
            "status": status,
            "winner": winner,
            "draw_reason": draw_reason,
            "halfmove_clock": self.game.halfmove_clock,
            "move_limit": self.game.move_limit,
            "clock": self.clock.to_json() if self.clock is not None else None,
            "pending_promotion": self.game.pending_promotion,
            "move_history": self.game.move_history
        }

    def _error_response(self, error):
        response = self._state_response()
        response["success"] = False
        response["error"] = str(error)
        return response

    # ==================== GAME SETUP ====================

    def new_game(self, rocks=True, move_limit=50, clock=None):
        """clock: None for an untimed game, or {"initial": seconds, "increment": seconds}"""
        try:
            if type(move_limit) is not int or not 1 <= move_limit <= 500:
                raise ValueError("move_limit must be a whole number from 1 to 500")

            new_clock = None
            if clock is not None:
                initial = clock.get("initial") if isinstance(clock, dict) else None
                increment = clock.get("increment", 0) if isinstance(clock, dict) else None
                if type(initial) is not int or not 10 <= initial <= 6 * 3600:
                    raise ValueError("clock.initial must be a whole number of seconds from 10 to 21600")
                if type(increment) is not int or not 0 <= increment <= 300:
                    raise ValueError("clock.increment must be a whole number of seconds from 0 to 300")
                new_clock = ChessClock(initial, increment, now=lambda: self._now())

            game = GameState(move_limit=move_limit)
            if not rocks:
                board = game.get_board_state()
                for coord, piece in list(board.board.items()):
                    if isinstance(piece, Rock):
                        board.remove_piece(coord)
                game.reset_tracking()
            self._replace_game(game, new_clock)
            return self._state_response()
        except ValueError as e:
            return self._error_response(e)

    def _replace_game(self, game, clock=None):
        self.game = game
        self.clock = clock
        self.result = None
        self._clock_stack = []

    def _mark_check(self, response):
        """Note on the last history entry whether that move gave check or checkmate (for move notation)"""
        if self.game.move_history and self.game.pending_promotion is None:
            status = response["status"]
            self.game.move_history[-1]["check"] = status if status in ("check", "checkmate") else None
        return response

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

    def _finish_turn(self, mover):
        if self.clock is not None and self.game.current_player != mover:
            self.clock.finish_turn(mover, self.game.current_player)

    def make_move(self, from_coord, to_coord):
        try:
            self._check_flag()
            if self.result is not None:
                raise ValueError("The game is over")

            mover = self.game.current_player
            snapshot = self.clock.snapshot() if self.clock is not None else None
            self.game.make_move(from_coord, to_coord)
            self._clock_stack.append(snapshot)
            self._finish_turn(mover)
            return self._mark_check(self._state_response())
        except ValueError as e:
            return self._error_response(e)

    def promote_pawn(self, coord, new_piece):
        try:
            self._check_flag()
            if self.result is not None:
                raise ValueError("The game is over")

            mover = self.game.current_player
            self.game.promote_pawn(coord, new_piece)
            self._finish_turn(mover)
            return self._mark_check(self._state_response())
        except ValueError as e:
            return self._error_response(e)

    # ==================== ENDING THE GAME BY CHOICE ====================

    def resign(self, color=None):
        try:
            self._check_flag()
            if color is None:
                color = self.game.current_player
            if color not in ("white", "black"):
                raise ValueError(f"Invalid color: {color}")
            if self.result is not None or self._state_response()["status"] not in ("ongoing", "check"):
                raise ValueError("The game is over")
            self.result = {"kind": "resigned", "winner": other(color)}
            return self._state_response()
        except ValueError as e:
            return self._error_response(e)

    def agree_draw(self):
        try:
            self._check_flag()
            if self.result is not None or self._state_response()["status"] not in ("ongoing", "check"):
                raise ValueError("The game is over")
            self.result = {"kind": "agreed_draw", "winner": None}
            return self._state_response()
        except ValueError as e:
            return self._error_response(e)

    # ==================== RECOVERY ====================

    def undo_move(self):
        """Take back the last turn. Also reopens a game that ended by resignation, agreement or timeout,
        and puts the clocks back to where they were before that turn."""
        if not self.game.undo_move():
            return self._error_response("No moves to undo")
        self.result = None
        snapshot = self._clock_stack.pop() if self._clock_stack else None
        if self.clock is not None and snapshot is not None:
            self.clock.restore(snapshot)
        return self._state_response()

    # ==================== SANDBOX (TESTING ONLY) ====================
    # Edit the position directly to test move/capture behavior. Every edit
    # starts a fresh position: move history and undo are cleared.

    def _create_piece(self, piece_type, color, coord, size=8):
        if piece_type == "Rock":
            return Rock()
        if piece_type not in PIECE_CLASSES:
            raise ValueError(f"Invalid piece type: {piece_type}")
        if color not in ("white", "black"):
            raise ValueError(f"Invalid color: {color}")

        piece = PIECE_CLASSES[piece_type](color)

        # Only pieces on their starting squares keep double-step / castling rights
        x, y, z = coord
        home_rank = 0 if color == "white" else size - 1
        pawn_rank = 1 if color == "white" else size - 2
        if isinstance(piece, Pawn):
            piece.has_moved = not (y == pawn_rank and z == 0)
        elif isinstance(piece, King):
            piece.has_moved = size != 8 or (x, y, z) != (4, home_rank, 0)
        elif isinstance(piece, Rook):
            piece.has_moved = size != 8 or (x, y, z) not in ((0, home_rank, 0), (7, home_rank, 0))
        return piece

    def _set_square(self, coord, piece):
        board = self.game.get_board_state()
        if board.get_piece(coord) is not None:
            board.remove_piece(coord)
        if piece is not None:
            board.set_piece(piece, coord)

    def setup_position(self, pieces, current_player="white", rocks=True, size=8, z_min=-2, z_max=2):
        """Replace the whole position. pieces: list of {"coord", "type", "color"} ("Rock" needs no color).
        size/z_min/z_max choose the board: 8, -2, 2 is the full board; lessons use 5, -1, 1."""
        try:
            if current_player not in ("white", "black"):
                raise ValueError(f"Invalid color: {current_player}")
            if type(size) is not int or not 4 <= size <= 8:
                raise ValueError("size must be a whole number from 4 to 8")
            if type(z_min) is not int or type(z_max) is not int or not -2 <= z_min <= 0 <= z_max <= 2:
                raise ValueError("layers must run from z_min (-2 to 0) to z_max (0 to 2)")

            game = GameState(size=size, z_min=z_min, z_max=z_max)
            game.board.board = {}
            # The standard rock layout only fits the full board
            if rocks and game.board.is_standard():
                game.board.init_rocks()
            for item in pieces:
                coord = item["coord"]
                game.board.is_valid_coordinate(coord)
                game.board.board[coord] = self._create_piece(item["type"], item.get("color"), coord, size)
            game.current_player = current_player
            game.reset_tracking()

            self._replace_game(game)
            return self._state_response()
        except ValueError as e:
            return self._error_response(e)

    def place_piece(self, coord, piece_type, color):
        try:
            self._set_square(coord, self._create_piece(piece_type, color, coord, self.game.board.size))
            self.game.reset_tracking()
            self._replace_game(self.game)
            return self._state_response()
        except ValueError as e:
            return self._error_response(e)

    def remove_piece(self, coord):
        try:
            self._set_square(coord, None)
            self.game.reset_tracking()
            self._replace_game(self.game)
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
        if enabled and board.is_standard():
            board.init_rocks()  # overwrites any piece standing on a rock square
        self.game.reset_tracking()
        self._replace_game(self.game)
        return self._state_response()
