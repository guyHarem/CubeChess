"""
Chess clock for one game: each player has a countdown that runs only on their turn.
"""
import time


class ChessClock:
    def __init__(self, initial, increment=0, now=time.monotonic):
        self.initial = initial        # seconds each player starts with
        self.increment = increment    # seconds added after each move the player makes
        self.remaining = {"white": float(initial), "black": float(initial)}
        self.running = None           # the colour whose clock is counting down, or None
        self._started_at = None
        self._now = now               # injectable so tests don't have to wait

    # ==================== QUERIES ====================

    def time_left(self, color):
        left = self.remaining[color]
        if self.running == color:
            left -= self._now() - self._started_at
        return max(0.0, left)

    def flagged(self):
        """The colour that ran out of time, or None"""
        if self.running is not None and self.time_left(self.running) <= 0:
            return self.running
        return None

    def to_json(self):
        return {
            "initial": self.initial,
            "increment": self.increment,
            "white": round(self.time_left("white"), 2),
            "black": round(self.time_left("black"), 2),
            "running": self.running
        }

    # ==================== CONTROL ====================

    def stop(self):
        """Freeze both clocks (the game is over)"""
        if self.running is not None:
            self.remaining[self.running] = self.time_left(self.running)
        self.running = None
        self._started_at = None

    def start(self, color):
        self.stop()
        self.running = color
        self._started_at = self._now()

    def finish_turn(self, mover, next_player):
        """The mover has completed a move: bank their time, add the increment, start the opponent.
        White's first move is free: nothing runs (and no increment is earned) until it is made."""
        was_running = self.running == mover
        self.stop()
        if was_running:
            self.remaining[mover] += self.increment
        self.start(next_player)

    # ==================== UNDO SUPPORT ====================

    def snapshot(self):
        return ({"white": self.time_left("white"), "black": self.time_left("black")}, self.running)

    def restore(self, snapshot):
        self.stop()
        self.remaining = dict(snapshot[0])
        if snapshot[1] is not None:
            self.start(snapshot[1])
