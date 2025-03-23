import queue
from src.danmaku.models import Message, MessageType, User


class EnterMessageQueue:
    def __init__(self):
        self._queue = queue.PriorityQueue()

    def put_message(self, user: User, content: str):
        msg = Message(
            priority=-1,
            user=user,
            content=content,
            type=MessageType.LIKE
        )
        self._queue.put(msg)
        print("[添加] 进入房间消息已插入")

    def get(self) -> Message:
        return self._queue.get()

    def empty(self) -> bool:
        return self._queue.empty()
