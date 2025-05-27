"""
src/runtime/live_chat.py
------------------------
实时语音 → LLM(带记忆) → 实时 TTS
打断逻辑：Whisper VAD 首帧回调 → 立即 .set() stop_event
"""

import threading, time, queue

# ===== 你已有的模块 =====
from src.asr.model import stream_transcripts
from src.chatbot.memory_chat_engine import MemoryChatEngine
from src.chatbot.config import Config
# from src.tts.tts_stream import tts_streaming
from src.tts.realtime_tts import tts_in_chunks

# -------------------- LLM 初始化 --------------------
cfg = Config(
    model_name="chatgpt-4o-latest",
    temperature=0.4,
    max_tokens=256,
    top_k=10,
    top_p=0.95,
    score_threshold=0.65,
    max_hits=2,
    chat_with=1,
    use_long_term=False,
    enable_vision=False
)
chat = MemoryChatEngine(cfg)

pause_mic = threading.Event()
pause_mic.set()
user_talking = threading.Event()
tts_stop_evt = threading.Event()

asr_q: "queue.Queue[str]" = queue.Queue()


def _on_partial():
    """Whisper 检测到首帧语音——立即停 TTS"""
    user_talking.set()
    pause_mic.set()  # 保证麦克风开着
    tts_stop_evt.set()  # 通知 tts_streaming 立刻停止


def asr_worker():
    for text in stream_transcripts(
            pause_event=pause_mic,
            on_partial=_on_partial):
        if text:
            asr_q.put(text)


threading.Thread(target=asr_worker, daemon=True).start()

# -------------------- 主循环 --------------------
print("🎤  开始聊天 Ctrl+C 退出")
try:
    while True:
        user_txt = asr_q.get()
        if not user_txt.strip():
            continue

        # 2. LLM 回复（自动写入 MemoryChatEngine 的记忆）
        reply = chat.chat("187238941adskmfl;sdfqwueoalnm", user_txt, language="Chinese")
        print(f"\n👤 {user_txt}\n🤖 {reply}")

        # 3. 播放：静音麦 -> 清除 stop 信号 -> 调用 tts_streaming
        pause_mic.clear()  # 朗读期间关闭麦克风输入
        tts_stop_evt.clear()
        t0 = time.perf_counter()
        # tts_streaming(reply)
        tts_in_chunks(reply)
        print(f"[TTS] 用时 {time.perf_counter() - t0:.2f}s")

        user_talking.clear()
        pause_mic.set()

except KeyboardInterrupt:
    tts_stop_evt.set()
    print("\n🛑  已退出")
