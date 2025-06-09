import asyncio
import os
import queue
import re
import sqlite3
import threading
from datetime import datetime
from typing import Annotated, Any, Dict, List, Sequence, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from src.prompt.builders.prompt_builder_config import PromptBuilderConfig
from src.tts.tts_player import TTSPlayer
from src.tts.tts_config import TTSConfig
from src.memory.long_term.elastic_search import LongTermMemoryES
from src.prompt.templates.general import general_settings_prompt_english

from src.prompt.builders.prompt_builder import PromptBuilder
from src.prompt.builders.base import PromptContext, DialogueActor

from src.utils.path import find_project_root

# Config
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
    memory: Dict[str, ChatMemory]


class ChatEngine:
    """LangGraph + TTSPlayer 实时对话引擎（线程/协程安全单例）"""

    _instance: "ChatEngine | None" = None
    _instance_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        raise RuntimeError("Use ChatEngine.get_instance() instead.")

    @classmethod
    def get_instance(cls, talk_to: DialogueActor, connect_to_unity: bool = False) -> "ChatEngine":
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_once(talk_to=talk_to, connect_to_unity=connect_to_unity)
            return cls._instance

    # ───── 私有初始化 ─────
    def _init_once(self, talk_to: DialogueActor, connect_to_unity: bool = False):
        print(f"[ChatEngine] Initializing (connect_to_unity={connect_to_unity})")

        # chat memory (进程内)
        self._memory: Dict[str, ChatMemory] = {}
        self._memory_lock = threading.RLock()
        self.dialogue_actor = talk_to

        # TTS player & 队列
        self._tts_player = TTSPlayer(TTSConfig(connect_to_unity=connect_to_unity))
        self._speak_q: "queue.Queue[str]" = __import__("queue").Queue()
        self._start_tts_thread()

        # Prompt Builder
        self.prompt_builder_config = PromptBuilderConfig(dialogue_actor=DialogueActor.AUDIENCE)
        self.prompt_builder = PromptBuilder(self.prompt_builder_config)
        self.context = PromptContext()
        self.system_msg = self.prompt_builder.create_system_message(self.context)

        self._llm = self._init_llm()

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
            if self._sync_db_conn:  # Close if SqliteSaver failed
                self._sync_db_conn.close()
                self._sync_db_conn = None
            print("[Checkpoint-sync] MemorySaver —", exc)

        # Lazy-per-loop async graphs and their savers
        self._loop_graph_components: Dict[
            int, tuple[StateGraph, AsyncSqliteSaver, Any]] = {}  # Stores (graph, saver, conn)
        self._loop_graphs_lock = threading.RLock()

    # ───────── 公共协程入口 ─────────
    async def stream_chat(self, user_id: str, msg: str, language: str = "English") -> str:
        graph, _, _ = await self._graph_for_loop()  # We only need the graph here
        cfg = {"configurable": {"thread_id": f"persistent_{user_id}"}}
        state = {
            "messages": [HumanMessage(content=msg)],
            "user_id": user_id,
            "language": language,
            "memory": self._memory,
        }
        result = await graph.ainvoke(state, cfg)
        return result["messages"][-1].content

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

    def _init_llm(self):
        if self.dialogue_actor == DialogueActor.AUDIENCE:
            # when talking to audience, use local llama cpp
            return ChatOpenAI(
                openai_api_base=OPENAI_BASE,
                openai_api_key=OPENAI_KEY,
                model_name=MODEL_NAME,
                streaming=True,
            )
        else:
            # when talking to whisper or hybrid, using high speed api
            return ChatOpenAI(
                openai_api_key=os.getenv("OPENAI_API_KEY"),
                model_name="chatgpt-4o-latest",
                streaming=True,
            )

    # LangGraph 节点
    def _retrieve_memory(self, state: ChatState) -> ChatState:
        uid = state["user_id"]
        with self._memory_lock:
            if uid not in self._memory:
                self._memory[uid] = ChatMemory(conversation_history=[], user_info={}, last_interaction="")
            self._memory[uid]["last_interaction"] = datetime.now().isoformat()
        return state

    @staticmethod
    def _process_message(state: ChatState) -> ChatState:
        uid = state["user_id"]
        txt = state["messages"][-1].content.lower()
        if "my name is" in txt:
            name = txt.split("my name is", 1)[1].strip().split()[0].capitalize()
            state["memory"][uid]["user_info"]["name"] = name
        return state

    async def _gen_response(self, state: ChatState) -> ChatState:  # noqa: C901
        uid = state["user_id"]
        mem = state["memory"][uid]

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
            {"history": mem["conversation_history"], "messages": state["messages"]}
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
                self._speak_q.put(final_content)  # Send fallback to TTS

        except Exception as e:
            # Catch any exception during the streaming process
            print(f"\n[ChatEngine _gen_response] Error during LLM stream: {type(e).__name__}: {e}")
            # Provide a fallback response if an error occurs
            final_content = "I encountered an issue while processing your request. Please try again."
            self._speak_q.put(final_content)  # Send fallback to TTS
            # The exception 'e' is not re-raised, allowing graph execution to continue with fallback content.

        ai_msg = AIMessage(content=final_content)
        mem["conversation_history"].extend(state["messages"])
        mem["conversation_history"].append(ai_msg)
        return {"messages": [ai_msg]}

    # ───────── Graph cache per-loop ─────────
    async def _graph_for_loop(self) -> tuple[StateGraph, AsyncSqliteSaver, Any]:  # Return tuple
        loop_id = id(asyncio.get_running_loop())
        with self._loop_graphs_lock:
            if loop_id in self._loop_graph_components:
                return self._loop_graph_components[loop_id]

        import aiosqlite  # Import here as it's an async context

        conn = None
        saver = None
        try:
            conn = await aiosqlite.connect(DB_PATH)
            saver = AsyncSqliteSaver(conn)
            print(f"[Checkpoint-async] SQLite aio → {DB_PATH} (loop {loop_id})")
        except Exception as exc:  # pragma: no cover
            if conn:  # Close connection if AsyncSqliteSaver failed
                await conn.close()
            conn = None
            saver = MemorySaver()  # Fallback to MemorySaver
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

    async def close(self):  # Make close async
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
                        await conn.close()  # Close the aiosqlite connection directly
                        print(f"[Checkpoint-async] SQLite aio connection closed for loop {id(graph)}.")
                    except Exception as e:
                        print(f"[Checkpoint-async] Error closing SQLite aio connection: {e}")
            self._loop_graph_components.clear()

    def tts_is_busy(self) -> bool:
        return self._tts_player.is_busy()

    def speech_queue_empty(self) -> bool:
        return self._speak_q.empty()

    def is_speaking(self) -> bool:
        """检查 TTS 是否正在说话或队列中是否有待处理的语音。"""
        return not self._speak_q.empty() or self._tts_player.is_busy()


# cli quick test
async def _cli():
    eng = ChatEngine.get_instance(talk_to=DialogueActor.WHISPER, connect_to_unity=True)
    print(" Real-time voice chat — please input words (quit/exit 退出)\n")
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
