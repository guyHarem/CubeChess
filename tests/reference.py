"""
Independent move generator used only by the tests.

It is written straight from the rules (walking rays square by square on a copy
of the board) and shares no logic with engine/game_state.py, so the two can be
compared against each other on thousands of positions.
"""
from itertools import product

ROOK_DIRS = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
# Two axes change by one step each, the third stays put
BISHOP_DIRS = [d for d in product((-1, 0, 1), repeat=3) if sorted(map(abs, d)) == [0, 1, 1]]
KING_DIRS = [d for d in product((-1, 0, 1), repeat=3) if d[2] == 0 and d != (0, 0, 0)] + [(0, 0, 1), (0, 0, -1)]
KNIGHT_JUMPS = [d for d in product((-2, -1, 0, 1, 2), repeat=3) if sorted(map(abs, d)) == [0, 1, 2]]


def name(piece):
    return type(piece).__name__


def inside(c):
    return 0 <= c[0] <= 7 and 0 <= c[1] <= 7 and -2 <= c[2] <= 2


def add(c, d, n=1):
    return (c[0] + d[0] * n, c[1] + d[1] * n, c[2] + d[2] * n)


def forward(color):
    return 1 if color == "white" else -1


def enemy(board, coord, color):
    piece = board.get(coord)
    return piece is not None and name(piece) != "Rock" and piece.color != color


def attacked_squares(board, coord):
    """Squares the piece on coord attacks (occupied or not)"""
    piece = board[coord]
    kind = name(piece)
    out = []
    if kind == "Pawn":
        d = forward(piece.color)
        out = [add(coord, (dx, d, dz)) for dx in (-1, 1) for dz in (-1, 0, 1)]
    elif kind == "Knight":
        out = [add(coord, j) for j in KNIGHT_JUMPS]
    elif kind == "King":
        out = [add(coord, d) for d in KING_DIRS]
    else:
        dirs = {"Rook": ROOK_DIRS, "Bishop": BISHOP_DIRS, "Queen": ROOK_DIRS + BISHOP_DIRS}[kind]
        for d in dirs:
            square = add(coord, d)
            while inside(square):
                out.append(square)
                if square in board:
                    break
                square = add(square, d)
    return [c for c in out if inside(c)]


def is_attacked(board, square, by_color):
    return any(name(p) != "Rock" and p.color == by_color and square in attacked_squares(board, c)
               for c, p in board.items())


def find_king(board, color):
    for c, p in board.items():
        if name(p) == "King" and p.color == color:
            return c
    return None


def in_check(board, color):
    king = find_king(board, color)
    other = "black" if color == "white" else "white"
    return king is not None and is_attacked(board, king, other)


def en_passant_square(history):
    """(skipped square, pawn square) if the last move was a pawn double-step"""
    if not history:
        return None
    last = history[-1]
    if last["special_move"] or not last["moving_piece"].startswith("Pawn"):
        return None
    a, b = last["from"], last["to"]
    if abs(a[1] - b[1]) != 2:
        return None
    return tuple((a[i] + b[i]) // 2 for i in range(3)), tuple(b)


def legal_moves(board, coord, history):
    """All legal destinations for the piece on coord"""
    piece = board[coord]
    kind, color = name(piece), piece.color
    other = "black" if color == "white" else "white"
    candidates = []  # (destination, extra square to empty)

    if kind == "Pawn":
        d = forward(color)
        for dz in (-1, 0, 1):
            one = add(coord, (0, d, dz))
            if inside(one) and one not in board:
                candidates.append((one, None))
                two = add(coord, (0, d, dz), 2)
                if not piece.has_moved and inside(two) and two not in board:
                    candidates.append((two, None))
        for square in attacked_squares(board, coord):
            if enemy(board, square, color):
                candidates.append((square, None))
        ep = en_passant_square(history)
        if ep and ep[0] in attacked_squares(board, coord) and enemy(board, ep[1], color):
            candidates.append((ep[0], ep[1]))
    else:
        for square in attacked_squares(board, coord):
            if square not in board or enemy(board, square, color):
                candidates.append((square, None))

    moves = []
    for dest, also_empty in candidates:
        after = dict(board)
        del after[coord]
        if also_empty:
            del after[also_empty]
        after[dest] = piece
        if not in_check(after, color):
            moves.append(dest)

    if kind == "King" and not piece.has_moved and not in_check(board, color):
        for rook_x, step in ((7, 1), (0, -1)):
            rook = board.get((rook_x, coord[1], coord[2]))
            if rook is None or name(rook) != "Rook" or rook.color != color or rook.has_moved:
                continue
            between = range(coord[0] + step, rook_x, step)
            if any((x, coord[1], coord[2]) in board for x in between):
                continue
            passes = [add(coord, (step, 0, 0)), add(coord, (step, 0, 0), 2)]
            if not any(is_attacked(board, square, other) for square in passes):
                moves.append(passes[1])

    return moves
