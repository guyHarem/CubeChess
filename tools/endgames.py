"""
Can the computer finish off a bare king?

Random positions where one side has a king and a few pieces against a lone king are played
out, the computer on both sides. For each kind of material this reports how often the
stronger side delivered checkmate before a draw rule ended the game, and how long it took.

    venv/bin/python tools/endgames.py                      # the current scoring
    venv/bin/python tools/endgames.py --params first-guesses
    venv/bin/python tools/endgames.py --games 40 --nodes 40000
"""
import argparse
import multiprocessing
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.board import FastBoard
from ai.search import Search
from api.game_manager import GameManager
from engine import pieces
from tools.tune import load_params

MATERIAL = {
    "queen": ["Queen"],
    "queen + rook": ["Queen", "Rook"],
    "queen + bishop": ["Queen", "Bishop"],
    "queen + knight": ["Queen", "Knight"],
    "two rooks": ["Rook", "Rook"],
    "rook + bishop + knight": ["Rook", "Bishop", "Knight"],
    "two queens": ["Queen", "Queen"],
    "three rooks": ["Rook", "Rook", "Rook"],
}
MAX_PLIES = 400


def start_position(rng, material):
    """A random legal position: White has the material and the move, Black a bare king"""
    while True:
        probe = GameManager()
        probe.setup_position([], rocks=True)
        free = [(x, y, z) for x in range(8) for y in range(8) for z in range(-2, 3)
                if probe.game.board.get_piece((x, y, z)) is None]
        rng.shuffle(free)
        placed = [{"coord": free.pop(), "type": "King", "color": "white"},
                  {"coord": free.pop(), "type": "King", "color": "black"}]
        placed += [{"coord": free.pop(), "type": kind, "color": "white"} for kind in material]
        manager = GameManager()
        manager.setup_position(placed, "white", rocks=True)
        game = manager.game
        if not game.is_in_check("black") and not game.is_in_check("white"):
            return manager


def play_out(job):
    name, seed, params, nodes, seconds = job
    rng = random.Random(seed)
    manager = start_position(rng, MATERIAL[name])
    for ply in range(MAX_PLIES):
        color = manager.game.current_player
        board = FastBoard.from_game_state(manager.game, params)
        move = Search(board).run(nodes=nodes, seconds=seconds).move
        from_coord, to_coord, promotion = board.describe(move)
        response = manager.make_move(from_coord, to_coord)
        if response["success"] and response["pending_promotion"] is not None:
            response = manager.promote_pawn(to_coord, getattr(pieces, promotion)(color))
        if not response["success"]:
            raise RuntimeError(response["error"])
        if response["status"] not in ("ongoing", "check"):
            return name, response["status"] == "checkmate", (ply + 2) // 2, response["draw_reason"] or response["status"]
    return name, False, MAX_PLIES // 2, "too long"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--params", default="default")
    parser.add_argument("--games", type=int, default=20, help="positions per kind of material")
    parser.add_argument("--nodes", type=int, default=20000, help="positions searched per move")
    parser.add_argument("--seconds", type=float, default=None, help="think this long per move instead")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--set", action="append", default=[], metavar="NAME=VALUE",
                        help="override one scoring parameter (may be repeated)")
    parser.add_argument("--brief", action="store_true", help="print only the total")
    args = parser.parse_args()
    params = load_params(args.params)
    for item in args.set:
        name, value = item.split("=")
        if name not in params:
            parser.error(f"unknown parameter {name}")
        params[name] = float(value)
    nodes = None if args.seconds else args.nodes
    jobs = [(name, args.seed + i, params, nodes, args.seconds) for name in MATERIAL for i in range(args.games)]
    results = {name: [] for name in MATERIAL}
    started = time.perf_counter()
    # Timed runs leave some cores free so that every game gets a fair share of the clock
    with multiprocessing.Pool(max(1, multiprocessing.cpu_count() - 3) if args.seconds else None) as pool:
        for name, mated, moves, ending in pool.imap_unordered(play_out, jobs):
            results[name].append((mated, moves, ending))
    if args.brief:
        mated = sum(m for games in results.values() for m, _, _ in games)
        print(f"{' '.join(args.set) or 'as is'}: {mated} of {len(jobs)} mated")
        return
    print(f"{'White has king +':24} {'mated':>8} {'average moves to mate':>24}   other endings")
    total = 0
    for name, games in results.items():
        mates = [moves for mated, moves, _ in games if mated]
        others = {}
        for mated, _, ending in games:
            if not mated:
                others[ending] = others.get(ending, 0) + 1
        total += len(mates)
        average = f"{sum(mates) / len(mates):.0f}" if mates else "-"
        print(f"{name:24} {len(mates):>3} of {len(games):<2} {average:>24}   {others or ''}")
    print(f"{total} of {len(jobs)} mated, in {time.perf_counter() - started:.0f}s")


if __name__ == "__main__":
    main()
