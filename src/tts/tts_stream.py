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
import socket
import json
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

# ───────── Unity Socket 连接 ─────────
_unity_socket = None
_unity_connected = False
UNITY_HOST = "localhost"
UNITY_PORT = 5005


def _connect_unity():
    """连接到Unity TCP服务器"""
    global _unity_socket, _unity_connected
    try:
        _unity_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _unity_socket.connect((UNITY_HOST, UNITY_PORT))
        _unity_connected = True
        LOGGER.info(f"Connected to Unity at {UNITY_HOST}:{UNITY_PORT}")
    except Exception as e:
        LOGGER.warning(f"Failed to connect to Unity: {e}")
        _unity_connected = False
        _unity_socket = None


def _send_unity_command(command: str):
    """发送命令到Unity"""
    global _unity_socket, _unity_connected
    if not _unity_connected or not _unity_socket:
        # 尝试重新连接
        _connect_unity()
        if not _unity_connected:
            return

    try:
        message = json.dumps({"command": command})
        _unity_socket.send(message.encode('utf-8'))
        LOGGER.info(f"Sent to Unity: {command}")
    except Exception as e:
        LOGGER.warning(f"Failed to send command to Unity: {e}")
        _unity_connected = False
        if _unity_socket:
            try:
                _unity_socket.close()
            except:
                pass
            _unity_socket = None


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
    speaking_started = False

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
                            if not speaking_started:
                                # 开始播放音频，通知Unity开始张嘴
                                _send_unity_command("START_SPEAK")
                                speaking_started = True
                            _current_stream.write(header_buf[data_start:])
                        header_done = True
                    except wave.Error as e:
                        LOGGER.error(f"WAV 头解析失败: {e}")
                        return
            else:
                if not speaking_started:
                    # 开始播放音频，通知Unity开始张嘴
                    _send_unity_command("START_SPEAK")
                    speaking_started = True
                _current_stream.write(chunk)

        if _current_stream:
            _current_stream.stop_stream()

    finally:
        # 播放结束，通知Unity停止张嘴
        if speaking_started:
            _send_unity_command("STOP_SPEAK")

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
def tts_streaming(text: str, speed_factor: float = 1.1) -> None:
    """阻塞：向 TTS 服务器发送文本并播放"""
    text = _clean_text(text.strip())
    if not text:
        return

    payload = {
        "text": text,
        "text_lang": "en",
        "ref_audio_path": "/Users/liuyitong/projects/Seranion/src/tts/audio/Ulia_ref.mp3",
        "prompt_lang": "en",
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
    # 停止时也通知Unity停止张嘴
    _send_unity_command("STOP_SPEAK")


# ───────── 初始化Unity连接 ─────────
def init_unity_connection():
    """初始化Unity连接"""
    _connect_unity()


if __name__ == "__main__":
    text = """
  Currently? Mastering the art of looking effortlessly cool while pretending to scroll through… things. It's a vital skill for a streamer, you know. Gotta maintain the illusion of a life, even if it's mostly just waiting for *you* guys to give me something to react to. Don't read too much into it. It's not like I *need* entertainment. Just… observing. Yeah, observing.
 """

    # 初始化Unity连接
    init_unity_connection()
    tts_streaming(text)
