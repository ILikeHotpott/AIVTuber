# danmu_queue.py
from collections import deque
from src.danmaku.models import Message, MessageType, User


class DanmuMessageQueue:
    def __init__(self, max_size: int = 20):
        self._queue: deque[Message] = deque()
        self._max_size = max_size

    def put_message(self, user: User, content: str):
        if len(self._queue) >= self._max_size:
            self._queue.popleft()
        msg = Message(priority=-3, user=user, content=content, type=MessageType.DANMU)
        self._queue.append(msg)

    def get(self) -> Message:
        return self._queue.popleft()

    def empty(self) -> bool:
        return len(self._queue) == 0

    def peek(self):
        return self._queue[0]
