#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
memory_chat_stream_tts.py — 2025-05-28 (strict-sentence-boundary)
────────────────────────────────────────────────────────────
• 完全依赖句末标点才播报，绝不在句中断句
• 支持 Elasticsearch-based **长记忆检索**（--no-ltm 关闭）
• 其余流式分句 + TTS 逻辑与旧版一致
"""

from __future__ import annotations

import os, re, queue, sqlite3, threading, time, asyncio, argparse
from datetime import datetime
from typing import Annotated, Dict, List, Sequence, Any, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langgraph.graph import START, END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from src.prompt.templates.general import general_settings_prompt
from src.memory.long_term.elastic_search import LongTermMemoryES
from src.tts.tts_stream import tts_streaming
from src.utils.path import find_project_root

# ───────── CLI & Config ─────────
config = {"use_ltm": True}
parser = argparse.ArgumentParser(description="Realtime chat + TTS (with long-term memory)")
parser.add_argument("--no-ltm", action="store_true", help="disable Elasticsearch long-term memory")
args, _ = parser.parse_known_args()
if args.no_ltm:
    config["use_ltm"] = False

load_dotenv()
BASE_DIR = find_project_root()
DB_PATH = BASE_DIR / "src" / "runtime" / "chat" / "chat_memory.db"
USE_LONG_TERM = config.get("use_ltm", True)

# ───────── LLM ─────────
model = ChatOpenAI(
    openai_api_base="http://127.0.0.1:8080/v1",
    openai_api_key="sk-fake-key",
    model_name="llama",
    streaming=True,
)

# ───────── 长记忆检索器 ─────────
_long_prefix_header = "（我记得这些事好像在哪里听过，也许能用上...）\n"
ltm = (
    LongTermMemoryES(persist=True, threshold=float(os.getenv("LTM_SCORE_THRESHOLD", 0.65)))
    if USE_LONG_TERM
    else None
)
MAX_HITS = int(os.getenv("LTM_MAX_HITS", 3))


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


# ───────── Checkpointer (sync) ─────────
try:
    _sync_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    _sync_saver = SqliteSaver(_sync_conn)
    print("[Checkpoint-sync] SQLite ->", DB_PATH)
except Exception as e:
    print("[Checkpoint-sync] fallback MemorySaver —", e)
    _sync_saver = MemorySaver()


# ───────── Prompt builder helper ─────────
def build_prompt_template(memory_prefix: str = "") -> ChatPromptTemplate:
    system_text = f"{memory_prefix}{general_settings_prompt}"
    return ChatPromptTemplate.from_messages(
        [
            ("system", system_text),
            MessagesPlaceholder("history"),
            MessagesPlaceholder("messages"),
        ]
    )


_BOUNDARY_RE = re.compile(
    r"""
    [。！？；]                              # 中文句末
    |
    ([.!?])(?=\s|$)                         # 英文句末候选（但不排除缩写）
    """,
    re.X
)

# 英文缩写列表（用于后处理）
_ABBR = {"Mr", "Mrs", "Ms", "Dr", "Prof", "Sr", "Jr", "St"}

_speak_q: queue.Queue[str] = queue.Queue()


def _is_ellipsis(txt: str, idx: int) -> bool:
    return txt[idx] == "." and idx >= 2 and txt[idx - 2: idx + 1] == "..."


def _tts_worker():
    while True:
        part = _speak_q.get()
        if part is None:
            break
        try:
            tts_streaming(part)
        except Exception as e:
            print(f"\n[TTS error] {e}\n")


_tts_thread = threading.Thread(target=_tts_worker, daemon=True)
_tts_thread.start()


# ───────── LangGraph 节点 ─────────
def _retrieve_memory(state: ChatState) -> ChatState:
    uid = state["user_id"]
    mem = state.setdefault("memory", {})
    if uid not in mem:
        mem[uid] = ChatMemory(conversation_history=[], user_info={}, last_interaction="")
    mem[uid]["last_interaction"] = datetime.now().isoformat()
    return state


def _process_message(state: ChatState) -> ChatState:
    uid = state["user_id"]
    txt = state["messages"][-1].content.lower()
    if "my name is" in txt:
        name = txt.split("my name is", 1)[1].strip().split()[0].capitalize()
        state["memory"][uid]["user_info"]["name"] = name
    return state


async def _generate_response_stream(state: ChatState) -> ChatState:
    uid = state["user_id"]
    mem = state["memory"][uid]

    # ----- long-term memory -----
    memory_prefix = ""
    if ltm and state["messages"]:
        query = state["messages"][-1].content
        docs = ltm.retrieve(query, k=MAX_HITS)
        if docs:
            body = "\n\n".join(f"[{d['score']:.2f}] {d['content']}" for d in docs)
            memory_prefix = f"{_long_prefix_header}{body}\n\n"

    prompt_tmpl = build_prompt_template(memory_prefix)
    prompt = prompt_tmpl.invoke(
        {
            "history": mem["conversation_history"],
            "messages": state["messages"],
        }
    )

    buf = ""
    tokens = []

    async for chunk in model.astream(prompt):
        tok = chunk.content if isinstance(chunk, AIMessage) else chunk.get("content", "")
        print(tok, end="", flush=True)
        buf += tok
        tokens.append(tok)

        # 只在真正句末标点处分句
        while True:
            m = _BOUNDARY_RE.search(buf)
            if not m or _is_ellipsis(buf, m.start()):
                break
            cut = m.end()
            sent = buf[:cut].strip()
            if sent:
                _speak_q.put(sent)
            buf = buf[cut:]

    # flush 余下残句
    if buf.strip():
        _speak_q.put(buf.strip())

    full_msg = AIMessage(content="".join(tokens))
    mem["conversation_history"].extend(state["messages"])
    mem["conversation_history"].append(full_msg)
    return {"messages": [full_msg]}


# ───────── Build graph helper ─────────
def _build_graph(checkpointer):
    g = StateGraph(state_schema=ChatState)
    g.add_node("retrieve_memory", _retrieve_memory)
    g.add_node("process_message", _process_message)
    g.add_node("generate_response", _generate_response_stream)
    g.add_edge(START, "retrieve_memory")
    g.add_edge("retrieve_memory", "process_message")
    g.add_edge("process_message", "generate_response")
    g.add_edge("generate_response", END)
    return g.compile(checkpointer=checkpointer)


# ───────── Async graph cache per-loop ─────────
_graph_cache: Dict[int, StateGraph] = {}


async def _graph_for_current_loop() -> StateGraph:
    loop_id = id(asyncio.get_running_loop())
    if loop_id in _graph_cache:
        return _graph_cache[loop_id]

    import aiosqlite

    try:
        conn = await aiosqlite.connect(DB_PATH)
        saver = AsyncSqliteSaver(conn)
        print(f"[Checkpoint-async] SQLite aio -> {DB_PATH} (loop {loop_id})")
    except Exception as e:
        print("[Checkpoint-async] fallback MemorySaver —", e)
        saver = MemorySaver()

    g = _build_graph(saver)
    _graph_cache[loop_id] = g
    return g


# ───────── Public entry point ─────────
async def stream_chat(user_id: str, msg: str, language: str = "English") -> str:
    graph = await _graph_for_current_loop()
    cfg = {"configurable": {"thread_id": f"persistent_{user_id}"}}
    state = {
        "messages": [HumanMessage(content=msg)],
        "user_id": user_id,
        "language": language,
        "memory": {},
    }
    result = await graph.ainvoke(state, cfg)
    return result["messages"][-1].content


# ───────── CLI interface ─────────
async def main():
    print("💬 Real-time voice chat — type something (type 'quit' to exit)\n")
    try:
        while True:
            inp = input("👤 > ").strip()
            if inp.lower() in {"quit", "exit"}:
                break
            if not inp:
                continue
            await stream_chat("demo_user3", inp, language="Chinese")
            print()
    finally:
        # 确保 TTS 线程优雅退出
        _speak_q.put(None)
        _tts_thread.join()


# ───────── Entrypoint ─────────
if __name__ == "__main__":
    asyncio.run(main())
