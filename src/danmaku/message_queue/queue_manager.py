import queue
from typing import Optional

from sympy import content

from src.danmaku.message_queue.queue_types.danmu_queue import DanmuMessageQueue
from src.danmaku.message_queue.queue_types.enter_queue import EnterMessageQueue
from src.danmaku.message_queue.queue_types.fans_queue import FansMessageQueue
from src.danmaku.message_queue.queue_types.follow_queue import FollowMessageQueue
from src.danmaku.message_queue.queue_types.gift_queue import GiftMessageQueue
from src.danmaku.message_queue.queue_types.like_queue import LikeMessageQueue
from src.danmaku.models import MessageType, Message, User


class TotalMessageQueue:
    def __init__(self):
        self.like_queue = LikeMessageQueue()
        self.danmu_queue = DanmuMessageQueue()
        self.enter_queue = EnterMessageQueue()
        self.gift_queue = GiftMessageQueue()
        self.fans_queue = FansMessageQueue()
        self.follow_queue = FollowMessageQueue()

    def put_danmu(self, user: User, content: str):
        self.danmu_queue.put_message(user, content)

    def put_like(self, user: User, content: str):
        self.like_queue.put_message(user, content)

    def put_follow(self, user: User, content: str):
        self.follow_queue.put_message(user, content)

    def put_enter(self, user: User, content: str):
        self.enter_queue.put_message(user, content)

    def put_fans(self, user: User, content: str):
        self.fans_queue.put_message(user, content)

    def put_gift(self, gift_name: str, gift_count: int, user: User):
        self.gift_queue.put_message(gift_name, gift_count, user)

    def get_next_message(self) -> Optional[Message]:
        temp_pq = queue.PriorityQueue()
        peeked_messages = []

        for q in [
            self.like_queue,
            self.danmu_queue,
            self.enter_queue,
            self.gift_queue,
            self.fans_queue,
            self.follow_queue,
        ]:
            msg = q.peek()
            if msg:
                temp_pq.put(msg)
                peeked_messages.append(msg)

        if temp_pq.empty():
            return None

        top_msg = temp_pq.get()

        if top_msg.type == MessageType.LIKE:
            return self.like_queue.get()
        elif top_msg.type == MessageType.DANMU:
            return self.danmu_queue.get()
        elif top_msg.type == MessageType.ENTER:
            return self.enter_queue.get()
        elif top_msg.type == MessageType.GIFT:
            return self.gift_queue.get()
        elif top_msg.type == MessageType.FANS:
            return self.fans_queue.get()
        elif top_msg.type == MessageType.FOLLOW:
            return self.follow_queue.get()
        else:
            return None
