"""
Play the computer levels against each other and report who wins.

Used to check that the levels are in the right order (hard beats medium beats easy) and,
later, to tell whether a change to the computer player made it stronger.

    venv/bin/python tools/play_match.py                       # hard v medium and medium v easy, 40 games each
    venv/bin/python tools/play_match.py hard easy --games 20
    venv/bin/python tools/play_match.py --hard-seconds 3      # hard at its full thinking time (slow)
"""
import argparse
import multiprocessing
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.levels import choose_move
from api.game_manager import GameManager
from engine import pieces

MAX_PLIES = 400


def play_game(job):
    """One game. Returns (winner colour or None, single moves played, how it ended, positions searched, seconds thinking)"""
    white, black, seed, hard_seconds = job
    rng = random.Random(seed)
    manager = GameManager()
    levels = {"white": white, "black": black}
    searched = thinking = 0
    for ply in range(MAX_PLIES):
        color = manager.game.current_player
        level = levels[color]
        choice = choose_move(manager.game, level, seconds=hard_seconds if level == "hard" else None, rng=rng)
        searched += choice.nodes
        thinking += choice.seconds
        response = manager.make_move(choice.from_coord, choice.to_coord)
        if response["success"] and response["pending_promotion"] is not None:
            response = manager.promote_pawn(choice.to_coord, getattr(pieces, choice.promotion)(color))
        if not response["success"]:
            raise RuntimeError(f"{level} played an illegal move {choice.from_coord}->{choice.to_coord}: {response['error']}")
        if response["status"] not in ("ongoing", "check"):
            return response["winner"], ply + 1, response["draw_reason"] or response["status"], searched, thinking
    return None, MAX_PLIES, "too long", searched, thinking


def match(first, second, games, hard_seconds, pool):
    """`first` plays `second`, taking White in every other game"""
    jobs = []
    for game in range(games):
        white, black = (first, second) if game % 2 == 0 else (second, first)
        jobs.append((white, black, 1000 + game, hard_seconds))
    wins = draws = losses = plies = searched = 0
    thinking = 0.0
    endings = {}
    started = time.perf_counter()
    for job, (winner, length, ending, nodes, seconds) in zip(jobs, pool.imap(play_game, jobs)):
        first_color = "white" if job[0] == first else "black"
        if winner is None:
            draws += 1
        elif winner == first_color:
            wins += 1
        else:
            losses += 1
        plies += length
        searched += nodes
        thinking += seconds
        endings[ending] = endings.get(ending, 0) + 1
    points = (wins + draws / 2) / games
    print(f"{first} v {second}: {wins} wins, {draws} draws, {losses} losses for {first} "
          f"({points:.0%} of the points) in {time.perf_counter() - started:.0f}s")
    print(f"  average game {plies / games / 2:.0f} moves each; endings {endings}; "
          f"{searched / max(thinking, 1e-9):,.0f} positions searched per second")
    return points


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("levels", nargs="*", help="two levels to pit against each other (default: both standard pairings)")
    parser.add_argument("--games", type=int, default=40)
    parser.add_argument("--hard-seconds", type=float, default=1.0, help="thinking time for hard (the game uses 3)")
    args = parser.parse_args()
    pairings = [tuple(args.levels)] if len(args.levels) == 2 else [("hard", "medium"), ("medium", "easy")]
    with multiprocessing.Pool() as pool:
        for first, second in pairings:
            match(first, second, args.games, args.hard_seconds, pool)


if __name__ == "__main__":
    main()
