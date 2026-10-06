X, Y, Z = 0 ,1 ,2

class Rock:
    def __init__(self):
        pass
    
    def __str__(self):
        return f"Rock"

class Piece:
    def __init__(self,color):
        self.color = color
    
    @staticmethod
    def is_coord_in_board(coord:tuple):
        return ( 0 <= coord[X]<= 7 and
                0 <= coord[Y] <= 7 and
                -2 <= coord[Z] <= 2)
        
    @staticmethod
    def coord_sum(coord1:tuple, coord2:tuple) -> tuple:
        return(coord1[X]+coord2[X],
               coord1[Y]+coord2[Y],
               coord1[Z]+coord2[Z])
        
    @staticmethod    
    def iterate_moves(self_coord:tuple, vector:tuple) -> list:
        vector_moves = []
        check_coord = self_coord
        while True:
            check_coord = Piece.coord_sum(check_coord,vector)
            if Piece.is_coord_in_board(check_coord):
                vector_moves.append(check_coord)
            else:
                break
        return vector_moves
            
             
class Rook(Piece):
    def __init__(self,color):
        super().__init__(color)
        self.has_moved = False
    
    def __str__(self):
        return f"Rook({self.color})"
        
    def get_possible_moves(self,self_coord:tuple):
        moves = []
        x, y, z = self_coord      
        for new_x in range(8):
            if new_x != x:
                moves.append((new_x, y, z))
        for new_y in range(8):
            if new_y != y:
                moves.append((x, new_y, z))            
        for new_z in range(-2,3):
            if new_z != z:
                moves.append((x, y, new_z))            
        return moves
                           
class Bishop(Piece):
    def __init__(self,color):
        super().__init__(color)
    
    def get_square_color(self, coord):
        """Get the square color this bishop is on given a coordinate (0=light, 1=dark)"""
        return (coord[X] + coord[Y]) % 2
    
    def __str__(self):
        return f"Bishop({self.color})"
    
    def get_possible_moves(self,self_coord:tuple):
        all_moves = []
        bishop_vectors = [
            (1,1,0), (1,-1,0), (-1,1,0), (-1,-1,0),
            (1,0,1), (1,0,-1), (-1,0,1), (-1,0,-1),
            (0,1,1), (0,1,-1), (0,-1,1), (0,-1,-1),
        ] # (1,1,0) example moving diagonal forward and right
        
        # Iterate each vector and try to add the move
        for vector in bishop_vectors:
            vector_moves = Piece.iterate_moves(self_coord,vector)
            all_moves.extend(vector_moves)
            
        return all_moves
        

class Knight(Piece):
    def __init__(self,color):
        super().__init__(color)
        
    def __str__(self):
        return f"Knight({self.color})"
    
    def get_possible_moves(self, self_coord: tuple):
        all_knight_moves = []
        
        # All 24 knight moves: (±2, ±1, 0) and (±1, ±2, 0) patterns rotated through dimensions
        knight_vectors = [
            # XY plane (2 in X, 1 in Y)
            (2,1,0), (2,-1,0), (-2,1,0), (-2,-1,0),
            (1,2,0), (1,-2,0), (-1,2,0), (-1,-2,0),
            # XZ plane (2 in X, 1 in Z)
            (2,0,1), (2,0,-1), (-2,0,1), (-2,0,-1),
            (1,0,2), (1,0,-2), (-1,0,2), (-1,0,-2),
            # YZ plane (2 in Y, 1 in Z)
            (0,2,1), (0,2,-1), (0,-2,1), (0,-2,-1),
            (0,1,2), (0,1,-2), (0,-1,2), (0,-1,-2),
        ]
        
        for vector in knight_vectors:
            new_coord = Piece.coord_sum(self_coord, vector)
            if Piece.is_coord_in_board(new_coord):
                all_knight_moves.append(new_coord)
        
        return all_knight_moves
        
class Queen(Piece):
    def __init__(self, color):
        super().__init__(color)

    def __str__(self):
        return f"Queen({self.color})"
    
    def get_possible_moves(self, self_coord: tuple):
        all_queen_moves = []
        
        # Combine both Rook and Bishop vectors
        rook_vectors = [(1,0,0), (-1,0,0), (0,1,0), (0,-1,0), (0,0,1), (0,0,-1)]
        bishop_vectors = [(1,1,0), (1,-1,0), (-1,1,0), (-1,-1,0), (1,0,1), (1,0,-1), (-1,0,1), (-1,0,-1), (0,1,1), (0,1,-1), (0,-1,1), (0,-1,-1)]
        
        for vector in rook_vectors + bishop_vectors:
            all_queen_moves.extend(Piece.iterate_moves(self_coord, vector))
            
        return all_queen_moves
        

class King(Piece):
    def __init__(self,color):
        super().__init__(color)
        self.has_moved = False
        
    def __str__(self):
        return f"King({self.color})"
        
    def get_possible_moves(self, self_coord: tuple):
        all_king_moves = []
        
        # XY plane movements (8 directions) + Z movements (2 directions)
        king_vectors = [
            (1,0,0), (-1,0,0), (0,1,0), (0,-1,0),
            (1,1,0), (1,-1,0), (-1,1,0), (-1,-1,0),
            (0,0,1), (0,0,-1)
        ]
        
        for vector in king_vectors:
            new_coord = Piece.coord_sum(self_coord, vector)
            if Piece.is_coord_in_board(new_coord):
                all_king_moves.append(new_coord)
                
        return all_king_moves
            
        
class Pawn(Piece):
    def __init__(self,color):
        super().__init__(color)
        self.has_moved = False
        
    def __str__(self):
        return f"Pawn({self.color})"
        
    def get_possible_moves(self, self_coord: tuple):
        all_pawn_moves = []
        all_pawn_captures = []
        
        # White pawns advance toward Y=7, black pawns toward Y=0
        d = 1 if self.color == "white" else -1
        
        # Normal movement vectors
        move_vectors = [(0,d,0), (0,d,1), (0,d,-1)]
        if not self.has_moved:
            move_vectors += [(0,2*d,0), (0,2*d,2), (0,2*d,-2)]
        
        # Capture vectors
        capture_vectors = [(1,d,0), (-1,d,0), (1,d,1), (-1,d,1), (1,d,-1), (-1,d,-1)]
        
        for vector in move_vectors:
            new_coord = Piece.coord_sum(self_coord, vector)
            if Piece.is_coord_in_board(new_coord):
                all_pawn_moves.append(new_coord)
        
        for vector in capture_vectors:
            new_coord = Piece.coord_sum(self_coord, vector)
            if Piece.is_coord_in_board(new_coord):
                all_pawn_captures.append(new_coord)
        
        return all_pawn_moves, all_pawn_captures
