import threading, queue
from typing import Callable, Optional
from src.asr.model import stream_transcripts


class ASRWorker(threading.Thread):
    def __init__(
            self,
            out_queue: "queue.Queue[str]",
            pause_event: threading.Event,
            on_partial_callback: Optional[Callable[[], None]] = None,
    ):
        super().__init__(daemon=True)
        self.out_q = out_queue
        self.pause_event = pause_event
        self.on_partial_callback = on_partial_callback
        self._stop = threading.Event()

    def run(self):
        last: str | None = None
        for text in stream_transcripts(
                pause_event=self.pause_event,
                on_partial=self.on_partial_callback,
        ):
            if self._stop.is_set():
                break

            text = text.strip()
            if not text:  # ② 过滤空字符串
                continue
            if text == last:  # ③ 连续重复也跳过
                continue

            self.out_q.put(text)
            last = text

    def stop(self):
        self._stop.set()
