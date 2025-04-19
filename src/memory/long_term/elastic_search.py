from uuid import uuid4
from elasticsearch import Elasticsearch
from langchain_openai import OpenAIEmbeddings
from langchain_elasticsearch import ElasticsearchStore
from src.memory.long_term.memory_documents import docs
from dotenv import load_dotenv

load_dotenv()


class LongTermMemoryES:
    def __init__(
            self,
            es_url="http://localhost:9200",
            index_name="langchain_index",
            es_user="elastic",
            es_password="changeme",
            embedding_model="text-embedding-3-large",
            persist=True
    ):
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

        if persist and not self.es.indices.exists(index=index_name):
            print("📦 向量库未初始化，正在写入文档...")
            self._init_index()

    def _init_index(self):
        ids = [str(abs(hash(doc.page_content)) % (10 ** 12)) for doc in docs]
        self.vector_store.add_documents(docs, ids=ids)
        print(f"已写入 {len(docs)} 条文档到索引 '{self.index_name}'")

    def reset_index(self):
        if self.es.indices.exists(index=self.index_name):
            self.es.indices.delete(index=self.index_name)
            print(f"已删除索引 '{self.index_name}'")
        self._init_index()

    def retrieve(self, query: str, k=3):
        results = self.vector_store.similarity_search_with_score(query, k=k)
        return [
            {
                "score": round(score, 4),
                "content": doc.page_content,
                "metadata": doc.metadata
            }
            for doc, score in results
        ]


if __name__ == "__main__":
    ltm = LongTermMemoryES()
    # ltm.reset_index() 添加了新记忆/需要重置记忆的时候用，平时搜索就用retrieve
    result = ltm.retrieve("主播喜欢吃什么", k=3)
    print(result)
