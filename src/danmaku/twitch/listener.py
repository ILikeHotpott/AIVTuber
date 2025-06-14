# src/danmaku/twitch/listener.py

import asyncio
import nest_asyncio
from twitchio.ext import commands
from src.danmaku.twitch.config import TwitchConfig


class TwitchCommentListener(commands.Bot):
    def __init__(self, config: TwitchConfig):
        super().__init__(
            token=config.access_token,
            prefix="!",
            nick=config.nick,
            initial_channels=[config.channel],
        )
        self.config = config  # 保存配置对象（可选）

    async def event_ready(self):
        print(f"Bot 已上线：{self.nick}")

    async def event_message(self, message):
        if message.echo:
            return
        print(f"[💬] {message.author.name}: {message.content}")


# 启动入口
def run_twitch_listener():
    config = TwitchConfig()
    bot = TwitchCommentListener(config)

    nest_asyncio.apply()
    asyncio.get_event_loop().run_until_complete(bot.run())


if __name__ == "__main__":
    run_twitch_listener()
