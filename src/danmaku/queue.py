import asyncio
import threading
from collections import deque
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from .buffer import DanmakuJsonStorage


class DanmakuMessage(BaseModel):
    content: str
    user_id: str
    timestamp: str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    priority: int = 0  # （0-10, 数字越大优先级越高）
    emoticon: Optional[str] = None  # 表情链接
    source: str = "douyin"
    message_id: str


class DanmakuQueue:
    def __init__(self, max_length=200, json_storage: DanmakuJsonStorage = None):
        """
        :param max_length: 队列最大长度（这里设置为 200 条弹幕）
        :param json_storage: 绑定的 JSON 存储实例，用于后续存盘处理
        """
        self.queue = deque(maxlen=max_length)
        self.lock = threading.Lock()
        self.event = asyncio.Event()
        self.json_storage = json_storage

    def add_message(self, message: dict, category: str):
        """
        添加一条消息到队列，并交给 JSON 存储系统处理
        :param message: 消息字典（例如 {"content": "弹幕内容", ...}）
        :param category: 消息类别，如 "chat", "gift" 等
        """
        with self.lock:
            self.queue.append(message)
            self.event.set()
            if self.json_storage is not None:
                self.json_storage.add_message(category, message)

    def consume_one(self) -> dict:
        """
        消费队列中的一条消息（只消费一条，不清空队列中其他消息）
        :return: 消费的消息字典，如果队列为空则返回 None
        """
        with self.lock:
            if self.queue:
                message = self.queue.popleft()
                if not self.queue:
                    self.event.clear()
                return message
            else:
                self.event.clear()
                return None
