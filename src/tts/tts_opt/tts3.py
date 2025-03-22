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
    加强稳定性，防止播放过程中出现微小电流声或噪点。
    """
    import time

    p = pyaudio.PyAudio()
    stream = None

    while True:
        file_path = AUDIO_QUEUE.get()  # 阻塞等待队列内容
        if file_path is None:
            # None 表示没有后续音频，结束播放线程
            break

        # 打开 wav 文件
        wf = wave.open(file_path, 'rb')

        # 初始化 stream 或重建（确保参数一致）
        wf_format = p.get_format_from_width(wf.getsampwidth())
        wf_channels = wf.getnchannels()
        wf_rate = wf.getframerate()

        if stream is None:
            stream = p.open(
                format=wf_format,
                channels=wf_channels,
                rate=wf_rate,
                output=True
            )
        else:
            # 如果当前 stream 参数不匹配，重建 stream（防止杂音）
            if (stream._format != wf_format or
                    stream._channels != wf_channels or
                    stream._rate != wf_rate):
                stream.stop_stream()
                stream.close()
                stream = p.open(
                    format=wf_format,
                    channels=wf_channels,
                    rate=wf_rate,
                    output=True
                )

        # 播放音频内容，使用更大 buffer 避免杂音
        chunk_size = 2048
        data = wf.readframes(chunk_size)
        while data:
            stream.write(data, exception_on_underflow=False)
            data = wf.readframes(chunk_size)

        wf.close()

    # 结束播放，安全清理
    if stream is not None:
        stream.stop_stream()
        time.sleep(0.1)  # 确保缓冲区播放完毕
        stream.close()
    p.terminate()


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
        "fragment_interval": 0,
        "seed": 128123,
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
    阳光透过窗棂，落在案头的书页上，像一场不期而至的邂逅，温柔而静谧。
    """
    tts_in_chunks(text)
