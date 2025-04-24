import os
import threading
from typing import Optional, Iterable

import pyaudio
from six.moves import queue
from google.cloud import speech
from dotenv import load_dotenv

# ------------------- env & constants -------------------
load_dotenv()
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")

RATE = 16_000
CHUNK = RATE // 10  # 100 ms


# ------------------- microphone stream -----------------
class MicrophoneStream:
    """Yield audio chunks; when pause_event is cleared, emit silence frames."""

    def __init__(self, rate: int = RATE, chunk: int = CHUNK):
        self.rate = rate
        self.chunk = chunk
        self._buff: queue.Queue[bytes | None] = queue.Queue()
        self.closed = True

    def __enter__(self):
        self._pa = pyaudio.PyAudio()
        self._stream = self._pa.open(
            format=pyaudio.paInt16, channels=1, rate=self.rate, input=True,
            frames_per_buffer=self.chunk, stream_callback=self._fill_buffer
        )
        self.closed = False
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._stream.stop_stream();
        self._stream.close();
        self._pa.terminate()
        self.closed = True
        self._buff.put(None)

    def _fill_buffer(self, in_data, *_):
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self, pause_event: Optional[threading.Event] = None):
        silence = b"\x00" * self.chunk * 2
        while not self.closed:
            if pause_event and not pause_event.is_set():
                yield silence
                continue
            data = self._buff.get()
            if data is None:
                return
            yield data
            while True:
                try:
                    data = self._buff.get_nowait()
                    if data is None:
                        return
                    yield data
                except queue.Empty:
                    break


# ------------------- streaming STT ---------------------
def google_streaming_transcripts(
        pause_event: threading.Event,
        on_partial: Optional[callable] = None,
) -> Iterable[str]:
    """
    Yields *final* transcripts. Calls `on_partial()` immediately when Google
    returns an interim hypothesis—可用于立刻 stop TTS。
    """
    client = speech.SpeechClient()
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        language_code="zh-CN",
        use_enhanced=True,
    )
    streaming_config = speech.StreamingRecognitionConfig(
        config=config,
        interim_results=True  # 打开 partial
    )

    with MicrophoneStream() as mic:
        requests = (
            speech.StreamingRecognizeRequest(audio_content=chunk)
            for chunk in mic.generator(pause_event=pause_event)
        )
        responses = client.streaming_recognize(streaming_config, requests)

        try:
            for resp in responses:
                if not resp.results:
                    continue
                res = resp.results[0]

                # ---------- 实时打断 ----------
                if not res.is_final and res.alternatives and on_partial:
                    on_partial()  # 通知外部“有人说话”
                    continue

                # ---------- 最终结果 ----------
                if res.is_final and res.alternatives:
                    yield res.alternatives[0].transcript.strip()
        except Exception as e:
            print("[ASR] Error:", e)
