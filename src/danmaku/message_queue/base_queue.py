import asyncio
from collections import deque
from typing import Deque, Optional
from src.danmaku.models import Message


class BaseQueue:
    """A bounded FIFO queue with async locks for multi‑producer safety."""

    def __init__(self, max_size: int = 100):
        self._dq: Deque[Message] = deque()
        self._max_size = max_size
        self._lock = asyncio.Lock()

    async def put(self, msg: Message) -> None:
        async with self._lock:
            if len(self._dq) >= self._max_size:
                self._dq.popleft()  # drop oldest
            self._dq.append(msg)

    async def get(self) -> Optional[Message]:
        async with self._lock:
            if self._dq:
                return self._dq.popleft()
            return None

    async def peek(self) -> Optional[Message]:
        async with self._lock:
            return self._dq[0] if self._dq else None

    async def empty(self) -> bool:
        async with self._lock:
            return not self._dq