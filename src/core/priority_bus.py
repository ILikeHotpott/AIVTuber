import queue
from typing import Optional
from src.core.event import Event


class PriorityBus:
    """线程安全、带优先级的事件队列"""

    def __init__(self):
        self.q = queue.PriorityQueue()

    def push(self, evt: Event):
        self.q.put(evt)

    def pop(self, timeout: Optional[float] = None) -> Event:
        return self.q.get(timeout=timeout)

    def empty(self) -> bool:
        return self.q.empty()
