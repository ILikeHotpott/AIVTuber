from elasticsearch import Elasticsearch
from langchain_core.documents import Document
from src.memory.long_term.memory_documents import docs
from typing import List
import hashlib
import time


class MemoryManager:
    def __init__(self, index_name="chat_memory", es_url="http://localhost:9200"):
        self.index_name = index_name
        self.es = Elasticsearch(es_url)
        self._create_index_if_needed()

    def _create_index_if_needed(self):
        if not self.es.indices.exists(index=self.index_name):
            self.es.indices.create(
                index=self.index_name,
                body={
                    "mappings": {
                        "properties": {
                            "content": {"type": "text"},
                            "metadata": {"type": "object"}
                        }
                    }
                }
            )

    def _content_to_id(self, content: str) -> str:
        return hashlib.md5(content.encode("utf-8")).hexdigest()

    def save(self, docs: List[Document]):
        for doc in docs:
            doc_id = self._content_to_id(doc.page_content)
            if self.es.exists(index=self.index_name, id=doc_id):
                continue
            self.es.index(
                index=self.index_name,
                id=doc_id,
                document={
                    "content": doc.page_content,
                    "metadata": doc.metadata
                }
            )

    def search(self, query: str, top_k: int = 3) -> List[dict]:
        body = {
            "query": {
                "match": {
                    "content": query
                }
            },
            "size": top_k
        }

        res = self.es.search(index=self.index_name, body=body)
        results = []
        for hit in res["hits"]["hits"]:
            results.append({
                "score": hit["_score"],
                "content": hit["_source"]["content"],
                "metadata": hit["_source"]["metadata"]
            })

        return results

    def reset_index(self):
        if self.es.indices.exists(index=self.index_name):
            self.es.indices.delete(index=self.index_name)
        self._create_index_if_needed()


if __name__ == "__main__":
    time1 = time.time()
    memory = MemoryManager()
    memory.save(docs)

    results = memory.search("你叫啥", top_k=4)
    time2 = time.time()
    for r in results:
        print(f"[Score: {r['score']:.2f}] {r['content']}")
        print(f"Metadata: {r['metadata']}")
        print("---")

    print(time2 - time1)