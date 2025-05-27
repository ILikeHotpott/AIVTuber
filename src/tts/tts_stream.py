"""
流式 TTS 播放器：
‣ tts_streaming(text)      把文本送到本地 http://localhost:9880/tts，边收边播
‣ stop_tts_playback()      线程安全地发停止信号（不直接关句柄）
"""

from __future__ import annotations

import io
import threading
import wave
import logging
from typing import Optional

import requests
import pyaudio

# ───────── 日志 ─────────
LOGGER = logging.getLogger("TTSStream")
# 若主程序未统一配置日志，可解开下一行
# logging.basicConfig(level=logging.INFO,
#                     format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# ───────── 全局播放状态 ─────────
_playback_lock = threading.Lock()
_current_stream: Optional[pyaudio.Stream] = None
_current_pyaudio: Optional[pyaudio.PyAudio] = None
_stop_flag = threading.Event()


# ───────── 文本清洗 ─────────
def _clean_text(text: str) -> str:
    """去掉 </think>… 和所有括号内容"""
    idx = text.find("</think>")
    if idx != -1:
        text = text[idx + len("</think>"):]

    stack, out = [], []
    for ch in text:
        if ch in ("(", "（"):
            stack.append(len(out))
        elif ch in (")", "）") and stack:
            out = out[: stack.pop()]
        elif not stack:
            out.append(ch)
    return "".join(out)


# ───────── 播放 WAV 流 ─────────
def _play_chunks(resp: requests.Response, chunk_size: int = 1024) -> None:
    """把 HTTP 响应中的 wav 字节流写进声卡；_stop_flag 为打断信号"""
    global _current_stream, _current_pyaudio
    pa = wave_file = None
    try:
        pa = pyaudio.PyAudio()
        _current_pyaudio = pa

        header_buf = b""
        header_done = False
        bytes_iter = resp.raw.stream(chunk_size, decode_content=False)

        for chunk in bytes_iter:
            if _stop_flag.is_set():
                LOGGER.info("收到停止信号，中断播放循环")
                break
            if not chunk:
                continue

            if not header_done:
                header_buf += chunk
                if len(header_buf) >= 44:  # 足够解析 wav 头
                    try:
                        with wave.open(io.BytesIO(header_buf), "rb") as wave_file:
                            fmt = pa.get_format_from_width(wave_file.getsampwidth())
                            _current_stream = pa.open(
                                format=fmt,
                                channels=wave_file.getnchannels(),
                                rate=wave_file.getframerate(),
                                output=True,
                            )
                        data_start = header_buf.find(b'data')
                        if data_start != -1:
                            data_start += 8
                            _current_stream.write(header_buf[data_start:])
                        header_done = True
                    except wave.Error as e:
                        LOGGER.error(f"WAV 头解析失败: {e}")
                        return
            else:
                _current_stream.write(chunk)

        if _current_stream:
            _current_stream.stop_stream()

    finally:
        if _current_stream:
            _current_stream.close()
        if _current_pyaudio:
            _current_pyaudio.terminate()
        _current_stream = None
        _current_pyaudio = None
        _stop_flag.clear()
        if resp:
            resp.close()


# ───────── 公开 API ─────────
def tts_streaming(text: str, speed_factor: float = 1.2) -> None:
    """阻塞：向 TTS 服务器发送文本并播放"""
    text = _clean_text(text.strip())
    if not text:
        return

    payload = {
        "text": text,
        "text_lang": "zh",
        "ref_audio_path": "/Users/liuyitong/projects/Seranion/src/tts/audio/bear_reference.FLAC",
        "prompt_lang": "zh",
        "speed_factor": speed_factor,
        "streaming_mode": True,
        "media_type": "wav",
    }
    url = "http://localhost:9880/tts"
    resp = requests.post(url, json=payload, stream=True, timeout=300)
    resp.raise_for_status()

    if resp.headers.get("Content-Type") != "audio/wav":
        raise RuntimeError(f"TTS server did not return audio/wav (got {resp.headers.get('Content-Type')})")

    with _playback_lock:  # 保证一次只播一条
        _stop_flag.clear()
        _play_chunks(resp)


def stop_tts_playback() -> None:
    """线程安全地请求停止播放"""
    _stop_flag.set()


if __name__ == "__main__":
    text = """
     阳光透过窗帘缝隙洒在书桌上，空气中漂浮着轻微的灰尘，整个房间显得安静而慵懒。她坐在窗边，一边喝着热茶，一边看着手中的旧书。翻页的声音在静谧中格外清晰，仿佛时间都慢了下来。窗外的风轻轻拂过树梢，带来一阵微弱的花香。她忽然想起多年前的某个春日午后，也是这样安静、温暖，有点怀旧，有点安心。她轻轻叹了口气，嘴角却带着微笑。生活似乎没有太多波澜，却也因此多了一分安稳的味道。
 """

    tts_streaming(text)
