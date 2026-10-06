from engine.board import Board
from engine.pieces import Piece, Rock, King, Queen, Rook, Bishop, Knight, Pawn
X, Y, Z = 0, 1, 2
white, black = "white", "black"


class GameState:
    
    # ==================== INITIALIZATION & UTILITIES ====================
    
    def __init__(self, move_limit=50):
        self.board = Board()
        self.current_player = white
        self.white_king_pos = (4,0,0) # white king init tile
        self.black_king_pos = (4,7,0) # black king init tile
        self.move_history = [] # (move,what happened)
        self._undo_stack = [] # one record per move_history entry, holds the real piece objects
        self.pending_promotion = None # coord of a pawn waiting for promote_pawn()
        self.move_limit = move_limit # draw after this many moves by each player with no capture or pawn move
        self.halfmove_clock = 0 # single moves (plies) since the last capture or pawn move
        self._position_keys = [self._position_key()] # every position so far, for threefold repetition

    
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
    
    def reset_tracking(self):
        """Call after editing the board directly (sandbox): re-find the kings and forget history"""
        white_kings = self.find_piece_by_type(King, white)
        black_kings = self.find_piece_by_type(King, black)
        self.white_king_pos = white_kings[0][0] if white_kings else None
        self.black_king_pos = black_kings[0][0] if black_kings else None
        self.move_history = []
        self._undo_stack = []
        self.pending_promotion = None
        self.restart_draw_tracking()
    
    def restart_draw_tracking(self):
        """Treat the current position as the first one (repetition and move-limit counters start over)"""
        self.halfmove_clock = 0
        self._position_keys = [self._position_key()]
    
    def end_turn(self):
        """Pass the turn and remember the new position for threefold repetition"""
        self.switch_turn()
        self._position_keys.append(self._position_key())
    
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

    def add_to_undo_stack(self, from_coord, to_coord, piece, captured_piece=None, captured_coord=None,
                          rook=None, rook_from=None, rook_to=None, special_move=None):
        """Internal: remember everything undo_move needs to restore the exact previous state"""
        self._undo_stack.append({
            'from': from_coord,
            'to': to_coord,
            'piece': piece,
            'had_moved': getattr(piece, 'has_moved', None),
            'halfmove_clock': self.halfmove_clock,
            'captured_piece': captured_piece,
            'captured_coord': captured_coord,
            'rook': rook,
            'rook_from': rook_from,
            'rook_to': rook_to,
            'special_move': special_move
        })


    # ==================== MOVE EXECUTION (CORE) ====================
    
    def _execute_move(self, from_coord, to_coord):
        """Internal: Execute move without validation or side effects"""
        # Remove captured piece if exists
        captured_piece = self.board.get_piece(to_coord)
        if captured_piece is not None:
            self.board.remove_piece(to_coord)
            # Only possible in sandbox positions: a captured king is no longer tracked
            if isinstance(captured_piece, King):
                if captured_piece.color == white:
                    self.white_king_pos = None
                else:
                    self.black_king_pos = None
        
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
        if self.pending_promotion is not None:
            raise ValueError("Promote the pawn before making another move!")
        
        piece = self.board.get_piece(from_coord)
        
        if piece is None or isinstance(piece, Rock):
            raise ValueError("No piece to move at this coordinate!")
        
        if piece.color != self.current_player:
            raise ValueError("Not your turn!")
        
        # Validate move is legal
        if not self.is_legal_move(from_coord, to_coord):
            raise ValueError("Illegal move!")
        
        # Check if this is a castling move
        if isinstance(piece, King) and to_coord in self.is_castle_available(self.current_player):
            self.do_castle(from_coord, to_coord)
            self.end_turn()
            return
        
        # Check if this is an en passant move
        if isinstance(piece, Pawn) and to_coord in self.get_en_passant_moves(from_coord):
            self.do_en_passant(from_coord, to_coord)
            self.end_turn()
            return
        
        # Capture piece info before executing move
        captured_piece = self.board.get_piece(to_coord)
        
        # Record history (before has_moved changes, so undo can restore it)
        self.add_to_move_history(from_coord, to_coord, moving_piece=piece, captured_piece=captured_piece)
        self.add_to_undo_stack(from_coord, to_coord, piece, captured_piece=captured_piece, captured_coord=to_coord)
        
        # Execute the move
        self._execute_move(from_coord, to_coord)
        
        # Side effects
        if isinstance(piece, (Pawn, King, Rook)):
            piece.has_moved = True
        
        # Captures and pawn moves can't be taken back, so they restart the move-limit count
        if isinstance(piece, Pawn) or captured_piece is not None:
            self.halfmove_clock = 0
        else:
            self.halfmove_clock += 1
        
        # A pawn on the last rank keeps the turn until promote_pawn() is called
        if self.is_pawn_promotion(to_coord):
            self.pending_promotion = to_coord
        else:
            self.end_turn()

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
            # Rook must be unmoved, on same Y and Z, and in the castling direction
            if (not rook_piece.has_moved and
                rook_pos[Y] == king_from[Y] and rook_pos[Z] == king_from[Z] and
                (rook_pos[X] - king_from[X]) * direction > 0):
                rook_coord = rook_pos
                break
        
        if rook_coord is None:
            raise ValueError("Rook not found for castling!")
        
        rook_piece = self.board.get_piece(rook_coord)
        
        # Calculate rook destination (one square toward center from king's destination)
        rook_dest = (king_to[X] - direction, king_to[Y], king_to[Z])
        
        # Record history (before has_moved changes, so undo can restore it)
        self.add_to_move_history(king_from, king_to, moving_piece=king_piece, special_move="castling")
        self.add_to_undo_stack(king_from, king_to, king_piece, rook=rook_piece, rook_from=rook_coord,
                               rook_to=rook_dest, special_move="castling")
        
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
        
        self.halfmove_clock += 1
    
    def do_en_passant(self, from_coord, to_coord):
        player_pawn = self.board.get_piece(from_coord)
        
        opponent_pawn_coord = self.get_en_passant_target()[1]
        opponent_pawn = self.board.get_piece(opponent_pawn_coord)
        
        self.add_to_move_history(from_coord, to_coord, moving_piece=player_pawn, captured_piece=opponent_pawn, special_move="en_passant")
        self.add_to_undo_stack(from_coord, to_coord, player_pawn, captured_piece=opponent_pawn,
                               captured_coord=opponent_pawn_coord, special_move="en_passant")
        
        self.board.remove_piece(opponent_pawn_coord)
        
        self.board.move_piece(from_coord,to_coord)
        
        player_pawn.has_moved = True
        
        self.halfmove_clock = 0
    
    # ==================== MOVE VALIDATION (MIDDLE LAYER) ====================
    
    def is_path_clear(self, from_coord, to_coord):
        """Check that every square strictly between two coords on a straight line is empty"""
        dx = (to_coord[X] - from_coord[X])
        dy = (to_coord[Y] - from_coord[Y])
        dz = (to_coord[Z] - from_coord[Z])
        
        # Inline sign function
        sign = lambda x: 1 if x > 0 else (-1 if x < 0 else 0)
        
        dir_vector = (sign(dx), sign(dy), sign(dz))
        distance = max(abs(dx), abs(dy), abs(dz))
        
        # Walk intermediate squares and check for blocking pieces (or rocks)
        current = from_coord
        for step in range(1, distance):
            current = GameState.coord_sum(current, dir_vector)
            if self.board.get_piece(current) is not None:
                return False  # path blocked
        
        return True  # path is clear
    
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
        return self.is_path_clear(from_coord, to_coord)
    
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
        
        # Sandbox positions may have no king at all
        if king_pos is None:
            return False
        
        # Get all opponent pieces
        opponent_color = black if color == white else white
        opponent_pieces = self.get_all_pieces_of_color(opponent_color)
        
        # Check if any opponent can attack the king
        for opponent_coord, opponent_piece in opponent_pieces:
            if self.can_piece_attack_square(opponent_piece, opponent_coord, king_pos):
                return True  # King is under attack!
        
        return False  # King is safe
    
    
    def simulate_move(self, piece, from_coord, to_coord, also_remove=None):
        """Simulate a move and check if it leaves king safe.
        also_remove: coord of a pawn captured en passant (it is not on to_coord)"""
        # Save state
        captured_piece = self.board.get_piece(to_coord)
        saved_white_king = self.white_king_pos
        saved_black_king = self.black_king_pos
        removed_piece = None
        if also_remove is not None:
            removed_piece = self.board.get_piece(also_remove)
            self.board.remove_piece(also_remove)
        
        # Execute
        self._execute_move(from_coord, to_coord)
        
        # Check if king is safe
        is_safe = not self.is_in_check(piece.color)
        
        # Restore state
        self.board.move_piece(to_coord, from_coord)
        if captured_piece is not None:
            self.board.set_piece(captured_piece, to_coord)
        if removed_piece is not None:
            self.board.set_piece(removed_piece, also_remove)
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
            possible_moves, possible_captures = piece.get_possible_moves(from_coord)
            
            # Process Pawn moves: must be empty squares
            for possible_move in possible_moves:
                if self.board.get_piece(possible_move) is not None:
                    continue  # Skip, not empty
                
                if not self.is_path_clear(from_coord, possible_move):
                    continue  # Skip, double-step can't jump over a piece or rock
                
                if self.simulate_move(piece, from_coord, possible_move):
                    legal_moves.append(possible_move)
            
            # Process Pawn captures: must be enemy pieces
            for possible_capture in possible_captures:
                destination_piece = self.board.get_piece(possible_capture)
                
                if destination_piece is None or isinstance(destination_piece, Rock):
                    continue  # Skip, empty square or rock
                if destination_piece.color == piece.color:
                    continue  # Skip, own piece
                
                if self.simulate_move(piece, from_coord, possible_capture):
                    legal_moves.append(possible_capture)
        
        # Non-Pawn pieces
        else:
            possible_moves = piece.get_possible_moves(from_coord)
            can_jump = isinstance(piece, (Knight, King))  # King only moves 1 step
            
            for possible_move in possible_moves:
                destination_piece = self.board.get_piece(possible_move)
                
                # Skip if rock (rocks can't be captured)
                if isinstance(destination_piece, Rock):
                    continue
                
                # Skip if own piece
                if destination_piece is not None and destination_piece.color == piece.color:
                    continue
                
                # Skip if a piece or rock is in the way
                if not can_jump and not self.is_path_clear(from_coord, possible_move):
                    continue
                
                if self.simulate_move(piece, from_coord, possible_move):
                    legal_moves.append(possible_move)
        
        # Add castling destinations if piece is King
        if isinstance(piece, King):
            castling_dests = self.is_castle_available(piece.color)
            legal_moves.extend(castling_dests)
        
        # Add en passant destination if piece is Pawn
        if isinstance(piece, Pawn):
            legal_moves.extend(self.get_en_passant_moves(from_coord))
        
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
        
        # Check if its actually the pawn that just reached the promotion line
        pawn = self.board.get_piece(coord)
        if coord != self.pending_promotion or not self.is_pawn_promotion(coord):
            raise ValueError("No pawn waiting for promotion at this coordinate!")
        if new_piece.color != pawn.color:
            raise ValueError("New Piece must be the same color as the pawn!")
        
        self.board.remove_piece(coord)
        self.board.set_piece(new_piece, coord)
        if isinstance(new_piece, Rook):
            new_piece.has_moved = True  # A promoted rook can never castle
        
        self.add_to_move_history(coord, coord, moving_piece=pawn, promotion_piece=new_piece, special_move="promotion")
        self.add_to_undo_stack(coord, coord, pawn, special_move="promotion")
        
        # The promotion completes the turn
        self.pending_promotion = None
        self.end_turn()
        return True
        
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
        
        if king_coord is None:
            return []
        
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
    
    def get_en_passant_target(self):
        """If the last move was a pawn double-step, return (skipped_square, pawn_coord), else None"""
        if len(self.move_history) == 0:
            return None
        
        last_move = self.move_history[-1]
        from_coord = last_move['from']
        to_coord = last_move['to']
        
        if last_move['special_move'] is not None:
            return None
        if not last_move['moving_piece'].startswith("Pawn("):
            return None
        if abs(to_coord[Y] - from_coord[Y]) != 2:
            return None
        
        # The square the pawn skipped over (halfway, also in Z for a climbing double-step)
        skipped = ((from_coord[X] + to_coord[X]) // 2,
                   (from_coord[Y] + to_coord[Y]) // 2,
                   (from_coord[Z] + to_coord[Z]) // 2)
        return skipped, to_coord
    
    def get_en_passant_moves(self, pawn_coord):
        """Get the en passant destination (if any) for the pawn at pawn_coord"""
        target = self.get_en_passant_target()
        if target is None:
            return []
        skipped, enemy_pawn_coord = target
        
        pawn = self.board.get_piece(pawn_coord)
        enemy_pawn = self.board.get_piece(enemy_pawn_coord)
        if enemy_pawn is None or enemy_pawn.color == pawn.color:
            return []
        
        # Our pawn must be able to capture onto the skipped square
        if skipped not in pawn.get_possible_moves(pawn_coord)[1]:
            return []
        
        # Capturing must not leave our own king in check
        if not self.simulate_move(pawn, pawn_coord, skipped, also_remove=enemy_pawn_coord):
            return []
        
        return [skipped]
    
    def undo_move(self):
        """Undo the last move"""
        if len(self._undo_stack) == 0:
            return False  # Nothing to undo
        
        self.move_history.pop()
        record = self._undo_stack.pop()
        from_coord = record['from']
        to_coord = record['to']
        piece = record['piece']
        
        # Handle promotion: put the pawn back, then also undo the pawn move (same turn)
        if record['special_move'] == "promotion":
            self.board.remove_piece(to_coord)
            self.board.set_piece(piece, to_coord)
            self._position_keys.pop()
            self.switch_turn()
            self.pending_promotion = to_coord
            return self.undo_move()
        
        # Move piece back
        self.board.move_piece(to_coord, from_coord)
        
        # Restore captured piece if any (for en passant it is not on to_coord)
        if record['captured_piece'] is not None:
            self.board.set_piece(record['captured_piece'], record['captured_coord'])
            if isinstance(record['captured_piece'], King):
                if record['captured_piece'].color == white:
                    self.white_king_pos = record['captured_coord']
                else:
                    self.black_king_pos = record['captured_coord']
        
        # Castling: move the rook back too (it had never moved before castling)
        if record['rook'] is not None:
            self.board.move_piece(record['rook_to'], record['rook_from'])
            record['rook'].has_moved = False
        
        # Restore has_moved
        if record['had_moved'] is not None:
            piece.has_moved = record['had_moved']
        
        # Restore king position if King moved
        if isinstance(piece, King):
            if piece.color == white:
                self.white_king_pos = from_coord
            else:
                self.black_king_pos = from_coord
        
        self.halfmove_clock = record['halfmove_clock']
        
        # Switch turn back (a pawn waiting for promotion never passed the turn)
        if self.pending_promotion is not None:
            self.pending_promotion = None
        else:
            self._position_keys.pop()
            self.switch_turn()
        return True
    
    
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
            
            # King + only bishops, all on same color squares (can't mate)
            if material['Bishop'] == total_pieces:
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
    
    
    # ==================== DRAW RULES ====================
    
    def _castling_rights(self):
        """Coords of the rooks that could still castle one day (unmoved, next to an unmoved king)"""
        rights = []
        for color, king_coord in ((white, self.white_king_pos), (black, self.black_king_pos)):
            if king_coord is None or self.board.get_piece(king_coord).has_moved:
                continue
            for rook_coord, rook in self.find_piece_by_type(Rook, color):
                if not rook.has_moved and rook_coord[Y] == king_coord[Y] and rook_coord[Z] == king_coord[Z]:
                    rights.append(rook_coord)
        return frozenset(rights)
    
    def _en_passant_rights(self):
        """The en passant captures the player to move could make right now"""
        if self.get_en_passant_target() is None:
            return frozenset()
        return frozenset((pawn_coord, move)
                         for pawn_coord, pawn in self.find_piece_by_type(Pawn, self.current_player)
                         for move in self.get_en_passant_moves(pawn_coord))
    
    def _position_key(self):
        """Two positions are 'the same' for threefold repetition when their keys are equal:
        same pieces on the same squares, same player to move, same castling and en passant options"""
        pieces = frozenset((coord, str(piece)) for coord, piece in self.board.board.items()
                           if not isinstance(piece, Rock))
        return (pieces, self.current_player, self._castling_rights(), self._en_passant_rights())
    
    def is_threefold_repetition(self):
        """Check if the current position has now occurred three times"""
        return self._position_keys.count(self._position_keys[-1]) >= 3
    
    def is_move_limit_reached(self):
        """Check if both players made move_limit moves in a row with no capture and no pawn move"""
        return self.halfmove_clock >= 2 * self.move_limit
    
    def get_draw_reason(self):
        """Why the game is a draw: "stalemate", "repetition", "move_limit",
        "insufficient_material", or None if it is not a draw"""
        # A checkmate delivered on the very move that would trigger a draw still wins
        if self.is_checkmate(self.current_player):
            return None
        if self.is_stalemate(self.current_player):
            return "stalemate"
        if self.is_threefold_repetition():
            return "repetition"
        if self.is_move_limit_reached():
            return "move_limit"
        if self.is_insufficient_material():
            return "insufficient_material"
        return None
    
    def is_draw(self):
        """Check if the game is a draw (see get_draw_reason)"""
        return self.get_draw_reason() is not None
