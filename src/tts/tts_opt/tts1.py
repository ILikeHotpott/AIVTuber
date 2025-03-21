import os
import re
import time
import requests
import threading


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


def split_by_punctuation(text: str):
    """
    按照中文逗号、句号、感叹号进行分割，并保留标点符号本身。
    以避免空段和重复段的方式进行处理。
    """
    # 去除开头结尾多余空白，减少空段
    text = text.strip()

    # 用正则把文本按（，。！）分割，并保留分隔符
    # parts: ["清晨的城市被薄雾轻轻拥抱", "，", "阳光透过云层洒下金色的光芒", "。", "街道上", "，", ...]
    parts = re.split(r'([，。！])', text)

    chunks = []
    # i 走 0,2,4,... 偶数位；i+1 如果存在，则是那个标点
    for i in range(0, len(parts), 2):
        chunk_text = parts[i].strip()
        if not chunk_text:
            continue

        # 如果 i+1 < len(parts)，则 parts[i+1] 为标点
        if i + 1 < len(parts):
            punct = parts[i + 1].strip()
            # 拼上标点
            if punct:
                chunk_text += punct
        # 再 strip 一下
        chunk_text = chunk_text.strip()

        if chunk_text:
            chunks.append(chunk_text)

    return chunks


def tts_chunk(text_chunk: str, index: int):
    """
    针对单个文本块调用 TTS 接口，并写入 output/output{index}.wav 文件。
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
        "fragment_interval": 0.3,
        "seed": 123456,
        "media_type": "wav",
        "streaming_mode": False,
        "parallel_infer": True,
        "repetition_penalty": 1.35
    }

    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            output_path = f"output/output{index}.wav"
            with open(output_path, "wb") as f:
                f.write(response.content)
            print(f"第 {index} 个分段 TTS 完成：{output_path}")
        else:
            print(f"第 {index} 个分段请求失败，状态码: {response.status_code}, 响应: {response.text}")
    except Exception as e:
        print(f"第 {index} 个分段 TTS 异常: {e}")


def tts_in_chunks(text: str):
    """
    将文本分段后，启动多线程 TTS 并按顺序播放。
    """
    text = clean_text(text)
    text = text.strip()

    # 3. 分段
    chunks = split_by_punctuation(text)
    if not chunks:
        print("清洗后文本为空，无需处理。")
        return

    # 4. 确保 output 文件夹存在
    os.makedirs("output", exist_ok=True)

    # 5. 启动多线程并行 TTS
    threads = []
    for i, chunk in enumerate(chunks, 1):
        t = threading.Thread(target=tts_chunk, args=(chunk, i))
        t.start()
        threads.append(t)

    # 6. 按顺序播放（边生成边播放）
    for i, chunk in enumerate(chunks, 1):
        output_file = f"output/output{i}.wav"
        while not os.path.exists(output_file):
            time.sleep(0.1)

        print(f"开始播放第 {i} 个分段：{chunk}")
        # 这里用 afplay 播放并阻塞，直到播放结束；其他平台可换成合适的播放命令
        os.system(f"afplay '{output_file}'")
        print(f"播放结束：{output_file}")

    print("全部分段播放完成！")


if __name__ == "__main__":
    text = """
    清晨的城市被薄雾轻轻拥抱，阳光透过云层洒下金色的光芒。街道上，早起的人们匆匆赶往工作。
    小鸟在树枝间欢快地歌唱，为这个美好的早晨增添了生机！
    """
    tts_in_chunks(text)
