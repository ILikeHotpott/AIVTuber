from uuid import uuid4
import dotenv
import time
from langchain_openai import OpenAIEmbeddings
from langchain_elasticsearch import ElasticsearchStore
from src.memory.long_term.documents import docs

dotenv.load_dotenv()
embeddings = OpenAIEmbeddings(
    model="text-embedding-3-large",
    # dimensions=1024
)

vector_store = ElasticsearchStore(
    es_url="http://localhost:9200",
    index_name="langchain_index",
    embedding=embeddings,
    es_user="elastic",
    es_password="changeme",
)

uuids = [str(uuid4()) for _ in range(len(docs))]
vector_store.add_documents(documents=docs, ids=uuids)

results = vector_store.similarity_search("主播喜欢什么电视剧", k=1)

# 打印结果
for res in results:
    print(f"* {res.page_content} [{res.metadata}]")
