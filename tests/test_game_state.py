import unittest
from engine.game_state import GameState
from engine.pieces import King, Queen, Rook, Bishop, Knight, Pawn, Rock


def custom_game(pieces, current_player="white", rocks=True):
    """Build a game from a {coord: piece} dict (must contain both kings)"""
    game = GameState()
    if rocks:
        game.board.board = {c: p for c, p in game.board.board.items() if isinstance(p, Rock)}
    else:
        game.board.board = {}
    for coord, piece in pieces.items():
        game.board.set_piece(piece, coord)
        if isinstance(piece, King):
            if piece.color == "white":
                game.white_king_pos = coord
            else:
                game.black_king_pos = coord
    game.current_player = current_player
    return game


def moved(piece):
    piece.has_moved = True
    return piece


def snapshot(game):
    """Everything that undo must restore"""
    board = {c: (str(p), getattr(p, 'has_moved', None)) for c, p in game.board.board.items()}
    return (board, game.current_player, game.white_king_pos, game.black_king_pos,
            game.pending_promotion, list(game.move_history))


class TestOpeningPosition(unittest.TestCase):
    def setUp(self):
        self.game = GameState()

    def test_king_trackers_point_at_kings(self):
        self.assertIsInstance(self.game.board.get_piece(self.game.white_king_pos), King)
        self.assertIsInstance(self.game.board.get_piece(self.game.black_king_pos), King)

    def test_every_piece_can_be_queried(self):
        for coord in list(self.game.board.board):
            self.game.get_legal_moves(coord)  # must not raise

    def test_not_check_mate_or_draw(self):
        for color in ("white", "black"):
            self.assertFalse(self.game.is_in_check(color))
            self.assertFalse(self.game.is_checkmate(color))
            self.assertFalse(self.game.is_stalemate(color))
        self.assertFalse(self.game.is_draw())

    def test_rook_cannot_jump_over_pieces(self):
        # Hemmed in on its layer, but free to ride the "elevator"
        self.assertEqual(sorted(self.game.get_legal_moves((0, 0, 0))),
                         [(0, 0, -2), (0, 0, -1), (0, 0, 1), (0, 0, 2)])

    def test_bishop_cannot_jump_over_pieces(self):
        moves = self.game.get_legal_moves((2, 0, 0))
        self.assertEqual(len(moves), 12)
        self.assertTrue(all(z != 0 for _, _, z in moves))

    def test_king_has_only_vertical_moves(self):
        self.assertEqual(sorted(self.game.get_legal_moves((4, 0, 0))), [(4, 0, -1), (4, 0, 1)])

    def test_knight_jumps(self):
        moves = self.game.get_legal_moves((1, 0, 0))
        self.assertIn((2, 2, 0), moves)
        self.assertIn((0, 2, 0), moves)

    def test_white_pawn_moves(self):
        self.assertEqual(sorted(self.game.get_legal_moves((4, 1, 0))),
                         [(4, 2, -1), (4, 2, 0), (4, 2, 1), (4, 3, -2), (4, 3, 0), (4, 3, 2)])

    def test_black_pawn_moves(self):
        self.assertEqual(sorted(self.game.get_legal_moves((4, 6, 0))),
                         [(4, 4, -2), (4, 4, 0), (4, 4, 2), (4, 5, -1), (4, 5, 0), (4, 5, 1)])

    def test_pawn_cannot_enter_or_pass_a_rock(self):
        moves = self.game.get_legal_moves((2, 1, 0))
        self.assertNotIn((2, 2, -1), moves)  # rock
        self.assertNotIn((2, 3, -2), moves)  # behind the rock (and a rock itself)

    def test_black_cannot_move_first(self):
        with self.assertRaises(ValueError):
            self.game.make_move((4, 6, 0), (4, 4, 0))
        self.assertEqual(self.game.current_player, "white")

    def test_illegal_move_rejected(self):
        with self.assertRaises(ValueError):
            self.game.make_move((0, 0, 0), (0, 5, 0))
        with self.assertRaises(ValueError):
            self.game.make_move((3, 3, 0), (3, 4, 0))  # empty square
        with self.assertRaises(ValueError):
            self.game.make_move((2, 2, -1), (2, 3, -1))  # rock

    def test_turns_alternate(self):
        self.game.make_move((4, 1, 0), (4, 3, 0))
        self.assertEqual(self.game.current_player, "black")
        self.game.make_move((4, 6, 0), (4, 4, 0))
        self.assertEqual(self.game.current_player, "white")
        self.assertEqual(len(self.game.move_history), 2)


