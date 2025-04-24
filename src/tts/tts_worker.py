import threading, time
from collections import deque
from src.tts.tts_stream import tts_streaming


class TTSWorker(threading.Thread):
    def __init__(self, max_queue: int = 2, poll: float = .1):
        super().__init__(daemon=True)
        self.q: deque[str] = deque(maxlen=max_queue)
        self._poll = poll
        self._stop = threading.Event()

    def run(self):
        while not self._stop.is_set():
            if self.q:
                txt = self.q.popleft()
                try:
                    tts_streaming(txt)
                except Exception as e:
                    print("[TTS] 播放失败:", e)
            else:
                time.sleep(self._poll)

    def enqueue(self, txt: str):
        if len(self.q) == self.q.maxlen:
            self.q.clear()
        self.q.append(txt)

    def stop(self):
        self._stop.set()
