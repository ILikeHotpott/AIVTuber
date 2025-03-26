from RealtimeSTT import AudioToTextRecorder


def process_text(text):
    print(text)


if __name__ == '__main__':
    recorder = AudioToTextRecorder(
        model="large-v3",
        language="zh"
    )
    while True:
        recorder.text(process_text)
