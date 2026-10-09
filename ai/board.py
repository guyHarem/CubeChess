"""
FastBoard: a compact copy of a position that the computer player can search quickly.

It follows exactly the same rules as engine/game_state.py (tests/test_fast_board.py compares
the two move for move), but stores the board as a flat list of small numbers and makes and
takes back moves in place, which is about a thousand times faster.

A cell holds 0 (empty), ROCK, or piece type | colour bit | UNMOVED bit.
A move is one integer: from | to << 9 | promotion piece << 18 | kind << 21.
"""
from ai.evaluate import build_piece_square_values
from ai.tables import (tables_for, PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING, ROCK,
                       WHITE, BLACK, UNMOVED)

SQUARE = 511                 # mask for a square number inside a move
NORMAL, DOUBLE, EN_PASSANT, CASTLE = 0, 1 << 21, 2 << 21, 3 << 21
KIND = 3 << 21
PROMOTIONS = (QUEEN, ROOK, BISHOP, KNIGHT)

TYPE_OF = {"Pawn": PAWN, "Knight": KNIGHT, "Bishop": BISHOP, "Rook": ROOK, "Queen": QUEEN, "King": KING}
NAME_OF = {value: name for name, value in TYPE_OF.items()}

# ENEMY[colour index][cell]: can the player of that colour capture what stands in the cell?
ENEMY = (tuple(1 <= (code & 7) <= 6 and bool(code & BLACK) for code in range(32)),
         tuple(1 <= (code & 7) <= 6 and not code & BLACK for code in range(32)))


def move_from(move):
    return move & SQUARE


def move_to(move):
    return (move >> 9) & SQUARE


def move_promotion(move):
    return (move >> 18) & 7