class TestBlocking(unittest.TestCase):
    def test_rock_blocks_rook_and_cannot_be_captured(self):
        game = custom_game({(4, 0, 0): King("white"), (4, 7, 0): King("black"),
                            (2, 0, -1): Rook("white")})
        moves = game.get_legal_moves((2, 0, -1))
        self.assertIn((2, 1, -1), moves)
        self.assertNotIn((2, 2, -1), moves)  # the rock
        self.assertNotIn((2, 3, -1), moves)  # behind the rock

    def test_knight_ignores_rocks_in_the_way_but_cannot_land_on_one(self):
        game = custom_game({(4, 0, 0): King("white"), (4, 7, 0): King("black"),
                            (4, 2, -1): Knight("white")})
        moves = game.get_legal_moves((4, 2, -1))
        self.assertIn((4, 4, -2), moves)     # past the rocks at (4,3,-1) and (4,3,-2)
        self.assertNotIn((3, 4, -1), moves)  # a rock
        self.assertIn((2, 3, -1), moves)     # past the rock at (3,3,-1)

    def test_pawn_double_step_blocked(self):
        game = custom_game({(4, 0, 0): King("white"), (4, 7, 0): King("black"),
                            (0, 1, 0): Pawn("white"), (0, 2, 0): Knight("black")})
        moves = game.get_legal_moves((0, 1, 0))
        self.assertNotIn((0, 2, 0), moves)
        self.assertNotIn((0, 3, 0), moves)
        self.assertIn((0, 3, 2), moves)  # climbing path is still open

    def test_pinned_piece_cannot_move_away(self):
        game = custom_game({(4, 0, 0): King("white"), (4, 7, 0): King("black"),
                            (4, 1, 0): Rook("white"), (4, 6, 0): Rook("black")})
        moves = game.get_legal_moves((4, 1, 0))
        self.assertTrue(moves)
        self.assertTrue(all(x == 4 and z == 0 for x, _, z in moves))


class TestCheck(unittest.TestCase):
    def test_check_from_another_layer(self):
        game = custom_game({(4, 0, 0): King("white"), (4, 7, 0): King("black"),
                            (4, 0, 2): Rook("black")})
        self.assertTrue(game.is_in_check("white"))
        self.assertFalse(game.is_checkmate("white"))

    def test_must_get_out_of_check(self):
        game = custom_game({(4, 0, 0): King("white"), (4, 7, 0): King("black"),
                            (4, 0, 2): Rook("black"), (0, 1, 0): Pawn("white")})
        self.assertEqual(game.get_legal_moves((0, 1, 0)), [])

    def test_checkmate(self):
        game = custom_game({(0, 0, -2): King("white"), (2, 2, -2): King("black"),
                            (1, 1, -2): Queen("black"), (0, 5, -1): Rook("black")}, rocks=False)
        self.assertTrue(game.is_checkmate("white"))
        self.assertFalse(game.is_stalemate("white"))

    def test_stalemate(self):
        game = custom_game({(0, 0, -2): King("white"), (7, 7, 2): King("black"),
                            (1, 2, -2): Queen("black"), (5, 0, -1): Rook("black")}, rocks=False)
        self.assertFalse(game.is_in_check("white"))
        self.assertTrue(game.is_stalemate("white"))
        self.assertTrue(game.is_draw())


class TestCastling(unittest.TestCase):
    def setUp(self):
        self.game = custom_game({(4, 0, 0): King("white"), (4, 7, 0): King("black"),
                                 (0, 0, 0): Rook("white"), (7, 0, 0): Rook("white")})

    def test_both_sides_available(self):
        moves = self.game.get_legal_moves((4, 0, 0))
        self.assertIn((6, 0, 0), moves)
        self.assertIn((2, 0, 0), moves)

    def test_kingside_castle_and_undo(self):
        before = snapshot(self.game)
        self.game.make_move((4, 0, 0), (6, 0, 0))
        self.assertIsInstance(self.game.board.get_piece((6, 0, 0)), King)
        self.assertIsInstance(self.game.board.get_piece((5, 0, 0)), Rook)
        self.assertEqual(self.game.white_king_pos, (6, 0, 0))
        self.assertEqual(self.game.move_history[-1]['special_move'], "castling")
        self.assertTrue(self.game.undo_move())
        self.assertEqual(snapshot(self.game), before)

    def test_queenside_castle(self):
        self.game.make_move((4, 0, 0), (2, 0, 0))
        self.assertIsInstance(self.game.board.get_piece((3, 0, 0)), Rook)
        self.assertIsNone(self.game.board.get_piece((0, 0, 0)))

    def test_no_castle_through_attacked_square(self):
        self.game.board.set_piece(Rook("black"), (5, 5, 0))
        moves = self.game.get_legal_moves((4, 0, 0))
        self.assertNotIn((6, 0, 0), moves)
        self.assertIn((2, 0, 0), moves)

    def test_no_castle_after_king_moved(self):
        self.game.make_move((4, 0, 0), (4, 1, 0))
        self.game.make_move((4, 7, 0), (4, 6, 0))
        self.game.make_move((4, 1, 0), (4, 0, 0))
        self.game.make_move((4, 6, 0), (4, 7, 0))
        self.assertNotIn((6, 0, 0), self.game.get_legal_moves((4, 0, 0)))


