import unittest
from engine.board import Board
from engine.pieces import King, Rook, Pawn, Rock


class TestBoard(unittest.TestCase):
    def setUp(self):
        self.board = Board()
        
    def test_board_init(self):
        king = self.board.get_piece((4,0,0))
        self.assertIsNotNone(king)
        
    def test_get_piece(self):
        rook = self.board.get_piece((0,0,0))
        self.assertIsNotNone(rook)
        

if __name__ == '__main__':
    unittest.main()
        
