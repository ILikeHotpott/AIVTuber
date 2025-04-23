import time
from src.vision.context import VisionContext
from src.vision.screen_describer import ScreenDescriber
from src.chatbot.memory_chat_engine import MemoryChatEngine
from src.chatbot.config import Config
from src.tts.tts_stream import tts_streaming
from src.prompt.roles.vision import vision_prompt
from src.vision.capture_screen import grab_screen
from src.tts.worker import TTSWorker

tts_worker = TTSWorker(max_queue=2)
tts_worker.start()

cfg = Config(
    # model_name="chatgpt-4o-latest",
    model_name="gpt-4.1",
    temperature=0.4,
    max_tokens=500,
    top_k=10,
    top_p=0.95,
    score_threshold=0.65,
    max_hits=2,
    chat_with=1
)
chat_engine = MemoryChatEngine(cfg)

describer = ScreenDescriber(min_diff=0.05, cooldown=3.0)
vision_ctx = VisionContext(max_items=5)


def build_trigger_prompt(vc: VisionContext) -> str:
    """
    把 general_settings_prompt + vision_prompt + 屏幕描述 合成一条 system 消息
    """
    return (
            vision_prompt  # 你的模板，已经包含 general_settings_prompt
            + "\n"
            + vc.prompt_block()  # 最近 5 条屏幕描述
            + "\n\n请像坐在旁边一样继续吐槽屏幕上的内容。"
    )


def drive_loop(user_id: str = "whisper123"):
    print("开始实时吐槽！（Ctrl+C 退出）")
    while True:
        try:
            screenshot = grab_screen()
            caption = describer.describe_images([screenshot])

            if caption:
                vision_ctx.add(caption)
                trigger_prompt = build_trigger_prompt(vision_ctx)

                reply = chat_engine.chat(user_id, trigger_prompt, language="Chinese")
                print("回答:", reply)
                tts_worker.enqueue(reply)  # ← 不再阻塞！

            time.sleep(1)

        except KeyboardInterrupt:
            tts_worker.stop()
            break
        except Exception as err:
            print(f"[drive_loop] 捕获异常：{err}")


if __name__ == '__main__':
    drive_loop()
