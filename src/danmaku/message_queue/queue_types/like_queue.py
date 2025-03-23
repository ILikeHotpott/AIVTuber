import queue
import time
from src.danmaku.models import Message, MessageType, User


class LikeMessageQueue:
    def __init__(self, cooldown_seconds: int = 60):
        self._queue = queue.PriorityQueue()
        self._cooldown_seconds = cooldown_seconds
        self._last_dequeue_time: float | None = None

    def put_message(self, user: User, content: str):
        now = time.time()
        if self._last_dequeue_time is not None and now - self._last_dequeue_time < self._cooldown_seconds:
            print("[跳过] 冷却中，点赞消息不再插入")
            return

        if not self._queue.empty():
            print("[跳过] 队列中已有一个点赞消息，忽略新消息")
            return

        msg = Message(
            priority=-2,
            user=user,
            content=content,
            type=MessageType.LIKE
        )
        self._queue.put(msg)
        print("[添加] 点赞消息已插入")

    def get(self) -> Message:
        """ 获取队列优先级最高的消息（实际上只有一个优先级） """
        msg = self._queue.get()
        self._last_dequeue_time = time.time()
        return msg

    def empty(self) -> bool:
        return self._queue.empty()
