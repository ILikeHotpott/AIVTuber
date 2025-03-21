import requests
import pyaudio
import io
import wave
import threading
import queue
import re
import time


class AudioChunk:
    """音频块类，包含序列号和音频数据"""

    def __init__(self, sequence, audio_data):
        self.sequence = sequence
        self.audio_data = audio_data
        self.duration = None  # 音频时长（秒）


def split_text_by_punctuation(text):
    """按中英文标点符号分割文本"""
    # 定义可以结束一个语音块的标点
    punctuation = r'[，。！？；：,.!?;:]'

    # 找到所有标点符号位置
    positions = [m.start() for m in re.finditer(punctuation, text)]

    if not positions:
        return [text]

    chunks = []
    start = 0

    for pos in positions:
        # 包含标点符号在内的文本块
        chunks.append(text[start:pos + 1])
        start = pos + 1

    # 添加剩余文本
    if start < len(text):
        chunks.append(text[start:])

    return chunks


def get_audio_data(text, api_params):
    """发送文本到TTS API并返回音频数据"""
    url = "http://localhost:9880/tts"

    payload = api_params.copy()
    payload["text"] = text

    response = requests.post(url, json=payload)

    if response.status_code == 200:
        return response.content
    else:
        print(f"请求失败: {response.status_code}, 响应: {response.text}")
        return None


def get_audio_duration(audio_data):
    """从WAV音频数据中获取时长（秒）"""
    try:
        wav_file = io.BytesIO(audio_data)
        with wave.open(wav_file, 'rb') as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            duration = frames / float(rate)
            return duration
    except Exception as e:
        print(f"获取音频时长时出错: {e}")
        # 假定平均时长
        return len(audio_data) / 48000  # 粗略估计


def process_chunk(chunk_text, chunk_index, audio_queue, api_params):
    """处理单个文本块并将结果添加到队列"""
    try:
        print(f"处理块 {chunk_index}: {chunk_text}")
        audio_data = get_audio_data(chunk_text, api_params)
        if audio_data:
            chunk = AudioChunk(chunk_index, audio_data)
            chunk.duration = get_audio_duration(audio_data)
            audio_queue.put(chunk)
            print(f"块 {chunk_index} 处理成功，时长: {chunk.duration:.2f}秒")
    except Exception as e:
        print(f"处理块 {chunk_index} 时出错: {e}")


def play_audio_data(audio_data):
    """播放音频数据（bytes对象）"""
    p = pyaudio.PyAudio()
    audio_stream = None

    try:
        # 解析WAV头部
        wav_file = io.BytesIO(audio_data)
        with wave.open(wav_file, 'rb') as wf:
            format = p.get_format_from_width(wf.getsampwidth())
            channels = wf.getnchannels()
            rate = wf.getframerate()

            audio_stream = p.open(
                format=format,
                channels=channels,
                rate=rate,
                output=True
            )

            # 读取音频数据并播放
            chunk_size = 1024
            wav_file.seek(44)  # 跳过WAV头部
            data = wav_file.read(chunk_size)

            while data:
                audio_stream.write(data)
                data = wav_file.read(chunk_size)

            return True
    except Exception as e:
        print(f"播放音频时出错: {e}")
        # 尝试使用默认参数
        try:
            audio_stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=24000,
                output=True
            )
            # 跳过假定的头部
            audio_stream.write(audio_data[44:])
            return True
        except Exception as e2:
            print(f"备用播放也失败: {e2}")
            return False
    finally:
        if audio_stream:
            audio_stream.stop_stream()
            audio_stream.close()
        p.terminate()


