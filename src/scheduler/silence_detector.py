import threading, time
from src.core.event import Event, EventType


class SilenceDetector(threading.Thread):
    """没观众也要说点啥 → 注入 SILENCE 事件"""

    def __init__(self, bus, idle_secs=3):
        super().__init__(daemon=True)
        self.bus = bus
        self.idle_secs = idle_secs
        self.last_activity = time.time()

    def reset(self):
        self.last_activity = time.time()

    def run(self):
        while True:
            if time.time() - self.last_activity >= self.idle_secs:
                self.bus.push(Event.make(EventType.SILENCE))
                self.reset()
            time.sleep(1)
