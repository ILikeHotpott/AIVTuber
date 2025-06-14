from src.danmaku.message_queue.base_queue import BaseQueue
from src.danmaku.models import Message, MessageType, User


class DanmuMessageQueue(BaseQueue):
    async def put_danmu(self, user: User, content: str) -> None:
        await self.put(Message(priority=-3, user=user, content=content, type=MessageType.DANMU))

    async def put_superchat(self, user: User, content: str, price: int) -> None:
        # SuperChat is treated as boosted Danmu – we still label it DANMU.
        await self.put(Message(priority=-price, user=user, content=content, type=MessageType.DANMU))
