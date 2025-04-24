"""Streaming TTS helper.

Wraps your FastAPI TTS endpoint at http://localhost:9880/tts and plays
WAV chunks via PyAudio **with interrupt support**.

Public API
==========
* **tts_streaming(text, speed_factor=1.2)** – blocking playback.
* **stop_tts_playback()**              – abort current playback (called
  by `TTSWorker.stop_current`).
"""
from __future__ import annotations

import io
import threading
import wave
from typing import Optional

import pyaudio
import requests

from src.tts.utils.split_text import process_text_for_tts

# ---------------------------------------------------------------------------
# Global playback state (protected by lock)
# ---------------------------------------------------------------------------
_playback_lock = threading.Lock()
_current_stream: Optional[pyaudio.Stream] = None
_current_pyaudio: Optional[pyaudio.PyAudio] = None
_stop_flag = threading.Event()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_text(text: str) -> str:
    """Remove </think>… and all bracketed segments."""
    idx = text.find("</think>")
    if idx != -1:
        text = text[idx + len("</think>"):].strip()
    stack, out = [], []
    for ch in text:
        if ch in ("(", "（"):
            stack.append(len(out))
        elif ch in (")", "）") and stack:
            out = out[: stack.pop()]
        elif not stack:
            out.append(ch)
    return "".join(out)


def _play_chunks(resp, chunk_size: int = 1024) -> None:
    """Stream WAV data to PyAudio, respecting _stop_flag."""
    global _current_stream, _current_pyaudio

    pa = pyaudio.PyAudio()
    _current_pyaudio = pa
    hdr_buf = b""
    header_done = False

    try:
        for chunk in resp.iter_content(chunk_size=chunk_size):
            if _stop_flag.is_set():
                break
            if not chunk:
                continue
            hdr_buf += chunk
            if not header_done and len(hdr_buf) >= 44:
                with wave.open(io.BytesIO(hdr_buf), "rb") as wf:
                    _current_stream = pa.open(
                        format=pa.get_format_from_width(wf.getsampwidth()),
                        channels=wf.getnchannels(),
                        rate=wf.getframerate(),
                        output=True,
                    )
                # write any audio that followed header
                data_start = hdr_buf[44:]
                if data_start:
                    _current_stream.write(data_start)
                header_done = True
                continue
            if header_done and _current_stream:
                _current_stream.write(chunk)
    except requests.exceptions.ChunkedEncodingError:
        print("[TTS] HTTP stream closed early – finishing playback")
    finally:
        if _current_stream:
            try:
                _current_stream.stop_stream()
                _current_stream.close()
            except Exception:
                pass
        pa.terminate()
        _current_stream = None
        _current_pyaudio = None
        _stop_flag.clear()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def tts_streaming(text: str, speed_factor: float = 1.2) -> None:
    """Blocking call: send ``text`` to TTS server and play it."""
    cleaned = _clean_text(text)
    processed = process_text_for_tts(cleaned)

    payload = {
        "text": processed,
        "text_lang": "zh",
        "ref_audio_path": "/Users/liuyitong/projects/Seranion/src/tts/audio/bear_reference.FLAC",
        "aux_ref_audio_paths": [],
        "prompt_lang": "zh",
        "prompt_text": "",
        "top_k": 5,
        "top_p": 1,
        "temperature": 0.5,
        "text_split_method": "cut0",
        "batch_size": 1,
        "split_bucket": True,
        "speed_factor": speed_factor,
        "fragment_interval": 0.3,
        "seed": 132094,
        "media_type": "wav",
        "streaming_mode": True,
        "parallel_infer": True,
        "repetition_penalty": 1.35,
    }

    try:
        resp = requests.post(
            "http://localhost:9880/tts",
            json=payload,
            stream=True,
            timeout=300,
        )
    except Exception as exc:
        raise RuntimeError(f"TTS HTTP request failed: {exc}") from exc

    if resp.status_code != 200:
        raise RuntimeError(f"TTS server error {resp.status_code}: {resp.text}")

    with _playback_lock:
        _stop_flag.clear()
    _play_chunks(resp)


def stop_tts_playback() -> None:
    """Abort the current sentence (used by TTSWorker.stop_current)."""
    with _playback_lock:
        _stop_flag.set()
        if _current_stream:
            try:
                _current_stream.stop_stream()
                _current_stream.close()
            except Exception:
                pass
            _current_stream = None
        if _current_pyaudio:
            try:
                _current_pyaudio.terminate()
            except Exception:
                pass
            _current_pyaudio = None


if __name__ == "__main__":
    text = """
     阳光透过窗帘缝隙洒在书桌上，空气中漂浮着轻微的灰尘，整个房间显得安静而慵懒。她坐在窗边，一边喝着热茶，一边看着手中的旧书。翻页的声音在静谧中格外清晰，仿佛时间都慢了下来。窗外的风轻轻拂过树梢，带来一阵微弱的花香。她忽然想起多年前的某个春日午后，也是这样安静、温暖，有点怀旧，有点安心。她轻轻叹了口气，嘴角却带着微笑。生活似乎没有太多波澜，却也因此多了一分安稳的味道。
 """

    tts_streaming(text)
