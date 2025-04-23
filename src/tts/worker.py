import threading
import time
from collections import deque
from src.tts.tts_stream import tts_streaming


class TTSWorker(threading.Thread):
    """
    独立线程：不断从队列中取文本朗读。
    队列满时，新文本会替换旧排队内容；正在播放的文本不会被打断。
    """

    def __init__(self, max_queue: int = 2, poll_interval: float = 0.1):
        super().__init__(daemon=True)
        self.queue: deque[str] = deque(maxlen=max_queue)
        self._poll = poll_interval
        self._stop = threading.Event()

    def run(self) -> None:
        while not self._stop.is_set():
            if self.queue:
                text = self.queue.popleft()
                try:
                    tts_streaming(text)  # 阻塞播放
                except Exception as exc:
                    print(f"[TTSWorker] 播放失败：{exc}")
            else:
                time.sleep(self._poll)

    def enqueue(self, text: str) -> None:
        """如果队列已满就清空，只保留最新一条"""
        if len(self.queue) == self.queue.maxlen:
            self.queue.clear()
        self.queue.append(text)

    def stop(self) -> None:
        self._stop.set()
