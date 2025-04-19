import sqlite3
from datetime import datetime
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_core.messages import HumanMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.vectorstores.utils import filter_complex_metadata

from typing import Sequence, Dict, Any
from src.chatbot.model_loader import MODEL_REGISTRY
from src.memory.long_term.ltm import LongTermMemory
from src.chatbot.config import Config
from langchain_openai import OpenAIEmbeddings
from langchain_chroma.vectorstores import Chroma
from dotenv import load_dotenv

load_dotenv()


class ChatMemory(Dict[str, Any]):
    conversation_history: list[BaseMessage]
    user_info: Dict[str, Any]
    last_interaction: str


class ChatState(Dict[str, Any]):
    messages: Sequence[BaseMessage]
    user_id: str
    language: str
    memory: Dict[str, ChatMemory]


class MemoryChatEngine:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.model = self._load_model()
        self.ltm = self._init_ltm()
        self.prompt = self._init_prompt()
        self.checkpointer = self._init_checkpointer()
        self.workflow = self._build_chatbot()
        self.long_term_memory_prefix = "（我记得这些事好像在哪里听过，也许能用上...）"

    def _load_model(self):
        loader_cls = MODEL_REGISTRY[self.cfg.model_name.lower()]
        return loader_cls(self.cfg.model_name).load(
            temperature=self.cfg.temperature,
            max_tokens=self.cfg.max_tokens,
            top_k=self.cfg.top_k,
            top_p=self.cfg.top_p,
        )

    def _init_ltm(self):
        from src.memory.long_term.memory_documents import docs
        docs_cleaned = filter_complex_metadata(docs)
        vector_store = Chroma.from_documents(
            documents=docs_cleaned,
            embedding=OpenAIEmbeddings(),
            collection_name="creator_roast_memory"
        )
        return LongTermMemory(vector_store, score_threshold=self.cfg.score_threshold, max_hits=self.cfg.max_hits)

    def _init_prompt(self):
        from src.prompt.templates.general import general_settings_prompt
        return ChatPromptTemplate.from_messages([
            ("system", general_settings_prompt),
            MessagesPlaceholder(variable_name="history"),
            MessagesPlaceholder(variable_name="messages"),
        ])

    def _init_checkpointer(self):
        try:
            conn = sqlite3.connect(self.cfg.db_path, check_same_thread=False)
            return SqliteSaver(conn)
        except Exception as exc:
            print("⚠️ SQLite unavailable, using in‑memory checkpoints:", exc)
            return MemorySaver()

    def _retrieve_memory(self, state: ChatState) -> ChatState:
        user_id = state["user_id"]
        memory = state.setdefault("memory", {})
        if user_id not in memory:
            memory[user_id] = {
                "conversation_history": [],
                "user_info": {},
                "last_interaction": datetime.now().isoformat()
            }
        memory[user_id]["last_interaction"] = datetime.now().isoformat()
        return state

    def _process_message(self, state: ChatState) -> ChatState:
        user_id = state["user_id"]
        msg = state["messages"][-1].content.lower()
        if "my name is" in msg:
            name = msg.split("my name is")[1].strip().split()[0].capitalize()
            state["memory"][user_id]["user_info"]["name"] = name
        return state

    def _generate_response(self, state: ChatState) -> ChatState:
        uid = state["user_id"]
        memory = state["memory"][uid]
        history = memory["conversation_history"]
        msg = state["messages"][-1].content
        ltm_text = self.ltm.retrieve(msg)
        msg_list = []
        if ltm_text:
            msg_list.append(HumanMessage(content=f"{self.long_term_memory_prefix}:\n{ltm_text}"))
        msg_list.append(HumanMessage(content=msg))
        prompt = self.prompt.invoke({
            "language": state["language"],
            "user_info": ", ".join(f"{k}: {v}" for k, v in memory["user_info"].items()) or "N/A",
            "history": history,
            "messages": msg_list,
        })
        response = self.model.invoke(prompt)
        history.extend(state["messages"])
        history.append(response)
        return {"messages": [response]}

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

    def chat(self, user_id: str, message: str, language: str = "English") -> str:
        initial_state = {
            "messages": [HumanMessage(content=message)],
            "user_id": user_id,
            "language": language,
            "memory": {},
        }
        result = self.workflow.invoke(initial_state, {"configurable": {"thread_id": f"persistent_{user_id}"}})
        return result["messages"][-1].content


if __name__ == '__main__':
    cfg = Config(
        model_name="gpt-4o",  # 支持：gpt-4o, gpt-4.1, deepseek-chat, DeepSeek-R1 等
        temperature=0.7,
        max_tokens=500,
        top_k=10,
        top_p=0.95,
        score_threshold=0.7,  # 设置向量相似度检索的阈值
        max_hits=2,  # 每轮检索最多返回几个记忆片段
        chat_with=1  # 选择使用哪一个 prompt 模板（目前仅支持 general_settings_prompt）
    )
    engine = MemoryChatEngine(cfg)
    response = engine.chat("user_123", "你的创造者是谁", language="Chinese")
    print("AI:", response)