class FastBoard:
    def __init__(self, size=8, z_min=-2, z_max=2):
        self.t = tables = tables_for(size, z_min, z_max)
        if tables.pst is None:
            tables.pst = build_piece_square_values(tables)
        self.cells = [0] * tables.n
        self.side = WHITE                  # WHITE (0) or BLACK (8) to move
        self.squares = (set(), set())      # where each colour's pieces stand
        self.kings = [-1, -1]              # king squares, -1 when a practice position has no king
        self.counts = [0] * 16             # how many of each piece are on the board
        self.ep = -1                       # square a pawn may capture onto en passant, or -1
        self.ep_pawn = -1                  # the pawn that capture would remove
        self.half = 0                      # single moves since the last capture or pawn move
        self.move_limit = 50               # draw after this many quiet moves by each player
        self.score = 0                     # material and placement, White minus Black
        self.pieces_key = 0                # fingerprint of the pieces alone
        self.rights_key = 0                # ... of the castling options still open
        self.key = 0                       # ... of the whole position (see _full_key)
        self.history = []                  # keys of every earlier position, oldest first
        self._undo = []

    # ==================== BUILDING A POSITION ====================

    @classmethod
    def from_game_state(cls, game):
        """Copy a live game (which must not be waiting for a promotion choice)"""
        if game.pending_promotion is not None:
            raise ValueError("Promote the pawn before asking the computer to think")
        board = cls(*game.board.bounds)
        index = board.t.index
        for coord, piece in game.board.board.items():
            name = type(piece).__name__
            if name == "Rock":
                board.cells[index[coord]] = ROCK
                continue
            unmoved = UNMOVED if getattr(piece, "has_moved", True) is False else 0
            board.put(index[coord], TYPE_OF[name] | (BLACK if piece.color == "black" else WHITE) | unmoved)
        board.side = BLACK if game.current_player == "black" else WHITE
        target = game.get_en_passant_target()
        if target is not None:
            board.ep, board.ep_pawn = index[target[0]], index[target[1]]
        board.half = game.halfmove_clock
        board.move_limit = game.move_limit
        board.rights_key = board._castling_key()
        board.key = board._full_key(board._en_passant_key())
        # Earlier positions matter for the repetition rule
        board.history = [board.key_of_engine_position(key) for key in game._position_keys[:-1]]
        return board

    def put(self, square, code):
        """Place a piece on an empty square (setting up only)"""
        self.cells[square] = code
        base = code & 15
        colour = (code & BLACK) >> 3
        self.squares[colour].add(square)
        self.counts[base] += 1
        self.score += self.t.pst[base][square]
        self.pieces_key ^= self.t.z_piece[base][square]
        if code & 7 == KING:
            self.kings[colour] = square

    # ==================== FINGERPRINTS ====================
    # Two positions get the same key exactly when the engine's repetition rule calls them the
    # same: same pieces, same player to move, same castling options, same en passant options.

    def _castling_key(self):
        key = 0
        cells, tables = self.cells, self.t
        for colour in (WHITE, BLACK):
            king = self.kings[colour >> 3]
            if king < 0 or not cells[king] & UNMOVED:
                continue
            rook = ROOK | colour | UNMOVED
            for line in tables.row[king]:
                for square in line:
                    if cells[square] == rook:
                        key ^= tables.z_castle[square]
        return key

    def _en_passant_key(self):
        """Counts only when the player to move really has a legal en passant capture"""
        if self.ep < 0:
            return 0
        colour = self.side
        pawn = PAWN | colour
        for square in self.t.pawn_attackers[colour >> 3][self.ep]:
            if self.cells[square] & 15 == pawn and self._safe(square | self.ep << 9 | EN_PASSANT):
                return self.t.z_en_passant[self.ep]
        return 0

    def _full_key(self, en_passant_key):
        key = self.pieces_key ^ self.rights_key ^ en_passant_key
        return key ^ self.t.z_black_to_move if self.side else key

    def key_of_engine_position(self, position_key):
        """The same fingerprint, worked out from one of GameState's remembered positions"""
        pieces, player, castling, en_passant = position_key
        tables = self.t
        key = 0
        for coord, text in pieces:
            name, colour = text[:-1].split("(")
            key ^= tables.z_piece[TYPE_OF[name] | (BLACK if colour == "black" else WHITE)][tables.index[coord]]
        for coord in castling:
            key ^= tables.z_castle[tables.index[coord]]
        for _, target in en_passant:
            key ^= tables.z_en_passant[tables.index[target]]
            break  # every capture lands on the same square
        return key ^ tables.z_black_to_move if player == "black" else key

    # ==================== ATTACKS ====================

    def attacked(self, square, by):
        """Is the square attacked by a piece of colour `by` (WHITE or BLACK)?"""
        cells, tables = self.cells, self.t
        knight = KNIGHT | by
        for origin in tables.knight[square]:
            if cells[origin] == knight:
                return True
        king = KING | by
        for origin in tables.king[square]:
            if cells[origin] & 15 == king:
                return True
        pawn = PAWN | by
        for origin in tables.pawn_attackers[by >> 3][square]:
            if cells[origin] & 15 == pawn:
                return True
        rook, bishop, queen = ROOK | by, BISHOP | by, QUEEN | by
        for line in tables.slides[ROOK][square]:
            for origin in line:
                piece = cells[origin]
                if piece:
                    piece &= 15
                    if piece == rook or piece == queen:
                        return True
                    break
        for line in tables.slides[BISHOP][square]:
            for origin in line:
                piece = cells[origin]
                if piece:
                    piece &= 15
                    if piece == bishop or piece == queen:
                        return True
                    break
        return False

    def _attacked_along(self, line, straight, by):
        """Is the first piece on this line (which starts beside a king) an enemy slider facing it?"""
        cells = self.cells
        for square in line:
            piece = cells[square]
            if piece:
                piece &= 15
                return piece == (QUEEN | by) or piece == ((ROOK if straight else BISHOP) | by)
        return False

    def exposes_king(self, move, was_in_check):
        """Call right after make(move): did the mover leave their own king attacked?
        Quick when the mover was not in check: only a king move, an en passant capture or a
        piece leaving a line it shared with the king can do that."""
        opponent = self.side
        king = self.kings[(opponent ^ BLACK) >> 3]
        if king < 0:
            return False
        if was_in_check or (move >> 9) & SQUARE == king or move & KIND == EN_PASSANT:
            return self.attacked(king, opponent)
        entry = self.t.line_to[king].get(move & SQUARE)
        return entry is not None and self._attacked_along(entry[1], entry[0], opponent)

    def gives_check(self, move):
        """Call right after make(move), once the move is known to be legal: is the player now
        to move in check? Looks only at the moved piece and at the line it uncovered."""
        side = self.side
        king = self.kings[side >> 3]
        if king < 0:
            return False
        by = side ^ BLACK
        if move & KIND >= EN_PASSANT:  # en passant and castling move a second piece too
            return self.attacked(king, by)
        tables = self.t
        target = (move >> 9) & SQUARE
        lines = tables.line_to[king]
        piece = self.cells[target] & 7
        if piece == KNIGHT:
            if target in tables.knight_set[king]:
                return True
        elif piece == PAWN:
            if target in tables.pawn_attacker_set[by >> 3][king]:
                return True
        elif piece != KING:
            entry = lines.get(target)
            if entry is not None and (piece == QUEEN or (piece == ROOK) == entry[0]):
                for square in entry[1]:
                    if self.cells[square]:
                        if square == target:
                            return True
                        break
        entry = lines.get(move & SQUARE)
        return entry is not None and self._attacked_along(entry[1], entry[0], by)

    def in_check(self, colour=None):
        """Is that colour's king attacked? (The player to move, unless a colour is given)"""
        if colour is None:
            colour = self.side
        king = self.kings[colour >> 3]
        return king >= 0 and self.attacked(king, colour ^ BLACK)

    # ==================== MOVE GENERATION ====================

    def pseudo_moves(self):
        """Every move of the player to move that obeys how the pieces move. Some may leave
        the mover's own king attacked; legal_moves() removes those."""
        cells, tables = self.cells, self.t
        side = self.side
        colour = side >> 3
        enemy = ENEMY[colour]
        slides = tables.slides
        moves = []
        add = moves.append
        for origin in self.squares[colour]:
            piece = cells[origin]
            kind = piece & 7
            if kind == PAWN:
                promotes = tables.promotes[colour]
                for target in tables.pawn_steps[colour][origin]:
                    if cells[target] == 0:
                        if promotes[target]:
                            for choice in PROMOTIONS:
                                add(origin | target << 9 | choice << 18)
                        else:
                            add(origin | target << 9)
                if piece & UNMOVED:
                    for target, middle in tables.pawn_doubles[colour][origin]:
                        if cells[target] == 0 and cells[middle] == 0:
                            if promotes[target]:  # only on very small boards
                                for choice in PROMOTIONS:
                                    add(origin | target << 9 | choice << 18)
                            else:
                                add(origin | target << 9 | DOUBLE)
                for target in tables.pawn_captures[colour][origin]:
                    if enemy[cells[target]]:
                        if promotes[target]:
                            for choice in PROMOTIONS:
                                add(origin | target << 9 | choice << 18)
                        else:
                            add(origin | target << 9)
                    elif target == self.ep:
                        add(origin | target << 9 | EN_PASSANT)
            elif kind == KNIGHT:
                for target in tables.knight[origin]:
                    occupant = cells[target]
                    if occupant == 0 or enemy[occupant]:
                        add(origin | target << 9)
            elif kind == KING:
                for target in tables.king[origin]:
                    occupant = cells[target]
                    if occupant == 0 or enemy[occupant]:
                        add(origin | target << 9)
                if piece & UNMOVED:
                    self._add_castling(origin, side, add)
            else:
                for line in slides[kind][origin]:
                    for target in line:
                        occupant = cells[target]
                        if occupant == 0:
                            add(origin | target << 9)
                        else:
                            if enemy[occupant]:
                                add(origin | target << 9)
                            break
        return moves

    def _add_castling(self, king, side, add):
        """The king steps two squares towards an unmoved rook on its rank: nothing between
        them, the king not in check, and the two squares it crosses not attacked"""
        cells = self.cells
        rook = ROOK | side | UNMOVED
        opponent = side ^ BLACK
        in_check = None
        for line in self.t.row[king]:
            for distance, square in enumerate(line):
                if cells[square]:
                    if cells[square] == rook and distance >= 2:
                        if in_check is None:
                            in_check = self.attacked(king, opponent)
                        if not in_check and not self.attacked(line[0], opponent) and not self.attacked(line[1], opponent):
                            add(king | line[1] << 9 | CASTLE)
                    break

    def captures(self):
        """Pseudo-legal captures and promotions only (for the search at the end of a line)"""
        cells, tables = self.cells, self.t
        colour = self.side >> 3
        enemy = ENEMY[colour]
        slides = tables.slides
        moves = []
        add = moves.append
        for origin in self.squares[colour]:
            kind = cells[origin] & 7
            if kind == PAWN:
                promotes = tables.promotes[colour]
                for target in tables.pawn_captures[colour][origin]:
                    if enemy[cells[target]]:
                        if promotes[target]:
                            add(origin | target << 9 | QUEEN << 18)
                        else:
                            add(origin | target << 9)
                    elif target == self.ep:
                        add(origin | target << 9 | EN_PASSANT)
                for target in tables.pawn_steps[colour][origin]:
                    if promotes[target] and cells[target] == 0:
                        add(origin | target << 9 | QUEEN << 18)
            elif kind == KNIGHT:
                for target in tables.knight[origin]:
                    if enemy[cells[target]]:
                        add(origin | target << 9)
            elif kind == KING:
                for target in tables.king[origin]:
                    if enemy[cells[target]]:
                        add(origin | target << 9)
            else:
                for line in slides[kind][origin]:
                    for target in line:
                        occupant = cells[target]
                        if occupant:
                            if enemy[occupant]:
                                add(origin | target << 9)
                            break
        return moves

    def needs_check_test(self, in_check):
        """Returns a test: does this pseudo-legal move need its king safety checked? When the
        mover is not in check, only king moves, en passant and pieces standing in line with
        the king can expose it."""
        king = self.kings[self.side >> 3]
        if king < 0:
            return lambda move: False
        if in_check:
            return lambda move: True
        aligned = self.t.aligned[king]
        return lambda move: (move & SQUARE) == king or (move & SQUARE) in aligned or (move & KIND) == EN_PASSANT

    def _safe(self, move):
        """Play the move and see whether the mover's king is left alone"""
        colour = self.side
        self.make(move, track=False)
        king = self.kings[colour >> 3]
        safe = king < 0 or not self.attacked(king, colour ^ BLACK)
        self.unmake()
        return safe

    def legal_moves(self):
        moves = self.pseudo_moves()
        if self.kings[self.side >> 3] < 0:
            return moves
        risky = self.needs_check_test(self.in_check())
        return [move for move in moves if not risky(move) or self._safe(move)]

    # ==================== MAKING AND TAKING BACK MOVES ====================

    def make(self, move, track=True):
        """Play a pseudo-legal move. track=False skips the fingerprint and en passant
        bookkeeping (enough for a quick king-safety test that is taken straight back)."""
        cells, tables = self.cells, self.t
        origin = move & SQUARE
        target = (move >> 9) & SQUARE
        kind = move & KIND
        side = self.side
        colour = side >> 3
        piece = cells[origin]
        placed = piece & 15
        if kind == EN_PASSANT:
            taken_on = self.ep_pawn
        else:
            taken_on = target
        taken = cells[taken_on]
        rook_from = -1

        self._undo.append((move, piece, taken, taken_on, self.ep, self.ep_pawn, self.half,
                           self.score, self.pieces_key, self.rights_key, self.key))
        self.history.append(self.key)

        pst, z = tables.pst, tables.z_piece
        score = self.score - pst[placed][origin]
        pieces_key = self.pieces_key ^ z[placed][origin]
        promotion = (move >> 18) & 7
        if promotion:
            self.counts[placed] -= 1
            placed = promotion | side
            self.counts[placed] += 1
        score += pst[placed][target]
        pieces_key ^= z[placed][target]

        if taken:
            base = taken & 15
            score -= pst[base][taken_on]
            pieces_key ^= z[base][taken_on]
            self.squares[colour ^ 1].remove(taken_on)
            self.counts[base] -= 1
            cells[taken_on] = 0
            if base & 7 == KING:
                self.kings[colour ^ 1] = -1

        cells[origin] = 0
        cells[target] = placed
        mine = self.squares[colour]
        mine.remove(origin)
        mine.add(target)

        if placed & 7 == KING:
            self.kings[colour] = target
            if kind == CASTLE:
                step = 1 if target > origin else -1
                rook_to = target - step
                rook_from = target + step
                while not cells[rook_from]:
                    rook_from += step
                rook = ROOK | side
                cells[rook_from] = 0
                cells[rook_to] = rook
                mine.remove(rook_from)
                mine.add(rook_to)
                score += pst[rook][rook_to] - pst[rook][rook_from]
                pieces_key ^= z[rook][rook_from] ^ z[rook][rook_to]
                self._undo[-1] += (rook_from,)

        self.score = score
        self.pieces_key = pieces_key
        self.half = 0 if (piece & 7 == PAWN or taken) else self.half + 1
        self.ep = self.ep_pawn = -1
        if kind == DOUBLE:
            self.ep = (origin + target) >> 1
            self.ep_pawn = target
        self.side = side ^ BLACK

        if track:
            # Castling options only change when an unmoved king or rook moves or is taken
            if (piece & UNMOVED and piece & 7 in (KING, ROOK)) or (taken & UNMOVED and taken & 7 in (KING, ROOK)):
                self.rights_key = self._castling_key()
            self.key = self._full_key(self._en_passant_key() if kind == DOUBLE else 0)

    def unmake(self):
        record = self._undo.pop()
        move, piece, taken, taken_on, self.ep, self.ep_pawn, self.half, self.score, \
            self.pieces_key, self.rights_key, self.key = record[:11]
        self.history.pop()
        cells = self.cells
        origin = move & SQUARE
        target = (move >> 9) & SQUARE
        self.side = side = self.side ^ BLACK
        colour = side >> 3

        placed = cells[target]
        if (move >> 18) & 7:
            self.counts[placed] -= 1
            self.counts[piece & 15] += 1
        cells[target] = 0
        cells[origin] = piece
        mine = self.squares[colour]
        mine.remove(target)
        mine.add(origin)

        if taken:
            cells[taken_on] = taken
            self.squares[colour ^ 1].add(taken_on)
            self.counts[taken & 15] += 1
            if taken & 7 == KING:
                self.kings[colour ^ 1] = taken_on

        if piece & 7 == KING:
            self.kings[colour] = origin
            if len(record) > 11:  # castling: the rook goes home too
                rook_from = record[11]
                rook_to = target - (1 if target > origin else -1)
                cells[rook_to] = 0
                cells[rook_from] = ROOK | side | UNMOVED
                mine.remove(rook_to)
                mine.add(rook_from)

    # ==================== DRAW RULES ====================

    def repetitions(self):
        """How many earlier positions equal the current one"""
        return self.history.count(self.key)

    def insufficient(self, colour):
        """Could this colour (0 white, 1 black) never checkmate a bare king? Same rule as
        GameState.has_insufficient_material."""
        base = colour << 3
        counts = self.counts
        bishops = counts[base | BISHOP]
        total = counts[base | PAWN] + counts[base | KNIGHT] + bishops + counts[base | ROOK] + counts[base | QUEEN]
        if total == 0:
            return True
        if total == 1:
            layered = self.t.z_min != self.t.z_max
            return counts[base | KNIGHT] == 1 or bishops == 1 or (counts[base | ROOK] == 1 and layered)
        if bishops == total:
            bishop = base | BISHOP
            coords = self.t.coords
            shades = {sum(coords[square]) % 2
                      for square in self.squares[colour] if self.cells[square] == bishop}
            return len(shades) == 1
        return False

    # ==================== TALKING TO THE REST OF THE PROGRAM ====================

    def describe(self, move):
        """(from coord, to coord, promotion piece name or None) for the game manager"""
        promotion = (move >> 18) & 7
        return (self.t.coords[move & SQUARE], self.t.coords[(move >> 9) & SQUARE],
                NAME_OF[promotion] if promotion else None)

    def find_move(self, from_coord, to_coord, promotion=None):
        """The legal move matching a human-style description, or None"""
        wanted = (tuple(from_coord), tuple(to_coord), promotion)
        for move in self.legal_moves():
            described = self.describe(move)
            if described == wanted or (promotion is None and described[:2] == wanted[:2]):
                return move
        return None
