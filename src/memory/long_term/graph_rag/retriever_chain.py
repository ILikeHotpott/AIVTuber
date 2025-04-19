from langchain_openai import OpenAIEmbeddings
from langchain_chroma.vectorstores import Chroma
from langchain_graph_retriever import GraphRetriever
from langchain_graph_retriever.transformers import ShreddingTransformer
from langchain_graph_retriever.adapters.chroma import ChromaAdapter
from graph_retriever.strategies import Eager
from langchain_core.runnables import Runnable
from src.memory.long_term.memory_documents import docs
from dotenv import load_dotenv

load_dotenv()

shredder = ShreddingTransformer()
vector_store = Chroma.from_documents(
    documents=list(shredder.transform_documents(docs)),
    embedding=OpenAIEmbeddings(),
    collection_name="creator_roast_memory"
)

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


def format_docs(docs):
    return "\n\n".join(f"{doc.page_content}" for doc in docs)


def retrieve_long_term_memory() -> Runnable:
    """返回一个可以用 .invoke(prompt) 的长记忆图检索器"""
    return retriever | format_docs
