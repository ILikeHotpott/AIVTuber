from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class Config:
    model_name: str = "gpt-4o"
    temperature: float = 0.5
    max_tokens: int = 200
    top_k: int = 10
    top_p: float = 0.95
    score_threshold: float = 0.7
    max_hits: int = 4
    chat_with: int = 1
    use_long_term: bool = True

    root: Path = field(default_factory=lambda: Path(__file__).resolve().parents[2])

    @property
    def db_path(self) -> Path:
        return self.root / "src" / "runtime" / "chat" / "chat_memory.db"

