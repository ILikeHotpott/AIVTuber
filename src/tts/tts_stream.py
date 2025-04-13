import requests
import pyaudio
import io
import wave
from src.tts.utils.split_text import process_text_for_tts


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


def stream_audio_response(response, chunk_size=1024):
    p = pyaudio.PyAudio()
    audio_stream = None
    buffer = b""
    header_parsed = False

    for chunk in response.iter_content(chunk_size=chunk_size):
        if chunk:
            buffer += chunk

            # 等待足够数据以解析 WAV 头
            if not header_parsed:
                try:
                    if len(buffer) >= 44:  # WAV header 至少需要 44 字节
                        wav_file = io.BytesIO(buffer)
                        with wave.open(wav_file, 'rb') as wf:
                            audio_stream = p.open(
                                format=p.get_format_from_width(wf.getsampwidth()),
                                channels=wf.getnchannels(),
                                rate=wf.getframerate(),
                                output=True
                            )
                            # 跳过 header，从数据块开始播放
                            wav_file.seek(44)  # 通常 WAV 音频数据从第 44 字节开始
                            remaining_data = wav_file.read()
                            if remaining_data:
                                audio_stream.write(remaining_data)
                        header_parsed = True
                        buffer = b""  # 清空 buffer，只留后续音频数据
                    continue
                except Exception as e:
                    print("解析WAV头失败，使用默认参数播放")
                    audio_stream = p.open(
                        format=pyaudio.paInt16,
                        channels=1,
                        rate=24000,
                        output=True
                    )
                    audio_stream.write(buffer)
                    buffer = b""
                    header_parsed = True
                    continue

            # 后续直接播放音频数据
            if audio_stream:
                audio_stream.write(chunk)

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
        "seed": 123789,
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


def tts_streaming(text):
    """
    Process text and send to streaming TTS
    """
    text1 = process_text_for_tts(clean_text(text))
    print(text1)
    response_to_speech_streaming(text1)


if __name__ == "__main__":
    text = """
Of course not. Who would fight with a platypus for cookies? I’m not a saint. Besides, would it appreciate the cookies I baked? I don’t know 🙂
    """

    tts_streaming(text)

    a = """
        In a quiet town by the sea, an old lighthouse stood tall, guiding ships through the darkest nights. 
        The waves crashed against the rocky shore, whispering secrets of the deep. Seagulls soared above,
        their cries echoing in the salty air. Life moved slowly, embraced by the ocean’s rhythm.
    """
