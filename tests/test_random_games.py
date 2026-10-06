"""
Randomised tests: play random moves and build random positions, and after every
step compare the engine with the independent generator in tests/reference.py.

Seeds are fixed, so a failure is reproducible: the message names the seed.
"""
import random
import unittest
from engine.game_state import GameState
from engine.pieces import King, Queen, Rook, Bishop, Knight, Pawn, Rock
from tests import reference

PROMOTIONS = [Queen, Rook, Bishop, Knight]


def other(color):
    return "black" if color == "white" else "white"


def snapshot(game):
    """Everything that undo must restore"""
    board = {c: (str(p), getattr(p, 'has_moved', None)) for c, p in game.board.board.items()}
    return (board, game.current_player, game.white_king_pos, game.black_king_pos,
            game.pending_promotion, [dict(m) for m in game.move_history])


def empty_game(rocks):
    game = GameState()
    game.board.board = {c: p for c, p in game.board.board.items() if rocks and isinstance(p, Rock)}
    return game


class RandomisedTestCase(unittest.TestCase):
    def assert_matches_reference(self, game, tag):
        """Check, kings, every legal move, checkmate and stalemate must all agree. Returns the move count."""
        board = game.board.board
        player = game.current_player

        for color in ("white", "black"):
            self.assertEqual(game.is_in_check(color), reference.in_check(board, color), f"{tag}: check {color}")
        self.assertEqual(game.white_king_pos, reference.find_king(board, "white"), f"{tag}: white king tracker")
        self.assertEqual(game.black_king_pos, reference.find_king(board, "black"), f"{tag}: black king tracker")

        total = 0
        for coord, piece in game.get_all_pieces_of_color(player):
            engine_moves = game.get_legal_moves(coord)
            self.assertEqual(len(engine_moves), len(set(engine_moves)), f"{tag}: duplicate moves for {piece} {coord}")
            self.assertEqual(sorted(engine_moves),
                             sorted(reference.legal_moves(board, coord, game.move_history)),
                             f"{tag}: legal moves of {piece} at {coord}")
            total += len(engine_moves)

        in_check = reference.in_check(board, player)
        self.assertEqual(game.is_checkmate(player), in_check and total == 0, f"{tag}: checkmate")
        self.assertEqual(game.is_stalemate(player), not in_check and total == 0, f"{tag}: stalemate")
        return total

    def play_and_undo(self, game, from_coord, to_coord, rng, tag):
        """Play one full turn (with promotion), check it, and check that undo/redo round-trip"""
        before = snapshot(game)
        mover = game.current_player
        self.assertNotIsInstance(game.board.get_piece(to_coord), King, f"{tag}: a king can be captured")

        def play(promote_to):
            game.make_move(from_coord, to_coord)
            if game.pending_promotion is not None:
                game.promote_pawn(to_coord, promote_to(mover))

        promote_to = rng.choice(PROMOTIONS)
        play(promote_to)
        self.assertFalse(reference.in_check(game.board.board, mover), f"{tag}: move left own king in check")
        self.assertEqual(game.current_player, other(mover), f"{tag}: turn did not pass")
        after = snapshot(game)

        self.assertTrue(game.undo_move())
        self.assertEqual(snapshot(game), before, f"{tag}: undo")
        play(promote_to)
        self.assertEqual(snapshot(game), after, f"{tag}: redo")


class TestRandomGames(RandomisedTestCase):
    def test_random_games_from_the_starting_position(self):
        for seed in range(6):
            rng = random.Random(seed)
            game = GameState()
            for ply in range(60):
                tag = f"game seed {seed} ply {ply}"
                if self.assert_matches_reference(game, tag) == 0:
                    break
                moves = [(coord, move)
                         for coord, _ in game.get_all_pieces_of_color(game.current_player)
                         for move in game.get_legal_moves(coord)]
                # Favour captures so the games don't just shuffle pieces
                captures = [m for m in moves if game.board.get_piece(m[1]) is not None]
                from_coord, to_coord = rng.choice(captures if captures and rng.random() < 0.5 else moves)
                self.play_and_undo(game, from_coord, to_coord, rng, tag)

            # Undoing everything must give back a brand new game
            while game.undo_move():
                pass
            self.assertEqual(snapshot(game), snapshot(GameState()), f"game seed {seed}: full unwind")


