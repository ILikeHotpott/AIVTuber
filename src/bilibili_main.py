# -*- coding: utf-8 -*-

import threading
import asyncio
import time
import os
from datetime import datetime
from typing import Optional

from danmaku.buffer import DanmakuJsonStorage
from src.danmaku.models import Message, MessageType
from src.tts.tts_stream import tts_streaming
from src.memory.short_term.memory_chatbot_engine import chat
from blivedm.sample import MyHandler

BILIBILI_ROOM_ID = 22889482
MEMORY_CONFIG_NAME = "user_50"

# 全局的 TTS 播报同步事件，和 Douyin 代码一致
tts_playing_event = threading.Event()
tts_playing_event.set()  # 初始允许生成回答


def chat_with_memory_and_extra_prompt(message: Message, memory_config: str, extra_prompt: str):
    """
    模仿 Douyin 里的 chat + TTS 处理逻辑
    """
    # 等待上一次 TTS 播放结束
    tts_playing_event.wait()
    print(f"[用户提问内容] {extra_prompt}")
    response = chat(memory_config, extra_prompt, language="Chinese")
    print(f"[AI回到用户]: {response}")
    # 播放 TTS 的时候先把 event 清掉, 防止并发
    tts_playing_event.clear()

    if message.type == MessageType.DANMU:
        # 如果是普通弹幕, 可能先把原文再读一遍
        tts_streaming(message.content + response)
    else:
        # 否则直接读回复
        tts_streaming(response)

    # TTS 结束，释放事件
    tts_playing_event.set()


class BilibiliLiveFetcher:
    """
    模仿 DouyinLiveWebFetcher 的写法,
    内部启动一个异步线程去跑 B站的弹幕监听,
    并提供 get_next_message() 给外部使用(同步风格).
    """

    def __init__(self, room_id: int):
        self.room_id = room_id
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._handler = MyHandler()  # 你的 Handler, 内部含有一个 total_queue

        start_time = datetime.now().strftime("%H-%M-%S")
        self.json_storage = DanmakuJsonStorage(
            room_id=str(room_id),
            start_time=start_time,
            output_dir=os.path.join("data", "danmaku_bili"),
            max_length=100
        )

    def start(self):
        """
        启动后台线程，运行事件循环
        """
        self._thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._main_coroutine())
        finally:
            self._loop.run_until_complete(self._loop.shutdown_asyncgens())
            self._loop.close()

    async def _main_coroutine(self):
        """
        真正的异步主函数：
        1) 初始化session
        2) 启动 BLiveClient
        3) 等待直到退出
        """
        import aiohttp
        import http.cookies
        from blivedm.blivedm.clients.web import BLiveClient

        sessdata = '930f628b%2C1752848382%2C654bd%2A11CjAphrMsUET-VvlcbVv0ew4W-ykvUZH7gMmWOly39ao-AB3kC--QchlBU4Ep1nQUBbYSVmRGSXBwNWo3X1BRVWlBak1LUW9IdmFqbms3UFQ1NWl2Wm1kR0ZJempreDZSb0g0VUh5dnNNNFoyajgyUTZwcjRlcFQzdEdONmR4TVJOellZZmx5TmpnIIEC'
        cookies = http.cookies.SimpleCookie()
        cookies['SESSDATA'] = sessdata
        cookies['SESSDATA']['domain'] = 'bilibili.com'

        session = aiohttp.ClientSession()
        session.cookie_jar.update_cookies(cookies)

        # (2) 启动 BLiveClient 并设置 handler
        client = BLiveClient(self.room_id, session=session)
        client.set_handler(self._handler)
        client.start()

        try:
            # 阻塞直到客户端完成(理论上是直播结束或者抛异常才会退出)
            await client.join()
        finally:
            await client.stop_and_close()
            await session.close()

    def get_next_message(self) -> Optional[Message]:
        """
        模仿 Douyin 写法，尝试从 handler 的队列中获取下一条弹幕 Message.
        """
        # 你的 MyHandler 里一般会管理一个 total_queue
        # 例如：return self._handler.total_queue.get_next_message()
        return self._handler.total_queue.get_next_message()

    def stop(self):
        """
        退出逻辑(可选)：如果需要主动退出，可以加上类似 Douyin flush 的处理
        """
        # 比如：
        if self.json_storage:
            self.json_storage.flush_all()
        # 你也可以想办法关闭 event_loop/客户端等


def start_bilibili_fetcher(room_id: int) -> BilibiliLiveFetcher:
    """
    启动抓取线程并返回 BilibiliLiveFetcher 实例
    """
    fetcher = BilibiliLiveFetcher(room_id)
    fetcher.start()
    return fetcher


def main():
    fetcher = start_bilibili_fetcher(BILIBILI_ROOM_ID)
    print("开始获取B站弹幕并播报...按 Ctrl+C 退出。")

    try:
        while True:
            message_obj = fetcher.get_next_message()
            if message_obj:
                # 拿到 Message 对象，提取 prompt 文本
                prompt_text = message_obj.prompt  # 你定义在 models.Message 里的 prompt, 或者 message_obj.content
                chat_with_memory_and_extra_prompt(message_obj, MEMORY_CONFIG_NAME, prompt_text)
            else:
                print("暂时没有新弹幕，睡眠1秒...")
                time.sleep(1)

    except KeyboardInterrupt:
        print("收到 KeyboardInterrupt，准备退出...")
        fetcher.stop()
        print("已将统计数据写入文件。")


if __name__ == "__main__":
    main()
