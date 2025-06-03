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
            return f"💬 {username} 发来弹幕：{content}"
        elif self.type == MessageType.FANS:
            return f"⭐ {username} 加入了粉丝团，请说出用户名进行简短的感谢"
        elif self.type == MessageType.FOLLOW:
            return f"👣 {username} 关注了主播，请说出用户名进行简短感谢"
        elif self.type == MessageType.LIKE:
            return f"❤️ {username} 点了个赞，请说一些简短的感谢"
        elif self.type == MessageType.ENTER:
            return f"🚪 {username} 进入了直播间，简短的话欢迎"
        else:
            return f"{username}：{content}"
