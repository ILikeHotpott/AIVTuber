from collections import deque
from src.core.event import Event, EventType


class TopicPlanner:
    def __init__(self):
        self.queue = deque([
            "今天你被哪款游戏惊喜到了？",
            "童年动画片里的白月光角色是谁？"
        ])

    def next(self) -> Event | None:
        if not self.queue:
            return None
        topic = self.queue.popleft()
        # 把 topic 放优先级最低
        return Event.make(EventType.INTERNAL_TOPIC, topic)
