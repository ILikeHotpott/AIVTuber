import queue, threading
from typing import Callable

from src.asr.google_asr import google_streaming_transcripts


class ASRWorker(threading.Thread):
    """
    Background thread:
      * writes final transcripts into `out_queue`
      * calls `on_partial_callback` as soon as Google returns an interim result
    """

    def __init__(
            self,
            out_queue: "queue.Queue[str]",
            pause_event: threading.Event,
            on_partial_callback: Callable[[], None] | None = None,
    ):
        super().__init__(daemon=True)
        self.out_q = out_queue
        self.pause_event = pause_event
        self.on_partial_callback = on_partial_callback
        self._stop = threading.Event()

    def run(self):
        for text in google_streaming_transcripts(
                pause_event=self.pause_event,
                on_partial=self.on_partial_callback,
        ):
            if self._stop.is_set():
                break
            if text:
                self.out_q.put(text)

    def stop(self):
        self._stop.set()
