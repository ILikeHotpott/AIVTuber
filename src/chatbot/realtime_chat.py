import threading
from src.asr.google_asr import get_transcript_streaming
from src.tts.realtime_tts import tts_in_chunks
from src.memory.short_term.memory_with_me import chat


def run_voice_chat_loop():
    print("🎙️ 开始语音对话（Ctrl+C 退出）")
    pause_event = threading.Event()
    try:
        for transcript in get_transcript_streaming(pause_event=pause_event):
            if transcript:
                print(f"[🗣️ 你说] {transcript}")

                reply = chat("realtime_1", transcript)
                print(f"[🤖 回复] {reply}")

                # 播放前暂停识别
                pause_event.set()
                tts_in_chunks(reply)
                # 播放后恢复识别
                pause_event.clear()

    except KeyboardInterrupt:
        print("\n🛑 语音对话已结束")


if __name__ == "__main__":
    run_voice_chat_loop()
