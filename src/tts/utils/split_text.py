import re

PUNCT = "。？！，,!?;；:："  # 便于复用


def split_into_sentences(text: str) -> list[str]:
    """按中英文标点切分，标点保留在前一段末尾"""
    pattern = fr"([{PUNCT}])"
    parts = re.split(pattern, text)

    sentences = []
    for i in range(0, len(parts), 2):
        chunk = parts[i]
        if i + 1 < len(parts):
            chunk += parts[i + 1]  # 把标点拼回
        if chunk.strip():
            sentences.append(chunk.strip())
    return sentences


def merge_small_fragments(parts: list[str], thresh: int = 3) -> list[str]:
    """把 <= thresh 字的碎片合并到相邻块（优先向前合并）"""
    merged = []
    for seg in parts:
        if len(seg) <= thresh:
            if merged:  # 有前块 → 拼前块
                merged[-1] += seg
            else:  # 没前块 → 留给下一块
                merged.append(seg)
        else:
            if merged and len(merged[-1]) <= thresh:
                merged[-1] += seg  # 把开头碎片拼过来
            else:
                merged.append(seg)
    return merged


def break_long_line(text: str, max_length: int = 120) -> list[str]:
    """超长段落递归折行（保持原算法）"""
    if len(text) <= max_length:
        return [text]

    punct_positions = [i for i, ch in enumerate(text) if ch in PUNCT]
    if not punct_positions:
        return [text[:max_length]] + break_long_line(text[max_length:], max_length)

    center = len(text) // 2
    best_pos = min(punct_positions, key=lambda p: abs(p - center))

    left = text[:best_pos + 1]
    right = text[best_pos + 1:]
    return break_long_line(left, max_length) + break_long_line(right, max_length)


def consolidate_short_lines(lines: list[str], min_len: int = 15) -> list[str]:
    """首行之外若不足 min_len 字就拼接下一块"""
    if not lines:
        return lines

    result = [lines[0]]  # 首行保留
    i = 1
    while i < len(lines):
        cur = lines[i]
        while len(cur) < min_len and i + 1 < len(lines):
            i += 1
            cur += lines[i]
        result.append(cur)
        i += 1
    return result


def process_text_for_tts(text: str) -> str:
    """
    1. 标点切分 → sentences
    2. 合并碎片（≤3 字）→ sentences2
    3. 前 4 块两两合并（总长 ≤25）
    4. 其余合并成一段，大于 120 再折行
    5. 首行外若 <15 字继续拼下一块
    6. \n 拼接
    """
    sentences = merge_small_fragments(split_into_sentences(text))
    if not sentences:
        return text.strip()

    lines = []
    i, limit = 0, min(4, len(sentences))
    while i < limit:
        if i + 1 < limit and len(sentences[i]) + len(sentences[i + 1]) <= 25:
            lines.append(sentences[i] + sentences[i + 1])
            i += 2
        else:
            lines.append(sentences[i])
            i += 1

    rest_start = limit
    if rest_start < len(sentences):
        rest = "".join(sentences[rest_start:])
        lines.extend(break_long_line(rest, 120))

    # 再做一次“短行拼接”
    final_lines = consolidate_short_lines(lines)

    return "\n".join(final_lines)


# -------------------- demo --------------------
if __name__ == "__main__":
    demo_text = """
    哼，那当然啦！毕竟像我这么有趣又毒舌的虚拟主播，可不是随便哪里都能遇到的哦～  Whisper那个家伙，明明自己头发都快熬夜熬没了，还总想装作很厉害的样子，不吐槽他简直对不起我的嘴巴！不过说真的，能让你每天都开心，我是不是有点太优秀了？以后想听我吐槽谁，随时点单，反正我嘴皮子溜得很，谁都不怕！不过你可别学我，毕竟不是每个人都能毒舌得这么可爱～
    """
    print(process_text_for_tts(demo_text))
