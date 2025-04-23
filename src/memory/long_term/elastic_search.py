import time
from dotenv import load_dotenv
import hashlib
from elasticsearch import Elasticsearch
from langchain_openai import OpenAIEmbeddings
from langchain_elasticsearch import ElasticsearchStore
from src.memory.long_term.memory_documents import docs
from src.utils.dev_modes import is_dev
from src.utils.docs_change_detect import has_docs_changed
from src.utils.path import find_project_root

load_dotenv()


class LongTermMemoryES:
    def __init__(
            self,
            threshold,
            es_url="http://localhost:9200",
            index_name="langchain_index",
            es_user="elastic",
            es_password="changeme",
            embedding_model="text-embedding-3-large",
            persist=True,
    ):
        self.threshold = threshold
        self.index_name = index_name
        self.es = Elasticsearch(
            es_url,
            basic_auth=(es_user, es_password)
        )
        self.embeddings = OpenAIEmbeddings(model=embedding_model)
        self.vector_store = ElasticsearchStore(
            es_url=es_url,
            index_name=index_name,
            embedding=self.embeddings,
            es_user=es_user,
            es_password=es_password
        )

        index_exists = self.es.indices.exists(index=index_name)
        need_reload = is_dev and has_docs_changed(
            docs,
            cache_path=find_project_root() / "src/runtime/storage/.docs_fingerprint"
        )

        if persist and (not index_exists or need_reload):
            print("[向量库] 初始化或文档有变更，正在写入...")
            self._init_index()

    def _get_id(self, content: str) -> str:
        return hashlib.md5(content.encode("utf-8")).hexdigest()

    def _init_index(self):
        ids = [self._get_id(doc.page_content) for doc in docs]
        self.vector_store.add_documents(docs, ids=ids)
        print(f"[向量库] 已写入 {len(docs)} 条文档到索引 '{self.index_name}'")

    def reset_index(self):
        if self.es.indices.exists(index=self.index_name):
            self.es.indices.delete(index=self.index_name)
            print(f"[向量库] 已删除索引 '{self.index_name}'")
        self._init_index()

    def retrieve(self, query: str, k=3):
        results = self.vector_store.similarity_search_with_score(query, k=k)
        res = [
            {
                "score": round(score, 4),
                "content": doc.page_content,
                "metadata": doc.metadata
            }
            for doc, score in results
            if score >= self.threshold
        ]
        print(res)
        return res


if __name__ == "__main__":
    time1 = time.time()
    ltm = LongTermMemoryES(threshold=0.68)
    # ltm.reset_index() 需要重置的时候执行
    result = ltm.retrieve("讲讲Whisper这个人", k=3)
    time2 = time.time()
    print(result)
    print(time2 - time1)
