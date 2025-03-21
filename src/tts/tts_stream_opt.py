import requests

import pyaudio
import wave
import io
import logging

logging.basicConfig(level=logging.INFO)


def parse_wav_header(buffer):
    try:
        wav_file = io.BytesIO(buffer)
        with wave.open(wav_file, 'rb') as wf:
            format_info = {
                'format': pyaudio.PyAudio().get_format_from_width(wf.getsampwidth()),
                'channels': wf.getnchannels(),
                'rate': wf.getframerate()
            }
            wav_file.seek(44)
            remaining_data = wav_file.read()
            return format_info, remaining_data
    except wave.Error as e:
        logging.warning(f"WAV 头解析失败: {e}")
        return None, None


def stream_audio_response(response, chunk_size=1024):
    p = pyaudio.PyAudio()
    audio_stream = None
    buffer = b""
    header_parsed = False

    try:
        for chunk in response.iter_content(chunk_size=chunk_size):
            if not chunk:
                continue

            buffer += chunk

            if not header_parsed and len(buffer) >= 44:
                format_info, initial_audio = parse_wav_header(buffer)
                if format_info:
                    audio_stream = p.open(
                        format=format_info['format'],
                        channels=format_info['channels'],
                        rate=format_info['rate'],
                        output=True
                    )
                    if initial_audio:
                        audio_stream.write(memoryview(initial_audio))
                else:
                    # 回退方案：使用默认参数
                    logging.info("使用默认参数播放")
                    audio_stream = p.open(
                        format=pyaudio.paInt16,
                        channels=1,
                        rate=24000,
                        output=True
                    )
                    audio_stream.write(memoryview(buffer))
                header_parsed = True
                buffer = b""
                continue

            if header_parsed and audio_stream:
                audio_stream.write(memoryview(chunk))

    except Exception as e:
        logging.error(f"播放过程中出错: {e}")
    finally:
        if audio_stream:
            audio_stream.stop_stream()
            audio_stream.close()
        p.terminate()


def response_to_speech_streaming(text):
    """
    Send text to TTS API and play the response in streaming mode.

    Args:
        text: The text to be synthesized
    """
    url = "http://localhost:9880/tts"
    payload = {
        "text": text,
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
        "media_type": "wav",  # Using WAV format for streaming
        "streaming_mode": True,  # Enable streaming mode
        "parallel_infer": True,
        "repetition_penalty": 1.35
    }

    response = requests.post(url, json=payload, stream=True)

    if response.status_code == 200:
        print("开始播放流式音频...")
        stream_audio_response(response)
        print("音频播放完毕")
    else:
        print(f"请求失败，状态码: {response.status_code}, 响应: {response.text}")


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


def tts_streaming(text):
    """
    Process text and send to streaming TTS
    """
    text1 = clean_text(text)
    response_to_speech_streaming(text1)


if __name__ == "__main__":
    text = """
    清晨的城市被薄雾轻轻拥抱，街角早餐铺飘来油条豆浆的香气。地铁里人潮涌动，耳机里播放着熟悉的旋律。
    阳光逐渐穿破高楼缝隙，照亮奔忙的身影，平凡日子里，藏着生活最真实的温柔。
"""

    text1 = clean_text(text)
    print(text1)
    response_to_speech_streaming(text1)

    a = """
        In a quiet town by the sea, an old lighthouse stood tall, guiding ships through the darkest nights. 
        The waves crashed against the rocky shore, whispering secrets of the deep. Seagulls soared above,
        their cries echoing in the salty air. Life moved slowly, embraced by the ocean’s rhythm.
    """
