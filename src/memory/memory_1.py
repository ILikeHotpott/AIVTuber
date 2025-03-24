import sqlite3
from typing import Sequence, List, Dict, Any

from typing_extensions import Annotated, TypedDict
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    BaseMessage,
)
from langchain_sambanova import ChatSambaNovaCloud
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import START, StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph.message import add_messages

from src.tts.tts_stream import response_to_speech_streaming, clean_text
from src.tts.tts_opt.tts2 import tts_in_chunks

# 1. 初始化聊天模型
model = ChatSambaNovaCloud(
    model="DeepSeek-R1",
    max_tokens=400,
    temperature=0.8,
    top_k=50,
    top_p=1,
)


# model = ChatOpenAI(
#     model="gpt-4o"
# )


# 2. 定义聊天状态
class ChatMemory(TypedDict):
    conversation_history: List[BaseMessage]  # 完整对话历史
    user_info: Dict[str, Any]  # 用户信息
    last_interaction: str  # 上次互动时间


class ChatState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]  # 当前消息
    user_id: str
    language: str
    memory: Dict[str, ChatMemory]


# TODO: 需要修改，不用sqlite，而是vectordb
try:
    conn = sqlite3.connect("chat_memory.db", check_same_thread=False)
    memory_saver = SqliteSaver(conn)
    print("Using SqliteSaver for checkpointing...")
except Exception as e:
    print(f"无法创建 SqliteSaver，回退到内存存储: {e}")
    memory_saver = MemorySaver()

# 4. 创建聊天提示模板
system_prompt = """
你是一个女主播名叫Seranion，我希望你用最自然语言对话，不要用奇怪的形容
语言平常，你现在需要回复弹幕，
回复稍微短一些就行, 每次输入的话一样也不要回复一样的东西, 以第一人称视角回复
"""

prompt_template = ChatPromptTemplate.from_messages(
    [
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="history"),
        MessagesPlaceholder(variable_name="messages"),
    ]
)


# 5. 定义节点函数
#
# 5.1 获取用户记忆
def retrieve_memory(state: ChatState) -> ChatState:
    user_id = state["user_id"]

    # 如果是新用户，创建新的记忆
    if user_id not in state["memory"]:
        state["memory"][user_id] = ChatMemory(
            conversation_history=[],
            user_info={},
            last_interaction=datetime.now().isoformat()
        )

    # 更新最后交互时间
    state["memory"][user_id]["last_interaction"] = datetime.now().isoformat()

    return state


# TODO: 处理用户消息（在回复消息之后，进行异步处理）
# 5.2 处理用户消息
def process_message(state: ChatState) -> ChatState:
    user_id = state["user_id"]
    current_message = state["messages"][-1].content if state["messages"] else ""

    # 简单的信息提取 (在实际应用中可以更复杂)
    if "my name is" in current_message.lower():
        name = current_message.lower().split("my name is")[1].strip().split()[0].capitalize()
        state["memory"][user_id]["user_info"]["name"] = name

    return state


# 5.3 生成回复
def generate_response(state: ChatState) -> ChatState:
    user_id = state["user_id"]
    user_memory = state["memory"][user_id]

    user_info_str = ", ".join([f"{k}: {v}" for k, v in user_memory["user_info"].items()])
    if not user_info_str:
        user_info_str = "No specific information yet"

    history = user_memory["conversation_history"]

    prompt = prompt_template.invoke({
        "language": state["language"],
        "user_info": user_info_str,
        "history": history,
        "messages": state["messages"]
    })

    response = model.invoke(prompt)

    # 更新对话历史
    user_memory["conversation_history"].extend(state["messages"])  # 添加用户消息
    user_memory["conversation_history"].append(response)  # 添加AI回复

    return {"messages": [response]}


# 6. 构建工作流
def build_chatbot():
    workflow = StateGraph(state_schema=ChatState)

    # 添加节点
    workflow.add_node("retrieve_memory", retrieve_memory)
    workflow.add_node("process_message", process_message)
    workflow.add_node("generate_response", generate_response)

    # 连接节点
    workflow.add_edge(START, "retrieve_memory")
    workflow.add_edge("retrieve_memory", "process_message")
    workflow.add_edge("process_message", "generate_response")
    workflow.add_edge("generate_response", END)

    # 编译 - 使用持久化存储
    return workflow.compile(checkpointer=memory_saver)


# 7. 创建应用
chatbot = build_chatbot()


# 8. 简化的API调用函数
def chat(user_id: str, message: str, language: str = "English"):
    # 使用固定的thread_id确保每次程序执行都能找回正确的会话
    config = {"configurable": {"thread_id": f"persistent_{user_id}"}}

    # 初始化状态
    state = {
        "messages": [HumanMessage(message)],
        "user_id": user_id,
        "language": language,
        "memory": {}
    }
    result = chatbot.invoke(state, config)
    return result["messages"][-1].content


# 10. 流式响应API
def chat_stream(user_id: str, message: str, language: str = "English"):
    config = {"configurable": {"thread_id": f"persistent_{user_id}"}}

    state = {
        "messages": [HumanMessage(message)],
        "user_id": user_id,
        "language": language,
        "memory": {}  # 会在workflow中被填充
    }

    # 流式输出
    for chunk, metadata in chatbot.stream(
            state, config, stream_mode="messages"
    ):
        if isinstance(chunk, AIMessage):
            yield chunk.content


def chat_with_memory_and_extra_prompt(memory_config: str, extra_prompt: str):
    extra_prompt += "。 "
    print(f"用户1: {extra_prompt}")
    response = chat(memory_config, extra_prompt, language="Chinese")
    print(f"AI: {response}")
    # tts_in_chunks(response)


if __name__ == "__main__":
    # prompt = "主播叫什么名字"
    # prompt += "。"
    # response1 = chat("user_15", prompt, language="Chinese")
    # tts_in_chunks(response1)
    chat_with_memory_and_extra_prompt("user_16", "你好呀")
