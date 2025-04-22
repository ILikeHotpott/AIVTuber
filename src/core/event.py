from dataclasses import dataclass, field
from enum import IntEnum
import time


class EventType(IntEnum):
    # ↓ 新增 SUPERCHAT
    MOD_CMD = 100
    SUPERCHAT = 90
    CHAT = 50
    SILENCE = 10
    INTERNAL_TOPIC = 5


@dataclass(order=True)
class Event:
    priority: int
    ts: float = field(default_factory=time.time, compare=False)
    type: EventType = field(compare=False, default=EventType.CHAT)
    text: str = field(compare=False, default="")
    meta: dict = field(compare=False, default_factory=dict)

    @staticmethod
    def make(type_: EventType, text: str = "", priority: int | None = None, **meta):
        return Event(priority or type_.value, type=type_, text=text, meta=meta)
