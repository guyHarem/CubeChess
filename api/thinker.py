"""
Where the computer player does its thinking.

A search keeps one CPU core busy for seconds, so the web server hands it to a separate
worker process and stays free to answer the page (clock updates, undo, a new game).
"""
import multiprocessing
from concurrent.futures import ProcessPoolExecutor

from ai.levels import choose_move


def think(game, level, seconds):
    """Runs in the worker: choose a move for the player to move. Returns a plain dict, or None"""
    choice = choose_move(game, level, seconds=seconds)
    if choice is None:
        return None
    return {"from": choice.from_coord, "to": choice.to_coord, "promotion": choice.promotion,
            "score": choice.score, "depth": choice.depth, "nodes": choice.nodes,
            "seconds": round(choice.seconds, 3), "mate_in": choice.mate_in}


def _ready():
    return True


class ProcessThinker:
    """Thinks in a worker process, started the first time it is needed"""
    def __init__(self):
        self._pool = None

    def _workers(self):
        if self._pool is None:
            self._pool = ProcessPoolExecutor(max_workers=2, mp_context=multiprocessing.get_context("spawn"))
        return self._pool

    def warm_up(self):
        """Start the worker ahead of time so the first move is not slowed by its start-up"""
        try:
            self._workers().submit(_ready)
        except Exception:
            self._pool = None

    def __call__(self, game, level, seconds):
        try:
            return self._workers().submit(think, game, level, seconds).result()
        except Exception:
            # A broken worker must not stop the game: forget it and think right here
            self._pool = None
            return think(game, level, seconds)
