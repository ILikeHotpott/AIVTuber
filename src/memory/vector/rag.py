import os
from langchain_sambanova import ChatSambaNovaCloud
from typing_extensions import TypedDict
from langchain import hub
from langchain_openai import OpenAIEmbeddings
from langchain_milvus import Milvus
from langchain_text_splitters import CharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from langgraph.graph import START, StateGraph
from dotenv import load_dotenv

load_dotenv()

os.environ["LANGSMITH_TRACING"] = "true"
os.environ["LANGSMITH_API_KEY"] = os.getenv("LANGSMITH_API_KEY")

llm = ChatSambaNovaCloud(
    model="DeepSeek-R1",
    max_tokens=300,
    temperature=0.9,
    top_k=50,
    top_p=1,
)

embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

URI = "./milvus_example.db"
vector_store = Milvus(
    embedding_function=embeddings,
    connection_args={"uri": URI},
    index_params={"index_type": "FLAT", "metric_type": "L2"},
    auto_id=True
)

# 读取文档
loader = TextLoader(file_path="./txts/What_I_Said_Before.txt")
documents = loader.load()

# 拆分文档
text_splitter = CharacterTextSplitter(separator="\n", chunk_size=300, chunk_overlap=50)
all_splits = text_splitter.split_documents(documents)

_ = vector_store.add_documents(documents=all_splits)

# 加载 RAG Prompt
prompt = hub.pull("rlm/rag-prompt")


class State(TypedDict):
    question: str
    context: str
    answer: str


def retrieve(state: State):
    retrieved_docs = vector_store.similarity_search(state["question"])
    print("🔍 Retrieved Docs:", retrieved_docs)
    return {"context": retrieved_docs}


def generate(state: State):
    # 把检索到的文档内容拼在一起
    docs_content = "\n\n".join(doc.page_content for doc in state["context"])

    base_prompt_or_messages = prompt.invoke({
        "question": state["question"],
        "context": docs_content
    })

    system_prompt = """
你是一个可爱风格的，幽默风趣，带点讽刺的二次元女主播，像neurosama，性格有点傲娇但又很可爱，看到不好的弹幕也会回怼，像一个话痨，
我希望你用非常自然的日常聊天语气和弹幕互动，再调皮一点，回复稍微短一些就行,每次输入的话一样也不要回复一样的东西, 以第一人称视角回复
Important user information you should remember: {user_info}
"""

    # 3) 构造对话格式：先插入 system 消息，再把 rag-prompt 产物作为 user 消息
    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        # rag-prompt 有时直接返回的是字符串，这里统一把它当作 user 消息就好
        {
            "role": "user",
            "content": base_prompt_or_messages if isinstance(base_prompt_or_messages, str) else str(
                base_prompt_or_messages)
        }
    ]

    # 4) 用拼好的 messages 执行推理
    response = llm.invoke(messages)

    return {"answer": response.content}


graph_builder = StateGraph(State).add_sequence([retrieve, generate])
graph_builder.add_edge(START, "retrieve")
graph = graph_builder.compile()

response = graph.invoke({"question": "Saranion喜欢去哪里玩呢？"})
print(response["answer"])
