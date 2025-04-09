import threading
import time
import os
from datetime import datetime
from danmaku.buffer import DanmakuJsonStorage
from external.DouyinLiveWebFetcher import DouyinLiveWebFetcher
from src.memory.short_term.memory_chatbot_engine import chat
from src.tts.realtime_tts import tts_in_chunks
from src.danmaku.models import Message, MessageType


def start_fetcher(live_id):
    """
    启动抓取线程并返回 DouyinLiveWebFetcher 实例。
    这里假设 DouyinLiveWebFetcher 的构造与之前相同。
    """
    start_time = datetime.now().strftime("%H-%M-%S")
    json_storage = DanmakuJsonStorage(
        room_id=live_id,
        start_time=start_time,
        output_dir=os.path.join("data", "danmaku"),
        max_length=100
    )
    fetcher = DouyinLiveWebFetcher(live_id, json_storage=json_storage)
    t = threading.Thread(target=fetcher.start, daemon=True)
    t.start()
    return fetcher


# 定义全局的 tts 播放同步事件
tts_playing_event = threading.Event()
tts_playing_event.set()  # 初始允许生成回答


def chat_with_memory_and_extra_prompt(message: Message, memory_config: str, extra_prompt: str):
    tts_playing_event.wait()
    print(f"用户1: {extra_prompt}")
    response = chat(memory_config, extra_prompt, language="Chinese")
    print(f"AI: {response}")

    tts_playing_event.clear()

    # 如果是回复弹幕评论，就要先读一遍弹幕，然后再回复
    if message.type == MessageType.DANMU:
        tts_in_chunks(message.content + response)
    else:
        tts_in_chunks(response)

    tts_playing_event.set()


def main():
    live_id = "82506711433"

    # 1) 启动弹幕抓取线程
    fetcher = start_fetcher(live_id)

    print("开始获取弹幕并播报...按 Ctrl+C 退出。")

    try:
        while True:
            message_obj = fetcher.get_next_message()
            if message_obj:
                prompt_text = message_obj.prompt
                chat_with_memory_and_extra_prompt(message_obj, "user_18", prompt_text)
            else:
                print("Message对象获取失败，睡眠1秒")
                time.sleep(1)
    except KeyboardInterrupt:
        print("收到 KeyboardInterrupt，准备退出...")
        if fetcher.danmaku_queue and fetcher.danmaku_queue.json_storage:
            fetcher.danmaku_queue.json_storage.flush_all()
        print("已将统计数据写入文件。")


if __name__ == "__main__":
    main()
