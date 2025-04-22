import queue
from typing import Optional
from src.danmaku.message_queue.queue_types.danmu_queue import DanmuMessageQueue
from src.danmaku.message_queue.queue_types.follow_queue import FollowMessageQueue
from src.danmaku.message_queue.queue_types.gift_queue import GiftMessageQueue
from src.danmaku.models import MessageType, Message, User


class TotalMessageQueue:
    def __init__(self):
        self.danmu_queue = DanmuMessageQueue()
        self.gift_queue = GiftMessageQueue()
        self.follow_queue = FollowMessageQueue()

    def put_danmu(self, user: User, content: str):
        self.danmu_queue.put_message(user, content)

    def put_super_chat(self, user: User, content: str, price: int):
        self.danmu_queue.put_superchat(user, content, price)

    def put_follow(self, user: User, content: str):
        self.follow_queue.put_message(user, content)

    def put_gift(self, gift_name: str, gift_count: int, user: User):
        self.gift_queue.put_message(gift_name, gift_count, user)

    def get_next_message(self) -> Optional[Message]:
        temp_pq = queue.PriorityQueue()
        peeked_messages = []

        for q in [
            self.danmu_queue,
            self.gift_queue,
            self.follow_queue,
        ]:
            msg = q.peek()
            if msg:
                temp_pq.put(msg)
                peeked_messages.append(msg)

        if temp_pq.empty():
            return None

        top_msg = temp_pq.get()

        if top_msg.type == MessageType.DANMU:
            return self.danmu_queue.get()
        elif top_msg.type == MessageType.GIFT:
            return self.gift_queue.get()
        elif top_msg.type == MessageType.FOLLOW:
            return self.follow_queue.get()
        else:
            return None
