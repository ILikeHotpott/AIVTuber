import os
import websocket
import sounddevice as sd
import numpy as np
import json
import base64
import struct
import threading
import simpleaudio as sa
from dotenv import load_dotenv

load_dotenv()

# ========== 配置 ==========
API_KEY = os.getenv("OPENAI_API_KEY")
WS_URL = "wss://api.openai.com/v1/realtime"
VOICE = "echo"
MODEL = "gpt-4o-realtime-preview"
SAMPLE_RATE = 16000
CHUNK = 1024  # 实时采集的每个帧大小


# ========== 音频处理 ==========
def float_to_pcm16(float_array):
    clipped = np.clip(float_array, -1.0, 1.0)
    int_samples = (clipped * 32767).astype(np.int16)
    return int_samples.tobytes()


def play_audio_from_base64(b64_audio):
    raw = base64.b64decode(b64_audio)
    try:
        wave_obj = sa.WaveObject(raw, num_channels=1, bytes_per_sample=2, sample_rate=SAMPLE_RATE)
        wave_obj.play()
    except Exception as e:
        print("播放失败:", e)


# ========== WebSocket 交互 ==========
def on_message(ws, message):
    data = json.loads(message)
    if data["type"] == "response.audio.delta":
        audio_chunk = data["delta"]
        play_audio_from_base64(audio_chunk)
    elif data["type"] == "response.text.delta":
        print("📝", data["delta"]["text"], end='', flush=True)
    elif data["type"] == "response.done":
        print("\n✅ 响应完成\n")


def on_error(ws, error):
    print("❌ 错误:", error)


def on_close(ws, close_status_code, close_msg):
    print("🔒 连接关闭")


def on_open(ws):
    print("✅ WebSocket 连接已建立")

    # 初始化 session
    session_update = {
        "type": "session.update",
        "session": {
            "model": MODEL,
            "voice": VOICE,
            "instructions": "You are a helpful assistant.",
            "modalities": ["audio", "text"],
            "input_audio_format": {
                "type": "linear_pcm",
                "sample_rate": SAMPLE_RATE,
                "channels": 1,
                "sample_size": 16
            },
            "output_audio_format": {
                "type": "linear_pcm"
            }
        }
    }
    ws.send(json.dumps(session_update))

    # 启动录音线程
    threading.Thread(target=stream_audio_from_microphone, args=(ws,), daemon=True).start()


def stream_audio_from_microphone(ws):
    print("🎤 开始录音（按 Ctrl+C 停止）...")

    def callback(indata, frames, time, status):
        if status:
            print("⚠️", status)
        audio_bytes = float_to_pcm16(indata[:, 0])
        encoded = base64.b64encode(audio_bytes).decode("ascii")
        ws.send(json.dumps({
            "type": "input_audio_buffer.append",
            "audio": encoded
        }))

    try:
        print(sd.query_devices())
        with sd.InputStream(device=1, samplerate=SAMPLE_RATE, channels=1, dtype='float32', blocksize=CHUNK, callback=callback):
            while True:
                sd.sleep(1000)
    except KeyboardInterrupt:
        print("🛑 停止录音")
        ws.close()


# ========== 启动 ==========
def start_realtime():
    ws = websocket.WebSocketApp(
        WS_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        header={"Authorization: Bearer " + API_KEY}
    )
    ws.run_forever()


if __name__ == "__main__":
    start_realtime()
