from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph

# 初始化聊天模型
model = ChatOpenAI(model="gpt-4o-mini")

# 设置 LangGraph 流程
workflow = StateGraph(state_schema=MessagesState)


# 设置消息修剪策略（仅保留最近 5 条消息）
def trim_messages(messages, max_length=5):
    return messages[-max_length:]


# 定义模型调用函数，包含消息修剪和自动记忆
def call_model(state: MessagesState):
    system_prompt = "You are an AI assistant. Keep track of previous conversations."
    messages = [SystemMessage(content=system_prompt)] + trim_messages(state["messages"], max_length=5)
    response = model.invoke(messages)
    return {"messages": response}


# 添加节点和边
workflow.add_node("model", call_model)
workflow.add_edge(START, "model")

# 启用持久化记忆
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)


# 运行 Chatbot
def chatbot(user_input, thread_id="1"):
    response = app.invoke(
        {"messages": [HumanMessage(content=user_input)]},
        config={"configurable": {"thread_id": thread_id}}
    )
    return response["messages"][-1].content


# 示例使用
if __name__ == "__main__":
    print("Chatbot Initialized! Type 'exit' to quit.")
    thread_id = "chat-1"
    while True:
        user_input = input("You: ")
        if user_input.lower() == "exit":
            break
        response = chatbot(user_input, thread_id=thread_id)
        print(f"Bot: {response}")
