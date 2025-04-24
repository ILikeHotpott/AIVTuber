"""
TTSWorker  –  background thread that plays sentences one-by-one
via `tts_streaming()`, supports:

* enqueue(text)      – 把句子加入播放队列（长度上限 max_queue）
* stop_current()     – 立即打断正在播放的句子
* flush_queue()      – 清空尚未播放的队列
* stop()             – 结束线程（会先打断当前播放）
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Deque

from src.tts.tts_stream import tts_streaming, stop_tts_playback


class TTSWorker(threading.Thread):
    def __init__(self, max_queue: int = 2, idle_sleep: float = 0.05):
        super().__init__(daemon=True)
        self._queue: Deque[str] = deque(maxlen=max_queue)
        self._idle = idle_sleep
        self._terminate = threading.Event()
        self._playing = threading.Event()

    # ---------- public API ----------
    def enqueue(self, text: str) -> None:
        """Add a sentence; drop backlog if queue is full."""
        if len(self._queue) == self._queue.maxlen:
            self._queue.clear()
        self._queue.append(text)

    def stop_current(self) -> None:
        """Abort the sentence currently being spoken."""
        if self._playing.is_set():
            try:
                stop_tts_playback()  # implemented in tts_stream.py
            except Exception:
                pass
            self._playing.clear()

    def flush_queue(self) -> None:
        """Remove all pending sentences (does NOT stop current)."""
        self._queue.clear()

    def stop(self) -> None:
        """Terminate the worker thread."""
        self._terminate.set()
        self.stop_current()

    # ---------- thread loop ----------
    def run(self) -> None:
        while not self._terminate.is_set():
            if self._queue:
                text = self._queue.popleft()
                self._playing.set()
                try:
                    tts_streaming(text)
                except Exception as exc:
                    print(f"[TTSWorker] playback failed: {exc}")
                self._playing.clear()
            else:
                time.sleep(self._idle)

    @property
    def is_playing(self) -> bool:
        return self._playing.is_set()
