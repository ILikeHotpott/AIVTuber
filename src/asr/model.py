# --- dependencies ---
# pip install sounddevice soundfile numpy webrtcvad lightning-whisper-mlx

from __future__ import annotations
import threading, time, tempfile, collections, itertools
from typing import Iterable, Callable, Optional, Deque

import numpy as np, sounddevice as sd, soundfile as sf, webrtcvad
from lightning_whisper_mlx import LightningWhisperMLX

# ---------- 参数 ----------
SAMPLE_RATE = 16_000
FRAME_DURATION_MS = 30  # WebRTC VAD 支持 10 / 20 / 30
FRAME_SIZE = SAMPLE_RATE * FRAME_DURATION_MS // 1000  # samples / frame
MAX_SILENCE_FRAMES = int(0.6 * 1000 / FRAME_DURATION_MS)  # 0.6s
MIN_SPEECH_FRAMES = int(0.3 * 1000 / FRAME_DURATION_MS)  # 0.3s
VAD_SENSITIVITY = 2  # 0=最宽松, 3=最严格
DEBUG = False

_model: LightningWhisperMLX | None = None


def _lazy_model() -> LightningWhisperMLX:
    global _model
    if _model is None:
        print("⌛ 正在加载 Whisper-MLX…")
        _model = LightningWhisperMLX(model="small", batch_size=12)
        print("✅ Whisper-MLX ready")
    return _model


def stream_transcripts(
        pause_event: threading.Event,
        on_partial: Optional[Callable[[], None]] = None,
) -> Iterable[str]:
    """
    + pause_event.clear()  → 静音麦
    + on_partial()         → 第一帧语音立刻调用（可用于 stop-TTS）
    """
    whisper = _lazy_model()
    vad = webrtcvad.Vad(VAD_SENSITIVITY)

    def is_speech(frame: bytes) -> bool:
        return vad.is_speech(frame, SAMPLE_RATE)

    with sd.RawInputStream(
            samplerate=SAMPLE_RATE, channels=1, blocksize=FRAME_SIZE, dtype="int16"
    ) as stream:
        buf: Deque[bytes] = collections.deque()
        silence = 0
        speech = 0
        spoke = False

        while True:
            if not pause_event.is_set():  # 麦克风被静音
                stream.read(FRAME_SIZE)
                continue

            data, _ = stream.read(FRAME_SIZE)
            if len(data) == 0:
                continue

            talking = is_speech(data)

            if DEBUG:
                print("🗣️" if talking else "·", end="", flush=True)

            if talking:
                if not spoke and on_partial:
                    on_partial()  # 第一次检测到语音
                buf.append(data)
                silence = 0
                speech += 1
                spoke = True
            else:
                if spoke:
                    silence += 1

            # 语音结束：累积静默 > MAX_SILENCE_FRAMES
            if spoke and silence >= MAX_SILENCE_FRAMES:
                if speech >= MIN_SPEECH_FRAMES:
                    pcm = b"".join(buf)
                    wav = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                        sf.write(tmp.name, wav, SAMPLE_RATE, subtype="PCM_16")
                        t0 = time.perf_counter()
                        text = whisper.transcribe(audio_path=tmp.name)["text"].strip()
                        print(f"\n[Whisper] ⏱ {(time.perf_counter() - t0):.2f}s -> {text}")
                        yield text
                # reset
                buf.clear()
                silence = speech = 0
                spoke = False
                if DEBUG: print()  # 换行显示
