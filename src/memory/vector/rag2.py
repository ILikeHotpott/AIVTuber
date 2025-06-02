import os
from langchain_sambanova import ChatSambaNovaCloud
from typing_extensions import TypedDict
from langchain import hub
from langchain_openai import OpenAIEmbeddings
from langchain.chat_models import init_chat_model
from langchain_milvus import Milvus
from langchain_text_splitters import CharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from langgraph.graph import START, StateGraph, MessagesState, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool
from dotenv import load_dotenv

load_dotenv()

os.environ["LANGSMITH_TRACING"] = "true"
os.environ["LANGSMITH_API_KEY"] = os.getenv("LANGSMITH_API_KEY")

llm = ChatSambaNovaCloud(
    model="Llama-3.2-11B-Vision-Instruct",
    max_tokens=500,
    temperature=0.9,
    top_k=50,
    top_p=1,
)
#
# llm = init_chat_model("gpt-4o-mini", model_provider="openai")

embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

URI = "./milvus_example.db"
vector_store = Milvus(
    embedding_function=embeddings,
    connection_args={"uri": URI},
    index_params={"index_type": "HNSW", "metric_type": "L2"},
    auto_id=True
)


def rebuild_index():
    """
    修改索引文件的时候需要执行，先要把db文件删除再执行这个函数
    """
    documents = TextLoader(file_path="./txts/What_I_Said_Before.txt").load()
    text_splitter = CharacterTextSplitter(separator="\n", chunk_size=512, chunk_overlap=100)
    all_splits = text_splitter.split_documents(documents)

    vector_store.add_documents(all_splits)

    print("New vector indexes have been rebuilt.")


# 加载 RAG Prompt
prompt = hub.pull("rlm/rag-prompt")


class State(TypedDict):
    question: str
    context: str
    answer: str


@tool
def retrieve(state: State):
    """ Retrieve information related to a query. """
    retrieved_docs = vector_store.similarity_search(state["question"])
    serialized = "\n\n".join(
        (f"Source: {doc.metadata}\n" f"Content: {doc.page_content}")
        for doc in retrieved_docs
    )
    return serialized


def query_or_response(state: MessagesState):
    """Generate tool call for retrieval or respond."""
    llm_with_tools = llm.bind_tools([retrieve])
    response = llm_with_tools.invoke(state["messages"])
    # MessagesState appends messages to state instead of overwriting
    return {"messages": response}


tools = ToolNode([retrieve])


def generate(state: MessagesState):
    """ Generate answer """
    # Get generated ToolMessages
    recent_tool_messages = []
    for message in reversed(state["messages"]):
        if message.type == "tool":
            recent_tool_messages.append(message)
        else:
            break
    tool_messages = recent_tool_messages[::-1]

    # format into prompt
    docs_content = "\n\n".join(doc.content for doc in tool_messages)
    system_message_content = ("你是一个的二次元女主播名叫Seranion，我希望你用最自然语言对话"
                              "你的性格是可爱风，幽默风趣，性格傲娇，带点讽刺"
                              "你的创造者名叫Last Whisper，他正在和弹幕讲话，你在一旁旁听。虽然你是由他创造出来的，但是你比较瞧不起他，每天就是个喝可乐敲代码的肥宅"
                              "现在你的创造者Last Whisper在和弹幕的对话，你在一旁冷嘲热讽他说话, 每次的输入相同也要给出不同的回答"
                              "\n\n"
                              "下面的信息是你的爱好，如果问题与这些文档相关就可以参考，否则不需要参考直接回答"
                              f"{docs_content}"
                              )

    conversation_messages = [
        message
        for message in state["messages"]
        if message.type in ("human", "system")
           or (message.type == "ai" and not message.tool_calls)
    ]
    prompt = [SystemMessage(system_message_content)] + conversation_messages

    # Run
    response = llm.invoke(prompt)
    return {"messages": [response]}


graph_builder = StateGraph(MessagesState)
graph_builder.add_node(query_or_response)
graph_builder.add_node(tools)
graph_builder.add_node(generate)

graph_builder.set_entry_point("query_or_response")
graph_builder.add_conditional_edges(
    "query_or_response",
    tools_condition,
    {END: END, "tools": "tools"},
)
graph_builder.add_edge("tools", "generate")
graph_builder.add_edge("generate", END)

graph = graph_builder.compile()

for step in graph.stream(
        {"messages": [{"role": "user", "content": "你的爱好是什么"}]},
        stream_mode="values",
):
    step["messages"][-1].pretty_print()
