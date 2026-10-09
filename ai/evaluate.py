"""
Scoring a position for the computer player, in hundredths of a pawn.

The score is material plus a value for where each piece stands. FastBoard keeps it up to
date on every move, so reading it costs nothing.

Every number that goes into it is a named parameter in DEFAULT_PARAMS. Each piece on each
square has a list of features (how many squares it reaches from there, how far it is from
the Ground, how far a pawn has advanced...), and its value is the sum of feature x parameter.
That makes the numbers tunable: tools/tune.py plays the computer against itself and fits
the parameters to who won.
"""
from ai.tables import PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING, BLACK

# Tuned by self-play (tools/tune.py). The starting guesses came from how many squares each
# piece reaches on an empty board compared with ordinary chess; FIRST_GUESSES keeps them.
DEFAULT_PARAMS = {
    # What a piece is worth (the pawn is the fixed yardstick)
    "pawn": 100, "knight": 447, "bishop": 477, "rook": 476, "queen": 1168,
    # ... plus this much for each square it could reach, above its average. (A rook reaches
    # the same number of squares from everywhere, so it has no such term.)
    "reach_knight": 4.84, "reach_bishop": 0.97, "reach_queen": -0.14,
    # ... plus this much for each layer it stands away from the Ground
    "layer_knight": -5.36, "layer_bishop": -13.45, "layer_rook": -29.0, "layer_queen": 0.24,
    # A pawn that has advanced 1, 2, ... ranks (5 = one step from promotion on the full board)
    "pawn_advance_1": -3.74, "pawn_advance_2": 2.7, "pawn_advance_3": 65, "pawn_advance_4": 158, "pawn_advance_5": 164,
    "pawn_central": 3.34,    # scales the bonus for central pawns stepping forward
    "pawn_layer": 3.62,      # per layer away from the Ground, until the pawn is far advanced
    # King: per rank it has left its back rank (up to 4), and per layer away from the Ground
    "king_rank": -19.0, "king_layer": -9.28,
}
FIRST_GUESSES = {
    "pawn": 100, "knight": 480, "bishop": 500, "rook": 540, "queen": 1150,
    "reach_knight": 2.0, "reach_bishop": 1.5, "reach_queen": 0.5,
    "layer_knight": 0.0, "layer_bishop": 0.0, "layer_rook": 0.0, "layer_queen": 0.0,
    "pawn_advance_1": 2, "pawn_advance_2": 5, "pawn_advance_3": 10, "pawn_advance_4": 22, "pawn_advance_5": 45,
    "pawn_central": 1.0, "pawn_layer": -3.0,
    "king_rank": -12.0, "king_layer": 0.0,
}
FIXED_PARAMS = ("pawn",)     # never tuned: everything else is measured against it
PARAM_NAMES = tuple(DEFAULT_PARAMS)

NAME_OF_PIECE = {PAWN: "pawn", KNIGHT: "knight", BISHOP: "bishop", ROOK: "rook", QUEEN: "queen"}
VALUES = {piece: DEFAULT_PARAMS[name] for piece, name in NAME_OF_PIECE.items()}
VALUES[KING] = 0

MATE = 100_000       # scores at or beyond MATE - 1000 mean a forced mate
DRAW = 0


def piece_features(tables):
    """features[piece][square] = {parameter name: amount} for a WHITE piece on that square.
    Built once per board size."""
    if getattr(tables, "features", None) is not None:
        return tables.features
    size, n = tables.size, tables.n
    features = {piece: [dict() for _ in range(n)] for piece in (PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING)}

    for piece in (KNIGHT, BISHOP, ROOK, QUEEN):
        name = NAME_OF_PIECE[piece]
        if piece == KNIGHT:
            reach = [len(tables.knight[square]) for square in range(n)]
        else:
            reach = [sum(len(line) for line in tables.slides[piece][square]) for square in range(n)]
        average = sum(reach) / n
        for square, (x, y, z) in enumerate(tables.coords):
            entry = {name: 1, f"layer_{name}": abs(z)}
            if piece != ROOK:
                entry[f"reach_{name}"] = reach[square] - average
            features[piece][square] = entry

    middle = (size - 1) / 2
    for square, (x, y, z) in enumerate(tables.coords):
        advanced = max(0, y - 1)
        central = middle - abs(x - middle)
        pawn = {"pawn": 1, "pawn_central": central * (2 + 2 * min(advanced, 3))}
        if advanced:
            pawn[f"pawn_advance_{min(advanced, 5)}"] = 1
        if advanced <= 3:
            pawn["pawn_layer"] = abs(z)
        features[PAWN][square] = pawn
        features[KING][square] = {"king_rank": min(y, 4), "king_layer": abs(z)}

    tables.features = features
    return features


def build_piece_square_values(tables, params=None):
    """pst[piece code][square]: what the piece is worth on that square. White's values are
    positive and Black's negative, so the sum over the board is White's lead."""
    params = params or DEFAULT_PARAMS
    features = piece_features(tables)
    size, n = tables.size, tables.n
    pst = [[0] * n for _ in range(16)]
    for piece, per_square in features.items():
        white = [round(sum(params[name] * amount for name, amount in per_square[square].items()))
                 for square in range(n)]
        for square, (x, y, z) in enumerate(tables.coords):
            pst[piece][square] = white[square]
            # Black sees the board from the other end
            pst[piece | BLACK][square] = -white[tables.index[(x, size - 1 - y, z)]]
    return pst


def position_features(board):
    """{parameter name: White's amount minus Black's} for a whole position. With the
    parameters, this gives board.score (up to rounding); the tuner works on these."""
    tables = board.t
    features = piece_features(tables)
    size = tables.size
    total = dict.fromkeys(PARAM_NAMES, 0.0)
    for colour, sign in ((0, 1), (1, -1)):
        for square in board.squares[colour]:
            piece = board.cells[square] & 7
            if colour:
                x, y, z = tables.coords[square]
                square = tables.index[(x, size - 1 - y, z)]
            for name, amount in features[piece][square].items():
                total[name] += sign * amount
    return total


def evaluate(board):
    """The position's score for the player to move"""
    # Only tiny positions can be dead draws, so the check is skipped for all the others
    if len(board.squares[0]) + len(board.squares[1]) <= 4 and board.insufficient(0) and board.insufficient(1):
        return DRAW
    return board.score if board.side == 0 else -board.score
