from dataclasses import dataclass


@dataclass
class TTSConfig:
    server_url: str = "http://localhost:9880/tts"
    ref_audio_path: str = "/Users/liuyitong/projects/Seranion/src/tts/audio/Ulia_ref.mp3"
    unity_host: str = "localhost"
    unity_port: int = 5005
    language: str = "en"
    speed_factor: float = 1.1
    connect_to_unity: bool = False
