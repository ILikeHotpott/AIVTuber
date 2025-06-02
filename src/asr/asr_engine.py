import os
import threading, queue, time, tempfile, collections
from typing import Callable, Optional, Deque
import numpy as np, sounddevice as sd, soundfile as sf, webrtcvad
from lightning_whisper_mlx import LightningWhisperMLX
from huggingface_hub import snapshot_download
from src.asr.asr_config import ASRConfig


class ASREngine:
    def __init__(self, config: ASRConfig):
        self.config = config
        self.model = None
        self.out_q: queue.Queue[str] = queue.Queue()
        self.pause_event = threading.Event()
        self.pause_event.set()  # 开启麦
        self._stop_event = threading.Event()
        self._thread = None
        self._model: LightningWhisperMLX | None = None

    def _lazy_model(self):
        if self.model is None:
            print("Loading Whisper-MLX…")

            os.environ.setdefault("HF_HOME", str(self.config.model_root))

            snapshot_download(
                repo_id=f"mlx-community/whisper-{self.config.model_name}-mlx",
                cache_dir=str(self.config.model_root),
                local_files_only=False,  # first run may download, then cached
            )

            self.model = LightningWhisperMLX(
                model=self.config.model_name,
                batch_size=self.config.batch_size,
            )

            print("✅ Whisper-MLX ready (cached in)", self.config.model_root)
        return self.model

    def _stream_loop(self, on_partial: Optional[Callable[[], None]] = None):
        whisper = self._lazy_model()
        vad = webrtcvad.Vad(self.config.vad_sensitivity)

        def is_speech(frame: bytes) -> bool:
            return vad.is_speech(frame, self.config.sample_rate)

        with sd.RawInputStream(
                samplerate=self.config.sample_rate,
                channels=1,
                blocksize=self.config.frame_size,
                dtype="int16"
        ) as stream:
            buf: Deque[bytes] = collections.deque()
            silence = 0
            speech = 0
            spoke = False

            while not self._stop_event.is_set():
                if not self.pause_event.is_set():
                    stream.read(self.config.frame_size)
                    continue

                data, _ = stream.read(self.config.frame_size)
                if len(data) == 0:
                    continue

                talking = is_speech(data)

                if self.config.debug:
                    print("🗣️" if talking else "·", end="", flush=True)

                if talking:
                    if not spoke and on_partial:
                        on_partial()  # 第一次检测到语音
                    buf.append(data)
                    silence = 0
                    speech += 1
                    spoke = True
                else:
                    if spoke:
                        silence += 1

                if spoke and silence >= self.config.max_silence_frames:
                    if speech >= self.config.min_speech_frames:
                        pcm = b"".join(buf)
                        wav = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768
                        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                            sf.write(tmp.name, wav, self.config.sample_rate, subtype="PCM_16")
                            t0 = time.perf_counter()
                            text = whisper.transcribe(audio_path=tmp.name)["text"].strip()
                            print(f"\n[Whisper] ⏱ {(time.perf_counter() - t0):.2f}s -> {text}")
                            self.out_q.put(text)
                    buf.clear()
                    silence = speech = 0
                    spoke = False
                    if self.config.debug: print()

    def start(self, on_partial: Optional[Callable[[], None]] = None):
        if self._thread is not None:
            print("ASREngine already running.")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._stream_loop, args=(on_partial,), daemon=True)
        self._thread.start()
        print("ASREngine started.")

    def stop(self):
        if self._thread is None:
            print("ASREngine is not running.")
            return
        self._stop_event.set()
        self._thread.join()
        self._thread = None
        print("ASREngine stopped.")

    def pause(self):
        self.pause_event.clear()
        print("ASREngine paused.")

    def resume(self):
        self.pause_event.set()
        print("ASREngine resumed.")

    def get_text(self, timeout: float = 1.0) -> Optional[str]:
        try:
            return self.out_q.get(timeout=timeout)
        except queue.Empty:
            return None


if __name__ == "__main__":
    config = ASRConfig(debug=True)
    asr = ASREngine(config)
    asr.start()

    try:
        while True:
            text = asr.get_text(timeout=1)
            if text:
                print(f"[ASR] {text}")
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("Stopping ASREngine...")
        asr.stop()
