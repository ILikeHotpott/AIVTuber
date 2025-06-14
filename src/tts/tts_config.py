from dataclasses import dataclass


@dataclass
class TTSConfig:
    server_url: str = "http://localhost:9880/tts"
    ref_audio_path: str = "/Users/liuyitong/projects/Seranion/src/tts/audio/Lyra_v2_ref.wav"
    unity_host: str = "localhost"
    unity_port: int = 5005
    language: str = "en"
    speed_factor: float = 1.1
    connect_to_unity: bool = False
