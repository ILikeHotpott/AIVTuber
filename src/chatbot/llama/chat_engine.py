"""
Realtime LangGraph chat engine —— 带 ElasticSearch 长记忆检索 + Unity 口型同步 TTS。
依赖:
  • src/tts/tts_player.py      (提供 TTSPlayer / TTSConfig)
  • src/memory/long_term/...   (可选)
  • src/prompt/templates/...   (系统提示词)
  • src/user/user_manager.py   (新增：用户管理)
作者: Yitong  · 2025-05-31
"""

from __future__ import annotations

import asyncio
import os
import re
import sqlite3
import threading
from datetime import datetime
from typing import Annotated, Any, Dict, List, Sequence, TypedDict, Optional

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from src.tts.tts_player import TTSPlayer
from src.tts.tts_config import TTSConfig

from src.utils.path import find_project_root

# ═══════════════ 新增：用户管理集成 ═══════════════
from src.danmaku.user.user_manager import UserManager

# ───────── Optional project imports ─────────
try:
    from src.memory.long_term.elastic_search import LongTermMemoryES
    from src.prompt.templates.general import general_settings_prompt_english
except ModuleNotFoundError:
    LongTermMemoryES = None  # noqa: N816
    general_settings_prompt_english = "You are a helpful assistant."

# ═══════════════ 新增：集成多用户聊天服务 ═══════════════
from src.chatbot.services.multi_user_chat_service import (
    MultiUserChatService,
    ChatRequest, 
    ChatResponse,
    ChatServiceMode,
    create_multi_user_chat_service
)
from src.prompt.providers.prompt_provider import SecurityLevel

# ╭───────────────────── 环境配置 ─────────────────────╮
load_dotenv()
BASE_DIR = find_project_root()
DB_PATH = BASE_DIR / "src" / "runtime" / "chat" / "chat_memory.db"

OPENAI_BASE = os.getenv("OPENAI_BASE", "http://127.0.0.1:8080/v1")
OPENAI_KEY = os.getenv("OPENAI_KEY", "sk-fake-key")
MODEL_NAME = os.getenv("MODEL_NAME", "Gemma3")

USE_LTM = os.getenv("USE_LTM", "true").lower() not in {"0", "false", "no"}
LTM_SCORE_THRESHOLD = float(os.getenv("LTM_SCORE_THRESHOLD", 0.65))
LTM_MAX_HITS = int(os.getenv("LTM_MAX_HITS", 3))
# ╰────────────────────────────────────────────────────╯

# ═══════════════ 修改：支持用户管理模式 ═══════════════
USE_USER_MANAGER = os.getenv("USE_USER_MANAGER", "true").lower() not in {"0", "false", "no"}

# ═══════════════ 修改：支持多用户聊天服务模式 ═══════════════
USE_MULTI_USER_SERVICE = os.getenv("USE_MULTI_USER_SERVICE", "true").lower() not in {"0", "false", "no"}

# ╭───────────────────── Prompt / Regex ─────────────────────╮
_LONG_PREFIX_HEADER = "（我记得这些事好像在哪里听过，也许能用上...）\n"

_BOUNDARY_RE = re.compile(
    r"""
    [。！？；!?]            |   # CJK 句末
    ([.!?])(?=\s|$)            # 英文句末
    """,
    re.X,
)

_ABBR = {"Mr", "Mrs", "Ms", "Dr", "Prof", "Sr", "Jr", "St"}


# ───────── 类型定义 ─────────
class ChatMemory(TypedDict):
    conversation_history: List[BaseMessage]
    user_info: Dict[str, Any]
    last_interaction: str


class ChatState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_id: str
    language: str
    # ═══════════════ 修改：兼容旧版本记忆系统 ═══════════════
    memory: Dict[str, ChatMemory]  # 保持向后兼容


