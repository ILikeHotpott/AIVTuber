import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class TwitchConfig:
    access_token: str = os.getenv("TWITCH_ACCESS_TOKEN")
    nick: str = os.getenv("TWITCH_NICK")
    channel: str = os.getenv("TWITCH_CHANNELS")