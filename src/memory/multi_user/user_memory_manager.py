"""
企业级多用户记忆管理系统
支持个人记忆和全局记忆的分离管理，提供高性能、线程安全的记忆操作接口。

Author: Assistant
Date: 2025-01-10
"""

import asyncio
import json
import threading
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, Union
from uuid import uuid4

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage


class MemoryType(Enum):
    """记忆类型枚举"""
    PERSONAL = "personal"
    GENERAL = "general"


class MessagePriority(Enum):
    """消息优先级"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class MemoryMessage:
    """记忆消息数据模型"""
    id: str = field(default_factory=lambda: str(uuid4()))
    user_id: str = ""
    username: str = ""
    content: str = ""
    message_type: str = "human"  # human, ai, system
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    priority: MessagePriority = MessagePriority.NORMAL
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_langchain_message(
        cls, 
        message: BaseMessage, 
        user_id: str, 
        username: str = "", 
        priority: MessagePriority = MessagePriority.NORMAL,
        metadata: Optional[Dict[str, Any]] = None
    ) -> "MemoryMessage":
        """从Langchain消息创建MemoryMessage"""
        message_type = "human" if isinstance(message, HumanMessage) else "ai"
        return cls(
            user_id=user_id,
            username=username,
            content=message.content,
            message_type=message_type,
            priority=priority,
            metadata=metadata or {}
        )
    
    def to_langchain_message(self) -> BaseMessage:
        """转换为Langchain消息"""
        if self.message_type == "human":
            return HumanMessage(content=self.content)
        elif self.message_type == "ai":
            return AIMessage(content=self.content)
        else:
            raise ValueError(f"Unsupported message type: {self.message_type}")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "username": self.username,
            "content": self.content,
            "message_type": self.message_type,
            "timestamp": self.timestamp.isoformat(),
            "priority": self.priority.value,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryMessage":
        """从字典创建"""
        return cls(
            id=data["id"],
            user_id=data["user_id"],
            username=data["username"],
            content=data["content"],
            message_type=data["message_type"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            priority=MessagePriority(data["priority"]),
            metadata=data["metadata"]
        )


class MemoryStorage(Protocol):
    """记忆存储协议"""
    
    async def store_message(self, memory_type: MemoryType, message: MemoryMessage) -> bool:
        """存储消息"""
        ...
    
    async def retrieve_messages(
        self, 
        memory_type: MemoryType,
        user_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[MemoryMessage]:
        """检索消息"""
        ...
    
    async def delete_messages(
        self, 
        memory_type: MemoryType,
        user_id: Optional[str] = None,
        message_ids: Optional[List[str]] = None
    ) -> int:
        """删除消息，返回删除数量"""
        ...
    
    async def get_message_count(self, memory_type: MemoryType, user_id: Optional[str] = None) -> int:
        """获取消息数量"""
        ...


class InMemoryStorage(MemoryStorage):
    """内存存储实现"""
    
    def __init__(self, max_messages_per_user: int = 1000, max_general_messages: int = 5000):
        self.max_messages_per_user = max_messages_per_user
        self.max_general_messages = max_general_messages
        
        # 使用deque实现LRU行为
        self._personal_memories: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_messages_per_user))
        self._general_memory: deque = deque(maxlen=max_general_messages)
        self._lock = asyncio.Lock()
    
    async def store_message(self, memory_type: MemoryType, message: MemoryMessage) -> bool:
        """存储消息"""
        async with self._lock:
            try:
                if memory_type == MemoryType.PERSONAL:
                    self._personal_memories[message.user_id].append(message)
                elif memory_type == MemoryType.GENERAL:
                    self._general_memory.append(message)
                return True
            except Exception:
                return False
    
    async def retrieve_messages(
        self, 
        memory_type: MemoryType,
        user_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[MemoryMessage]:
        """检索消息"""
        async with self._lock:
            if memory_type == MemoryType.PERSONAL:
                if not user_id:
                    return []
                messages = list(self._personal_memories[user_id])
            else:
                messages = list(self._general_memory)
            
            # 时间过滤
            if start_time or end_time:
                filtered_messages = []
                for msg in messages:
                    if start_time and msg.timestamp < start_time:
                        continue
                    if end_time and msg.timestamp > end_time:
                        continue
                    filtered_messages.append(msg)
                messages = filtered_messages
            
            # 分页
            start_idx = offset
            end_idx = offset + limit
            return messages[start_idx:end_idx]
    
    async def delete_messages(
        self, 
        memory_type: MemoryType,
        user_id: Optional[str] = None,
        message_ids: Optional[List[str]] = None
    ) -> int:
        """删除消息"""
        async with self._lock:
            deleted_count = 0
            
            if memory_type == MemoryType.PERSONAL and user_id:
                if message_ids:
                    # 删除指定ID的消息
                    original_messages = list(self._personal_memories[user_id])
                    self._personal_memories[user_id].clear()
                    for msg in original_messages:
                        if msg.id not in message_ids:
                            self._personal_memories[user_id].append(msg)
                        else:
                            deleted_count += 1
                else:
                    # 删除用户的所有消息
                    deleted_count = len(self._personal_memories[user_id])
                    self._personal_memories[user_id].clear()
            
            elif memory_type == MemoryType.GENERAL:
                if message_ids:
                    # 删除指定ID的消息
                    original_messages = list(self._general_memory)
                    self._general_memory.clear()
                    for msg in original_messages:
                        if msg.id not in message_ids:
                            self._general_memory.append(msg)
                        else:
                            deleted_count += 1
                else:
                    # 删除所有一般消息
                    deleted_count = len(self._general_memory)
                    self._general_memory.clear()
            
            return deleted_count
    
    async def get_message_count(self, memory_type: MemoryType, user_id: Optional[str] = None) -> int:
        """获取消息数量"""
        async with self._lock:
            if memory_type == MemoryType.PERSONAL:
                if not user_id:
                    return sum(len(messages) for messages in self._personal_memories.values())
                return len(self._personal_memories[user_id])
            else:
                return len(self._general_memory)


@dataclass
class MemoryStats:
    """记忆统计信息"""
    total_users: int = 0
    total_personal_messages: int = 0
    total_general_messages: int = 0
    active_users_24h: int = 0
    most_active_user: Optional[str] = None
    average_messages_per_user: float = 0.0
    peak_memory_usage: int = 0
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class UserMemoryManager:
    """
    企业级多用户记忆管理器
    
    功能特性：
    - 个人记忆和全局记忆分离管理
    - 线程安全的异步操作
    - 可插拔的存储后端
    - 自动内存管理和清理
    - 详细的统计和监控
    - 消息优先级支持
    """
    
    def __init__(
        self,
        storage: Optional[MemoryStorage] = None,
        max_personal_messages_per_user: int = 1000,
        max_general_messages: int = 5000,
        auto_cleanup_enabled: bool = True,
        cleanup_interval_seconds: int = 3600  # 1小时
    ):
        self.storage = storage or InMemoryStorage(
            max_messages_per_user=max_personal_messages_per_user,
            max_general_messages=max_general_messages
        )
        self.auto_cleanup_enabled = auto_cleanup_enabled
        self.cleanup_interval_seconds = cleanup_interval_seconds
        
        # 统计信息
        self._stats = MemoryStats()
        self._stats_lock = asyncio.Lock()
        
        # 用户活动跟踪
        self._user_last_activity: Dict[str, datetime] = {}
        self._activity_lock = asyncio.Lock()
        
        # 清理任务
        self._cleanup_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        
        # 启动自动清理
        if self.auto_cleanup_enabled:
            self._start_cleanup_task()
    
    def _start_cleanup_task(self):
        """启动自动清理任务"""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def _cleanup_loop(self):
        """自动清理循环"""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(), 
                    timeout=self.cleanup_interval_seconds
                )
                break  # 收到关闭信号
            except asyncio.TimeoutError:
                # 执行清理任务
                await self._perform_cleanup()
    
    async def _perform_cleanup(self):
        """执行清理任务"""
        try:
            # 清理过期的用户活动记录（超过30天）
            cutoff_time = datetime.now(timezone.utc).replace(day=datetime.now().day - 30)
            
            async with self._activity_lock:
                expired_users = [
                    user_id for user_id, last_activity in self._user_last_activity.items()
                    if last_activity < cutoff_time
                ]
                
                for user_id in expired_users:
                    del self._user_last_activity[user_id]
            
            # 更新统计信息
            await self._update_stats()
            
        except Exception as e:
            print(f"[UserMemoryManager] Cleanup error: {e}")
    
    async def add_personal_message(
        self, 
        user_id: str, 
        message: Union[BaseMessage, MemoryMessage],
        username: str = "",
        priority: MessagePriority = MessagePriority.NORMAL,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """添加个人记忆消息"""
        if isinstance(message, BaseMessage):
            memory_message = MemoryMessage.from_langchain_message(
                message, user_id, username, priority, metadata
            )
        else:
            memory_message = message
            memory_message.user_id = user_id
        
        # 更新用户活动
        await self._update_user_activity(user_id)
        
        # 存储消息
        return await self.storage.store_message(MemoryType.PERSONAL, memory_message)
    
    async def add_general_message(
        self, 
        user_id: str,
        message: Union[BaseMessage, MemoryMessage],
        username: str = "",
        priority: MessagePriority = MessagePriority.NORMAL,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """添加全局记忆消息"""
        if isinstance(message, BaseMessage):
            memory_message = MemoryMessage.from_langchain_message(
                message, user_id, username, priority, metadata
            )
        else:
            memory_message = message
            memory_message.user_id = user_id
        
        # 更新用户活动
        await self._update_user_activity(user_id)
        
        # 存储消息
        return await self.storage.store_message(MemoryType.GENERAL, memory_message)
    
    async def add_message_to_both(
        self,
        user_id: str,
        message: Union[BaseMessage, MemoryMessage],
        username: str = "",
        priority: MessagePriority = MessagePriority.NORMAL,
        metadata: Optional[Dict[str, Any]] = None
    ) -> tuple[bool, bool]:
        """同时添加到个人记忆和全局记忆"""
        personal_success = await self.add_personal_message(
            user_id, message, username, priority, metadata
        )
        general_success = await self.add_general_message(
            user_id, message, username, priority, metadata
        )
        return personal_success, general_success
    
    async def get_personal_messages(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[MemoryMessage]:
        """获取用户个人记忆消息"""
        return await self.storage.retrieve_messages(
            MemoryType.PERSONAL, user_id, limit, offset, start_time, end_time
        )
    
    async def get_general_messages(
        self,
        limit: int = 100,
        offset: int = 0,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[MemoryMessage]:
        """获取全局记忆消息"""
        return await self.storage.retrieve_messages(
            MemoryType.GENERAL, None, limit, offset, start_time, end_time
        )
    
    async def get_personal_langchain_messages(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[BaseMessage]:
        """获取用户个人记忆的Langchain消息格式"""
        memory_messages = await self.get_personal_messages(user_id, limit, offset)
        return [msg.to_langchain_message() for msg in memory_messages]
    
    async def get_general_langchain_messages(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[BaseMessage]:
        """获取全局记忆的Langchain消息格式"""
        memory_messages = await self.get_general_messages(limit, offset)
        return [msg.to_langchain_message() for msg in memory_messages]
    
    async def delete_user_messages(self, user_id: str, memory_type: MemoryType) -> int:
        """删除用户的所有消息"""
        return await self.storage.delete_messages(memory_type, user_id)
    
    async def clear_general_memory(self) -> int:
        """清空全局记忆"""
        return await self.storage.delete_messages(MemoryType.GENERAL)
    
    async def _update_user_activity(self, user_id: str):
        """更新用户活动时间"""
        async with self._activity_lock:
            self._user_last_activity[user_id] = datetime.now(timezone.utc)
    
    async def _update_stats(self):
        """更新统计信息"""
        async with self._stats_lock:
            # 获取用户数量
            self._stats.total_users = len(self._user_last_activity)
            
            # 获取消息数量
            self._stats.total_personal_messages = await self.storage.get_message_count(MemoryType.PERSONAL)
            self._stats.total_general_messages = await self.storage.get_message_count(MemoryType.GENERAL)
            
            # 计算24小时内活跃用户
            cutoff_time = datetime.now(timezone.utc).replace(hour=datetime.now().hour - 24)
            active_users = [
                user_id for user_id, last_activity in self._user_last_activity.items()
                if last_activity >= cutoff_time
            ]
            self._stats.active_users_24h = len(active_users)
            
            # 找到最活跃用户
            if active_users:
                user_message_counts = {}
                for user_id in active_users:
                    count = await self.storage.get_message_count(MemoryType.PERSONAL, user_id)
                    user_message_counts[user_id] = count
                
                if user_message_counts:
                    self._stats.most_active_user = max(user_message_counts, key=user_message_counts.get)
            
            # 计算平均每用户消息数
            if self._stats.total_users > 0:
                self._stats.average_messages_per_user = (
                    self._stats.total_personal_messages / self._stats.total_users
                )
            
            self._stats.last_updated = datetime.now(timezone.utc)
    
    async def get_stats(self) -> MemoryStats:
        """获取统计信息"""
        await self._update_stats()
        async with self._stats_lock:
            return self._stats
    
    async def get_user_message_count(self, user_id: str) -> Dict[str, int]:
        """获取用户消息数量统计"""
        personal_count = await self.storage.get_message_count(MemoryType.PERSONAL, user_id)
        return {
            "personal_messages": personal_count,
            "last_activity": self._user_last_activity.get(user_id, datetime.min).isoformat() if user_id in self._user_last_activity else None
        }
    
    async def close(self):
        """关闭管理器"""
        self._shutdown_event.set()
        
        if self._cleanup_task and not self._cleanup_task.done():
            try:
                await asyncio.wait_for(self._cleanup_task, timeout=5.0)
            except asyncio.TimeoutError:
                self._cleanup_task.cancel()
        
        print("[UserMemoryManager] Closed successfully")


# 工厂函数
def create_user_memory_manager(
    storage_type: str = "memory",
    **kwargs
) -> UserMemoryManager:
    """创建用户记忆管理器的工厂函数"""
    if storage_type == "memory":
        storage = InMemoryStorage(
            max_messages_per_user=kwargs.get("max_personal_messages_per_user", 1000),
            max_general_messages=kwargs.get("max_general_messages", 5000)
        )
    else:
        raise ValueError(f"Unsupported storage type: {storage_type}")
    
    return UserMemoryManager(
        storage=storage,
        auto_cleanup_enabled=kwargs.get("auto_cleanup_enabled", True),
        cleanup_interval_seconds=kwargs.get("cleanup_interval_seconds", 3600)
    ) 