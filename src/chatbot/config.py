from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class Config:
    model_name: str = "gpt-4o"
    temperature: float = 0.5
    max_tokens: int = 400
    top_k: int = 10
    top_p: float = 0.95
    score_threshold: float = 0.8
    max_hits: int = 4
    chat_with: int = 1

    root: Path = field(default_factory=lambda: Path(__file__).resolve().parents[2])

    @property
    def db_path(self) -> Path:
        return self.root / "src" / "runtime" / "chat" / "chat_memory.db"
