import asyncio
import json
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from src.utils.path import find_project_root


class MemoryType(Enum):
    """记忆类型枚举"""
    PERSONAL = "personal"
    GENERAL = "general"


class UserStatus(Enum):
    """用户状态枚举"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    BANNED = "banned"


class User:
    """用户实体类"""
    def __init__(
        self,
        user_id: str,
        username: str = None,
        created_at: datetime = None,
        last_active: datetime = None,
        status: UserStatus = UserStatus.ACTIVE,
        metadata: Dict[str, Any] = None
    ):
        self.user_id = user_id
        self.username = username or user_id
        self.created_at = created_at or datetime.now()
        self.last_active = last_active or datetime.now()
        self.status = status
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "created_at": self.created_at.isoformat(),
            "last_active": self.last_active.isoformat(),
            "status": self.status.value,
            "metadata": json.dumps(self.metadata)
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "User":
        return cls(
            user_id=data["user_id"],
            username=data["username"],
            created_at=datetime.fromisoformat(data["created_at"]),
            last_active=datetime.fromisoformat(data["last_active"]),
            status=UserStatus(data["status"]),
            metadata=json.loads(data["metadata"]) if data["metadata"] else {}
        )


class ConversationMemory:
    """对话记忆类"""
    def __init__(self, user_id: str, memory_type: MemoryType):
        self.user_id = user_id
        self.memory_type = memory_type
        self.messages: List[BaseMessage] = []
        self.user_info: Dict[str, Any] = {}
        self.created_at = datetime.now()
        self.last_updated = datetime.now()
        self.message_count = 0

    def add_message(self, message: BaseMessage) -> None:
        """添加消息到记忆中"""
        self.messages.append(message)
        self.last_updated = datetime.now()
        self.message_count += 1

    def get_recent_messages(self, limit: int = 50) -> List[BaseMessage]:
        """获取最近的消息"""
        return self.messages[-limit:] if limit > 0 else self.messages

    def clear_old_messages(self, keep_count: int = 100) -> None:
        """清理旧消息，保留最近的消息"""
        if len(self.messages) > keep_count:
            self.messages = self.messages[-keep_count:]

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "user_id": self.user_id,
            "memory_type": self.memory_type.value,
            "messages": [self._message_to_dict(msg) for msg in self.messages],
            "user_info": self.user_info,
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "message_count": self.message_count
        }

    @staticmethod
    def _message_to_dict(message: BaseMessage) -> Dict[str, Any]:
        """将消息转换为字典"""
        return {
            "type": message.__class__.__name__,
            "content": message.content,
            "timestamp": getattr(message, "timestamp", datetime.now().isoformat())
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationMemory":
        """从字典反序列化"""
        memory = cls(data["user_id"], MemoryType(data["memory_type"]))
        memory.messages = [cls._dict_to_message(msg_data) for msg_data in data["messages"]]
        memory.user_info = data["user_info"]
        memory.created_at = datetime.fromisoformat(data["created_at"])
        memory.last_updated = datetime.fromisoformat(data["last_updated"])
        memory.message_count = data["message_count"]
        return memory

    @staticmethod
    def _dict_to_message(data: Dict[str, Any]) -> BaseMessage:
        """从字典转换为消息"""
        if data["type"] == "HumanMessage":
            return HumanMessage(content=data["content"])
        elif data["type"] == "AIMessage":
            return AIMessage(content=data["content"])
        else:
            return HumanMessage(content=data["content"])  # 默认为人类消息


class UserManager:
    """
    企业级用户管理器
    负责管理多用户的个人记忆和全局记忆
    """

    _instance: Optional["UserManager"] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, db_path: Optional[Path] = None):
        if hasattr(self, "_initialized"):
            return
        
        self._initialized = True
        self.db_path = db_path or (find_project_root() / "src" / "runtime" / "users" / "user_data.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 内存缓存
        self._users: Dict[str, User] = {}
        self._personal_memories: Dict[str, ConversationMemory] = {}
        self._general_memory: Optional[ConversationMemory] = None
        
        # 线程安全
        self._memory_lock = threading.RLock()
        self._user_lock = threading.RLock()
        
        # 配置
        self.max_personal_messages = 200
        self.max_general_messages = 500
        self.inactive_threshold = timedelta(days=30)
        
        # 初始化数据库和general记忆
        self._init_database()
        self._init_general_memory()
        
        # 启动后台清理任务
        self._start_cleanup_task()

    def _init_database(self) -> None:
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_active TEXT NOT NULL,
                    status TEXT NOT NULL,
                    metadata TEXT
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_updated TEXT NOT NULL,
                    UNIQUE(user_id, memory_type)
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_users_status 
                ON users(status)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_user_type 
                ON memories(user_id, memory_type)
            """)
            
            conn.commit()

    def _init_general_memory(self) -> None:
        """初始化全局记忆"""
        with self._memory_lock:
            self._general_memory = ConversationMemory("__GENERAL__", MemoryType.GENERAL)
            # 尝试从数据库加载
            self._load_memory_from_db("__GENERAL__", MemoryType.GENERAL)

    def register_user(
        self, 
        user_id: str, 
        username: str = None, 
        metadata: Dict[str, Any] = None
    ) -> User:
        """注册新用户或更新现有用户"""
        with self._user_lock:
            if user_id in self._users:
                user = self._users[user_id]
                user.last_active = datetime.now()
                if username:
                    user.username = username
                if metadata:
                    user.metadata.update(metadata)
            else:
                user = User(
                    user_id=user_id,
                    username=username,
                    metadata=metadata
                )
                self._users[user_id] = user
                
                # 初始化个人记忆
                with self._memory_lock:
                    if user_id not in self._personal_memories:
                        self._personal_memories[user_id] = ConversationMemory(
                            user_id, MemoryType.PERSONAL
                        )
                        # 尝试从数据库加载
                        self._load_memory_from_db(user_id, MemoryType.PERSONAL)
            
            # 保存到数据库
            self._save_user_to_db(user)
            return user

    def get_user(self, user_id: str) -> Optional[User]:
        """获取用户信息"""
        with self._user_lock:
            if user_id not in self._users:
                # 尝试从数据库加载
                self._load_user_from_db(user_id)
            return self._users.get(user_id)

    def get_personal_memory(self, user_id: str) -> Optional[ConversationMemory]:
        """获取用户个人记忆"""
        # 确保用户存在
        if not self.get_user(user_id):
            self.register_user(user_id)
        
        with self._memory_lock:
            return self._personal_memories.get(user_id)

    def get_general_memory(self) -> ConversationMemory:
        """获取全局记忆"""
        with self._memory_lock:
            return self._general_memory

    def add_message_to_personal(
        self, 
        user_id: str, 
        message: BaseMessage
    ) -> None:
        """添加消息到用户个人记忆"""
        memory = self.get_personal_memory(user_id)
        if memory:
            with self._memory_lock:
                memory.add_message(message)
                # 清理旧消息
                memory.clear_old_messages(self.max_personal_messages)
                # 异步保存到数据库
                asyncio.create_task(self._save_memory_to_db_async(memory))

    def add_message_to_general(self, message: BaseMessage) -> None:
        """添加消息到全局记忆"""
        with self._memory_lock:
            self._general_memory.add_message(message)
            # 清理旧消息
            self._general_memory.clear_old_messages(self.max_general_messages)
            # 异步保存到数据库
            asyncio.create_task(self._save_memory_to_db_async(self._general_memory))

    def add_message_to_both(
        self, 
        user_id: str, 
        message: BaseMessage
    ) -> None:
        """同时添加消息到个人和全局记忆"""
        self.add_message_to_personal(user_id, message)
        self.add_message_to_general(message)

    def get_active_users(self, limit: int = 50) -> List[User]:
        """获取活跃用户列表"""
        threshold = datetime.now() - self.inactive_threshold
        with self._user_lock:
            active_users = [
                user for user in self._users.values()
                if user.status == UserStatus.ACTIVE and user.last_active > threshold
            ]
            # 按最后活跃时间排序
            active_users.sort(key=lambda u: u.last_active, reverse=True)
            return active_users[:limit]

    def update_user_activity(self, user_id: str) -> None:
        """更新用户活跃时间"""
        user = self.get_user(user_id)
        if user:
            user.last_active = datetime.now()
            self._save_user_to_db(user)

    def ban_user(self, user_id: str) -> bool:
        """封禁用户"""
        user = self.get_user(user_id)
        if user:
            user.status = UserStatus.BANNED
            self._save_user_to_db(user)
            return True
        return False

    def unban_user(self, user_id: str) -> bool:
        """解封用户"""
        user = self.get_user(user_id)
        if user:
            user.status = UserStatus.ACTIVE
            self._save_user_to_db(user)
            return True
        return False

    def _save_user_to_db(self, user: User) -> None:
        """保存用户到数据库"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO users 
                    (user_id, username, created_at, last_active, status, metadata)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    user.user_id,
                    user.username,
                    user.created_at.isoformat(),
                    user.last_active.isoformat(),
                    user.status.value,
                    json.dumps(user.metadata)
                ))
                conn.commit()
        except Exception as e:
            print(f"[UserManager] Error saving user {user.user_id}: {e}")

    def _load_user_from_db(self, user_id: str) -> Optional[User]:
        """从数据库加载用户"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT * FROM users WHERE user_id = ?", (user_id,)
                )
                row = cursor.fetchone()
                if row:
                    user_data = {
                        "user_id": row[0],
                        "username": row[1],
                        "created_at": row[2],
                        "last_active": row[3],
                        "status": row[4],
                        "metadata": row[5]
                    }
                    user = User.from_dict(user_data)
                    self._users[user_id] = user
                    return user
        except Exception as e:
            print(f"[UserManager] Error loading user {user_id}: {e}")
        return None

    async def _save_memory_to_db_async(self, memory: ConversationMemory) -> None:
        """异步保存记忆到数据库"""
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, self._save_memory_to_db, memory
            )
        except Exception as e:
            print(f"[UserManager] Error saving memory async: {e}")

    def _save_memory_to_db(self, memory: ConversationMemory) -> None:
        """保存记忆到数据库"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO memories 
                    (user_id, memory_type, data, created_at, last_updated)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    memory.user_id,
                    memory.memory_type.value,
                    json.dumps(memory.to_dict()),
                    memory.created_at.isoformat(),
                    memory.last_updated.isoformat()
                ))
                conn.commit()
        except Exception as e:
            print(f"[UserManager] Error saving memory: {e}")

    def _load_memory_from_db(self, user_id: str, memory_type: MemoryType) -> None:
        """从数据库加载记忆"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT data FROM memories WHERE user_id = ? AND memory_type = ?",
                    (user_id, memory_type.value)
                )
                row = cursor.fetchone()
                if row:
                    memory_data = json.loads(row[0])
                    memory = ConversationMemory.from_dict(memory_data)
                    
                    if memory_type == MemoryType.GENERAL:
                        self._general_memory = memory
                    else:
                        self._personal_memories[user_id] = memory
        except Exception as e:
            print(f"[UserManager] Error loading memory {user_id}/{memory_type}: {e}")

    def _start_cleanup_task(self) -> None:
        """启动后台清理任务"""
        def cleanup_worker():
            while True:
                try:
                    # 每小时执行一次清理
                    time.sleep(3600)
                    self._cleanup_inactive_users()
                except Exception as e:
                    print(f"[UserManager] Cleanup error: {e}")

        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()

    def _cleanup_inactive_users(self) -> None:
        """清理非活跃用户"""
        threshold = datetime.now() - self.inactive_threshold
        inactive_users = []
        
        with self._user_lock:
            for user_id, user in self._users.items():
                if user.last_active < threshold and user.status == UserStatus.ACTIVE:
                    inactive_users.append(user_id)
        
        for user_id in inactive_users:
            # 将用户标记为非活跃，但不删除记忆
            if user_id in self._users:
                self._users[user_id].status = UserStatus.INACTIVE
                self._save_user_to_db(self._users[user_id])

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._user_lock, self._memory_lock:
            active_count = sum(
                1 for user in self._users.values() 
                if user.status == UserStatus.ACTIVE
            )
            
            return {
                "total_users": len(self._users),
                "active_users": active_count,
                "personal_memories": len(self._personal_memories),
                "general_messages": len(self._general_memory.messages) if self._general_memory else 0,
                "db_path": str(self.db_path)
            }

    async def close(self) -> None:
        """关闭用户管理器"""
        print("[UserManager] Shutting down...")
        
        # 保存所有内存中的数据
        with self._memory_lock:
            if self._general_memory:
                self._save_memory_to_db(self._general_memory)
            
            for memory in self._personal_memories.values():
                self._save_memory_to_db(memory)
        
        with self._user_lock:
            for user in self._users.values():
                self._save_user_to_db(user)
        
        print("[UserManager] Shutdown complete.") 