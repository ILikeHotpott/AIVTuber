from dataclasses import dataclass
from enum import Enum


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
    # 这里可以加更多字段，例如用户等级、粉丝团等级、总送礼数等
    # total_donation: int = 0  # TODO: 这里用数据库做，用来判断是否抬高弹幕优先级等,


@dataclass(order=True)
class Message:
    priority: int
    user: User
    content: str
    type: MessageType