class TestRandomPositions(RandomisedTestCase):
    def test_random_positions_on_all_layers(self):
        checked = 0
        for seed in range(250):
            rng = random.Random(seed)
            game = empty_game(rocks=True)
            free = [(x, y, z) for x in range(8) for y in range(8) for z in range(-2, 3)
                    if (x, y, z) not in game.board.board]
            rng.shuffle(free)
            pieces = [King("white"), King("black")]
            pieces += [rng.choice([Queen, Rook, Bishop, Knight, Pawn])(rng.choice(["white", "black"]))
                       for _ in range(rng.randint(2, 14))]
            for piece in pieces:
                coord = free.pop()
                if isinstance(piece, Pawn):
                    while coord[1] in (0, 7):
                        coord = free.pop()
                    piece.has_moved = rng.random() < 0.7
                if isinstance(piece, (King, Rook)):
                    piece.has_moved = True
                game.board.board[coord] = piece
            game.current_player = rng.choice(["white", "black"])
            game.reset_tracking()

            # Skip impossible positions where the side that just moved is in check
            if reference.in_check(game.board.board, other(game.current_player)):
                continue
            self.assert_matches_reference(game, f"position seed {seed}")
            checked += 1
        self.assertGreater(checked, 150)

    def test_en_passant_positions(self):
        available = 0
        for seed in range(300):
            rng = random.Random(seed)
            game = empty_game(rocks=rng.random() < 0.5)
            board = game.board.board
            mover = rng.choice(["white", "black"])
            start, d = (1, 1) if mover == "white" else (6, -1)

            for coord, color in (((4, 0, 2), "white"), ((4, 7, 2), "black")):
                board[coord] = King(color)
                board[coord].has_moved = True
            pawn_x = rng.randrange(8)
            board[(pawn_x, start, 0)] = Pawn(mover)
            # Enemy pawns around where the double-step lands, on various layers
            for _ in range(rng.randint(1, 6)):
                coord = (min(7, max(0, pawn_x + rng.choice([-2, -1, -1, 1, 1, 2]))),
                         start + 2 * d + rng.choice([0, 0, 0, d, -d]),
                         rng.choice([-2, -1, 0, 0, 1, 2]))
                if coord not in board:
                    board[coord] = Pawn(other(mover))
                    board[coord].has_moved = True
            for _ in range(rng.randint(0, 3)):
                coord = (rng.randrange(8), rng.randrange(8), rng.randrange(-2, 3))
                if coord not in board:
                    board[coord] = rng.choice([Queen, Bishop, Knight])(rng.choice(["white", "black"]))
            game.current_player = mover
            game.reset_tracking()
            if reference.in_check(board, other(mover)):
                continue

            double_steps = [m for m in game.get_legal_moves((pawn_x, start, 0)) if abs(m[1] - start) == 2]
            if not double_steps:
                continue
            game.make_move((pawn_x, start, 0), rng.choice(double_steps))
            tag = f"en passant seed {seed}"
            self.assert_matches_reference(game, tag)

            captures = [(coord, move)
                        for coord, piece in game.get_all_pieces_of_color(other(mover)) if isinstance(piece, Pawn)
                        for move in game.get_en_passant_moves(coord)]
            if captures:
                available += 1
                from_coord, to_coord = rng.choice(captures)
                self.play_and_undo(game, from_coord, to_coord, rng, tag)
                self.assertEqual(game.move_history[-1]['special_move'], "en_passant", tag)
                self.assert_matches_reference(game, tag + " (after)")
        self.assertGreater(available, 50)

    def test_castling_positions(self):
        available = 0
        for seed in range(300):
            rng = random.Random(seed)
            game = empty_game(rocks=False)
            board = game.board.board
            for color, rank in (("white", 0), ("black", 7)):
                board[(4, rank, 0)] = King(color)
                board[(4, rank, 0)].has_moved = rng.random() < 0.1
                for x in (0, 7):
                    if rng.random() < 0.85:
                        board[(x, rank, 0)] = Rook(color)
                        board[(x, rank, 0)].has_moved = rng.random() < 0.15
            for _ in range(rng.randint(0, 8)):
                coord = (rng.randrange(8), rng.randrange(8), rng.randrange(-2, 3))
                piece = rng.choice([Queen, Rook, Bishop, Knight, Pawn])(rng.choice(["white", "black"]))
                if coord in board or (isinstance(piece, Pawn) and coord[1] in (0, 7)):
                    continue
                if hasattr(piece, 'has_moved'):
                    piece.has_moved = True
                board[coord] = piece
            game.current_player = rng.choice(["white", "black"])
            game.reset_tracking()
            if reference.in_check(board, other(game.current_player)):
                continue

            tag = f"castling seed {seed}"
            self.assert_matches_reference(game, tag)
            king = game.white_king_pos if game.current_player == "white" else game.black_king_pos
            castles = [m for m in game.get_legal_moves(king) if abs(m[0] - king[0]) == 2]
            if castles:
                available += 1
                self.play_and_undo(game, king, rng.choice(castles), rng, tag)
                self.assertEqual(game.move_history[-1]['special_move'], "castling", tag)
                self.assert_matches_reference(game, tag + " (after)")
        self.assertGreater(available, 50)


if __name__ == '__main__':
    unittest.main()
