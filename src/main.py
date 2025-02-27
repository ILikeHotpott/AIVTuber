import threading
import time
import os
import api.main
from datetime import datetime
from chatbot.queue import ChatbotQueue
from danmaku.buffer import DanmakuJsonStorage
from DouyinLiveWebFetcher.liveMan import DouyinLiveWebFetcher


def start_fetcher(live_id):
    # 获取直播开始时间（格式为 HH-MM-SS）
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


def main():
    live_id = "110577451588"
    # 1) 创建存储对象
    json_storage = DanmakuJsonStorage(
        room_id=live_id,
        start_time=datetime.now().strftime("%H-%M-%S"),
        output_dir=os.path.join("data", "danmaku"),
        max_length=100
    )

    chat_queue = ChatbotQueue()
    api.main.chat_queue = chat_queue

    fetcher = DouyinLiveWebFetcher(
        live_id=live_id,
        json_storage=json_storage,
        chat_queue=chat_queue
    )
    fetch_thread = threading.Thread(target=fetcher.start, daemon=True)
    fetch_thread.start()

    api_thread = threading.Thread(target=api.main.start_api_server, daemon=True)
    api_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("收到 KeyboardInterrupt，准备退出...")

        if fetcher.danmaku_queue and fetcher.danmaku_queue.json_storage:
            fetcher.danmaku_queue.json_storage.flush_all()
        print("已将统计数据写入文件。")


if __name__ == "__main__":
    main()
