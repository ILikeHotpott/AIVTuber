from dataclasses import dataclass

from src.prompt.builders.base import SecurityLevel, DialogueActor


@dataclass
class PromptBuilderConfig:
    dialogue_actor: DialogueActor
    default_character: str = "default"
    default_security_level: SecurityLevel = SecurityLevel.MEDIUM
    enable_caching: bool = False
    cache_ttl_seconds: int = 300
