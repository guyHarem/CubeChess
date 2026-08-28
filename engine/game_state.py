from engine.board import Board
from engine.pieces import Piece, Rock, King, Queen, Rook, Bishop, Knight, Pawn
X, Y, Z = 0, 1, 2
white, black = "white", "black"


class GameState:
    
    # ==================== INITIALIZATION & UTILITIES ====================
    
    def __init__(self):
        self.board = Board()
        self.current_player = white
        self.white_king_pos = (5,0,0) # white king init tile
        self.black_king_pos = (5,7,0) # black king init tile
        self.move_history = [] # (move,what happened)
    
    
    @staticmethod
    def coord_sum(coord1: tuple, coord2: tuple) -> tuple:
        """Helper: Element-wise tuple addition"""
        return (coord1[X] + coord2[X],
                coord1[Y] + coord2[Y],
                coord1[Z] + coord2[Z])
    
    
    # ==================== BOARD STATE QUERIES ====================
    
    def get_board_state(self):
        """Return the board object"""
        return self.board
    
    
    def get_all_pieces_of_color(self, color):
        """Get all pieces (non-Rocks) of a given color"""
        color_pieces = []        
        for coord, piece in self.board.board.items():
            if isinstance(piece, Rock):
                continue
            if piece.color == color:
                color_pieces.append((coord, piece))
        return color_pieces
    
    def find_piece_by_type(self, piece_type, color):
        all_color_pieces = self.get_all_pieces_of_color(color)
        pieces_color_type = []      
        for coord, piece in all_color_pieces:
            if isinstance(piece, piece_type):
                pieces_color_type.append((coord, piece))      
        return pieces_color_type
        
        
    # ==================== GAME MANAGEMENT ====================
    
    def switch_turn(self):
        """Switch from white to black or black to white"""
        if self.current_player == white:
            self.current_player = black
        else:
            self.current_player = white
    
    def add_to_move_history(self, from_coord, to_coord, moving_piece=None, captured_piece=None, promotion_piece=None,
                            special_move=None):
        move_dict = {
            'from': from_coord,
            'to': to_coord,
            'moving_piece': str(moving_piece) if moving_piece is not None else None,
            'captured_piece': str(captured_piece) if captured_piece is not None else None,
            'promotion_piece': str(promotion_piece) if promotion_piece is not None else None,
            'special_move': special_move
        }
        
        self.move_history.append(move_dict)
        
            
    # ==================== MOVE EXECUTION (CORE) ====================
    
    def _execute_move(self, from_coord, to_coord):
        """Internal: Execute move without validation or side effects"""
        # Remove captured piece if exists
        if self.board.get_piece(to_coord) is not None:
            self.board.remove_piece(to_coord)
        
        # Move the piece
        self.board.move_piece(from_coord, to_coord)
        
        # Update king position if king moved
        moved_piece = self.board.get_piece(to_coord)
        if isinstance(moved_piece, King):
            if moved_piece.color == white:
                self.white_king_pos = to_coord
            else:
                self.black_king_pos = to_coord
    
    
    def make_move(self, from_coord, to_coord):
        """Public API: Execute move with validation and side effects"""
        piece = self.board.get_piece(from_coord)
        
        # Validate move is legal
        if not self.is_legal_move(from_coord, to_coord):
            raise ValueError("Illegal move!")
        
        # Check if this is a castling move
        if isinstance(piece, King) and to_coord in self.is_castle_available(self.current_player):
            self.do_castle(from_coord, to_coord)
            self.switch_turn()
            return
        
        # Check if this is an en passant move
        if isinstance(piece, Pawn) and to_coord in self.is_en_passant_available(self.current_player):
            self.do_en_passant(from_coord, to_coord)
            self.switch_turn()
            return
        
        # Capture piece info before executing move
        captured_piece = self.board.get_piece(to_coord)
        
        # Execute the move
        self._execute_move(from_coord, to_coord)
        
        # Side effects
        if isinstance(piece, Pawn):
            piece.has_moved = True
        
        if isinstance(piece, King):
            piece.has_moved = True
        
        if isinstance(piece, Rook):
            piece.has_moved = True
                
        
        # Switch turn and record history
        self.switch_turn()
        self.add_to_move_history(from_coord, to_coord, moving_piece=piece, captured_piece=captured_piece)

    def do_castle(self, king_from, king_to):
        """Execute a castling move"""
        # Get the king piece
        king_piece = self.board.get_piece(king_from)
        
        # Determine direction (1 for kingside, -1 for queenside)
        direction = 1 if king_to[X] > king_from[X] else -1
        
        # Find the rook in that direction on same rank and layer
        rook_coord = None
        rooks = self.find_piece_by_type(Rook, king_piece.color)
        for rook_pos, rook_piece in rooks:
            # Rook must be on same Y and Z, and in the castling direction
            if (rook_pos[Y] == king_from[Y] and rook_pos[Z] == king_from[Z] and
                (rook_pos[X] - king_from[X]) * direction > 0):
                rook_coord = rook_pos
                break
        
        if rook_coord is None:
            raise ValueError("Rook not found for castling!")
        
        rook_piece = self.board.get_piece(rook_coord)
        
        # Calculate rook destination (one square toward center from king's destination)
        rook_dest = (king_to[X] - direction, king_to[Y], king_to[Z])
        
        # Move both pieces
        self.board.move_piece(king_from, king_to)
        self.board.move_piece(rook_coord, rook_dest)
        
        # Update king position tracker
        if king_piece.color == white:
            self.white_king_pos = king_to
        else:
            self.black_king_pos = king_to
        
        # Mark both as moved
        king_piece.has_moved = True
        rook_piece.has_moved = True
        
        # Record in move history
        self.add_to_move_history(king_from, king_to, moving_piece=king_piece, special_move="castling")
    
    def do_en_passant(self, from_coord, to_coord):
        player_pawn = self.board.get_piece(from_coord)
        
        opponent_pawn_coord = self.move_history[-1]['to']
        opponent_pawn = self.board.get_piece(opponent_pawn_coord)
        
        self.board.remove_piece(opponent_pawn_coord)
        
        self.board.move_piece(from_coord,to_coord)
        
        player_pawn.has_moved = True
        
        self.add_to_move_history(from_coord, to_coord, moving_piece=player_pawn, captured_piece=opponent_pawn, special_move="en_passant")
    
    # ==================== MOVE VALIDATION (MIDDLE LAYER) ====================
    
    def can_piece_attack_square(self, piece, from_coord, to_coord):
        """Check if a piece can attack a square (with path blocking)"""
        # Get possible attack moves
        if isinstance(piece, Pawn):
            possible_moves = piece.get_possible_moves(from_coord)[1]  # captures only
        else:
            possible_moves = piece.get_possible_moves(from_coord)
        
        # Check if the target is attackable
        if to_coord not in possible_moves:
            return False
        
        # Knight can jump over anything (no blocking)
        # King attacks any adjacent square (no path blocking needed)
        if isinstance(piece, Knight) or isinstance(piece, King):
            return True
        
        # Check if path is free for other pieces
        dx = (to_coord[X] - from_coord[X])
        dy = (to_coord[Y] - from_coord[Y])
        dz = (to_coord[Z] - from_coord[Z])
        
        # Inline sign function
        sign = lambda x: 1 if x > 0 else (-1 if x < 0 else 0)
        
        dir_vector = (sign(dx), sign(dy), sign(dz))
        distance = max(abs(dx), abs(dy), abs(dz))
        
        # Walk intermediate squares and check for blocking pieces
        current = from_coord
        for step in range(1, distance):
            current = GameState.coord_sum(current, dir_vector)
            if self.board.get_piece(current) is not None:
                return False  # path blocked
        
        return True  # path is clear
    
    def is_square_under_attack(self, coord, by_color):
        opponent_pieces = self.get_all_pieces_of_color(by_color)
        for opponent_coord, opponent_piece in opponent_pieces:
            if self.can_piece_attack_square(opponent_piece,opponent_coord,coord):
                return True 
            
        return False
        
        
    def is_in_check(self, color):
        """Check if a king of given color is under attack"""
        # Get the king position for this color
        if color == white:
            king_pos = self.white_king_pos
        else:
            king_pos = self.black_king_pos
        
        # Get all opponent pieces
        opponent_color = black if color == white else white
        opponent_pieces = self.get_all_pieces_of_color(opponent_color)
        
        # Check if any opponent can attack the king
        for opponent_coord, opponent_piece in opponent_pieces:
            if self.can_piece_attack_square(opponent_piece, opponent_coord, king_pos):
                return True  # King is under attack!
        
        return False  # King is safe
    
    
    def simulate_move(self, piece, from_coord, to_coord):
        """Simulate a move and check if it leaves king safe"""
        # Save state
        captured_piece = self.board.get_piece(to_coord)
        saved_white_king = self.white_king_pos
        saved_black_king = self.black_king_pos
        
        # Execute
        self._execute_move(from_coord, to_coord)
        
        # Check if king is safe
        is_safe = not self.is_in_check(piece.color)
        
        # Restore state
        self.board.move_piece(to_coord, from_coord)
        if captured_piece is not None:
            self.board.set_piece(captured_piece, to_coord)
        self.white_king_pos = saved_white_king
        self.black_king_pos = saved_black_king
        
        return is_safe
    
    
    def get_legal_moves(self, from_coord):
        """Get all legal moves for a piece at given coordinate"""
        legal_moves = []
        piece = self.board.get_piece(from_coord)
        
        # Check if no piece in the square or if it's a rock -> return empty list
        if piece is None or isinstance(piece, Rock):
            return legal_moves
        
        # Pawn has different logic than other pieces
        if isinstance(piece, Pawn):
            possible_moves = piece.get_possible_moves(from_coord)[0]
            possible_captures = piece.get_possible_moves(from_coord)[1]
            
            # Process Pawn moves: must be empty squares
            for possible_move in possible_moves:
                if self.board.get_piece(possible_move) is not None:
                    continue  # Skip, not empty
                
                if self.simulate_move(piece, from_coord, possible_move):
                    legal_moves.append(possible_move)
            
            # Process Pawn captures: must be enemy pieces
            for possible_capture in possible_captures:
                destination_piece = self.board.get_piece(possible_capture)
                
                if destination_piece is None:
                    continue  # Skip, empty square
                if destination_piece.color == piece.color:
                    continue  # Skip, own piece
                
                if self.simulate_move(piece, from_coord, possible_capture):
                    legal_moves.append(possible_capture)
        
        # Non-Pawn pieces
        else:
            possible_moves = piece.get_possible_moves(from_coord)
            
            for possible_move in possible_moves:
                destination_piece = self.board.get_piece(possible_move)
                
                # Skip if own piece
                if destination_piece is not None and destination_piece.color == piece.color:
                    continue
                
                if self.simulate_move(piece, from_coord, possible_move):
                    legal_moves.append(possible_move)
        
        # Add castling destinations if piece is King
        if isinstance(piece, King):
            castling_dests = self.is_castle_available(piece.color)
            legal_moves.extend(castling_dests)
        
        # Add en passant destinations if piece is Pawn
        if isinstance(piece, Pawn):
            en_passant_dests = self.is_en_passant_available(piece.color)
            legal_moves.extend(en_passant_dests)
        
        return legal_moves
      
    def is_legal_move(self, from_coord, to_coord):
        piece_to_move = self.board.get_piece(from_coord)
        if piece_to_move is None or isinstance(piece_to_move, Rock):
            return False
        return to_coord in self.get_legal_moves(from_coord)
        
                    
    # ==================== GAME STATE ANALYSIS (HIGH LEVEL) ====================
    
    def is_pawn_promotion(self, coord):
        """Check if pawn at coord has reached the promotion line"""
        piece = self.board.get_piece(coord)
        
        # Check if that piece is a pawn
        if not isinstance(piece, Pawn):
            return False
        
        # Logic to check piece color and if reached end line
        if piece.color == white:
            if coord[Y] == 7:
                return True
        if piece.color == black:
            if coord[Y] == 0:
                return True
        return False  
    
    def promote_pawn(self, coord, new_piece):
        # Cant place another king, rock, or pawn
        if isinstance(new_piece, King) or isinstance(new_piece, Rock) or isinstance(new_piece, Pawn):
            raise ValueError("New Piece Can't be a King, Rock, or Pawn!")
        
        # Check if its actually a pawn in the coord and its on promotion line
        is_pawn = self.board.get_piece(coord)
        if isinstance(is_pawn, Pawn) and self.is_pawn_promotion(coord):
            self.board.remove_piece(coord)
            self.board.set_piece(new_piece, coord)
            self.add_to_move_history(coord, coord, moving_piece=is_pawn, promotion_piece=new_piece, special_move="promotion")
            return True
        return False
        
    def is_checkmate(self, color):
        """Check if a player is in checkmate (in check + no legal moves)"""
        if not self.is_in_check(color):
            return False  # Not in check = not checkmate
        
        # Check if ANY piece has a legal move
        all_pieces = self.get_all_pieces_of_color(color)
        for coord, piece in all_pieces:
            if len(self.get_legal_moves(coord)) > 0:
                return False  # Found an escape
        
        return True  # No escape = checkmate
    
    def is_stalemate(self, color):
        """Check if a player is in stalemate (not in check + no legal moves)"""
        if self.is_in_check(color):
            return False  # In check = not stalemate
        
        # Check if ANY piece has a legal move
        all_pieces = self.get_all_pieces_of_color(color)
        for coord, piece in all_pieces:
            if len(self.get_legal_moves(coord)) > 0:
                return False  # Found a legal move
        
        return True  # No legal moves and NOT in check = stalemate

    def is_castle_available(self, color):
        castling_destinations = []
        
        # Get king position and piece
        if color == white:
            king_coord = self.white_king_pos
        else:
            king_coord = self.black_king_pos
        
        king_piece = self.board.get_piece(king_coord)
        
        # Check king conditions
        if king_piece.has_moved or self.is_in_check(color):
            return []
        
        # Check each rook
        rooks = self.find_piece_by_type(Rook, color)
        for rook_coord, rook in rooks:
            if not rook.has_moved:
                # Check if same Y and Z (on same rank/layer)
                if king_coord[Y] != rook_coord[Y] or king_coord[Z] != rook_coord[Z]:
                    continue
                
                # Determine direction: kingside (right) or queenside (left)
                direction = 1 if rook_coord[X] > king_coord[X] else -1
                
                # Check if path between king and rook is clear
                path_clear = True
                for x in range(king_coord[X] + direction, rook_coord[X], direction):
                    check_coord = (x, king_coord[Y], king_coord[Z])
                    if self.board.get_piece(check_coord) is not None:
                        path_clear = False
                        break
                
                if not path_clear:
                    continue
                
                # Calculate intermediate and destination squares
                intermediate_coord = (king_coord[X] + direction, king_coord[Y], king_coord[Z])
                destination_coord = (king_coord[X] + 2 * direction, king_coord[Y], king_coord[Z])
                
                # Check if intermediate and destination are not under attack
                opponent_color = black if color == white else white
                if self.is_square_under_attack(intermediate_coord, opponent_color):
                    continue
                if self.is_square_under_attack(destination_coord, opponent_color):
                    continue
                
                # All checks pass, add destination
                castling_destinations.append(destination_coord)
        
        return castling_destinations
    
    def is_en_passant_available(self, color):
        
        # Check if last move was an opponent pawn double-move
        if len(self.move_history) > 0:
            last_move = self.move_history[-1]
        else:
            return []
        moving_piece = last_move['moving_piece']
        from_coord = last_move['from']
        to_coord = last_move['to']
        if self.current_player == white:
            if moving_piece != "Pawn(black)":
                return []
            if from_coord[Y] != 6 or to_coord[Y] != 4:
                return []
        else: # Black is current player
            if moving_piece != "Pawn(white)":
                return []
            if from_coord[Y] != 1 or to_coord[Y] != 3:
                return []
        
        # Find our pawns adjacent to enemy's final position
        en_passant_moves = []
        our_pawns = self.find_piece_by_type(Pawn, color)
        
        for pawn_coord, pawn in our_pawns:
            # Must be at same Y as enemy's final position
            if pawn_coord[Y] != to_coord[Y]:
                continue
            
            # Must be adjacent in X
            if abs(pawn_coord[X] - to_coord[X]) != 1:
                continue
            
            # Must be same or adjacent layer in Z
            if abs(pawn_coord[Z] - to_coord[Z]) > 1:
                continue
            
            # Calculate capture destination
            if color == white:
                capture_y = pawn_coord[Y] + 1
            else:
                capture_y = pawn_coord[Y] - 1
            
            capture_dest = (to_coord[X], capture_y, to_coord[Z])
            en_passant_moves.append(capture_dest)
        
        return en_passant_moves
    
    def undo_move(self):
        """Undo the last move"""
        if len(self.move_history) == 0:
            return False  # Nothing to undo
        
        last_move = self.move_history.pop()
        from_coord = last_move['from']
        to_coord = last_move['to']
        special_move = last_move['special_move']
        moving_piece_str = last_move['moving_piece']
        captured_piece_str = last_move['captured_piece']
        promotion_piece_str = last_move['promotion_piece']
        
        # Handle castling
        if special_move == "castling":
            # Get king and move it back
            king = self.board.get_piece(to_coord)
            self.board.move_piece(to_coord, from_coord)
            
            # Find and move rook back
            direction = 1 if to_coord[X] > from_coord[X] else -1
            rook_curr = (to_coord[X] - direction, to_coord[Y], to_coord[Z])
            rook_orig = (7, from_coord[Y], from_coord[Z]) if direction == 1 else (0, from_coord[Y], from_coord[Z])
            rook = self.board.get_piece(rook_curr)
            self.board.move_piece(rook_curr, rook_orig)
            
            # Restore has_moved for both
            king.has_moved = any(m['moving_piece'] == moving_piece_str for m in self.move_history)
            rook.has_moved = any(m['moving_piece'] == "Rook" + moving_piece_str.split("(")[1] for m in self.move_history)
            
            # Restore king position tracker
            if king.color == white:
                self.white_king_pos = from_coord
            else:
                self.black_king_pos = from_coord
        
        # Handle en passant
        elif special_move == "en_passant":
            # Move our pawn back
            pawn = self.board.get_piece(to_coord)
            self.board.move_piece(to_coord, from_coord)
            
            # Restore enemy pawn at original location from move_history
            enemy_pawn_orig = self.move_history[-1]['to'] if len(self.move_history) > 0 else None
            if enemy_pawn_orig and captured_piece_str:
                enemy_pawn = self._recreate_piece_from_string(captured_piece_str)
                self.board.set_piece(enemy_pawn, enemy_pawn_orig)
            
            # Restore has_moved for our pawn
            pawn.has_moved = any(m['moving_piece'] == moving_piece_str for m in self.move_history)
        
        # Handle promotion
        elif special_move == "promotion":
            # Remove promoted piece and restore pawn
            self.board.remove_piece(to_coord)
            pawn = self._recreate_piece_from_string(moving_piece_str)
            pawn.has_moved = False  # Pawn just got promoted, so set to False
            self.board.set_piece(pawn, to_coord)
        
        # Normal move
        else:
            # Move piece back
            piece = self.board.get_piece(to_coord)
            self.board.move_piece(to_coord, from_coord)
            
            # Restore captured piece if any
            if captured_piece_str:
                captured_piece = self._recreate_piece_from_string(captured_piece_str)
                self.board.set_piece(captured_piece, to_coord)
            
            # Restore has_moved
            piece.has_moved = any(m['moving_piece'] == moving_piece_str for m in self.move_history)
            
            # Restore king position if King moved
            if isinstance(piece, King):
                if piece.color == white:
                    self.white_king_pos = from_coord
                else:
                    self.black_king_pos = from_coord
        
        # Switch turn back
        self.switch_turn()
        return True
    
    
    def _recreate_piece_from_string(self, piece_str):
        """Recreate a piece object from its string representation"""
        if piece_str is None:
            return None
        
        # Parse piece_str format: "PieceName(color)"
        piece_name = piece_str.split("(")[0]
        piece_color = piece_str.split("(")[1].rstrip(")")
        
        piece_classes = {
            "Pawn": Pawn,
            "Rook": Rook,
            "Knight": Knight,
            "Bishop": Bishop,
            "Queen": Queen,
            "King": King,
        }
        
        PieceClass = piece_classes.get(piece_name)
        if PieceClass:
            return PieceClass(piece_color)
        return None
    
    
    def _get_material_count(self, color):
        """Count pieces by type for a player (helper for draw detection)"""
        material = {
            'Pawn': 0,
            'Rook': 0,
            'Knight': 0,
            'Bishop': 0,
            'Queen': 0
        }
        
        all_pieces = self.get_all_pieces_of_color(color)
        for coord, piece in all_pieces:
            if isinstance(piece, Pawn):
                material['Pawn'] += 1
            elif isinstance(piece, Rook):
                material['Rook'] += 1
            elif isinstance(piece, Knight):
                material['Knight'] += 1
            elif isinstance(piece, Bishop):
                material['Bishop'] += 1
            elif isinstance(piece, Queen):
                material['Queen'] += 1
        
        return material
    
    
    def is_insufficient_material(self):
        """Check if both players have insufficient material to force checkmate"""
        white_material = self._get_material_count(white)
        black_material = self._get_material_count(black)
        
        # Helper to check if a player's material is insufficient
        def is_insufficient(color, material):
            total_pieces = sum(material.values())
            
            # King only
            if total_pieces == 0:
                return True
            
            # King + 1 minor piece (Knight or Bishop)
            if total_pieces == 1:
                return material['Knight'] == 1 or material['Bishop'] == 1
            
            # King + only bishops on same color squares (can't mate)
            if material['Bishop'] > 0 and material['Knight'] == 0:
                # Get all bishops for this color with their coordinates
                bishops = self.find_piece_by_type(Bishop, color)
                if len(bishops) > 0:
                    # Get square color of first bishop using its method
                    first_bishop_color = bishops[0][1].get_square_color(bishops[0][0])
                    
                    # Check if ALL bishops are on same color
                    all_same_color = all(
                        bishop_piece.get_square_color(bishop_coord) == first_bishop_color
                        for bishop_coord, bishop_piece in bishops
                    )
                    
                    # If all bishops same color and no other pieces: insufficient
                    if all_same_color:
                        return True
            
            return False
        
        # Draw if BOTH players have insufficient material
        return is_insufficient(white, white_material) and is_insufficient(black, black_material)
    
    
    def is_draw(self):
        """Check if the game is a draw (stalemate or insufficient material)"""
        # Draw by stalemate
        if self.is_stalemate(self.current_player):
            return True
        
        # Draw by insufficient material
        if self.is_insufficient_material():
            return True
        
        return False
        
        













