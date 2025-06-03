"""
企业级聊天模式管理器 - 负责多种聊天模式的统一管理
支持实时聊天、弹幕聊天和混合模式，以及消息优先级处理
作者: Yitong · 2025-01-XX
"""

from __future__ import annotations

import asyncio
import os
import queue
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, IntEnum
from typing import Any, Callable, Dict, List, Optional, Union
from abc import ABC, abstractmethod

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_openai import ChatOpenAI

from src.danmaku.user.user_manager import UserManager
from src.asr.asr_engine import ASREngine
from src.asr.asr_config import ASRConfig

# 尝试导入 LlamaCpp（可选依赖）
try:
    from langchain_community.llms import LlamaCpp
    LLAMACPP_AVAILABLE = True
except ImportError:
    LlamaCpp = None
    LLAMACPP_AVAILABLE = False

# 加载环境变量
load_dotenv()


class ChatMode(Enum):
    """聊天模式枚举"""
    REALTIME = "realtime"          # 实时语音聊天（ASR + API）
    DANMAKU = "danmaku"           # 弹幕聊天（本地 LlamaCpp）
    HYBRID = "hybrid"             # 混合模式（ASR 优先 + 弹幕）


class MessagePriority(IntEnum):
    """消息优先级（数值越小优先级越高）"""
    ASR_URGENT = 0      # ASR 紧急消息
    ASR_NORMAL = 1      # ASR 普通消息
    DANMAKU_VIP = 5     # VIP 弹幕
    DANMAKU_NORMAL = 10 # 普通弹幕
    SYSTEM = 99         # 系统消息


class MessageSource(Enum):
    """消息来源枚举"""
    ASR = "asr"
    DANMAKU = "danmaku"
    SYSTEM = "system"


@dataclass
class ChatMessage:
    """聊天消息数据类"""
    content: str
    user_id: str
    source: MessageSource
    priority: MessagePriority
    timestamp: datetime = field(default_factory=datetime.now)
    username: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __lt__(self, other: "ChatMessage") -> bool:
        """用于优先级队列排序"""
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.timestamp < other.timestamp


class LLMBackend(ABC):
    """LLM 后端抽象基类"""
    
    @abstractmethod
    async def generate_response(
        self, 
        messages: List[BaseMessage], 
        stream: bool = False
    ) -> Union[str, AsyncIterator[str]]:
        """生成回复"""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """关闭后端"""
        pass


class OpenAIBackend(LLMBackend):
    """OpenAI API 后端"""
    
    def __init__(self, api_key: str = None, base_url: str = None, model: str = "chatgpt-4o-latest"):
        self.client = ChatOpenAI(
            openai_api_key=api_key or os.getenv("OPENAI_API_KEY"),
            openai_api_base=base_url,
            model_name=model,
            streaming=True,
            timeout=30,
            max_retries=3
        )
    
    async def generate_response(
        self, 
        messages: List[BaseMessage], 
        stream: bool = False
    ) -> Union[str, AsyncIterator[str]]:
        if stream:
            return self._stream_response(messages)
        else:
            response = await self.client.ainvoke(messages)
            return response.content
    
    async def _stream_response(self, messages: List[BaseMessage]):
        async for chunk in self.client.astream(messages):
            if hasattr(chunk, 'content') and chunk.content:
                yield chunk.content
    
    async def close(self) -> None:
        # OpenAI client 通常不需要显式关闭
        pass


class LlamaCppBackend(LLMBackend):
    """LlamaCpp 本地后端"""
    
    def __init__(self, model_path: str, **kwargs):
        if not LLAMACPP_AVAILABLE:
            raise ImportError("LlamaCpp not available. Install langchain-community.")
        
        default_params = {
            "temperature": 0.7,
            "max_tokens": 2048,
            "top_p": 0.9,
            "n_ctx": 4096,
            "n_threads": 4,
            "verbose": False
        }
        default_params.update(kwargs)
        
        self.client = LlamaCpp(
            model_path=model_path,
            **default_params
        )
    
    async def generate_response(
        self, 
        messages: List[BaseMessage], 
        stream: bool = False
    ) -> Union[str, AsyncIterator[str]]:
        # 将消息转换为字符串格式
        prompt = self._messages_to_prompt(messages)
        
        if stream:
            return self._stream_response(prompt)
        else:
            # 在线程池中运行同步调用
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, self.client, prompt)
            return response
    
    def _messages_to_prompt(self, messages: List[BaseMessage]) -> str:
        """将消息列表转换为提示词格式"""
        prompt_parts = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                prompt_parts.append(f"Human: {msg.content}")
            elif isinstance(msg, AIMessage):
                prompt_parts.append(f"Assistant: {msg.content}")
        prompt_parts.append("Assistant:")
        return "\n".join(prompt_parts)
    
    async def _stream_response(self, prompt: str):
        # LlamaCpp 的流式响应需要特殊处理
        loop = asyncio.get_event_loop()
        
        def generate():
            for chunk in self.client.stream(prompt):
                return chunk
        
        response = await loop.run_in_executor(None, generate)
        # 简化版本，实际实现可能需要更复杂的流式处理
        yield response
    
    async def close(self) -> None:
        # LlamaCpp 可能需要清理资源
        if hasattr(self.client, 'close'):
            self.client.close()


