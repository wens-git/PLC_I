"""Copy-on-publish snapshots and bounded command event history."""
from collections import deque
from copy import deepcopy
from threading import RLock
from datetime import datetime


class Tags:
    def __init__(self):
        self.lock = RLock()
        self.value = {"connected": False, "handshake": False, "axes": [], "cylinders": [],
                      "io": {"x": [], "y": []}, "alarms": [], "error": "未连接"}
        self.events = deque(maxlen=300)

    def publish(self, value):
        with self.lock:
            self.value = deepcopy(value)

    def event(self, message, **fields):
        with self.lock:
            self.events.appendleft({"time": datetime.now().isoformat(timespec="milliseconds"),
                                    "message": message, **fields})

    def snapshot(self):
        with self.lock:
            return deepcopy({**self.value, "events": list(self.events)})
