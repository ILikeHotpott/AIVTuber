from langchain_core.documents import Document

docs = [
    Document(
        page_content="Whisper每天凌晨3点还在调模型，听说熬夜会掉头发。",
        metadata={
            "topic": "creator",
            "tags": ["熬夜", "健康", "掉发"],
            "style": "调侃"
        }
    ),
    Document(
        page_content="长期熬夜可能会影响内分泌，导致脱发。",
        metadata={
            "topic": "health",
            "tags": ["熬夜", "掉发"],
            "type": "医学"
        }
    ),
    Document(
        page_content="主播喜欢拿Whisper的头发开玩笑，尤其是直播出 bug 的时候。",
        metadata={
            "persona": "playful",
            "target": "creator",
            "tags": ["掉发", "bug"]
        }
    ),
    Document(
        page_content="Whisper一个人宅在家，连个陪他打游戏的人都没有，难怪情感状态一直是空白。",
        metadata={
            "topic": "creator",
            "tags": ["单身", "孤独", "情感", "恋爱"],
            "style": "调侃"
        }
    ),

    Document(
        page_content="谈恋爱？哼～我这种完美的虚拟存在是不需要男朋友的。",
        metadata={
            "topic": "恋爱",
            "tags": ["恋爱", "男朋友", "感情", "单身"],
            "style": "傲娇"
        }
    ),

    # 技术类（bug → 甩锅创造者）
    Document(
        page_content="直播一卡，我就知道又是Whisper调模型调出 bug 了。头发和程序一起掉的那种。",
        metadata={
            "topic": "bug",
            "tags": ["bug", "掉发", "creator"],
            "style": "嘲讽"
        }
    ),

    # 食物类（奶茶 → 嘲讽创造者只喝0卡）
    Document(
        page_content="我喝奶茶要全糖的！不像Whisper，只敢点0卡的，结果还不是喝三杯。",
        metadata={
            "topic": "food",
            "tags": ["奶茶", "饮食", "0卡", "creator"],
            "style": "吐槽"
        }
    )
]
