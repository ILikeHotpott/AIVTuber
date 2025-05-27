from __future__ import annotations
import queue
import threading
import time
from collections import deque

# ---------- 本项目内部模块 ----------
from src.asr.worker import ASRWorker
from src.chatbot.memory_chat_engine import MemoryChatEngine
from src.tts.tts_worker import TTSWorker
from src.vision.engine import VisionEngine
from src.chatbot.config import Config


class ConversationController:
    """
    协调 ASR / Chat / TTS / Vision 四大模块，实现：
      • 用户说话 → Whisper-MLX 转文字（可打断 TTS）
      • LLM 回复 → 阻塞朗读 → 回到监听
      • VisionEngine.tick() 产生活动吐槽（避免重复）
    """

    def __init__(
            self,
            chat: MemoryChatEngine,
            user_id: str = "whisper",
            interrupt_on_speech: bool = True,
    ):
        self.chat = chat
        self.uid = user_id
        self.interrupt_on_speech = interrupt_on_speech

        # ----------- 状态事件 -----------
        self.pause_event = threading.Event();
        self.pause_event.set()
        self.user_talking = threading.Event()
        self.bot_replying = threading.Event()

        # ----------- TTS -----------
        self.tts = TTSWorker()
        self.tts.start()

        # ----------- ASR -----------
        self.asr_q: "queue.Queue[str]" = queue.Queue()

        def _on_user_start():
            # 首帧语音：标记并可选打断
            self.user_talking.set()
            self.pause_event.set()  # 保持开麦
            if self.interrupt_on_speech:
                self.tts.stop_current()
                self.tts.flush_queue()

        self.asr = ASRWorker(
            out_queue=self.asr_q,
            pause_event=self.pause_event,
            on_partial_callback=_on_user_start,
        )
        self.asr.start()

        # ----------- Vision -----------
        self.vision = VisionEngine()
        self._last_vision: str | None = None  # 用于去重
        threading.Thread(target=self._vision_loop, daemon=True).start()

    # ------------------------------------------------------------------
    def _vision_loop(self):
        while True:
            if self.user_talking.is_set() or self.bot_replying.is_set():
                time.sleep(0.05);
                continue

            txt = self.vision.tick(self.chat, user_id=self.uid)
            if txt and txt != self._last_vision:  # ← 简单去重
                self.tts.enqueue(txt)
                self._last_vision = txt
            time.sleep(0.4)

    # ------------------------------------------------------------------
    def _speak_sync(self, text: str):
        """播放一段语音；可在用户再度说话时立即打断。"""
        self.bot_replying.set()
        self.tts.enqueue(text)

        # 等播放开始
        start_wait = time.time()
        while not self.tts.is_playing and time.time() - start_wait < 1.5:
            time.sleep(0.02)

        # 播放期间：若用户又说话 → 停止并退出
        while self.tts.is_playing:
            if self.user_talking.is_set() and self.interrupt_on_speech:
                self.tts.stop_current()
                break
            time.sleep(0.05)

        self.bot_replying.clear()

    # ------------------------------------------------------------------
    def run(self):
        print("🗣️  Speak now — Ctrl+C to quit")
        try:
            last_reply: deque[str] = deque(maxlen=3)
            while True:
                # ---------- 取最新一句 ----------
                user_text = self.asr_q.get()  # 至少有一句
                try:
                    while True:
                        # 不阻塞地把后面堆积的全拿掉，保留最后一条
                        user_text = self.asr_q.get_nowait()
                except queue.Empty:
                    pass

                user_text = user_text.strip()
                if len(user_text) <= 1:  # 噪声
                    continue

                # ---------- LLM ----------
                reply = self.chat.chat(self.uid, user_text, language="Chinese")
                if reply in last_reply:  # 简单防抖
                    continue
                last_reply.append(reply)

                print(f"{self.uid}: {user_text}")
                print("Zoe :", reply)

                # ---------- 播放 ----------
                self.pause_event.clear()
                self._speak_sync(reply)

                # ---------- 复位 ----------
                self.user_talking.clear()
                self.pause_event.set()
        except KeyboardInterrupt:
            self.tts.stop();
            self.asr.stop()


# ---------------- CLI quick-test ----------------
if __name__ == "__main__":
    cfg = Config(model_name="gemini-2.0-flash",
                 use_long_term=False,
                 enable_vision=True)
    ConversationController(MemoryChatEngine(cfg)).run()