class DanmakuListener:
    """弹幕监听器抽象类"""
    
    def __init__(self, callback: Callable[[ChatMessage], None]):
        self.callback = callback
        self._running = False
        self._thread: Optional[threading.Thread] = None
    
    def start(self) -> None:
        """开始监听弹幕"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        print("[DanmakuListener] Started.")
    
    def stop(self) -> None:
        """停止监听弹幕"""
        if not self._running:
            return
        
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("[DanmakuListener] Stopped.")
    
    def _listen_loop(self) -> None:
        """弹幕监听循环（模拟实现）"""
        # 这里是一个模拟实现，实际需要接入真实的弹幕 API
        while self._running:
            try:
                # 模拟接收弹幕
                time.sleep(5)  # 模拟延迟
                
                # 创建模拟弹幕消息
                message = ChatMessage(
                    content="这是一条模拟弹幕消息",
                    user_id=f"danmaku_user_{int(time.time())}",
                    source=MessageSource.DANMAKU,
                    priority=MessagePriority.DANMAKU_NORMAL,
                    username="模拟用户"
                )
                
                if self.callback:
                    self.callback(message)
                    
            except Exception as e:
                print(f"[DanmakuListener] Error: {e}")
                time.sleep(1)


class ChatModeManager:
    """
    企业级聊天模式管理器
    负责处理多种聊天模式、消息优先级和不同 LLM 后端
    """
    
    def __init__(
        self,
        user_manager: UserManager,
        mode: ChatMode = ChatMode.HYBRID,
        realtime_backend: Optional[LLMBackend] = None,
        danmaku_backend: Optional[LLMBackend] = None
    ):
        self.user_manager = user_manager
        self.mode = mode
        
        # LLM 后端配置
        self.realtime_backend = realtime_backend or self._create_default_openai_backend()
        self.danmaku_backend = danmaku_backend or self._create_default_llamacpp_backend()
        
        # 消息队列（优先级队列）
        self.message_queue: queue.PriorityQueue[ChatMessage] = queue.PriorityQueue()
        
        # ASR 引擎
        self.asr_engine: Optional[ASREngine] = None
        self.asr_config = ASRConfig(debug=False)
        
        # 弹幕监听器
        self.danmaku_listener: Optional[DanmakuListener] = None
        
        # 控制变量
        self._running = False
        self._processing_thread: Optional[threading.Thread] = None
        self._asr_thread: Optional[threading.Thread] = None
        
        # 统计信息
        self.stats = {
            "asr_messages": 0,
            "danmaku_messages": 0,
            "processed_messages": 0,
            "start_time": None
        }
        
        # 回调函数
        self.response_callback: Optional[Callable[[str, ChatMessage], None]] = None
        
        # 线程安全
        self._stats_lock = threading.Lock()
        
        print(f"[ChatModeManager] Initialized with mode: {mode.value}")
    
    def _create_default_openai_backend(self) -> LLMBackend:
        """创建默认的 OpenAI 后端"""
        return OpenAIBackend()
    
    def _create_default_llamacpp_backend(self) -> Optional[LLMBackend]:
        """创建默认的 LlamaCpp 后端"""
        model_path = os.getenv("LLAMACPP_MODEL_PATH")
        if model_path and os.path.exists(model_path) and LLAMACPP_AVAILABLE:
            try:
                return LlamaCppBackend(model_path)
            except Exception as e:
                print(f"[ChatModeManager] Failed to load LlamaCpp: {e}")
        return None
    
    def set_response_callback(
        self, 
        callback: Callable[[str, ChatMessage], None]
    ) -> None:
        """设置响应回调函数"""
        self.response_callback = callback
    
    def start(self) -> None:
        """启动聊天模式管理器"""
        if self._running:
            print("[ChatModeManager] Already running.")
            return
        
        self._running = True
        self.stats["start_time"] = datetime.now()
        
        # 启动消息处理线程
        self._processing_thread = threading.Thread(
            target=self._message_processing_loop, 
            daemon=True
        )
        self._processing_thread.start()
        
        # 根据模式启动相应的输入源
        if self.mode in [ChatMode.REALTIME, ChatMode.HYBRID]:
            self._start_asr()
        
        if self.mode in [ChatMode.DANMAKU, ChatMode.HYBRID]:
            self._start_danmaku_listener()
        
        print(f"[ChatModeManager] Started in {self.mode.value} mode.")
    
    def stop(self) -> None:
        """停止聊天模式管理器"""
        if not self._running:
            return
        
        print("[ChatModeManager] Stopping...")
        self._running = False
        
        # 停止输入源
        if self.asr_engine:
            self.asr_engine.stop()
        
        if self.danmaku_listener:
            self.danmaku_listener.stop()
        
        # 等待处理线程结束
        if self._processing_thread:
            # 发送停止信号
            stop_message = ChatMessage(
                content="__STOP__",
                user_id="__SYSTEM__",
                source=MessageSource.SYSTEM,
                priority=MessagePriority.SYSTEM
            )
            self.message_queue.put(stop_message)
            self._processing_thread.join(timeout=5)
        
        print("[ChatModeManager] Stopped.")
    
    def _start_asr(self) -> None:
        """启动 ASR 引擎"""
        if self.asr_engine is None:
            self.asr_engine = ASREngine(self.asr_config)
        
        # 启动 ASR 监听线程
        self._asr_thread = threading.Thread(target=self._asr_loop, daemon=True)
        self._asr_thread.start()
        
        self.asr_engine.start()
        print("[ChatModeManager] ASR started.")
    
    def _start_danmaku_listener(self) -> None:
        """启动弹幕监听器"""
        self.danmaku_listener = DanmakuListener(self._on_danmaku_message)
        self.danmaku_listener.start()
        print("[ChatModeManager] Danmaku listener started.")
    
    def _asr_loop(self) -> None:
        """ASR 消息循环"""
        while self._running and self.asr_engine:
            try:
                text = self.asr_engine.get_text(timeout=1.0)
                if text:
                    message = ChatMessage(
                        content=text,
                        user_id="asr_user",  # 可以根据需要区分不同的 ASR 用户
                        source=MessageSource.ASR,
                        priority=MessagePriority.ASR_NORMAL,
                        username="语音用户"
                    )
                    self._add_message(message)
                    
                    with self._stats_lock:
                        self.stats["asr_messages"] += 1
                        
            except Exception as e:
                if self._running:  # 只在运行时记录错误
                    print(f"[ChatModeManager] ASR loop error: {e}")
                time.sleep(0.1)
    
    def _on_danmaku_message(self, message: ChatMessage) -> None:
        """处理弹幕消息"""
        self._add_message(message)
        
        with self._stats_lock:
            self.stats["danmaku_messages"] += 1
    
    def _add_message(self, message: ChatMessage) -> None:
        """添加消息到队列"""
        # 在混合模式下，如果正在处理 ASR 消息，暂停其他消息
        if (self.mode == ChatMode.HYBRID and 
            message.source != MessageSource.ASR and 
            self._is_asr_active()):
            # 延迟处理非 ASR 消息
            message.priority = MessagePriority(message.priority.value + 1)
        
        self.message_queue.put(message)
        print(f"[ChatModeManager] Message added: {message.source.value} - {message.content[:50]}...")
    
    def _is_asr_active(self) -> bool:
        """检查 ASR 是否活跃（简化实现）"""
        # 这里可以实现更复杂的 ASR 活跃检测逻辑
        return self.asr_engine and not self.message_queue.empty()
    
    def _message_processing_loop(self) -> None:
        """消息处理主循环"""
        while self._running:
            try:
                # 获取优先级最高的消息
                message = self.message_queue.get(timeout=1.0)
                
                # 检查停止信号
                if message.content == "__STOP__":
                    break
                
                # 处理消息
                asyncio.run(self._process_message(message))
                
                with self._stats_lock:
                    self.stats["processed_messages"] += 1
                    
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[ChatModeManager] Processing error: {e}")
    
    async def _process_message(self, message: ChatMessage) -> None:
        """处理单个消息"""
        try:
            # 选择合适的后端
            backend = self._select_backend(message)
            if not backend:
                print(f"[ChatModeManager] No backend available for {message.source.value}")
                return
            
            # 获取用户记忆
            personal_memory = self.user_manager.get_personal_memory(message.user_id)
            general_memory = self.user_manager.get_general_memory()
            
            # 构建对话历史
            messages = self._build_conversation_history(message, personal_memory, general_memory)
            
            # 生成回复
            response = await backend.generate_response(messages, stream=False)
            
            # 保存到记忆
            human_msg = HumanMessage(content=message.content)
            ai_msg = AIMessage(content=response)
            
            self.user_manager.add_message_to_both(message.user_id, human_msg)
            self.user_manager.add_message_to_both(message.user_id, ai_msg)
            
            # 更新用户活跃度
            self.user_manager.update_user_activity(message.user_id)
            
            # 调用回调函数
            if self.response_callback:
                self.response_callback(response, message)
            
            print(f"[ChatModeManager] Response generated for {message.user_id}: {response[:100]}...")
            
        except Exception as e:
            print(f"[ChatModeManager] Error processing message from {message.user_id}: {e}")
    
    def _select_backend(self, message: ChatMessage) -> Optional[LLMBackend]:
        """根据消息来源选择后端"""
        if message.source == MessageSource.ASR:
            return self.realtime_backend
        elif message.source == MessageSource.DANMAKU:
            return self.danmaku_backend or self.realtime_backend
        else:
            return self.realtime_backend
    
    def _build_conversation_history(
        self, 
        current_message: ChatMessage,
        personal_memory: Optional[Any],
        general_memory: Optional[Any]
    ) -> List[BaseMessage]:
        """构建对话历史"""
        messages = []
        
        # 添加系统提示
        system_prompt = self._get_system_prompt(current_message)
        if system_prompt:
            messages.append(HumanMessage(content=system_prompt))
        
        # 添加相关的历史消息
        if personal_memory:
            recent_personal = personal_memory.get_recent_messages(limit=10)
            messages.extend(recent_personal)
        
        # 添加当前消息
        messages.append(HumanMessage(content=current_message.content))
        
        return messages
    
    def _get_system_prompt(self, message: ChatMessage) -> str:
        """获取系统提示"""
        base_prompt = "你是一个友好的虚拟主播助手。请用自然、亲切的语气回复用户。"
        
        if message.source == MessageSource.ASR:
            return f"{base_prompt} 这是来自语音的实时消息，请简洁回复。"
        elif message.source == MessageSource.DANMAKU:
            return f"{base_prompt} 这是来自弹幕的消息，可以活泼一些回复。"
        else:
            return base_prompt
    
    def add_danmaku_message(
        self, 
        content: str, 
        user_id: str, 
        username: str = "",
        is_vip: bool = False
    ) -> None:
        """手动添加弹幕消息（用于外部接口）"""
        priority = MessagePriority.DANMAKU_VIP if is_vip else MessagePriority.DANMAKU_NORMAL
        
        message = ChatMessage(
            content=content,
            user_id=user_id,
            source=MessageSource.DANMAKU,
            priority=priority,
            username=username
        )
        
        self._add_message(message)
    
    def add_asr_message(self, content: str, user_id: str = "asr_user") -> None:
        """手动添加 ASR 消息（用于测试）"""
        message = ChatMessage(
            content=content,
            user_id=user_id,
            source=MessageSource.ASR,
            priority=MessagePriority.ASR_NORMAL,
            username="语音用户"
        )
        
        self._add_message(message)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._stats_lock:
            stats = self.stats.copy()
        
        if stats["start_time"]:
            runtime = datetime.now() - stats["start_time"]
            stats["runtime_seconds"] = runtime.total_seconds()
        
        stats.update({
            "mode": self.mode.value,
            "queue_size": self.message_queue.qsize(),
            "running": self._running,
            "asr_active": self.asr_engine is not None,
            "danmaku_active": self.danmaku_listener is not None
        })
        
        return stats
    
    async def close(self) -> None:
        """关闭管理器"""
        self.stop()
        
        # 关闭后端
        if self.realtime_backend:
            await self.realtime_backend.close()
        
        if self.danmaku_backend:
            await self.danmaku_backend.close()
        
        print("[ChatModeManager] Closed.") 