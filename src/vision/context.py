from collections import deque
from datetime import datetime


class VisionContext:
    """
    保存最近 5 条屏幕描述，并生成可插入的 vision_prompt 字符串
    """

    def __init__(self, max_items: int = 5) -> None:
        self.max_items = max_items
        self._buffer: deque[tuple[str, str]] = deque(maxlen=max_items)  # (ts, desc)

    # ---------- 写入 ----------
    def add(self, description: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self._buffer.appendleft((ts, description.strip()))

    # ---------- 读取 ----------
    def prompt_block(self) -> str:
        """
        生成拼接好的屏幕描述段落，用于放进 vision_prompt
        """
        if not self._buffer:
            return "（暂时没有可评论的屏幕内容）"

        joined = "\n".join(
            f"- [{ts}] {desc}" for ts, desc in self._buffer
        )
        return f"【最近屏幕画面】\n{joined}"
