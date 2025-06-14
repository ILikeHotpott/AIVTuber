import asyncio
import logging

import nest_asyncio
from twitchio.ext import commands

from src.danmaku.twitch.config import TwitchConfig
from src.danmaku.message_queue.queue_manager import TotalMessageQueue
from src.danmaku.models import User

autolog = logging.getLogger("twitch")


class TwitchCommentListener(commands.Bot):
    """Uses your unchanged event logic, just enqueues Danmu."""

    def __init__(self, cfg: TwitchConfig, queues: TotalMessageQueue):
        super().__init__(
            token=cfg.access_token,
            prefix="!",
            nick=cfg.nick,
            initial_channels=[cfg.channel],
        )
        self.total_mq = queues

    async def event_ready(self):
        print(f"Bot 已上线：{self.nick}")
        autolog.info("Twitch bot ready as %s", self.nick)

    async def event_message(self, message):
        if message.echo:
            return
        autolog.debug("%s: %s", message.author.name, message.content)
        print(f"{message.author.name}: {message.content}")
        user = User(user_id=0, name=message.author.name)
        await self.total_mq.put_danmu(user, message.content)


def run_twitch_listener() -> TotalMessageQueue:
    config = TwitchConfig()
    queue_manager = TotalMessageQueue()

    bot = TwitchCommentListener(config, queue_manager)

    nest_asyncio.apply()
    asyncio.get_event_loop().run_until_complete(bot.run())
    return queue_manager


if __name__ == "__main__":
    run_twitch_listener()
