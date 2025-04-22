import sqlite3
from datetime import datetime
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_core.messages import HumanMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from typing import Sequence, Dict, Any
from src.chatbot.model_loader import MODEL_REGISTRY
from src.prompt.templates.general import general_settings_prompt
from src.memory.long_term.elastic_search import LongTermMemoryES
from src.tts.tts_stream import tts_streaming
from src.chatbot.config import Config
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
        self.ltm = LongTermMemoryES(persist=True)
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

        memory_docs = self.ltm.retrieve(msg, k=self.cfg.max_hits)
        memory_text = "\n\n".join([
            f"[score={doc['score']}] {doc['content']}" for doc in memory_docs
        ])
        memory_prefix = f"{self.long_term_memory_prefix}:\n{memory_text}" if memory_text else ""

        prompt_template = ChatPromptTemplate.from_messages([
            ("system", memory_prefix + "\n\n" + general_settings_prompt),
            MessagesPlaceholder(variable_name="history"),
            MessagesPlaceholder(variable_name="messages"),
        ])

        rendered_prompt = prompt_template.invoke({
            "language": state["language"],
            "user_info": ", ".join(f"{k}: {v}" for k, v in memory["user_info"].items()) or "N/A",
            "history": history,
            "messages": [HumanMessage(content=msg)],
        })

        response = self.model.invoke(rendered_prompt)
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
        }
        result = self.workflow.invoke(initial_state, {"configurable": {"thread_id": f"persistent_{user_id}"}})
        return result["messages"][-1].content


if __name__ == '__main__':
    cfg = Config(
        # model_name="chatgpt-4o-latest",
        model_name="gpt-4.1",
        temperature=0.2,
        max_tokens=500,
        top_k=10,
        top_p=0.95,
        score_threshold=0.7,
        max_hits=2,
        chat_with=1
    )
    engine = MemoryChatEngine(cfg)
    I_said = ""
    response = engine.chat("random_kokasdkfn1", I_said, language="English")
    tts_streaming(response)