class TestEnPassant(unittest.TestCase):
    def setUp(self):
        self.game = custom_game({(4, 0, 0): King("white"), (4, 7, 0): King("black"),
                                 (4, 4, 0): moved(Pawn("white")), (0, 4, 0): moved(Pawn("white")),
                                 (3, 6, 0): Pawn("black")}, current_player="black")

    def test_planar_en_passant_and_undo(self):
        self.game.make_move((3, 6, 0), (3, 4, 0))
        self.assertIn((3, 5, 0), self.game.get_legal_moves((4, 4, 0)))
        self.assertNotIn((3, 5, 0), self.game.get_legal_moves((0, 4, 0)))  # only the adjacent pawn
        before = snapshot(self.game)
        self.game.make_move((4, 4, 0), (3, 5, 0))
        self.assertIsNone(self.game.board.get_piece((3, 4, 0)))
        self.assertEqual(self.game.move_history[-1]['special_move'], "en_passant")
        self.assertTrue(self.game.undo_move())
        self.assertEqual(snapshot(self.game), before)

    def test_climbing_double_step_en_passant(self):
        self.game.make_move((3, 6, 0), (3, 4, 2))
        self.assertIn((3, 5, 1), self.game.get_legal_moves((4, 4, 0)))
        self.game.make_move((4, 4, 0), (3, 5, 1))
        self.assertIsNone(self.game.board.get_piece((3, 4, 2)))

    def test_en_passant_expires(self):
        self.game.make_move((3, 6, 0), (3, 4, 0))
        self.game.make_move((4, 0, 0), (4, 1, 0))
        self.game.make_move((4, 7, 0), (4, 6, 0))
        self.assertNotIn((3, 5, 0), self.game.get_legal_moves((4, 4, 0)))

    def test_single_step_is_not_en_passant(self):
        game = custom_game({(4, 0, 0): King("white"), (4, 7, 0): King("black"),
                            (4, 4, 0): moved(Pawn("white")), (3, 5, 0): moved(Pawn("black"))},
                           current_player="black")
        game.make_move((3, 5, 0), (3, 4, 0))
        self.assertNotIn((3, 5, 0), game.get_legal_moves((4, 4, 0)))


class TestPromotion(unittest.TestCase):
    def setUp(self):
        self.game = custom_game({(4, 0, 0): King("white"), (4, 7, 0): King("black"),
                                 (0, 6, 1): moved(Pawn("white"))})

    def test_promotion_flow(self):
        self.game.make_move((0, 6, 1), (0, 7, 1))
        self.assertEqual(self.game.pending_promotion, (0, 7, 1))
        self.assertEqual(self.game.current_player, "white")  # turn not passed yet
        with self.assertRaises(ValueError):
            self.game.make_move((4, 0, 0), (4, 1, 0))
        with self.assertRaises(ValueError):
            self.game.promote_pawn((0, 7, 1), King("white"))
        with self.assertRaises(ValueError):
            self.game.promote_pawn((0, 7, 1), Queen("black"))
        self.game.promote_pawn((0, 7, 1), Queen("white"))
        self.assertIsInstance(self.game.board.get_piece((0, 7, 1)), Queen)
        self.assertIsNone(self.game.pending_promotion)
        self.assertEqual(self.game.current_player, "black")

    def test_undo_promotion_takes_back_the_whole_turn(self):
        before = snapshot(self.game)
        self.game.make_move((0, 6, 1), (0, 7, 1))
        self.game.promote_pawn((0, 7, 1), Knight("white"))
        self.assertTrue(self.game.undo_move())
        self.assertEqual(snapshot(self.game), before)

    def test_undo_while_promotion_pending(self):
        before = snapshot(self.game)
        self.game.make_move((0, 6, 1), (0, 7, 1))
        self.assertTrue(self.game.undo_move())
        self.assertEqual(snapshot(self.game), before)

    def test_cannot_promote_without_pending_pawn(self):
        with self.assertRaises(ValueError):
            self.game.promote_pawn((0, 6, 1), Queen("white"))


class TestUndo(unittest.TestCase):
    def test_nothing_to_undo(self):
        self.assertFalse(GameState().undo_move())

    def test_undo_restores_capture_and_has_moved(self):
        game = GameState()
        start = snapshot(game)
        game.make_move((4, 1, 0), (4, 3, 0))
        game.make_move((3, 6, 0), (3, 4, 0))
        after_two = snapshot(game)
        game.make_move((4, 3, 0), (3, 4, 0))  # capture
        self.assertEqual(game.move_history[-1]['captured_piece'], "Pawn(black)")
        self.assertTrue(game.undo_move())
        self.assertEqual(snapshot(game), after_two)
        game.undo_move()
        game.undo_move()
        self.assertEqual(snapshot(game), start)
        # Other pawns were never touched by the undone moves
        self.assertIn((0, 3, 0), game.get_legal_moves((0, 1, 0)))


class TestDraw(unittest.TestCase):
    def test_bare_kings(self):
        game = custom_game({(4, 0, 0): King("white"), (4, 7, 0): King("black")})
        self.assertTrue(game.is_insufficient_material())

    def test_bishop_plus_queen_is_enough(self):
        game = custom_game({(4, 0, 0): King("white"), (4, 7, 0): King("black"),
                            (2, 0, 0): Bishop("white"), (3, 0, 0): Queen("white")})
        self.assertFalse(game.is_insufficient_material())


if __name__ == '__main__':
    unittest.main()
