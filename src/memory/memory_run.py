from langchain.schema import Document
from memory_system import VTuberMemorySystem


def run_vtuber_memory():
    # 创建一个 VTuber 内存系统实例
    vtuber = VTuberMemorySystem("TestVTuber", llm_model="gpt-4o")

    # --- 测试短期记忆 ---
    # 预先写入一些对话记录（短期记忆保存最近的聊天）
    vtuber.short_term_memory.save_context(
        {"input": "[user1] 你好！"},
        {"output": "你好，我是TestVTuber，欢迎来到直播间！"}
    )

    # --- 测试本场直播记忆 ---
    # 写入一些直播对话摘要
    vtuber.mid_term_memory.save_context(
        {"input": "[user1] 今天天气真好，心情也不错。"},
        {"output": "确实，阳光明媚，正适合直播互动。"}
    )

    # --- 测试长期记忆 ---
    # 向角色信息向量库写入人设信息
    character_doc = Document(
        page_content="TestVTuber是一个活泼、热情的虚拟主播，喜欢音乐与游戏互动。",
        metadata={"source": "profile"}
    )
    vtuber.character_vectordb.add_documents([character_doc])
    vtuber.character_vectordb.persist()

    # 向热点梗向量库写入一个热点梗
    meme_doc = Document(
        page_content="热门梗：'这波操作真的666！'",
        metadata={"source": "meme"}
    )
    vtuber.memes_vectordb.add_documents([meme_doc])
    vtuber.memes_vectordb.persist()

    # --- 模拟用户发言，检验回复 ---
    user_id = "user1"
    user_input = "能介绍一下你自己吗？"
    response = vtuber.process_input(user_id, user_input)

    print("VTuber回复:")
    print(response)


if __name__ == "__main__":
    run_vtuber_memory()
