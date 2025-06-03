from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict


class PromptType(Enum):
    """Prompt type enumeration"""
    SYSTEM = "system"
    HUMAN = "human"
    AI = "ai"
    INSTRUCTION = "instruction"


class SecurityLevel(Enum):
    """Security level enumeration"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    MAXIMUM = 4


class DialogueActor(Enum):
    WHISPER = "whisper"
    AUDIENCE = "audience"
    HYBRID = "hybrid"


@dataclass
class PromptContext:
    """Prompt context data model"""
    user_id: str = "default_id"
    username: str = "default_username"
    language: str = "English"
    timezone_name: str = "Australia/Adelaide"
    security_level: SecurityLevel = SecurityLevel.MEDIUM
    custom_variables: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
