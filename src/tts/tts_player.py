import io
import json
import logging
import socket
import threading
import wave
from typing import Optional

import pyaudio
import requests

from src.tts.tts_config import TTSConfig

try:
    from src.memory.long_term.elastic_search import LongTermMemoryES
    from src.prompt.templates.general import (
        general_settings_prompt_english,
    )
    from src.utils.path import find_project_root
except ImportError:
    # Allow the module to be imported outside the mono‑repo for testing.
    LongTermMemoryES = None
    general_settings_prompt_english = "You are a helpful assistant."


# ---------------------------------------------------------------------------
# TTS Subsystem
# ---------------------------------------------------------------------------

class TTSPlayer:
    def __init__(self, config: TTSConfig, logger: logging.Logger | None = None) -> None:
        self.config = config
        self.server_url = self.config.server_url.rstrip("/")
        self.ref_audio_path = self.config.ref_audio_path
        self.unity_host = self.config.unity_host
        self.unity_port = self.config.unity_port
        self.language = self.config.language
        self.speed_factor = self.config.speed_factor
        self._connect_to_unity = self.config.connect_to_unity

        self._logger = logger or logging.getLogger(self.__class__.__name__)

        self._playback_lock = threading.Lock()
        self._stop_flag = threading.Event()
        self._current_stream: Optional[pyaudio.Stream] = None
        self._current_pyaudio: Optional[pyaudio.PyAudio] = None

        self._unity_socket: Optional[socket.socket] = None
        self._unity_connected = False

        self._busy = threading.Event()
        self._busy.clear()

        if self._connect_to_unity:
            self._connect_unity()

    # ───── Public API ─────

    def stream(self, text: str) -> None:
        """Blocking call — synthesize *text* and play through the speakers."""
        cleaned = self._clean_text(text)
        if not cleaned:
            return

        payload = {
            "text": cleaned,
            "text_lang": self.language,
            "prompt_lang": self.language,
            "speed_factor": self.speed_factor,
            "streaming_mode": True,
            "media_type": "wav",
        }
        if self.ref_audio_path:
            payload["ref_audio_path"] = self.ref_audio_path

        resp = requests.post(self.server_url, json=payload, stream=True, timeout=300)
        resp.raise_for_status()
        if resp.headers.get("Content-Type") != "audio/wav":
            raise RuntimeError("TTS server did not return audio/wav")

        # with self._playback_lock:
        #     self._stop_flag.clear()
        #     self._play_chunks(resp)
        self._busy.set()
        try:
            self._play_chunks(resp)
        finally:
            self._busy.clear()

    def is_busy(self) -> bool:
        return self._busy.is_set()

    def stop(self) -> None:
        """Request stop (non‑blocking, thread‑safe)."""
        self._stop_flag.set()
        self._send_unity_command("STOP_SPEAK")

    def close(self) -> None:
        """Release resources (socket, pyaudio)."""
        self.stop()
        if self._unity_socket:
            try:
                self._unity_socket.close()
            finally:
                self._unity_socket = None

    # ───── Internal helpers ─────

    def _connect_unity(self) -> None:
        try:
            self._unity_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._unity_socket.connect((self.unity_host, self.unity_port))
            self._unity_connected = True
            self._logger.info("Connected to Unity at %s:%d", self.unity_host, self.unity_port)
        except Exception as exc:  # pragma: no cover
            self._logger.warning("Unity connection failed: %s", exc)
            self._unity_connected = False
            self._unity_socket = None

    def _send_unity_command(self, command: str) -> None:
        if not self._connect_to_unity:
            return  # Skip if not connecting to Unity

        if not self._unity_connected or not self._unity_socket:
            self._connect_unity()
            if not self._unity_connected:
                return
        try:
            msg = json.dumps({"command": command}).encode()
            self._unity_socket.send(msg)
        except Exception as exc:  # pragma: no cover
            self._logger.warning("Failed to send Unity command: %s", exc)
            self._unity_connected = False
            if self._unity_socket:
                self._unity_socket.close()
            self._unity_socket = None

    @staticmethod
    def _clean_text(text: str) -> str:
        """Remove inner monologue tags and bracketed content."""
        idx = text.find("</think>")
        if idx != -1:
            text = text[idx + len("</think>"):]
        # Strip parentheses/brackets
        depth = 0
        out: list[str] = []
        for ch in text:
            if ch in "(（":
                depth += 1
                continue
            if ch in ")）":
                depth = max(depth - 1, 0)
                continue
            if depth == 0:
                out.append(ch)
        return "".join(out).strip()

    def _play_chunks(self, resp: requests.Response, chunk_size: int = 1024) -> None:  # noqa: C901
        pa = wave_file = None
        try:
            pa = pyaudio.PyAudio()
            header_buf = b""
            header_done = False
            stream_started = False

            for chunk in resp.raw.stream(chunk_size, decode_content=False):
                if self._stop_flag.is_set():
                    self._logger.debug("Stop flag set — abort playback")
                    break
                if not chunk:
                    continue

                if not header_done:
                    header_buf += chunk
                    if len(header_buf) >= 44:  # WAV header size
                        try:
                            with wave.open(io.BytesIO(header_buf), "rb") as wave_file:
                                fmt = pa.get_format_from_width(wave_file.getsampwidth())
                                self._current_stream = pa.open(
                                    format=fmt,
                                    channels=wave_file.getnchannels(),
                                    rate=wave_file.getframerate(),
                                    output=True,
                                )
                            # locate 'data' chunk offset
                            data_offset = header_buf.find(b"data")
                            if data_offset != -1:
                                data_offset += 8
                                self._send_unity_command("START_SPEAK")
                                stream_started = True
                                self._current_stream.write(header_buf[data_offset:])
                            header_done = True
                        except wave.Error as exc:
                            self._logger.error("Failed WAV header parse: %s", exc)
                            return
                else:
                    if not stream_started:
                        self._send_unity_command("START_SPEAK")
                        stream_started = True
                    self._current_stream.write(chunk)

            if self._current_stream:
                self._current_stream.stop_stream()
        finally:
            if stream_started:
                self._send_unity_command("STOP_SPEAK")
            if self._current_stream:
                self._current_stream.close()
            if pa:
                pa.terminate()
            self._current_stream = None
            self._stop_flag.clear()
            resp.close()


if __name__ == "__main__":
    tts_config = TTSConfig()
    tts_worker = TTSPlayer(config=tts_config, connect_to_unity=False)
    tts_worker.stream("How do you think of me honey?")