def sequential_play_with_preparation(audio_queue, max_chunks, overlap_ratio=0.1):
    """
    按顺序播放音频块，同时提前准备下一个块
    overlap_ratio: 在当前块播放到总时长的多少比例时开始准备下一个块
    """
    next_chunk_index = 0
    chunks_buffer = {}

    while next_chunk_index < max_chunks:
        # 检查下一个块是否可用
        current_chunk = None

        # 从缓冲区获取或从队列获取
        if next_chunk_index in chunks_buffer:
            current_chunk = chunks_buffer.pop(next_chunk_index)
        else:
            # 从队列查找下一个块
            timeout_counter = 0
            while timeout_counter < 100:  # 最多等待10秒
                if audio_queue.empty():
                    time.sleep(0.1)
                    timeout_counter += 1
                    continue

                chunk = audio_queue.get()
                if chunk.sequence == next_chunk_index:
                    current_chunk = chunk
                    break
                else:
                    # 存储未按顺序到达的块
                    chunks_buffer[chunk.sequence] = chunk

                timeout_counter += 1

        if current_chunk:
            # 播放当前块
            print(f"播放块 {next_chunk_index}")

            # 计算何时开始准备下一个块
            if current_chunk.duration:
                prepare_next_at = current_chunk.duration * (1 - overlap_ratio)
            else:
                prepare_next_at = 1.0  # 默认1秒

            start_time = time.time()

            # 开始播放当前块
            play_thread = threading.Thread(target=play_audio_data, args=(current_chunk.audio_data,))
            play_thread.start()

            # 在当前块播放期间，如果即将完成，可以开始准备下一个块
            next_index = next_chunk_index + 1
            if next_index < max_chunks and next_index not in chunks_buffer:
                # 等待直到接近当前块的结束
                wait_time = prepare_next_at - (time.time() - start_time)
                if wait_time > 0:
                    time.sleep(wait_time)

                # 此时我们可以检查队列中是否有下一个块，没有的话可以提示应该准备了
                if next_index not in chunks_buffer and audio_queue.empty():
                    print(f"提醒：应该开始准备块 {next_index} 了")

            # 等待当前播放完成
            play_thread.join()

            # 移动到下一个块
            next_chunk_index += 1
        else:
            print(f"没有找到块 {next_chunk_index}，跳过")
            next_chunk_index += 1

    print("所有块处理并播放完成")


def clean_text(text: str) -> str:
    """
    1. 删除 </think> 及其之前的所有内容（包括 </think>）。
    2. 移除括号及其内部内容，支持嵌套括号，支持全角和半角。
    """
    # 第一步：删除 </think> 及其之前内容
    idx = text.find("</think>")
    if idx != -1:
        text = text[idx + len("</think>"):].strip()

    # 第二步：移除括号内容（支持嵌套，中英文括号）
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


def tts_streaming_improved(text, max_threads=3, overlap_ratio=0.1):
    """
    改进的TTS流式处理：
    1. 并行处理文本块生成音频
    2. 有序播放，一个接一个
    3. 在当前块快结束时开始准备下一个块

    overlap_ratio: 在当前块播放到总时长的多少比例时开始准备下一个块
    """
    cleaned_text = clean_text(text)
    chunks = split_text_by_punctuation(cleaned_text)

    # 准备API参数
    api_params = {
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
        "speed_factor": 1.05,
        "fragment_interval": 0.3,
        "seed": 666,
        "media_type": "wav",
        "streaming_mode": False,  # 我们自己处理流式播放
        "parallel_infer": True,
        "repetition_penalty": 1.35
    }

    # 创建音频块队列
    audio_queue = queue.Queue()

    # 启动播放线程
    playback_thread = threading.Thread(
        target=sequential_play_with_preparation,
        args=(audio_queue, len(chunks), overlap_ratio)
    )
    playback_thread.start()

    # 创建处理线程池
    processing_threads = []

    # 首先处理前几个块（最多max_threads个）
    initial_chunks = min(max_threads, len(chunks))
    for i in range(initial_chunks):
        thread = threading.Thread(
            target=process_chunk,
            args=(chunks[i], i, audio_queue, api_params)
        )
        thread.start()
        processing_threads.append(thread)

    # 处理剩余的块，在前一批处理完成后
    next_chunk_index = initial_chunks
    while next_chunk_index < len(chunks):
        # 等待一个线程完成
        time.sleep(0.5)
        active_threads = [t for t in processing_threads if t.is_alive()]

        # 如果有线程完成，添加新的处理任务
        if len(active_threads) < max_threads:
            new_threads = []
            for _ in range(min(max_threads - len(active_threads), len(chunks) - next_chunk_index)):
                thread = threading.Thread(
                    target=process_chunk,
                    args=(chunks[next_chunk_index], next_chunk_index, audio_queue, api_params)
                )
                thread.start()
                new_threads.append(thread)
                next_chunk_index += 1

            processing_threads = active_threads + new_threads

    # 等待所有处理线程完成
    for thread in processing_threads:
        thread.join()

    # 等待播放完成
    playback_thread.join()
    print("所有文本处理并播放完成")


if __name__ == "__main__":
    test_text = """
    清晨的城市被薄雾轻轻拥抱，街角早餐铺飘来油条豆浆的香气。地铁里人潮涌动，耳机里播放着熟悉的旋律。
    阳光逐渐穿破高楼缝隙，照亮奔忙的身影，平凡日子里，藏着生活最真实的温柔。
    """

    tts_streaming_improved(test_text, max_threads=3, overlap_ratio=0.1)