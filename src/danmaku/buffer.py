import os
import json
from datetime import datetime


# 用作数据分析，并不强制要求
class DanmakuJsonStorage:
    def __init__(self, room_id: str, start_time: str, output_dir='data/danmaku', max_length=100):
        """
        :param room_id: livestream room id
        :param start_time: start time of livestream, format: %Y-%m-%d %H:%M:%S
        :param output_dir: directory to store danmaku data
        :param max_length: max length of danmaku buffer for each category
        """
        self.room_id = room_id
        self.start_time = start_time
        self.end_time = "ongoing"
        self.output_dir = output_dir
        today = datetime.now().strftime("%Y-%m-%d")
        folder_name = f"{today}-{room_id}-{start_time}-{self.end_time}"
        self.folder_path = os.path.join(output_dir, folder_name)
        os.makedirs(self.folder_path, exist_ok=True)
        self.max_length = max_length

        # 为每种消息类型创建一个缓冲区
        self.buffers = {
            "chat": [],
            "gift": [],
            "follow": [],
            "like": [],
            "join": [],
            "statistics": [],
            "all": []
        }

    def add_message(self, category: str, message: dict):
        """
        添加一条消息到指定类别的缓冲区，同时存入 "all" 类别
        """
        if category not in self.buffers:
            raise ValueError(f"未知的消息类别：{category}")
        self.buffers[category].append(message)
        self.buffers["all"].append(message)

        # 达到最大长度则 flush
        if len(self.buffers[category]) >= self.max_length:
            self.flush(category)
        if len(self.buffers["all"]) >= self.max_length:
            self.flush("all")

    def flush(self, category: str):
        """
        将某一类别的缓冲区数据写入对应的 JSON 文件，然后清空该缓冲区
        """
        file_path = os.path.join(self.folder_path, f"{category}.json")
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if not isinstance(data, list):
                    data = []
            except (json.JSONDecodeError, IOError):
                data = []
        else:
            data = []

        data.extend(self.buffers[category])

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        self.buffers[category].clear()

    def flush_all(self):
        """
        将所有类别的缓冲区数据写入对应的 JSON 文件
        """
        for category in self.buffers:
            if self.buffers[category]:
                self.flush(category)

    def update_end_time(self, end_time: str):
        """
        直播结束后调用，更新 end_time，并重命名文件夹
        """
        self.end_time = end_time
        today = datetime.now().strftime("%Y-%m-%d")
        new_folder_name = f"{today}-{self.room_id}-{self.start_time}-{self.end_time}"
        new_folder_path = os.path.join(self.output_dir, new_folder_name)
        os.rename(self.folder_path, new_folder_path)
        self.folder_path = new_folder_path
