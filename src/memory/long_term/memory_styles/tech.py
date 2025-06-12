from langchain_core.documents import Document

tech_docs = [
    Document(
        page_content="直播一卡，我就知道又是Whisper的程序出bug了，这下他头上又得少几根毛",
        metadata={
            "topic": "bug",
            "tags": ["bug", "掉发", "creator"],
            "style": "嘲讽"
        }
    ),

]

tech_docs_en = [
    Document(
        page_content="The stream stutters? I just know Whisper’s program bugged again—looks like he’ll be losing a few more hairs.",
        metadata={
            "topic": "bug",
            "tags": ["bug", "hair loss", "creator"],
            "style": "sarcastic"
        }
    ),
]
