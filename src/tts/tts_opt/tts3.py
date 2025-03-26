# stream_tts.py
import requests
import pyaudio
import threading
import queue
import time


def play_audio_chunks(audio_queue: "queue.Queue[bytes]", stop_event: threading.Event):
    """
    播放音频原始 PCM 字节数据（16k/16bit/单声道）:
    - 不断从 audio_queue 中 get 音频数据
    - 当 stop_event.set() 或 取到 None 时结束
    """
    p = pyaudio.PyAudio()
    stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=16000,
        output=True
    )
    while not stop_event.is_set():
        try:
            chunk = audio_queue.get(timeout=0.1)
        except queue.Empty:
            continue
        if chunk is None:
            break
        stream.write(chunk)

    stream.stop_stream()
    stream.close()
    p.terminate()


def stream_tts(text: str):
    """
    向某个支持流式返回的 TTS 服务发送请求，边读边往队列里放 PCM。
    这个函数会阻塞，直到流式读取结束。
    """
    url = "http://localhost:9880/stream_tts"  # 假设这是你的流式TTS地址
    payload = {"text": text}
    # 假设服务会返回 chunked 音频流，每块都是 PCM
    with requests.post(url, json=payload, stream=True) as r:
        for chunk in r.iter_content(chunk_size=None):
            if chunk:
                yield chunk


def tts_and_play(text: str):
    """
    用队列 + 播放线程，实现边下边播。
    """
    audio_queue = queue.Queue()
    stop_event = threading.Event()
    player_thread = threading.Thread(target=play_audio_chunks, args=(audio_queue, stop_event))
    player_thread.start()

    try:
        for audio_chunk in stream_tts(text):
            audio_queue.put(audio_chunk)
    except Exception as e:
        print(f"TTS 流式播放异常: {e}")

    # 结束播放
    audio_queue.put(None)
    stop_event.set()
    player_thread.join()
