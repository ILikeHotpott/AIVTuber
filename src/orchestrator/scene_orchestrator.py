import threading
import asyncio
import time

from src.asr.asr_engine import ASREngine
from src.asr.asr_config import ASRConfig
from src.chatbot.llama.chat_engine import ChatEngine


class SceneOrchestrator:
    def __init__(self, connect_to_unity: bool = True):
        self.asr = ASREngine(ASRConfig(debug=True))  # 可选 debug=True
        self.asr_running = False
        self._asr_thread = None
        self.loop = asyncio.get_event_loop()
        self.connect_to_unity = connect_to_unity
        self.chat_engine = ChatEngine.get_instance(connect_to_unity=self.connect_to_unity)

    def start(self):
        print("[SceneOrchestrator] Starting ASR...")
        self._start_asr()

    def _start_asr(self):
        if self.asr_running:
            print("[SceneOrchestrator] ASR already running.")
            return
        self.asr.start()
        self.asr_running = True
        self._asr_thread = threading.Thread(target=self._asr_loop, daemon=True)
        self._asr_thread.start()

    def _asr_safe_say(self, text: str):
        print("[SceneOrchestrator] PAUSE ASR")
        self.asr.pause()

        # 1) 生成 & 把文本送进 TTS 队列
        future = asyncio.run_coroutine_threadsafe(
            self.chat_engine.stream_chat("asr_user2", text),
            self.loop
        )
        try:
            reply = future.result()
        except Exception as e:
            print(f"[AI ERROR] {e}")

        # 2) **阻塞，直到 TTS 完全播放结束**
        while self.chat_engine.is_speaking():
            time.sleep(0.05)  # 50 ms 轮询一次，负担极小

        time.sleep(0.5)

        print("[SceneOrchestrator] RESUME ASR")
        self.asr.resume()

    def _asr_loop(self):
        print("[SceneOrchestrator] ASR loop started.")
        while self.asr_running:
            text = self.asr.get_text(timeout=1)
            if text:
                print(f"[ASR] {text}")
                self._asr_safe_say(text)

    def stop(self):
        print("[SceneOrchestrator] Stopping...")
        if self.asr_running:
            self.asr_running = False
            self.asr.stop()
            if self._asr_thread:
                self._asr_thread.join()

    async def stop_async_components(self):
        print("[SceneOrchestrator] Closing async components (ChatEngine)...")
        await self.chat_engine.close()
        print("[SceneOrchestrator] Async components closed.")


async def main(orchestrator: SceneOrchestrator):
    orchestrator.start()

    print("💬 Scene running (ASR active). Press Ctrl+C to stop.")

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("Stopping Scene...")
    finally:
        print("[SceneOrchestrator] Stopping synchronous components...")
        orchestrator.stop()
        # The async components will be stopped in the __main__ finally block


if __name__ == "__main__":
    orchestrator = SceneOrchestrator(connect_to_unity=False)
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main(orchestrator))
    except KeyboardInterrupt:
        print("Stopping Scene from __main__ (KeyboardInterrupt)...")
    finally:
        print("[SceneOrchestrator] Cleaning up...")
        if orchestrator:
            # First, stop synchronous parts if not already fully stopped by main()'s finally
            if orchestrator.asr_running:  # Check if ASR is still marked as running
                print("[SceneOrchestrator] Ensuring synchronous components are stopped from __main__...")
                orchestrator.stop()

                # Then, stop asynchronous components
            print("[SceneOrchestrator] Stopping asynchronous components from __main__...")
            loop.run_until_complete(orchestrator.stop_async_components())

        print("[SceneOrchestrator] Closing event loop...")
        loop.close()
        print("[SceneOrchestrator] Event loop closed.")