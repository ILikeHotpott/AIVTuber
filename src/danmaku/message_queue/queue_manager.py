import queue
import time
from typing import Optional
from src.danmaku.models import Message, MessageType, User
from .queue_types.like_queue import LikeMessageQueue
from src.danmaku.message_queue.queue_types import danmu_queue, enter_queue, fans_queue, follow_queue, gift_queue, like_queue


class MessagePicker:
    def __init__(self):
        self.queue = queue.PriorityQueue()

    def add_message(self, priority: int, user: int, content: str, type: str):
        pass


class TotalMessageQueue:
    def __init__(self):
        self.like_queue = LikeMessageQueue()
        self.cooldowns = {
            MessageType.LIKE: 60,  # 秒
            MessageType.ENTER: 60,
            MessageType.FANS: 60,
            MessageType.FOLLOW: 60,
        }
        self.last_access: dict[MessageType, float] = {
            MessageType.LIKE: 0,
            MessageType.ENTER: 0,
            MessageType.FANS: 0,
            MessageType.FOLLOW: 0,
        }

    def put_like(self, user, content: str):
        self.like_queue.put_message(user, content)

    def get_next_message(self) -> Optional[Message]:
        now = time.time()

        if not self.like_queue.empty():
            last_time = self.last_access[MessageType.LIKE]
            cooldown = self.cooldowns[MessageType.LIKE]
            if now - last_time >= cooldown:
                self.last_access[MessageType.LIKE] = now
                return self.like_queue.get()
            else:
                print("[冷却中] LIKE 消息未到时间")

        # TODO: 可在此加入更多队列（弹幕、礼物等）调度逻辑

        return None
