import time, logging
from src.vision.capture_screen import grab_screen
from src.vision.frame_differ import FrameDiffer
from src.vision.llm_proxy import VisionLLMProxy

LOGGER = logging.getLogger("VisionEngine")


class VisionEngine:
    """组合注入：Capture→Diff→LLM"""

    def __init__(self,
                 llm: VisionLLMProxy | None = None,
                 differ: FrameDiffer | None = None,
                 interval: float = 1.0,
                 ) -> None:
        self.llm = llm or VisionLLMProxy()
        self.differ = differ or FrameDiffer()
        self.interval = interval

    # vision/engine.py 核心改动
    def tick(self, mem_engine, user_id="whisper") -> str | None:
        shot = grab_screen()
        if not self.differ.should_process(shot):
            return None
        return mem_engine.chat_with_screen(
            user_id=user_id,
            image=shot,
            extra_text="请用不超过40字中文吐槽"
        )

    def run_forever(self, cb):
        """cb(text:str) 回调；Ctrl-C 退出"""
        while True:
            try:
                if text := self.tick():
                    cb(text)
                time.sleep(self.interval)
            except KeyboardInterrupt:
                break
            except Exception as e:
                LOGGER.exception(e)
