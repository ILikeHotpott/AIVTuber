import sqlite3
from datetime import datetime
from typing import Sequence, Dict, Any

from PIL import Image
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver

from src.chatbot.model_loader import MODEL_REGISTRY
from src.prompt.templates.general import general_settings_prompt
from src.prompt.roles.vision import vision_prompt
from src.memory.long_term.elastic_search import LongTermMemoryES
from src.vision.llm_proxy import _encode_img
from src.chatbot.config import Config

load_dotenv()


# ---------------------------------------------------------------------------
# State schemas
# ---------------------------------------------------------------------------
class ChatMemory(Dict[str, Any]):
    conversation_history: list[BaseMessage]
    user_info: Dict[str, Any]
    last_interaction: str


class ChatState(Dict[str, Any]):
    messages: Sequence[BaseMessage]
    user_id: str
    language: str
    images: list[str]  # base64 screenshots
    memory: Dict[str, ChatMemory]


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
class MemoryChatEngine:
    """Handles both text‑only and multimodal queries with short/long memory."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.model = self._load_model()
        self.ltm = LongTermMemoryES(persist=True, threshold=cfg.score_threshold)
        self._long_prefix_header = "（我记得这些事好像在哪里听过，也许能用上...）\n"

        self.text_prompt = self._init_text_prompt()  # pure‑text pathway
        self.checkpointer = self._init_checkpointer()
        self.workflow = self._build_chatbot()

    # ---------------- Init helpers ----------------
    def _load_model(self):
        loader_cls = MODEL_REGISTRY[self.cfg.model_name.lower()]
        return loader_cls(self.cfg.model_name).load(
            temperature=self.cfg.temperature,
            max_tokens=self.cfg.max_tokens,
            top_k=self.cfg.top_k,
            top_p=self.cfg.top_p,
        )

    def _build_system_text(self, memory_prefix: str = "") -> str:
        """Persona + scene rules + optional long‑term memory prefix."""
        scene_rule = vision_prompt  # 已含≤40字等指令
        return f"{memory_prefix}{general_settings_prompt}{scene_rule}"

    def _init_text_prompt(self):
        return ChatPromptTemplate.from_messages([
            ("system", self._build_system_text()),
            MessagesPlaceholder("history"),
            MessagesPlaceholder("messages"),
        ])

    def _init_checkpointer(self):
        try:
            conn = sqlite3.connect(self.cfg.db_path, check_same_thread=False)
            return SqliteSaver(conn)
        except Exception as exc:
            print("⚠ SQLite unavailable, using in‑memory checkpoints:", exc)
            return MemorySaver()

    # ---------------- Graph nodes ----------------
    def _retrieve_memory(self, state: ChatState) -> ChatState:
        uid = state["user_id"]
        mem = state.setdefault("memory", {})
        if uid not in mem:
            mem[uid] = {
                "conversation_history": [],
                "user_info": {},
                "last_interaction": datetime.now().isoformat(),
            }
        mem[uid]["last_interaction"] = datetime.now().isoformat()
        return state

    def _process_message(self, state: ChatState) -> ChatState:
        uid = state["user_id"]
        msg = state["messages"][-1].content.lower()
        if "my name is" in msg:
            name = msg.split("my name is")[1].strip().split()[0].capitalize()
            state["memory"][uid]["user_info"]["name"] = name
        return state

    def _generate_response(self, state: ChatState) -> ChatState:
        uid = state["user_id"]
        mem = state["memory"][uid]
        history = mem["conversation_history"]
        last_msg = state["messages"][-1].content
        images = state.get("images", [])

        # ----- Long‑term memory retrieval -----
        long_prefix = ""
        if getattr(self.cfg, "use_long_term", True):
            docs = self.ltm.retrieve(last_msg, k=self.cfg.max_hits)
            if docs:
                body = "\n\n".join(f"[{d['score']:.2f}] {d['content']}" for d in docs)
                long_prefix = f"{self._long_prefix_header}{body}\n\n"

        # ----- Build content parts -----
        parts = [{"type": "text", "text": self._build_system_text(long_prefix)}]
        if last_msg:
            parts.append({"type": "text", "text": last_msg})
        for url in images:
            parts.append({"type": "image_url", "image_url": url})

        response = self.model.invoke([HumanMessage(content=parts)])

        # ----- Update short‑term memory -----
        history.extend(state["messages"])
        history.append(response)
        return {"messages": [response]}

    # ---------------- LangGraph ----------------
    def _build_chatbot(self):
        g = StateGraph(state_schema=ChatState)
        g.add_node("retrieve_memory", self._retrieve_memory)
        g.add_node("process_message", self._process_message)
        g.add_node("generate_response", self._generate_response)
        g.add_edge(START, "retrieve_memory")
        g.add_edge("retrieve_memory", "process_message")
        g.add_edge("process_message", "generate_response")
        g.add_edge("generate_response", END)
        return g.compile(checkpointer=self.checkpointer)

    # ---------------- Public APIs ----------------
    def chat(self, user_id: str, message: str, language: str = "Chinese") -> str:
        init = {
            "messages": [HumanMessage(content=message)],
            "user_id": user_id,
            "language": language,
        }
        res = self.workflow.invoke(init, {"configurable": {"thread_id": f"persist_{user_id}"}})
        return res["messages"][-1].content

    def chat_with_screen(self, user_id: str, image: Image.Image, extra_text: str = "",
                         language: str = "Chinese") -> str:
        data_url = _encode_img(image)
        init = {
            "messages": [HumanMessage(content=extra_text)],
            "user_id": user_id,
            "language": language,
            "images": [data_url],
        }
        res = self.workflow.invoke(init, {"configurable": {"thread_id": f"persist_{user_id}"}})
        return res["messages"][-1].content


# ---------------------------------------------------------------------------
# CLI quick‑test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from src.tts.tts_stream import tts_streaming

    cfg = Config(
        model_name="gpt-4o",
        temperature=0.4,
        max_tokens=256,
        top_k=10,
        top_p=0.95,
        score_threshold=0.65,
        max_hits=2,
        chat_with=1,
        use_long_term=True,
    )
    engine = MemoryChatEngine(cfg)
    reply = engine.chat("demo", "弹幕：你最喜欢的食物是什么？")
    print("LLM:", reply)
    tts_streaming(reply)
