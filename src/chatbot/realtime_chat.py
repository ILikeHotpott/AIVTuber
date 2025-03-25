from src.asr.google_asr import get_transcript_streaming
from src.tts.tts_opt.tts2 import tts_in_chunks
from src.memory.memory_1 import chat


def run_voice_chat_loop(user_id="user_001"):
    print("🎙️ 开始语音对话（Ctrl+C 退出）")
    try:
        for transcript in get_transcript_streaming():  # 你可以封装成一个生成器
            if transcript:
                print(f"[🗣️ 你说] {transcript}")

                # 调用 chat 生成回复
                reply = chat(user_id, transcript, language="Chinese")
                print(f"[🤖 回复] {reply}")

                # 调用 TTS 播放语音
                tts_in_chunks(reply)

    except KeyboardInterrupt:
        print("\n🛑 语音对话已结束")


if __name__ == "__main__":
    run_voice_chat_loop()
