#!/usr/bin/env python3
# chat_talk.py  — 2025-05-27 改进版
import os, queue, threading, time, re
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_openai.chat_models import ChatOpenAI
from src.prompt.templates.general import general_settings_prompt_english
from src.tts.tts_stream import tts_streaming

# ───────── 环境 ─────────
load_dotenv()
chat = ChatOpenAI(
    openai_api_base=os.getenv("OPENAI_BASE", "http://127.0.0.1:8080/v1"),
    openai_api_key=os.getenv("OPENAI_KEY", "sk-fake-key"),
    model_name="gpt-4o",
    streaming=True,
)

_BOUNDARY_RE = re.compile(r"[。！？；]|[.!?](?=\s|$)", re.UNICODE)


def is_ellipsis(text: str, dot_pos: int) -> bool:
    """判断当前句点是否是 ... 里的最后一个点"""
    return (
            text[dot_pos] == "." and
            dot_pos >= 2 and
            text[dot_pos - 2:dot_pos + 1] == "..."
    )


def should_skip_boundary(text, match_start):
    """判断该标点是否应被跳过（因出现在缩写后）"""
    prefix = text[max(0, match_start - 10):match_start]
    for abbr in {"Mr", "Mrs", "Ms", "Dr", "Prof", "Sr", "Jr", "St"}:
        if prefix.endswith(abbr):
            return True
    return False


MAX_CHARS, MAX_WAIT_SECS = 120, 1.2

speak_queue: queue.Queue[str] = queue.Queue()


def tts_worker():
    while True:
        text = speak_queue.get()
        if text is None:
            break
        try:
            tts_streaming(text)
        except Exception as e:
            print(f"\n[TTS error] {e}\n")


def segmenter_stream(chat_response):
    buf, last_emit = "", time.time()

    # ---- 新增：短句累积缓冲区 ----
    acc_parts, acc_words = [], 0  # 待合并的片段 & 累计词数

    def flush_acc():
        nonlocal acc_parts, acc_words
        if acc_parts:
            speak_queue.put(" ".join(acc_parts).strip())
            acc_parts, acc_words = [], 0

    for chunk in chat_response:
        tok = chunk.content
        print(tok, end="", flush=True)
        buf += tok

        pos = 0
        for m in _BOUNDARY_RE.finditer(buf):
            if should_skip_boundary(buf, m.start()) or is_ellipsis(buf, m.start()):
                continue

            cut = m.end()
            sentence = buf[pos:cut].strip()
            pos = cut
            if not sentence:
                continue

            # ---------- 短句累积 ----------
            words = len(sentence.split())
            if acc_words + words < 10:
                acc_parts.append(sentence)
                acc_words += words
            else:
                acc_parts.append(sentence)
                flush_acc()  # 达到 ≥10 词，整块发送
            last_emit = time.time()

        buf = buf[pos:]

        # ---------- 超时 / 超长兜底 ----------
        if len(buf) >= MAX_CHARS or time.time() - last_emit >= MAX_WAIT_SECS:
            if buf.strip():
                acc_parts.append(buf.strip())
                acc_words += len(buf.split())
                buf = ""
                last_emit = time.time()
                if acc_words >= 10:
                    flush_acc()

    if buf.strip():
        acc_parts.append(buf.strip())
        acc_words += len(buf.split())
    flush_acc()


def chat_and_talk(user_input: str):
    full_prompt = f"""{general_settings_prompt_english}

Now, you are answering a comment. You must ONLY respond to the following comment
using the tone, personality, and constraints defined above.

You MUST ANSWER IN ENGLISH, no matter what comment said.

Comment:
{user_input}
"""
    stream = chat.stream([HumanMessage(content=full_prompt)])
    t = threading.Thread(target=tts_worker, daemon=True)
    t.start()
    segmenter_stream(stream)
    speak_queue.put(None)
    t.join()


# ───────── CLI DEMO ─────────
if __name__ == "__main__":
    print("💬 连续对话，输入 text 回车；exit/quit 退出\n")
    try:
        while True:
            msg = input("👤 > ").strip()
            if msg.lower() in {"exit", "quit"}:
                break
            if msg:
                chat_and_talk(msg)
                print()
    except KeyboardInterrupt:
        pass
