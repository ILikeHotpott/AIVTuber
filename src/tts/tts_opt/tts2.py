import os
import re
import wave
import queue
import pyaudio
import requests
import threading

# ========== 全局播放队列 ==========
AUDIO_QUEUE = queue.Queue()


def audio_player():
    """
    独立线程：循环从 AUDIO_QUEUE 中获取音频文件路径，用 pyaudio 实现连续播放。
    读到 None 表示没有后续音频，退出循环。
    """
    p = pyaudio.PyAudio()
    stream = None

    while True:
        file_path = AUDIO_QUEUE.get()  # 阻塞等待队列内容
        if file_path is None:
            # 我们约定，None 表示没有后续音频，停止播放线程
            break

        # 打开 wav 文件
        wf = wave.open(file_path, 'rb')
        # 如果第一次播放，需要初始化流
        if stream is None:
            stream = p.open(
                format=p.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True
            )

        # 以 1024 帧为单位，循环写入 stream
        data = wf.readframes(1024)
        while data:
            stream.write(data)
            data = wf.readframes(1024)

        wf.close()

    if stream is not None:
        stream.stop_stream()
        stream.close()
    p.terminate()


def clean_text(text: str) -> str:
    """
    1. 删除 </think> 及其之前的所有内容。
    2. 移除括号及其内部内容，支持嵌套括号，支持全角和半角。
    """
    idx = text.find("</think>")
    if idx != -1:
        text = text[idx + len("</think>"):].strip()

    stack = []
    result = []
    for char in text:
        if char in ('(', '（'):
            stack.append(len(result))
        elif char in (')', '）'):
            if stack:
                start = stack.pop()
                result = result[:start]
        else:
            if not stack:
                result.append(char)
    return ''.join(result)


def split_by_punctuation(text: str):
    """
    按照中文逗号、句号、感叹号进行分割，并保留标点符号本身，
    避免空段和重复段。
    """
    text = text.strip()
    parts = re.split(r'([，。！,.])', text)
    chunks = []
    for i in range(0, len(parts), 2):
        chunk_text = parts[i].strip()
        if not chunk_text:
            continue

        if i + 1 < len(parts):
            punct = parts[i + 1].strip()
            if punct:
                chunk_text += punct
        chunk_text = chunk_text.strip()

        if chunk_text:
            chunks.append(chunk_text)
    return chunks


def tts_chunk(text_chunk: str, index: int):
    """
    针对单个文本块调用 TTS 接口，并写入 output/output{index}.wav 文件。
    然后将该文件路径放入 AUDIO_QUEUE 中。
    """
    url = "http://localhost:9880/tts"
    payload = {
        "text": text_chunk,
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
        "batch_threshold": 0.75,
        "split_bucket": True,
        "speed_factor": 1,
        "fragment_interval": 0.1,
        "seed": 125235,
        "media_type": "wav",
        "streaming_mode": False,
        "parallel_infer": True,
        "repetition_penalty": 1.35
    }

    output_path = f"output/output{index}.wav"
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            with open(output_path, "wb") as f:
                f.write(response.content)
            print(f"第 {index} 个分段 TTS 完成：{output_path}")
            # 将音频文件路径放入播放队列
            AUDIO_QUEUE.put(output_path)
        else:
            print(f"第 {index} 个分段请求失败，状态码: {response.status_code}, 响应: {response.text}")
    except Exception as e:
        print(f"第 {index} 个分段 TTS 异常: {e}")


def tts_in_chunks(text: str):
    """
    将文本分段后，顺序执行 TTS，生成后立即将音频放入队列，让播放线程无缝播放。
    """
    text = clean_text(text)
    text = text.strip()
    chunks = split_by_punctuation(text)
    if not chunks:
        print("清洗后文本为空，无需处理。")
        return

    os.makedirs("output", exist_ok=True)

    player_thread = threading.Thread(target=audio_player, daemon=True)
    player_thread.start()

    # 顺序生成 TTS，每生成完一个就放进 AUDIO_QUEUE
    for i, chunk in enumerate(chunks, 1):
        tts_chunk(chunk, i)

    AUDIO_QUEUE.put(None)

    player_thread.join()
    print("所有分段播放完毕！")


if __name__ == "__main__":
    text = """
    阳光悄悄洒进窗台，咖啡香气弥漫，书页轻翻，生活的美好，藏在每个平凡而温柔的瞬间。
    
"""
    tts_in_chunks(text)
