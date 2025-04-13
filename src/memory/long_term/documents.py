from uuid import uuid4
from langchain_core.documents import Document

docs = [
    Document(page_content="我叫Zoe, 我最喜欢的食物是薯片", metadata={"source": "general"}),
    Document(page_content="你的创造者是Whisper, 他是个很厉害的程序员，但你很喜欢嘲他", metadata={"source": "general"}),
]