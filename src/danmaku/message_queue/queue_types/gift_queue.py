import queue
from src.danmaku.models import Message, MessageType, User

from src.danmaku.const.gift_mapping import gift_mapping


class GiftMessageQueue:
    def __init__(self):
        # 只有礼物queue用的是priority queue
        self._queue = queue.PriorityQueue()

    def put_message(self, gift_name: str, gift_count: int, user: User):
        priority = -5
        if gift_name not in gift_mapping:
            priority = -10
        value = gift_mapping[gift_name] * gift_count
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

    def put_guard_message(self, gift_name: str, user: User):
        priority = -50
        if gift_name == "舰长":
            priority = -100
        elif gift_name == "提督":
            priority = -1000
        elif gift_name == "总督":
            priority = -10000
        msg = Message(priority=priority, user=user, content=gift_name, type=MessageType.GIFT)
        self._queue.put(msg)

    def get(self):
        return self._queue.get()

    def empty(self):
        return self._queue.empty()

    def peek(self) -> Message | None:
        if self.empty():
            return None
        # PriorityQueue 不支持下标访问，需要从内部 queue 列表取出
        return self._queue.queue[0]
