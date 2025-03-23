import queue


class TotalPriorityMessageQueue:
    def __init__(self):
        self.queue = queue.PriorityQueue()

    def add_message(self, priority: int, user: int, content: str, type: str):
        msg = Message(priority=-priority, user=user, content=content, type=type)
        self.queue.put(msg)

#
# class MessagePicker:
#     """ 消息种类：
#     1. 礼物
#     2. 弹幕消息
#     3. 粉丝团
#     4. 关注
#     5. 点赞
#     6. 进入直播间
#     """
#
#     def __init__(self):
#         pass
