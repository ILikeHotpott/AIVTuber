from langchain_openai import OpenAIEmbeddings
from src.memory.long_term.memory_documents import docs
from langchain_chroma.vectorstores import Chroma
from langchain_core.documents import Document
from dotenv import load_dotenv

load_dotenv()


class LongTermMemory:
    def __init__(self, vector_store: Chroma, *, embeddings_model=None, score_threshold=0.2, max_hits=4):
        self.vs = vector_store
        self.embeddings = embeddings_model or OpenAIEmbeddings()
        self.score_threshold = score_threshold
        self.max_hits = max_hits
        self._last_query = None
        self._last_docs = []

    def retrieve(self, query: str) -> str:
        if not query.strip():
            return ""

        if query == self._last_query and self._last_docs:
            return "\n\n".join(self._last_docs)

        hits = self.vs.similarity_search_with_relevance_scores(
            query,
            k=self.max_hits,
            score_threshold=self.score_threshold
        )

        if not hits:
            self._last_docs = []
            self._last_query = query
            return ""

        # 添加带分数的输出
        formatted_results = []
        for doc, score in hits:
            formatted_results.append(f"[score={score:.4f}] {doc.page_content}")

        self._last_docs = [doc.page_content for doc, _ in hits]
        self._last_query = query
        return "\n\n".join(formatted_results)


def simplify_metadata(doc: Document) -> Document:
    new_meta = {
        k: ", ".join(v) if isinstance(v, list) else v
        for k, v in doc.metadata.items()
    }
    return Document(page_content=doc.page_content, metadata=new_meta)


docs_cleaned = [simplify_metadata(doc) for doc in docs]

# ----------------------------
# 创建向量库
# ----------------------------
vector_store = Chroma.from_documents(
    documents=docs_cleaned,
    embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
    collection_name="test_memory"
)

ltm = LongTermMemory(vector_store, score_threshold=0, max_hits=3)

query = "主播喜欢喝奶茶吗"
result = ltm.retrieve(query)

print("🧠 检索结果：\n")
print(result)
