import os
import re
import requests


def response_to_speech(response):
    url = "http://localhost:9880/tts"
    payload = {
        "text": response,
        "text_lang": "zh",
        "ref_audio_path": "/Users/liuyitong/projects/Seranion/src/tts/audio/neuro_sample.FLAC",
        "aux_ref_audio_paths": [],
        "prompt_lang": "zh",
        "prompt_text": "",
        "top_k": 5,
        "top_p": 1,
        "temperature": 0.5,
        "text_split_method": "cut5",
        "batch_size": 1,
        "batch_threshold": 0.75,
        "split_bucket": True,
        "speed_factor": 1,
        "fragment_interval": 0.3,
        "seed": -1,
        "media_type": "wav",
        "streaming_mode": False,
        "parallel_infer": True,
        "repetition_penalty": 1.35
    }

    response = requests.post(url, json=payload)
    if response.status_code == 200:
        with open("output.wav", "wb") as f:
            f.write(response.content)
            print("语音合成成功，已保存为 output.wav")
            os.system("afplay output.wav")

    else:
        print(f"请求失败，状态码: {response.status_code}, 响应: {response.text}")


def remove_bracketed_content(s: str) -> str:
    """
    移除字符串中所有括号及其内部的内容（支持嵌套括号，支持全角和半角）。
    """
    stack = []
    result = []

    for char in s:
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


def tts(text):
    text1 = remove_bracketed_content(text)
    text2 = extract_text_after_think(text1)
    response_to_speech(text2)


def extract_text_after_think(text):
    """
    Extracts the text after </think> and removes everything before it.
    """
    idx = text.find("</think>")
    return text[idx + 8:].strip() if idx != -1 else ""


if __name__ == "__main__":
    text = """是的，ElevenLabs 允许您上传一段音频来克隆声音，并将其用作模型。您需要创建一个免费账户，然后在语音合成页面的设置中上传音频文件."""

    text1 = remove_bracketed_content(text)
    response_to_speech(text1)
