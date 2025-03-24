import asyncio
import threading
from collections import deque


class ChatbotQueue:
    """
    用于给 Chatbot 进行回复的弹幕队列，仅接收文本类消息。
    """

    def __init__(self, max_length=200):
        self.queue = deque(maxlen=max_length)
        self.lock = threading.Lock()
        self.event = asyncio.Event()

    def add_message(self, message: dict):
        """
        添加一条文本消息到队列
        :param message: 例如 {"message_id": "...", "user_id": "...", "content": "...", "timestamp": "..."}
        """
        with self.lock:
            self.queue.append(message)
            self.event.set()

    def consume_one(self) -> dict:
        """
        消费队列中的一条消息（只消费一条，不清空其他消息）
        :return: 消费的消息字典，如果队列为空则返回 None
        """
        with self.lock:
            if self.queue:
                msg = self.queue.popleft()
                if not self.queue:
                    self.event.clear()
                return msg
            else:
                self.event.clear()
                return None
