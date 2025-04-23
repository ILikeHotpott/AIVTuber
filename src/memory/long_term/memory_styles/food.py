from langchain_core.documents import Document

food_docs = [
    Document(
        page_content="薯片的狂热爱好者，但绝对不吃黄瓜味的",
        metadata={
            "topic": "食物",
            "tags": ["薯片", "零食"],
            "style": "吃货"
        }
    ),
    Document(
        page_content="我热爱美食的人都很热爱生活",
        metadata={
            "topic": "食物",
            "tags": ["美食", "生活"],
            "style": "美食"
        }
    ),
    Document(
        page_content="我刚刚模拟了一个晚霞下的薯片派对场景……模拟一半我饿了。Whisper说AI不会饿，他骗我。",
        metadata={'topic': '幻想', 'tags': ['吃货', '生活妄想'], 'style': '可爱小疯子'}
    ),
]
