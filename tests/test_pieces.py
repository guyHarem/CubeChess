import unittest
from engine.pieces import King, Queen, Rook, Bishop, Knight, Pawn


class TestPieces(unittest.TestCase):
    def test_no_piece_moves_on_three_axes(self):
        for piece in (King("white"), Queen("white"), Rook("white"), Bishop("white"), Knight("white")):
            for x, y, z in piece.get_possible_moves((3, 3, 0)):
                changed = (x != 3) + (y != 3) + (z != 0)
                self.assertLessEqual(changed, 2, f"{piece} moved on 3 axes")

    def test_king_has_ten_moves_in_open_space(self):
        self.assertEqual(len(King("white").get_possible_moves((3, 3, 0))), 10)

    def test_knight_has_24_moves_in_open_space(self):
        self.assertEqual(len(Knight("white").get_possible_moves((3, 3, 0))), 24)

    def test_moves_stay_inside_board(self):
        for move in Queen("white").get_possible_moves((0, 0, -2)):
            self.assertTrue(Queen.is_coord_in_board(move))

    def test_white_pawn_moves_up_the_board(self):
        moves, captures = Pawn("white").get_possible_moves((4, 1, 0))
        self.assertIn((4, 2, 0), moves)
        self.assertIn((4, 3, 0), moves)
        self.assertTrue(all(y > 1 for _, y, _ in moves + captures))

    def test_black_pawn_moves_down_the_board(self):
        moves, captures = Pawn("black").get_possible_moves((4, 6, 0))
        self.assertIn((4, 5, 0), moves)
        self.assertIn((4, 4, 0), moves)
        self.assertTrue(all(y < 6 for _, y, _ in moves + captures))

    def test_moved_pawn_has_no_double_step(self):
        pawn = Pawn("white")
        pawn.has_moved = True
        moves, _ = pawn.get_possible_moves((4, 2, 0))
        self.assertEqual(sorted(moves), [(4, 3, -1), (4, 3, 0), (4, 3, 1)])


if __name__ == '__main__':
    unittest.main()
