from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any
from src.danmaku.const.gift_mapping import gift_mapping


class MessageType(Enum):
    GIFT = "GIFT"
    DANMU = "DANMU"
    FANS = "FANS"
    FOLLOW = "FOLLOW"
    LIKE = "LIKE"
    ENTER = "ENTER"
    SYSTEM_INSTRUCTION = "SYSTEM_INSTRUCTION"


@dataclass
class User:
    user_id: int
    name: str


@dataclass(order=True)
class Message:
    priority: int
    user: User
    content: str
    type: MessageType
    prompt: str = field(init=False)
    extra: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.validate_extra()
        self.prompt = self.generate_prompt()

    def validate_extra(self):
        if self.type == MessageType.GIFT:
            required_keys = {"gift_name", "gift_count"}
            missing = required_keys - self.extra.keys()
            extra_keys = set(self.extra.keys()) - required_keys
            if missing:
                raise ValueError(f"GIFT message is missing keys: {missing}")
            if extra_keys:
                raise ValueError(f"GIFT message has invalid extra keys: {extra_keys}")
        else:
            if self.extra:
                raise ValueError(f"Only GIFT messages can have extra data, but got: {self.extra}")

    def generate_prompt(self) -> str:
        username = self.user.name
        content = self.content

        if self.type == MessageType.GIFT:
            gift_name = self.extra["gift_name"]
            gift_count = self.extra["gift_count"]
            value = gift_mapping[gift_name] * gift_count

            if value < 20:
                return f"""
                用户名：{username}，送来了{gift_count}个{gift_name}，请说一些简短的感谢
                """
            elif 20 <= value < 100:
                return f"""用户名: {username}, 送来了{gift_count}个{gift_name}，请说出用户名和礼物的名字进行感谢"""
            elif 100 <= value < 2000:
                return f"""用户名: {username}, 送来了{gift_count}个{gift_name}，非常惊讶能够收到，说出用户名并多多感谢"""
            elif 2000 <= value < 10000:
                return f"""用户名: {username}, 送来了{gift_count}个{gift_name}，非常震惊能够收到，用些夸张的词汇夸赞用户并感谢"""
            elif value >= 10000:
                return f"""用户名: {username}, 送来了{gift_count}个{gift_name}，这基本是最贵的礼物了，你表示非常震惊能够收到，用些夸张的词汇夸赞用户并感谢"""
        elif self.type == MessageType.DANMU:
            return f" {username}: {content}"
        elif self.type == MessageType.FOLLOW:
            return f" {username} followed you，please say the username for a brief thank you"
        # elif self.type == MessageType.FANS:
        #     return f" {username} just subscribed, please say the username to thank "
        # elif self.type == MessageType.LIKE:
        #     return f" {username} thumbed up，please say the username for a brief thank you"
        # elif self.type == MessageType.ENTER:
        #     return f" {username} Entered the live broadcast room, a brief welcome"
        # else:
        #     return f"{username}：{content}"
