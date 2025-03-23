from dataclasses import dataclass
from enum import Enum


class MessageType(Enum):
    GIFT = "礼物"
    DANMU = "弹幕消息"
    FANS = "粉丝团"
    FOLLOW = "关注"
    LIKE = "点赞"
    ENTER = "进入直播间"


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
