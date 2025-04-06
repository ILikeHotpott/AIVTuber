import re


def split_into_sentences(text):
    """
    使用正则表达式，按照中英文标点分割文本，并让每个标点符号与其前面的文字一起保留在一个元素中。
    """
    # 常见的中英文标点，可按需增减
    pattern = r'(。？！，,!?;；)'
    parts = re.split(pattern, text)

    # 将前后拼起来，形成带有标点的“句子”
    sentences = []
    for i in range(0, len(parts), 2):
        chunk = parts[i]
        if i + 1 < len(parts):
            punct = parts[i + 1]
            chunk += punct
        if chunk.strip():
            sentences.append(chunk.strip())

    return sentences


def break_long_line(text, max_length=120):
    """
    若 text 超过 max_length，则尝试寻找最靠近中点的标点进行分割。
    找不到标点时就在 max_length 处硬切分。
    """
    punctuation_set = set("。？！，,!?;；:：")

    # 如果当前文本长度已不超过 max_length，则返回自身
    if len(text) <= max_length:
        return [text]

    center = len(text) // 2
    # 找到所有标点符号的位置
    punct_positions = [i for i, ch in enumerate(text) if ch in punctuation_set]

    if not punct_positions:
        # 没有标点时，直接在 max_length 处硬切
        return [text[:max_length]] + break_long_line(text[max_length:], max_length)

    # 在标点位置中，找到与 center 最近的
    best_pos = None
    best_dist = None
    for pos in punct_positions:
        dist = abs(pos - center)
        if best_dist is None or dist < best_dist:
            best_dist = dist
            best_pos = pos

    # 在 best_pos 后面分割，使标点留在左侧
    left_part = text[:best_pos + 1]
    right_part = text[best_pos + 1:]

    # 分别对左右两段继续处理
    return break_long_line(left_part, max_length) + break_long_line(right_part, max_length)


def process_text_for_tts(text):
    """
    1. 按标点切分，得到 sentences。
    2. 前 4 个 segment，按“两两合并后若总长 <= 25 则合并，否则分开”。
    3. 剩余的合并成一个大段落，若超过 120 则分割。
    4. 将所有段落用 \n 拼接返回。
    """
    # 1. 按标点切分文本
    sentences = split_into_sentences(text)
    if not sentences:
        return text  # 空文本直接返回

    result_lines = []

    # 2. 处理前 4 个 segment 的两两合并
    #   - step 2，(0,1) 和 (2,3) 分别组成 pairs
    used_sentences = 0
    limit = min(len(sentences), 4)

    i = 0
    while i < limit:
        # 若还能组成一对 (i, i+1)
        if i + 1 < limit:
            s1 = sentences[i]
            s2 = sentences[i + 1]
            if len(s1) + len(s2) <= 25:
                # 合并
                result_lines.append(s1 + s2)
                i += 2
            else:
                # 分开
                result_lines.append(s1)
                i += 1
        else:
            # 只剩一个
            result_lines.append(sentences[i])
            i += 1

    used_sentences = limit

    # 3. 将剩余部分（超过第 4 个 segment 之后的）合并成一个大段落
    if used_sentences < len(sentences):
        rest = "".join(sentences[used_sentences:])

        # 若大段落超过 120，则按照“寻找中点标点”策略分割
        splitted_rest = break_long_line(rest, max_length=120)
        result_lines.extend(splitted_rest)

    # 4. 用换行符拼接返回
    return "\n".join(result_lines)


if __name__ == "__main__":
    text = """
    第一句测试，刚好二十四个字。第二句只有两个字。第三句也很短。第四句凑够25字吧。
第五句开始之后，就要观察它们怎么合并了，因为已经超过了四个segment。
    """

    processed_text = process_text_for_tts(text)
    print(processed_text)

