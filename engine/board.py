from engine.pieces import King, Queen, Rook, Bishop, Knight, Pawn, Rock
X, Y, Z = 0, 1, 2

class Board:
    def __init__(self):
        self.board = dict()
        self.init_pieces()
        self.init_rocks()
                        
    def is_valid_coordinate(self, coord:tuple):
        if not ( 0 <= coord[X] <= 7 and 0 <= coord[Y] <= 7 and -2<= coord[Z] <= 2):
            raise ValueError("Invalid coordiante")

    def is_coordinate_in_board(self,coord:tuple):
        if ( 0 <= coord[X] <= 7 and 0 <= coord[Y] <= 7 and -2<= coord[Z] <= 2):
            return True
        else:
            return False
    
    def get_piece(self, coord:tuple):
        self.is_valid_coordinate(coord)
        return self.board.get(coord)
    
    def set_piece(self, Piece, coord):
        self.is_valid_coordinate(coord)
        if self.board.get(coord) is None:
            self.board[coord] = Piece
        else:
            raise ValueError("coordinate isn't free")
    
    def remove_piece(self,coord):
        self.is_valid_coordinate(coord)
        if self.board.get(coord) is None:
            raise ValueError("Trying to remove a piece from empty coordinate")
        else:
            del self.board[coord]  
            
    def move_piece(self, from_coord: tuple, to_coord: tuple):
        self.is_valid_coordinate(from_coord)
        self.is_valid_coordinate(to_coord)
        
        if self.board.get(from_coord) is None:
            raise ValueError("No piece at source")
        if self.board.get(to_coord) is not None:
            raise ValueError("Destination occupied")
        
        piece = self.board[from_coord]
        del self.board[from_coord]
        self.board[to_coord] = piece
    
    def init_pieces(self): 
        ## White placement
        self.board[(0,0,0)] = Rook("white")
        self.board[(1,0,0)] = Knight("white")
        self.board[(2,0,0)] = Bishop("white")
        self.board[(3,0,0)] = Queen("white")
        self.board[(4,0,0)] = King("white")
        self.board[(5,0,0)] = Bishop("white")
        self.board[(6,0,0)] = Knight("white")
        self.board[(7,0,0)] = Rook("white")
        for i in range(8):
            self.board[(i,1,0)] = Pawn("white")
        
        ## Black placement   
        self.board[(0,7,0)] = Rook("black")
        self.board[(1,7,0)] = Knight("black")
        self.board[(2,7,0)] = Bishop("black")
        self.board[(3,7,0)] = Queen("black")
        self.board[(4,7,0)] = King("black")
        self.board[(5,7,0)] = Bishop("black")
        self.board[(6,7,0)] = Knight("black")
        self.board[(7,7,0)] = Rook("black")
        for i in range(8):
            self.board[(i,6,0)] = Pawn("black")
                      
    def init_rocks(self):
        # Layer -1: Hourglass
        self.board[(2, 2, -1)] = Rock()
        self.board[(5, 2, -1)] = Rock()
        self.board[(3, 3, -1)] = Rock()
        self.board[(4, 3, -1)] = Rock()
        self.board[(3, 4, -1)] = Rock()
        self.board[(4, 4, -1)] = Rock()
        self.board[(2, 5, -1)] = Rock()
        self.board[(5, 5, -1)] = Rock()
        
        # Layer -2: Cross
        self.board[(3, 2, -2)] = Rock()
        self.board[(4, 2, -2)] = Rock()
        self.board[(2, 3, -2)] = Rock()
        self.board[(5, 3, -2)] = Rock()
        self.board[(2, 4, -2)] = Rock()
        self.board[(5, 4, -2)] = Rock()
        self.board[(3, 5, -2)] = Rock()
        self.board[(4, 5, -2)] = Rock()

