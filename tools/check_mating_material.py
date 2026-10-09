"""
Which single pieces can checkmate a bare king?

Looks at every position where a king plus one other piece gives check to a lone king,
and counts the checkmates. Zero means that piece is "insufficient material": see
GameState.has_insufficient_material, which relies on these results.

    venv/bin/python tools/check_mating_material.py            # full board with rocks
    venv/bin/python tools/check_mating_material.py 5 -1 1     # size, lowest layer, highest layer
"""
import multiprocessing
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.game_state import GameState
from engine.pieces import King, Queen, Rook, Bishop, Knight, Rock

PIECES = {"Knight": Knight, "Bishop": Bishop, "Rook": Rook, "Queen": Queen}


def empty_game(size, z_min, z_max, rocks):
    game = GameState(size=size, z_min=z_min, z_max=z_max)
    game.board.board = {coord: piece for coord, piece in game.board.board.items()
                        if rocks and isinstance(piece, Rock)}
    return game


def free_squares(game):
    size, z_min, z_max = game.board.bounds
    return [(x, y, z) for x in range(size) for y in range(size) for z in range(z_min, z_max + 1)
            if game.board.get_piece((x, y, z)) is None]


def count_mates(job):
    """All checkmates of a black king on one square by a white king and one white piece"""
    name, black_king, size, z_min, z_max, rocks = job
    game = empty_game(size, z_min, z_max, rocks)
    squares = free_squares(game)
    game.board.set_piece(King("black"), black_king)
    game.current_player = "black"
    game.black_king_pos = black_king

    # A white king further than two steps away guards none of the black king's exits,
    # which is the same as having no white king at all (None)
    x, y, z = black_king
    close = [c for c in squares if c != black_king and
             abs(c[0] - x) <= 2 and abs(c[1] - y) <= 2 and abs(c[2] - z) <= 2]

    examined, mates = 0, []
    for coord in squares:
        if coord == black_king:
            continue
        piece = PIECES[name]("white")
        game.board.set_piece(piece, coord)
        game.white_king_pos = None
        if game.can_piece_attack_square(piece, coord, black_king):
            for white_king in [None] + close:
                if white_king == coord:
                    continue
                if white_king is not None:
                    game.board.set_piece(King("white"), white_king)
                game.white_king_pos = white_king
                if not game.is_in_check("white"):  # the kings may not stand next to each other
                    examined += 1
                    if game.is_checkmate("black"):
                        mates.append((black_king, coord, white_king))
                if white_king is not None:
                    game.board.remove_piece(white_king)
        game.board.remove_piece(coord)
    return name, examined, mates


def search(size=8, z_min=-2, z_max=2, rocks=True):
    """{piece name: (positions examined, list of (black king, piece, white king) checkmates)}"""
    squares = free_squares(empty_game(size, z_min, z_max, rocks))
    jobs = [(name, square, size, z_min, z_max, rocks) for name in PIECES for square in squares]
    results = {name: [0, []] for name in PIECES}
    with multiprocessing.Pool() as pool:
        for name, examined, mates in pool.imap_unordered(count_mates, jobs, chunksize=8):
            results[name][0] += examined
            results[name][1] += mates
    return results


def bishops_on_one_color_can_mate(size=8, z_min=-2, z_max=2, rocks=True):
    """Could any number of bishops tied to one square color mate a bare king?
    A bishop never attacks a square of the other color, and the king's sideways and up/down
    neighbours are all of the other color. So each of those would have to be off the board,
    a rock, or guarded by the attacking king. Returns the (black king, white king) placements
    where that holds; none means such bishops can never mate."""
    game = empty_game(size, z_min, z_max, rocks)
    squares = free_squares(game)
    free = set(squares)
    king = King("white")
    reach = {square: set(king.get_possible_moves(square, game.board.bounds)) for square in squares}
    placements = []
    for black_king in squares:
        other_color = [n for n in reach[black_king] if n in free and (sum(n) - sum(black_king)) % 2 == 1]
        for white_king in squares:
            if white_king == black_king or white_king in reach[black_king]:
                continue  # the kings may not stand next to each other
            if all(n in reach[white_king] for n in other_color):
                placements.append((black_king, white_king))
    return placements


def main():
    size, z_min, z_max = (int(arg) for arg in sys.argv[1:4]) if len(sys.argv) >= 4 else (8, -2, 2)
    standard = (size, z_min, z_max) == (8, -2, 2)
    for rocks in ([True, False] if standard else [False]):
        print(f"Board {size}x{size}, layers {z_min} to {z_max}, {'with' if rocks else 'no'} rocks")
        for name, (examined, mates) in search(size, z_min, z_max, rocks).items():
            example = f", e.g. black king, {name.lower()}, white king = {mates[0]}" if mates else ""
            print(f"  King + {name:<6}: {len(mates):>5} checkmates in {examined} checking positions{example}")
        boxed = bishops_on_one_color_can_mate(size, z_min, z_max, rocks)
        print(f"  King + bishops on one square color: {'cannot mate' if not boxed else f'might mate, e.g. kings on {boxed[0]}'}")


if __name__ == "__main__":
    main()
