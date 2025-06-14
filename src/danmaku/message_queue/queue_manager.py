import queue
from typing import Optional

from src.danmaku.message_queue.queue_types.danmu_queue import DanmuMessageQueue
from src.danmaku.message_queue.queue_types.follow_queue import FollowMessageQueue
from src.danmaku.message_queue.queue_types.gift_queue import GiftMessageQueue
from src.danmaku.models import Message, MessageType, User


class TotalMessageQueue:
    """Holds three priority sub-queues and picks the highest-priority message."""

    def __init__(self) -> None:
        self.danmu_queue = DanmuMessageQueue()
        self.gift_queue = GiftMessageQueue()
        self.follow_queue = FollowMessageQueue()

    # ───────── Enqueue helpers ─────────
    async def put_danmu(self, user: User, content: str) -> None:
        await self.danmu_queue.put_danmu(user, content)

    async def put_super_chat(self, user: User, content: str, price: int) -> None:
        await self.danmu_queue.put_superchat(user, content, price)

    async def put_follow(self, user: User, content: str) -> None:
        await self.follow_queue.put_message(user, content)

    async def put_gift(self, gift_name: str, gift_count: int, user: User) -> None:
        await self.gift_queue.put_message(gift_name, gift_count, user)

    # ───────── Sync version (unused in bridge, kept for legacy) ─────────
    def get_next_message(self) -> Optional[Message]:
        temp_pq: queue.PriorityQueue[Message] = queue.PriorityQueue()
        for q in (self.danmu_queue, self.gift_queue, self.follow_queue):
            msg = q.peek()  # sync peek
            if msg:
                temp_pq.put(msg)

        if temp_pq.empty():
            return None

        top_msg: Message = temp_pq.get()
        if top_msg.type is MessageType.DANMU:
            return self.danmu_queue.get()
        if top_msg.type is MessageType.GIFT:
            return self.gift_queue.get()
        if top_msg.type is MessageType.FOLLOW:
            return self.follow_queue.get()
        return None

    # ───────── Async version used by bridge ─────────
    async def get_next_message_async(self) -> Optional[Message]:
        temp_pq: queue.PriorityQueue[Message] = queue.PriorityQueue()
        for q in (self.danmu_queue, self.gift_queue, self.follow_queue):
            try:
                msg = await q.peek()  # async peek
                if msg:
                    temp_pq.put(msg)
            except Exception:
                # 静默处理，队列为空是正常情况
                continue

        if temp_pq.empty():
            return None

        top_msg: Message = temp_pq.get()
        try:
            if top_msg.type is MessageType.DANMU:
                return await self.danmu_queue.get()
            if top_msg.type is MessageType.GIFT:
                return await self.gift_queue.get()
            if top_msg.type is MessageType.FOLLOW:
                return await self.follow_queue.get()
        except Exception as e:
            print(f"[TotalMessageQueue] Error getting message: {e}")
            
        return None
