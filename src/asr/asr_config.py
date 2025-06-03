from pathlib import Path
from dataclasses import dataclass, field

from src.utils.path import find_project_root


@dataclass
class ASRConfig:
    """ASR (Whisper-MLX) 配置"""

    # 音频流
    sample_rate: int = 16_000
    frame_duration_ms: int = 30
    frame_size: int = field(init=False)
    max_silence_duration_ms: int = 1500
    min_speech_duration_ms: int = 150
    max_silence_frames: int = field(init=False)
    min_speech_frames: int = field(init=False)
    vad_sensitivity: int = 3  # (0-3,越高越灵敏)

    debug: bool = False

    # Whisper-MLX 模型
    model_name: str = "base"  # tiny / base / small / medium / large-v2 / large-v3
    model_root: Path = find_project_root() / "src/asr/mlx_models"
    batch_size: int = 12

    def __post_init__(self):
        self.frame_size = self.sample_rate * self.frame_duration_ms // 1000
        self.max_silence_frames = self.max_silence_duration_ms // self.frame_duration_ms
        self.min_speech_frames = self.min_speech_duration_ms // self.frame_duration_ms

        # VAD 帧长必须是 10, 20, 或 30 ms
        if self.frame_duration_ms not in {10, 20, 30}:
            raise ValueError(
                f"ASRConfig: frame_duration_ms ({self.frame_duration_ms}) "
                f"must be 10, 20, or 30 ms for webrtcvad."
            )
