import os
import requests


def response_to_speech(response):
    url = "http://localhost:9880/tts"
    payload = {
        "text": response,
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
    text = """
    在一个阳光明媚的早晨，林浅浅走在去咖啡馆的路上，脑海中还在回味昨晚做的那个奇怪的梦。梦里她变成了一只猫，穿梭在城市的屋顶与街角，悄悄观察着人们的生活。有的人忙碌，有的人孤独，有的人快乐得像一首永不停歇的歌。梦醒之后，她有种说不清的感慨，仿佛那只猫是她心底的另一个自己，逃离现实、自由自在。咖啡馆的门铃叮当响起，她走进熟悉的空间，点了杯拿铁，坐到窗边的位置。外面的行人匆匆，世界还是一样地喧嚣。她翻开笔记本，开始记录下那只梦中的猫的故事。她打算写一个短篇小说，也许会叫《屋顶上的我》。她写着写着，突然觉得，也许生活的意义就藏在这种细碎的记录里。每一段文字，都是对自我的一次探索。窗外的阳光越发明亮，照进她的笔尖，也照亮了她的心。

夜幕缓缓降临，城市的灯光像星星一样亮起，倒映在玻璃大楼的外墙上。林浅浅依旧坐在咖啡馆的角落，敲打着笔记本的键盘。她已经写了三个小时，但却仍旧觉得故事不够完整。她想让那只猫不仅是观察者，也是一位改变者。或许，那只猫会在某个深夜，跳上一个孤独少年的窗台，与他静静对视，改变他一成不变的人生节奏；又或许，会陪伴一个年迈的画家，成为他最后一幅作品中的灵感缪斯。浅浅越写越投入，仿佛自己真的拥有了那只猫的视角，能听见它轻盈的脚步声，能感受到它跳跃屋檐时扑面而来的风。窗外，风轻轻吹动树叶，一片黄叶飘进咖啡馆，她随手拾起夹进笔记本里。这一刻，她明白了：写作不一定要有意义，但感受和表达本身就是一种意义。只要还有故事在心中燃烧，她就会一直写下去。

雨从下午就开始下了，一直没停，像是谁把天空的阀门打开忘了关。林浅浅坐在窗边，看着水珠顺着玻璃慢慢滑下。她没带伞，也不急着走。手边的书翻了几页，却怎么也看不进去。雨声、低沉的爵士乐、咖啡的香味交织在一起，形成了一种奇异的静谧。她突然想起小时候在老家，每次下雨都会坐在屋檐下，看着雨水从瓦片滴落，那时候没有烦恼，也不懂什么是孤独。现在长大了，反而越来越怀念那些无所事事的日子。她打开手机相册，翻出几张旧照片，笑着摇了摇头——原来那些看起来不起眼的瞬间，早已在心底生根发芽。她合上书，决定不再等雨停，直接走进雨里。街道被雨洗得干干净净，霓虹灯在水洼中晕染出五颜六色的梦。她拉高外套的帽子，踩着水花前行。雨水打湿了她的发梢，但她笑得像个刚从梦里醒来的孩子。
"""

    text1 = remove_bracketed_content(text)
    response_to_speech(text1)
