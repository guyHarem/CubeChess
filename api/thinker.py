"""
Where the computer player does its thinking.

A search keeps one CPU core busy for seconds, so the web server hands it to a separate
worker process and stays free to answer the page (clock updates, undo, a new game).
"""
import multiprocessing
import os
import threading
from concurrent.futures import ProcessPoolExecutor

from ai.levels import choose_move


class Busy(ValueError):
    """Every worker is taken and the line behind them is full"""


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


def default_workers():
    """One core is left for the web server; more than four thinkers at once is not needed"""
    return max(1, min(4, (os.cpu_count() or 2) - 1))


class ProcessThinker:
    """Thinks in worker processes, started the first time they are needed.

    workers: how many searches run at the same time (each uses one CPU core).
    waiting: how many more may wait in line for a free worker. Beyond that a request is
    turned away with Busy, and the page simply asks again a moment later."""
    def __init__(self, workers=None, waiting=None):
        self.workers = workers or default_workers()
        waiting = self.workers * 2 if waiting is None else waiting
        self._places = threading.BoundedSemaphore(self.workers + waiting)
        self._pool = None
        self._closed = False

    def _processes(self):
        if self._pool is None:
            self._pool = ProcessPoolExecutor(max_workers=self.workers, mp_context=multiprocessing.get_context("spawn"))
        return self._pool

    def warm_up(self):
        """Start a worker ahead of time so the first move is not slowed by its start-up"""
        try:
            self._processes().submit(_ready)
        except Exception:
            self._pool = None

    def close(self):
        """Stop the workers, for when the server shuts down. Left alone they would live on
        after it, each still holding memory."""
        self._closed = True
        pool, self._pool = self._pool, None
        if pool is not None:
            pool.terminate_workers()

    def __call__(self, game, level, seconds):
        if self._closed or not self._places.acquire(blocking=False):
            raise Busy("The computer is busy with other games. It will move in a moment.")
        try:
            try:
                return self._processes().submit(think, game, level, seconds).result()
            except Exception:
                if self._closed:
                    raise Busy("The server is shutting down.")
                # A broken worker must not stop the game: forget it and think right here
                self._pool = None
                return think(game, level, seconds)
        finally:
            self._places.release()
