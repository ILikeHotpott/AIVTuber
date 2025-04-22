import os
import time
import pyaudio
from six.moves import queue
from dotenv import load_dotenv
from google.cloud import speech

load_dotenv()
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_APPLICATION_CREDENTIALS

# 音频参数
RATE = 16000
CHUNK = int(RATE / 10)  # 100ms


# 麦克风流管理类
class MicrophoneStream:
    def __init__(self, rate, chunk):
        self.rate = rate
        self.chunk = chunk
        self._buff = queue.Queue()
        self.closed = True

    def __enter__(self):
        self.audio_interface = pyaudio.PyAudio()
        self.audio_stream = self.audio_interface.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.rate,
            input=True,
            frames_per_buffer=self.chunk,
            stream_callback=self._fill_buffer
        )
        self.closed = False
        return self

    def __exit__(self, type, value, traceback):
        self.audio_stream.stop_stream()
        self.audio_stream.close()
        self.closed = True
        self._buff.put(None)
        self.audio_interface.terminate()

    def _fill_buffer(self, in_data, frame_count, time_info, status_flags):
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self, pause_event=None):
        while not self.closed:
            if pause_event and pause_event.is_set():
                # 发送静音帧而不是暂停
                yield b'\x00' * self.chunk * 2
                continue

            chunk = self._buff.get()
            if chunk is None:
                return
            data = [chunk]

            while True:
                try:
                    chunk = self._buff.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                except queue.Empty:
                    break

            yield b''.join(data)


# 处理识别结果
def listen_print_loop(responses):
    for response in responses:
        if not response.results:
            continue
        result = response.results[0]
        if not result.alternatives:
            continue

        transcript = result.alternatives[0].transcript
        if result.is_final:
            print("你说的是：", transcript)


def main():
    language_code = "zh-CN"
    client = speech.SpeechClient()

    print(client._transport._host)  # 应该打印出 speech.googleapis.com

    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        language_code=language_code,
    )

    streaming_config = speech.StreamingRecognitionConfig(
        config=config,
        interim_results=True
    )

    with MicrophoneStream(RATE, CHUNK) as stream:
        audio_generator = stream.generator()
        requests = (
            speech.StreamingRecognizeRequest(audio_content=content)
            for content in audio_generator
        )

        responses = client.streaming_recognize(streaming_config, requests)

        print("🎤 开始说话吧（按 Ctrl+C 停止）")
        try:
            listen_print_loop(responses)
        except KeyboardInterrupt:
            print("\n 已停止识别")


def get_transcript_streaming(pause_event=None):
    client = speech.SpeechClient()
    language_code = "zh-CN"

    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        language_code=language_code,
        use_enhanced=True
    )

    streaming_config = speech.StreamingRecognitionConfig(
        config=config,
        interim_results=False
    )

    while True:
        with MicrophoneStream(RATE, CHUNK) as stream:
            audio_generator = stream.generator(pause_event=pause_event)
            requests = (
                speech.StreamingRecognizeRequest(audio_content=content)
                for content in audio_generator
            )
            responses = client.streaming_recognize(streaming_config, requests)

            try:
                for response in responses:
                    if not response.results:
                        continue
                    result = response.results[0]
                    if not result.alternatives:
                        continue
                    if result.is_final:
                        transcript = result.alternatives[0].transcript
                        yield transcript
                        break  # 识别一轮后 break，重新开启下一轮流式识别
            except Exception as e:
                print(f"[Google Streaming 出错] {e}")
                continue


if __name__ == "__main__":
    main()

