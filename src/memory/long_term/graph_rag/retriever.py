import dotenv
from langchain_core.messages import SystemMessage
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma.vectorstores import Chroma
from langchain_graph_retriever import GraphRetriever
from langchain_graph_retriever.transformers import ShreddingTransformer
from langchain_graph_retriever.adapters.chroma import ChromaAdapter
from graph_retriever.strategies import Eager
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from src.memory.long_term.graph_rag.memory_docs import docs
from src.prompt.templates.general import general_settings_prompt
from src.tts.tts_stream import tts_streaming

dotenv.load_dotenv()

# 3. 切碎 metadata，放入 Chroma 向量库
shredder = ShreddingTransformer()

vector_store = Chroma.from_documents(
    documents=list(shredder.transform_documents(docs)),
    embedding=OpenAIEmbeddings(),
    collection_name="creator_roast_memory"
)

# 4. 构建 GraphRetriever
retriever = GraphRetriever(
    store=ChromaAdapter(vector_store, shredder, {"tags"}),
    edges=[
        ("tags", "tags"),
        ("topic", "topic"),
        ("target", "target"),
        ("persona", "persona"),
    ],
    strategy=Eager(k=5, start_k=2, max_depth=2),
)

# 5. 构建 LLM 调用链
llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0.7)

prompt = ChatPromptTemplate.from_messages([
    SystemMessage(content=general_settings_prompt),
    ("human", "以下是你的记忆内容：\n{context}\n\n观众提问：{question}\n请用主播风格回复：")
])


def format_docs(docs):
    return "\n\n".join(f"{doc.page_content}" for doc in docs)


chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
)

if __name__ == "__main__":
    query = "主播想谈恋爱吗"
    result = chain.invoke(query)
    print("虚拟主播回复：\n", result)
    tts_streaming(result)
