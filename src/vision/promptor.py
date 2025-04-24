from typing import List, Dict, Any

BASE_INSTRUCTION = (
    "你正在实时观看 Whisper 的屏幕截图。"
    "请像坐在他旁边一样，用不超过40字简短的话，陪他他身边冲浪，可以好奇、疑问、吐槽。"
)


def build_prompt(extra_text: str = "") -> List[Dict[str, Any]]:
    """返回 Gemini content-parts（不含 image）"""
    txt = BASE_INSTRUCTION
    if extra_text:
        txt += "\n" + extra_text
    return [{"type": "text", "text": txt}]
