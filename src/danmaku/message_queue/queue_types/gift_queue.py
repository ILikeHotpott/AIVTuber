import queue
from src.danmaku.models import Message, MessageType, User

from .gift_mapping import gift_mapping


class GiftQueue:
    def __init(self):
        # 只有礼物queue用的是priority queue
        self._queue = queue.PriorityQueue()

    def put_message(self, gift_name: str, gift_cnt: int, user: User):
        priority = -5
        if gift_name not in gift_mapping:
            priority = -10
        value = gift_mapping[gift_name] * gift_cnt
        if value < 10:
            priority = -5
        elif 10 <= value < 100:
            priority = -10
        elif 100 <= value < 1000:
            priority = -20
        elif 1000 <= value < 10000:
            priority = -30
        elif 10000 < value:
            priority = -40
        msg = Message(priority=priority, user=user, content=gift_name, type=MessageType.GIFT)
        self._queue.put(msg)

    def get(self):
        return self._queue.get()

    def empty(self):
        return self._queue.empty()

    def peek(self):
        return self._queue.queue[0]