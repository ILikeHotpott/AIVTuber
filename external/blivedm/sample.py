# -*- coding: utf-8 -*-
import asyncio
import http.cookies
import random
from typing import *

import aiohttp

# import blivedm.models.web as web_models
from external.blivedm.blivedm.handlers import BaseHandler
from external.blivedm.blivedm.clients.web import BLiveClient
import external.blivedm.blivedm.models.web as web_models
from src.danmaku.models import User
from src.danmaku.message_queue.queue_manager import TotalMessageQueue
from src.danmaku.const.bilibili_mapping import guard_mapping

from src.memory.short_term.llama_chat_engine import chat_with_memory

# 直播间ID的取值看直播间URL
TEST_ROOM_IDS = [
    22889482
]

# 这里填一个已登录账号的cookie的SESSDATA字段的值。不填也可以连接，但是收到弹幕的用户名会打码，UID会变成0
# 这个可能会过期，过期了记得重新获取，进入直播间 => Inspect => Application => Cookies/https://live.bilibili.com => SESSDATA
SESSDATA = '930f628b%2C1752848382%2C654bd%2A11CjAphrMsUET-VvlcbVv0ew4W-ykvUZH7gMmWOly39ao-AB3kC--QchlBU4Ep1nQUBbYSVmRGSXBwNWo3X1BRVWlBak1LUW9IdmFqbms3UFQ1NWl2Wm1kR0ZJempreDZSb0g0VUh5dnNNNFoyajgyUTZwcjRlcFQzdEdONmR4TVJOellZZmx5TmpnIIEC'

session: Optional[aiohttp.ClientSession] = None


async def main():
    init_session()
    handler = MyHandler()

    try:
        # 启动直播弹幕监听和消息处理循环
        task1 = asyncio.create_task(run_single_client(handler))
        task2 = asyncio.create_task(message_processing_loop(handler))

        await asyncio.gather(task1, task2)

    finally:
        await session.close()


def init_session():
    cookies = http.cookies.SimpleCookie()
    cookies['SESSDATA'] = SESSDATA
    cookies['SESSDATA']['domain'] = 'bilibili.com'

    global session
    session = aiohttp.ClientSession()
    session.cookie_jar.update_cookies(cookies)


async def run_single_client(handler):
    """
    启动单个直播间监听
    """
    room_id = random.choice(TEST_ROOM_IDS)
    client = BLiveClient(room_id, session=session)
    client.set_handler(handler)

    client.start()
    try:
        await client.join()
    finally:
        await client.stop_and_close()


async def message_processing_loop(handler: 'MyHandler'):
    """
    弹幕处理循环：获取消息并交给 memory bot
    """
    while True:
        msg_obj = handler.get_next_msg()
        if msg_obj:
            user = msg_obj.user
            content = msg_obj.message
            print(f'[Memory Chatbot] 来自 {user.name} 的消息：{content}')

            # 调用记忆聊天模型
            response = await chat_with_memory(user.name, content)
            print(f'[Memory Chatbot] 回复：{response}')
        else:
            await asyncio.sleep(0.2)


class MyHandler(BaseHandler):
    # # 演示如何添加自定义回调
    # _CMD_CALLBACK_DICT = blivedm.BaseHandler._CMD_CALLBACK_DICT.copy()
    #
    # # 看过数消息回调
    # def __watched_change_callback(self, client: blivedm.BLiveClient, command: dict):
    #     print(f'[{client.room_id}] WATCHED_CHANGE: {command}')
    # _CMD_CALLBACK_DICT['WATCHED_CHANGE'] = __watched_change_callback  # noqa

    # def _on_heartbeat(self, client: blivedm.BLiveClient, message: web_models.HeartbeatMessage):
    #     print(f'[{client.room_id}] 心跳')

    def __init__(self):
        super().__init__()
        self.total_queue = TotalMessageQueue()

    def _on_danmaku(self, client: BLiveClient, message: web_models.DanmakuMessage):
        """
            普通弹幕消息
        """
        user = User(user_id=message.uid, name=message.uname)
        self.total_queue.put_danmu(user, message.msg)
        print(f'[{client.room_id}] {message.uname}：{message.msg}')

    def _on_super_chat(self, client: BLiveClient, message: web_models.SuperChatMessage):
        """
            醒目留言（SC）
        """
        user = User(user_id=message.uid, name=message.uname)
        self.total_queue.put_super_chat(user, message.message, message.price)
        print(f'[{client.room_id}] 醒目留言 ¥{message.price} {message.uname}：{message.message}')

    def _on_gift(self, client: BLiveClient, message: web_models.GiftMessage):
        """
            礼物消息
        """
        user = User(user_id=message.uid, name=message.uname)
        self.total_queue.put_gift(message.gift_name, message.num, user)
        print(f'[{client.room_id}] {message.uname} 赠送{message.gift_name}x{message.num}')
        # f' （{message.coin_type}瓜子x{message.total_coin} '

    def _on_buy_guard(self, client: BLiveClient, message: web_models.GuardBuyMessage):
        """
        简洁上舰处理（买舰队视为特殊礼物）
        """
        user = User(user_id=message.uid, name=message.username)
        mapping = guard_mapping.get(message.guard_level)
        if mapping:
            gift_name = mapping["gift_name"]
            price = mapping["price"]
            self.total_queue.gift_queue.put_guard_message(gift_name, user, price)
            print(f'[{client.room_id}] {message.username} 上舰（{gift_name}）')

    def _on_user_toast_v2(self, client: BLiveClient, message: web_models.UserToastV2Message):
        """
        上舰提醒消息（视为送舰队礼物）
        """
        user = User(user_id=message.uid, name=message.username)
        mapping = guard_mapping.get(message.guard_level)
        if mapping:
            gift_name = mapping["gift_name"]
            price = mapping["price"]
            self.total_queue.gift_queue.put_guard_message(gift_name, user, price)
            print(f'[{client.room_id}] {message.username} 上舰提醒（{gift_name}）')

    def _on_interact_word(self, client: BLiveClient, message: web_models.InteractWordMessage):
        user = User(user_id=message.uid, name=message.username)
        if message.msg_type == 1:
            # 进入房间 （先不放了）
            self.total_queue.put_enter(user, "进入房间")
            print(f'[{client.room_id}] {message.username} 进入房间')
        elif message.msg_type == 2:
            # 关注主播
            self.total_queue.put_follow(user, "关注了主播")
            print(f'[{client.room_id}] {message.username} 关注了主播')
        elif message.msg_type == 6:
            # 点赞 （先不放了）
            # self.total_queue.put_like(user, "点赞")
            print(f'[{client.room_id}] {message.username} 点赞')

    def get_next_msg(self):
        self.total_queue.get_next_message()


if __name__ == '__main__':
    asyncio.run(main())
