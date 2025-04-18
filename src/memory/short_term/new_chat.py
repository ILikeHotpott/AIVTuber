import sqlite3
from typing import Sequence, List, Dict, Any

from typing_extensions import Annotated, TypedDict
from datetime import datetime

from langchain_core.messages import (
    HumanMessage,
    BaseMessage,
)
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import START, StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph.message import add_messages
from src.prompt.templates.general import general_settings_prompt
from src.utils.path import find_project_root
from src.tts.tts_stream import tts_streaming
from src.memory.long_term.graph_rag.retriever_chain import retrieve_long_term_memory

from src.chatbot import model_loader
from dotenv import load_dotenv

load_dotenv()


class ChatMemory(TypedDict):
    conversation_history: List[BaseMessage]  # 完整对话历史
    user_info: Dict[str, Any]  # 用户信息
    last_interaction: str  # 上次互动时间


class ChatState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]  # 当前消息
    user_id: str
    language: str
    memory: Dict[str, ChatMemory]


class MemoryChatEngine:
    def __init__(
            self,
            model_name: str = "DeepSeek-R1",
            temperature: float = 0.5,
            max_tokens: int = 400,
            top_k: int = 10,
            top_p: float = 0.95,
            chat_with: int = 1,
    ):
        self.model_name = model_name
        self.model_config = {
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_k": top_k,
            "top_p": top_p
        }
        self.model = self._get_model_instance()
        self.db_path = find_project_root() / "src" / "runtime" / "chat" / "chat_memory.db"
        self.chat_with = 1
        self.prompt_template = self._init_prompt()
        self.checkpointer = self._init_checkpointer()
        self.chatbot = self._build_chatbot()
        self.long_term_memory_prefix = "（我记得这些事好像在哪里听过，也许能用上...）"

    def _get_model_instance(self):
        from src.chatbot.base import MODEL_REGISTRY
        key = self.model_name.lower()
        if key not in MODEL_REGISTRY:
            raise ValueError(f"Unsupported model: {self.model_name}")
        loader_cls = MODEL_REGISTRY[key]
        return loader_cls(self.model_name).load(**self.model_config)

    def _init_prompt(self):
        from src.prompt.templates.general import general_settings_prompt

        prompt_mapping = {
            1: general_settings_prompt,
        }

        system_prompt = prompt_mapping.get(self.chat_with)
        if not system_prompt:
            raise ValueError(f"Unsupported chat_with mode: {self.chat_with}. Must be 1, 2, or 3")

        return ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="history"),
            MessagesPlaceholder(variable_name="messages"),
        ])

    def _init_checkpointer(self):
        try:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            print("Using SqliteSaver for checkpointing...")
            return SqliteSaver(conn)
        except Exception as e:
            print(f"Unable to use SqliteSaver, falling back to MemorySaver: {e}")
            return MemorySaver()

    def _retrieve_memory(self, state: ChatState) -> ChatState:
        user_id = state["user_id"]
        if user_id not in state["memory"]:
            state["memory"][user_id] = ChatMemory(
                conversation_history=[],
                user_info={},
                last_interaction=datetime.now().isoformat()
            )
        state["memory"][user_id]["last_interaction"] = datetime.now().isoformat()
        return state

    def _process_message(self, state: ChatState) -> ChatState:
        user_id = state["user_id"]
        current_message = state["messages"][-1].content if state["messages"] else ""
        if "my name is" in current_message.lower():
            name = current_message.lower().split("my name is")[1].strip().split()[0].capitalize()
            state["memory"][user_id]["user_info"]["name"] = name
        return state

    def _generate_response(self, state: ChatState) -> ChatState:
        user_id = state["user_id"]
        user_memory = state["memory"][user_id]

        # 获取用户信息
        user_info_str = ", ".join([f"{k}: {v}" for k, v in user_memory["user_info"].items()])
        if not user_info_str:
            user_info_str = "No specific information yet"

        history = user_memory["conversation_history"]
        user_message = state["messages"][-1].content

        # ⏳ 获取长期记忆
        long_term_context = retrieve_long_term_memory().invoke(user_message)

        # ✅ 构造 messages: [长期记忆提示, 用户问题]
        message_list = []
        if long_term_context.strip():  # 有内容再添加
            memory_msg = f"{self.long_term_memory_prefix}：\n{long_term_context}"
            message_list.append(HumanMessage(content=memory_msg))

        # 用户输入
        message_list.append(HumanMessage(content=user_message))

        # 🔁 构造 Prompt
        prompt = self.prompt_template.invoke({
            "language": state["language"],
            "user_info": user_info_str,
            "history": history,
            "messages": message_list,
        })

        # 🧠 模型生成回复
        response = self.model.invoke(prompt)

        # 📝 更新短期记忆
        user_memory["conversation_history"].extend(state["messages"])
        user_memory["conversation_history"].append(response)

        return {"messages": [response]}

    def _build_chatbot(self):
        workflow = StateGraph(state_schema=ChatState)
        workflow.add_node("retrieve_memory", self._retrieve_memory)
        workflow.add_node("process_message", self._process_message)
        workflow.add_node("generate_response", self._generate_response)
        workflow.add_edge(START, "retrieve_memory")
        workflow.add_edge("retrieve_memory", "process_message")
        workflow.add_edge("process_message", "generate_response")
        workflow.add_edge("generate_response", END)
        return workflow.compile(checkpointer=self.checkpointer)

    def chat(self, user_id: str, message: str, language: str = "English") -> str:
        config = {"configurable": {"thread_id": f"persistent_{user_id}"}}
        state = {
            "messages": [HumanMessage(message)],
            "user_id": user_id,
            "language": language,
            "memory": {}
        }
        result = self.chatbot.invoke(state, config)
        return result["messages"][-1].content

    def chat_with_memory(self, user_id: str, message: str, with_tts: bool = True):
        print(f"User: {message}")
        response = self.chat(user_id, message, language="Chinese")
        print(f"AI: {response}")
        if with_tts:
            tts_streaming(response)


if __name__ == "__main__":
    engine = MemoryChatEngine(model_name="DeepSeek-R1", chat_with=1)
    engine.chat_with_memory("random_123123", "主播觉得全世界最帅的男人是谁")
