"""
Limits that keep one visitor from using up a hosted server.

They are only switched on in hosted mode (see api/app.py): on your own machine nothing is
limited. A "visitor" is an internet address.
"""
import threading
import time
from collections import deque


class Limiter:
    """At most `limit` events per visitor in any stretch of `seconds`"""
    def __init__(self, limit, seconds, now=time.monotonic):
        self.limit = limit
        self.seconds = seconds
        self._now = now
        self._events = {}
        self._lock = threading.Lock()

    def allow(self, visitor):
        now = self._now()
        with self._lock:
            events = self._events.get(visitor)
            if events is None:
                if len(self._events) > 20000:   # forget everyone rather than grow without end
                    self._events.clear()
                events = self._events[visitor] = deque()
            while events and events[0] <= now - self.seconds:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(now)
            return True


class Slots:
    """At most `limit` things going on at the same time per visitor"""
    def __init__(self, limit):
        self.limit = limit
        self._busy = {}
        self._lock = threading.Lock()

    def take(self, visitor):
        with self._lock:
            if self._busy.get(visitor, 0) >= self.limit:
                return False
            self._busy[visitor] = self._busy.get(visitor, 0) + 1
            return True

    def give_back(self, visitor):
        with self._lock:
            left = self._busy.get(visitor, 0) - 1
            if left > 0:
                self._busy[visitor] = left
            else:
                self._busy.pop(visitor, None)