class ChatEngine:
    """LangGraph + TTSPlayer 实时对话引擎（线程/协程安全单例）"""

    _instance: "ChatEngine | None" = None
    _instance_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        raise RuntimeError("Use ChatEngine.get_instance() instead.")

    @classmethod
    def get_instance(cls, connect_to_unity: bool = False, use_user_manager: bool = None) -> "ChatEngine":
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_once(
                    connect_to_unity=connect_to_unity,
                    use_user_manager=use_user_manager if use_user_manager is not None else USE_USER_MANAGER
                )
            return cls._instance

    # ───── 私有初始化 ─────
    def _init_once(self, connect_to_unity: bool = False, use_user_manager: bool = True):
        print(f"[ChatEngine] Initializing (connect_to_unity={connect_to_unity}, use_user_manager={use_user_manager})")

        # ═══════════════ 新增：多用户聊天服务集成 ═══════════════
        self.use_multi_user_service = USE_MULTI_USER_SERVICE
        if self.use_multi_user_service:
            self.multi_user_service = create_multi_user_chat_service(
                mode="hybrid",
                character_name="default",
                security_level="high"
            )
        else:
            self.multi_user_service = None

        # ═══════════════ 修改：用户管理器集成 ═══════════════
        self.use_user_manager = use_user_manager
        if self.use_user_manager and not self.use_multi_user_service:
            # 如果使用多用户服务，UserManager已经集成在服务中
            self.user_manager = UserManager()
        else:
            self.user_manager = None
            # 保持旧版本的内存管理方式
            self._memory: Dict[str, ChatMemory] = {}
            self._memory_lock = threading.RLock()

        # TTS player & 队列
        self._tts_player = TTSPlayer(TTSConfig(connect_to_unity=connect_to_unity))
        self._speak_q: "queue.Queue[str]" = __import__("queue").Queue()
        self._start_tts_thread()

        # LLM
        # self._llm = ChatOpenAI(
        #     openai_api_base=OPENAI_BASE,
        #     openai_api_key=OPENAI_KEY,
        #     model_name=MODEL_NAME,
        #     streaming=True,
        # )

        self._llm = ChatOpenAI(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            model_name="chatgpt-4o-latest",
            streaming=True,
        )

        # LTM
        self._ltm = (
            LongTermMemoryES(persist=True, threshold=LTM_SCORE_THRESHOLD)
            if USE_LTM and LongTermMemoryES
            else None
        )

        # Sync checkpointer
        self._sync_db_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        try:
            self._sync_saver = SqliteSaver(self._sync_db_conn)
            print("[Checkpoint-sync] SQLite →", DB_PATH)
        except Exception as exc:  # pragma: no cover
            self._sync_saver = MemorySaver()
            if self._sync_db_conn: # Close if SqliteSaver failed
                self._sync_db_conn.close()
                self._sync_db_conn = None
            print("[Checkpoint-sync] MemorySaver —", exc)

        # Lazy-per-loop async graphs and their savers
        self._loop_graph_components: Dict[int, tuple[StateGraph, AsyncSqliteSaver, Any]] = {} # Stores (graph, saver, conn)
        self._loop_graphs_lock = threading.RLock()

    # ───────── 公共协程入口 ─────────
    async def stream_chat(self, user_id: str, msg: str, language: str = "English") -> str:
        # ═══════════════ 新增：使用多用户聊天服务 ═══════════════
        if self.use_multi_user_service:
            return await self.stream_chat_multi_user(user_id, "", msg, language)
        
        # ═══════════════ 原有逻辑保持不变 ═══════════════
        graph, _, _ = await self._graph_for_loop() # We only need the graph here
        cfg = {"configurable": {"thread_id": f"persistent_{user_id}"}}
        
        # ═══════════════ 修改：支持新旧记忆系统 ═══════════════
        if self.use_user_manager:
            # 使用新的用户管理器
            memory = {}  # 空字典，因为记忆管理已迁移到 UserManager
        else:
            # 使用旧的内存记忆系统
            memory = self._memory
            
        state = {
            "messages": [HumanMessage(content=msg)],
            "user_id": user_id,
            "language": language,
            "memory": memory,
        }
        result = await graph.ainvoke(state, cfg)
        return result["messages"][-1].content

    # ═══════════════ 新增：多用户聊天接口 ═══════════════
    async def stream_chat_multi_user(
        self,
        user_id: str,
        username: str,
        message: str,
        language: str = "中文",
        security_level: SecurityLevel = SecurityLevel.HIGH,
        character_name: Optional[str] = None
    ) -> str:
        """使用新的多用户聊天服务进行对话"""
        if not self.use_multi_user_service or not self.multi_user_service:
            raise RuntimeError("MultiUserChatService is not enabled")
        
        # 创建聊天请求
        request = ChatRequest(
            user_id=user_id,
            username=username or user_id,
            message=message,
            language=language,
            security_level=security_level,
            character_name=character_name
        )
        
        # 处理请求
        response = await self.multi_user_service.process_chat_request(
            request,
            llm_callback=self._llm_callback_for_multi_user
        )
        
        # 处理TTS
        if response.response_message:
            sentences = self._split_into_sentences(response.response_message)
            for sentence in sentences:
                if sentence.strip():
                    self._speak_q.put(sentence.strip())
        
        return response.response_message

    async def _llm_callback_for_multi_user(
        self,
        chat_template: ChatPromptTemplate,
        history: List[BaseMessage],
        messages: List[BaseMessage]
    ) -> str:
        """多用户服务的LLM回调函数"""
        try:
            # 构建prompt
            prompt_obj = chat_template.invoke({
                "history": history,
                "messages": messages
            })

            # 流式生成
            buf = ""
            out_tokens: List[str] = []
            final_content = ""

            async for chunk in self._llm.astream(prompt_obj):
                tok = chunk.content if isinstance(chunk, AIMessage) else chunk.get("content", "")
                print(tok, end="", flush=True)
                buf += tok
                out_tokens.append(tok)

                # 实时TTS处理（如果需要）
                while True:
                    m = _BOUNDARY_RE.search(buf)
                    if not m or self._is_ellipsis(buf, m.start()):
                        break
                    cut = m.end()
                    sent = buf[:cut].strip()
                    if sent:
                        # 注意：这里不直接放入TTS队列，而是在上层处理
                        pass
                    buf = buf[cut:]

            if buf.strip():
                # 同样，这里不直接处理TTS
                pass

            final_content = "".join(out_tokens)

            if not final_content.strip():
                final_content = "抱歉，我没有理解您的意思，能再说一遍吗？"

            return final_content

        except Exception as e:
            print(f"\n[ChatEngine _llm_callback_for_multi_user] Error: {e}")
            return "抱歉，处理您的请求时出现了问题，请稍后再试。"

    # ═══════════════ 新增：多用户服务管理接口 ═══════════════
    def get_multi_user_service(self) -> MultiUserChatService:
        """获取多用户聊天服务实例"""
        if not self.use_multi_user_service or not self.multi_user_service:
            raise RuntimeError("MultiUserChatService is not enabled")
        return self.multi_user_service

    async def get_user_stats(self) -> Dict[str, Any]:
        """获取用户统计信息（集成版本）"""
        if self.use_multi_user_service and self.multi_user_service:
            service_stats = await self.multi_user_service.get_service_stats()
            return {
                "service_type": "multi_user_service",
                "stats": service_stats,
                "tts_queue_size": self._speak_q.qsize(),
                "tts_is_busy": self.tts_is_busy()
            }
        elif self.use_user_manager and self.user_manager:
            user_stats = self.user_manager.get_stats()
            return {
                "service_type": "user_manager",
                "stats": user_stats,
                "tts_queue_size": self._speak_q.qsize(),
                "tts_is_busy": self.tts_is_busy()
            }
        else:
            return {
                "service_type": "legacy",
                "memory_users": len(self._memory) if hasattr(self, '_memory') else 0,
                "tts_queue_size": self._speak_q.qsize(),
                "tts_is_busy": self.tts_is_busy()
            }

    # ═══════════════ 新增：集成接口方法 ═══════════════
    def get_user_manager(self) -> UserManager:
        """获取用户管理器实例"""
        if not self.use_user_manager:
            raise RuntimeError("UserManager is not enabled for this ChatEngine instance")
        return self.user_manager

    def register_user(self, user_id: str, username: str = None, metadata: Dict[str, Any] = None):
        """注册用户（便捷方法）"""
        if self.use_user_manager:
            return self.user_manager.register_user(user_id, username, metadata)
        else:
            # 旧版本兼容
            with self._memory_lock:
                if user_id not in self._memory:
                    self._memory[user_id] = ChatMemory(conversation_history=[], user_info={}, last_interaction="")

    def add_message_to_memories(self, user_id: str, human_msg: BaseMessage, ai_msg: BaseMessage) -> None:
        """添加消息到记忆系统"""
        if self.use_user_manager:
            # 使用新的用户管理器
            self.user_manager.add_message_to_both(user_id, human_msg)
            self.user_manager.add_message_to_both(user_id, ai_msg)
        else:
            # 使用旧的记忆系统
            with self._memory_lock:
                if user_id not in self._memory:
                    self._memory[user_id] = ChatMemory(conversation_history=[], user_info={}, last_interaction="")
                self._memory[user_id]["conversation_history"].extend([human_msg, ai_msg])
                self._memory[user_id]["last_interaction"] = datetime.now().isoformat()

    # ╭───────────────────── 内部：TTS 队列线程 ─────────────────────╮
    def _start_tts_thread(self):
        if hasattr(self, "_tts_thread") and self._tts_thread.is_alive():
            return

        def _worker():
            while True:
                part = self._speak_q.get()
                if part is None:
                    break
                try:
                    self._tts_player.stream(part)
                except Exception as exc:  # pragma: no cover
                    print(f"\n[TTS error] {exc}\n")

        self._tts_thread = threading.Thread(target=_worker, daemon=True)
        self._tts_thread.start()

    def _retrieve_memory(self, state: ChatState) -> ChatState:
        uid = state["user_id"]
        
        # ═══════════════ 修改：支持新旧记忆系统 ═══════════════
        if self.use_user_manager:
            # 确保用户已注册
            self.user_manager.register_user(uid)
            self.user_manager.update_user_activity(uid)
        else:
            # 使用旧的记忆系统
            with self._memory_lock:
                if uid not in self._memory:
                    self._memory[uid] = ChatMemory(conversation_history=[], user_info={}, last_interaction="")
                self._memory[uid]["last_interaction"] = datetime.now().isoformat()
                
        return state

    @staticmethod
    def _process_message(state: ChatState) -> ChatState:
        uid = state["user_id"]
        txt = state["messages"][-1].content.lower()
        
        # ═══════════════ 修改：这个方法在新系统中可能需要重构 ═══════════════
        # 简单的名字提取逻辑保持不变，但存储方式需要适配
        if "my name is" in txt:
            name = txt.split("my name is", 1)[1].strip().split()[0].capitalize()
            # 在新系统中，这个信息会通过 UserManager 存储
            if hasattr(state, 'memory') and uid in state["memory"]:
                state["memory"][uid]["user_info"]["name"] = name
                
        return state

    async def _gen_response(self, state: ChatState) -> ChatState:  # noqa: C901
        uid = state["user_id"]
        
        # ═══════════════ 修改：记忆获取逻辑 ═══════════════
        if self.use_user_manager:
            # 使用新的用户管理器获取记忆
            personal_memory = self.user_manager.get_personal_memory(uid)
            general_memory = self.user_manager.get_general_memory()
            conversation_history = personal_memory.get_recent_messages(limit=50) if personal_memory else []
        else:
            # 使用旧的记忆系统
            mem = state["memory"][uid]
            conversation_history = mem["conversation_history"]

        # ---------- LTM ----------
        prefix = ""
        if self._ltm and state["messages"]:
            q = state["messages"][-1].content
            docs = self._ltm.retrieve(q, k=LTM_MAX_HITS)
            if docs:
                body = "\n\n".join(f"[{d['score']:.2f}] {d['content']}" for d in docs)
                prefix = f"{_LONG_PREFIX_HEADER}{body}\n\n"

        prompt_obj = ChatPromptTemplate.from_messages(
            [
                ("system", f"{prefix}{general_settings_prompt_english}"),
                MessagesPlaceholder("history"),
                MessagesPlaceholder("messages"),
            ]
        ).invoke(
            {"history": conversation_history, "messages": state["messages"]}
        )

        buf = ""
        out_tokens: List[str] = []
        final_content = ""  # Initialize final_content

        try:
            async for chunk in self._llm.astream(prompt_obj):
                tok = chunk.content if isinstance(chunk, AIMessage) else chunk.get("content", "")
                print(tok, end="", flush=True)
                buf += tok
                out_tokens.append(tok)

                while True:
                    m = _BOUNDARY_RE.search(buf)
                    if not m or self._is_ellipsis(buf, m.start()):
                        break
                    cut = m.end()
                    sent = buf[:cut].strip()
                    if sent:
                        self._speak_q.put(sent)
                    buf = buf[cut:]
            
            if buf.strip():
                self._speak_q.put(buf.strip())
            
            final_content = "".join(out_tokens)

            # If after a successful stream, the content is empty/whitespace, provide a fallback.
            if not final_content.strip():
                print("\n[ChatEngine] LLM stream completed but resulted in empty/whitespace content. Using fallback.")
                final_content = "I'm sorry, I didn't quite understand. Could you say that again?"
                self._speak_q.put(final_content) # Send fallback to TTS

        except Exception as e:
            # Catch any exception during the streaming process
            print(f"\n[ChatEngine _gen_response] Error during LLM stream: {type(e).__name__}: {e}")
            # Provide a fallback response if an error occurs
            final_content = "I encountered an issue while processing your request. Please try again."
            self._speak_q.put(final_content) # Send fallback to TTS
            # The exception 'e' is not re-raised, allowing graph execution to continue with fallback content.

        ai_msg = AIMessage(content=final_content)
        
        # ═══════════════ 修改：消息保存逻辑 ═══════════════
        if self.use_user_manager:
            # 使用新的用户管理器保存消息
            human_msg = state["messages"][-1]  # 当前的人类消息
            self.user_manager.add_message_to_both(uid, human_msg)
            self.user_manager.add_message_to_both(uid, ai_msg)
        else:
            # 使用旧的记忆系统
            mem = state["memory"][uid]
            mem["conversation_history"].extend(state["messages"])
            mem["conversation_history"].append(ai_msg)
            
        return {"messages": [ai_msg]}

    # ───────── Graph cache per-loop ─────────
    async def _graph_for_loop(self) -> tuple[StateGraph, AsyncSqliteSaver, Any]: # Return tuple
        loop_id = id(asyncio.get_running_loop())
        with self._loop_graphs_lock:
            if loop_id in self._loop_graph_components:
                return self._loop_graph_components[loop_id]

        import aiosqlite # Import here as it's an async context

        conn = None
        saver = None
        try:
            conn = await aiosqlite.connect(DB_PATH)
            saver = AsyncSqliteSaver(conn)
            print(f"[Checkpoint-async] SQLite aio → {DB_PATH} (loop {loop_id})")
        except Exception as exc:  # pragma: no cover
            if conn: # Close connection if AsyncSqliteSaver failed
                await conn.close()
            conn = None
            saver = MemorySaver() # Fallback to MemorySaver
            print("[Checkpoint-async] MemorySaver —", exc)

        g = StateGraph(state_schema=ChatState)
        g.add_node("retrieve_memory", self._retrieve_memory)
        g.add_node("process_message", self._process_message)
        g.add_node("generate_response", self._gen_response)
        g.add_edge(START, "retrieve_memory")
        g.add_edge("retrieve_memory", "process_message")
        g.add_edge("process_message", "generate_response")
        g.add_edge("generate_response", END)
        graph = g.compile(checkpointer=saver)

        with self._loop_graphs_lock:
            # Store graph, saver, and connection for later cleanup
            self._loop_graph_components[loop_id] = (graph, saver, conn)
            return graph, saver, conn

    # ───────── Utils ─────────
    @staticmethod
    def _is_ellipsis(txt: str, idx: int) -> bool:
        return txt[idx] == "." and idx >= 2 and txt[idx - 2: idx + 1] == "..."

    async def close(self): # Make close async
        self._speak_q.put(None)
        if hasattr(self, "_tts_thread"):
            self._tts_thread.join()
        self._tts_player.close()

        # Close synchronous checkpointer connection
        if isinstance(self._sync_saver, SqliteSaver) and self._sync_db_conn:
            self._sync_db_conn.close()
            print("[Checkpoint-sync] SQLite connection closed.")
        
        # Close asynchronous checkpointer connections
        with self._loop_graphs_lock:
            for graph, saver, conn in self._loop_graph_components.values():
                if isinstance(saver, AsyncSqliteSaver) and conn:
                    try:
                        await conn.close() # Close the aiosqlite connection directly
                        print(f"[Checkpoint-async] SQLite aio connection closed for loop {id(graph)}.")
                    except Exception as e:
                        print(f"[Checkpoint-async] Error closing SQLite aio connection: {e}")
            self._loop_graph_components.clear()

        # ═══════════════ 新增：关闭用户管理器 ═══════════════
        if self.use_user_manager and self.user_manager:
            await self.user_manager.close()

    def tts_is_busy(self) -> bool:
        return self._tts_player.is_busy()

    def speech_queue_empty(self) -> bool:
        return self._speak_q.empty()

    def is_speaking(self) -> bool:
        """检查 TTS 是否正在说话或队列中是否有待处理的语音。"""
        return not self._speak_q.empty() or self._tts_player.is_busy()


# cli quick test
async def _cli():
    eng = ChatEngine.get_instance(connect_to_unity=False)
    print("💬  Real-time voice chat — 输入文字 (quit/exit 退出)\n")
    try:
        while True:
            inp = input("👤 > ").strip()
            if inp.lower() in {"quit", "exit"}:
                break
            if not inp:
                continue
            await eng.stream_chat("demo_user60", inp, language="English")
            print()
    finally:
        await eng.close()


if __name__ == "__main__":
    asyncio.run(_cli())
