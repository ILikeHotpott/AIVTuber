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
        if char in ('(', '（'):  # 识别半角和全角左括号
            stack.append(len(result))  # 记录括号的起始位置
        elif char in (')', '）'):  # 识别半角和全角右括号
            if stack:
                start = stack.pop()
                result = result[:start]  # 删除最近的匹配括号及其内容
        else:
            if not stack:  # 只有当栈为空时，才添加到结果
                result.append(char)

    return ''.join(result)



if __name__ == "__main__":
    text = """
哼哼~当然是京都的古街啦！穿着振袖踩着木屐转圈圈的时候，某个笨蛋要负责帮我拍三百张照片哦~（突然抱臂扭头）才、才不是想和你去呢！只是刚好缺个拎包的人而已！
"""
    text1 = remove_bracketed_content(text)
    response_to_speech(text1)
