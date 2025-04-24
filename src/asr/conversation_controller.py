# src/asr/conversation_controller.py
"""
Duplex voice chat
Google-ASR ⇆ MemoryChatEngine ⇆ interruptible TTS  +  Vision 自动吐槽
"""
from __future__ import annotations
import queue, threading, time

from src.asr.worker import ASRWorker
from src.chatbot.memory_chat_engine import MemoryChatEngine
from src.tts.tts_worker import TTSWorker
from src.vision.engine import VisionEngine
from src.chatbot.config import Config


class ConversationController:
    def __init__(self, chat: MemoryChatEngine, user_id: str = "whisper"):
        self.chat = chat
        self.uid = user_id

        # -------- 状态标志 --------
        self.pause_event = threading.Event();
        self.pause_event.set()  # 麦 ON
        self.user_talking = threading.Event()  # 用户正在说
        self.bot_replying = threading.Event()  # Zoe 正在朗读

        # -------- TTS --------
        self.tts = TTSWorker();
        self.tts.start()

        # -------- ASR --------
        self.asr_q: "queue.Queue[str]" = queue.Queue()

        def _on_user_start():
            """Google 出现 interim hypothesis — 秒停 Zoe 并清空队列"""
            self.user_talking.set()
            self.pause_event.set()  # 开麦
            self.tts.stop_current()
            self.tts.flush_queue()  # <-- 把残余吐槽清掉

        self.asr = ASRWorker(
            out_queue=self.asr_q,
            pause_event=self.pause_event,
            on_partial_callback=_on_user_start
        )
        self.asr.start()

        # -------- Vision --------
        self.vision = VisionEngine()
        threading.Thread(target=self._vision_loop, daemon=True).start()

    # ------------------------------------------------------------------
    # Vision thread  (低优先级)
    # ------------------------------------------------------------------
    def _vision_loop(self):
        while True:
            if self.user_talking.is_set() or self.bot_replying.is_set():
                time.sleep(0.05);
                continue

            txt = self.vision.tick(self.chat, user_id=self.uid)
            if txt:
                self.tts.enqueue(txt)
            time.sleep(0.4)

    # ------------------------------------------------------------------
    # helper：朗读并阻塞到播完
    # ------------------------------------------------------------------
    def _speak_sync(self, text: str):
        self.bot_replying.set()
        self.tts.enqueue(text)
        # 阻塞等待这句播完
        while self.tts.is_playing:
            time.sleep(0.05)
        self.bot_replying.clear()

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    def run(self):
        print("🗣️  Speak now — Ctrl+C to quit")
        try:
            while True:
                user_text = self.asr_q.get()  # 等 final
                if not user_text.strip():
                    continue

                reply = self.chat.chat(self.uid, user_text, language="Chinese")
                print(f"{self.uid}: {user_text}")
                print("Zoe :", reply)

                # 静音麦 -> 播回复
                self.pause_event.clear()
                self._speak_sync(reply)

                # 一轮结束，恢复监听 / 吐槽
                self.user_talking.clear()
                self.pause_event.set()
        except KeyboardInterrupt:
            self.tts.stop();
            self.asr.stop()


# ---------------- CLI test ----------------
if __name__ == "__main__":
    cfg = Config(model_name="gemini-2.0-flash", use_long_term=False)
    ConversationController(MemoryChatEngine(cfg)).run()
