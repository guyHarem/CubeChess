"""
Scoring a position for the computer player, in hundredths of a pawn.

The cheap part (material plus a value for where each piece stands) is kept up to date by
FastBoard on every move, so reading it costs nothing.

The piece values are first guesses for CubeChess, set from how many squares each piece
reaches on an empty board compared with ordinary chess (knight x2.7, bishop x2.4, rook x1.3,
queen x1.7). They are meant to be retuned by self-play.
"""
from ai.tables import PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING, BLACK

VALUES = {PAWN: 100, KNIGHT: 480, BISHOP: 500, ROOK: 540, QUEEN: 1150, KING: 0}

# Hundredths of a pawn for each extra square the piece could reach from where it stands
MOBILITY_WEIGHT = {KNIGHT: 2.0, BISHOP: 1.5, ROOK: 1.0, QUEEN: 0.5}

MATE = 100_000       # scores at or beyond MATE - 1000 mean a forced mate
DRAW = 0


def build_piece_square_values(tables):
    """pst[piece code][square]: what the piece is worth on that square. White's values are
    positive and Black's negative, so the sum over the board is White's lead."""
    size, n = tables.size, tables.n
    white = [[0] * n for _ in range(8)]

    for piece, weight in MOBILITY_WEIGHT.items():
        if piece == KNIGHT:
            reach = [len(tables.knight[square]) for square in range(n)]
        else:
            reach = [sum(len(line) for line in tables.slides[piece][square]) for square in range(n)]
        average = sum(reach) / n
        for square in range(n):
            white[piece][square] = VALUES[piece] + round(weight * (reach[square] - average))

    middle = (size - 1) / 2
    for square, (x, y, z) in enumerate(tables.coords):
        # Pawns: worth more the further they have advanced, and a little more on central files
        advanced = max(0, y - 1)
        white[PAWN][square] = VALUES[PAWN] + 4 * advanced + advanced * advanced + round(2 * (middle - abs(x - middle)))
        # King: safest on its own back ranks while the board is full
        white[KING][square] = -12 * min(y, 4)

    pst = [[0] * n for _ in range(16)]
    for piece in (PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING):
        for square, (x, y, z) in enumerate(tables.coords):
            pst[piece][square] = white[piece][square]
            # Black sees the board from the other end
            pst[piece | BLACK][square] = -white[piece][tables.index[(x, size - 1 - y, z)]]
    return pst


def evaluate(board):
    """The position's score for the player to move"""
    if board.insufficient(0) and board.insufficient(1):
        return DRAW
    return board.score if board.side == 0 else -board.score
