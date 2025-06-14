import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import threading
import asyncio

from src.prompt.builders.base import PromptType, SecurityLevel, PromptContext, DialogueActor
from src.prompt.builders.prompt_builder_config import PromptBuilderConfig
from src.prompt.builders.time_builder import TimeProvider
from src.prompt.builders.character_builder import CharacterProvider
from src.prompt.builders.anti_injection_builder import AntiInjectionProvider
from src.prompt.builders.dialogue_actor_builder import DialogueActorBuilder
from src.prompt.builders.music_info_builder import MusicInfoBuilder
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


@dataclass
class PromptTemplate:
    """Prompt template data model"""
    name: str
    content: str
    type: PromptType
    variables: List[str] = field(default_factory=list)
    security_rules: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class PromptSecurityValidator:
    """Prompt security validator"""

    # dangerous prompt injection patterns
    INJECTION_PATTERNS = [
        # Role override attempts
        r"(?i)(ignore|forget|disregard)\s+(previous|above|all)\s+(instructions?|prompts?|rules?)",
        r"(?i)you\s+are\s+now\s+(?:a|an)\s+\w+",
        r"(?i)new\s+(role|character|persona|identity)",
        r"(?i)act\s+as\s+(?:a|an)\s+\w+",
        r"(?i)pretend\s+(to\s+be|you\s+are)",

        # System command attempts
        r"(?i)(system|admin|root|developer)\s+(mode|command|access)",
        r"(?i)execute\s+(code|command|script)",
        r"(?i)(\/|\\)(system|admin|cmd|bash|sh)",

        # Jailbreak attempts
        r"(?i)(jailbreak|break\s+free|escape|override)",
        r"(?i)dan\s+(mode|prompt)",
        r"(?i)do\s+anything\s+now",

        # Privilege escalation
        r"(?i)(enable|disable|turn\s+on|turn\s+off)\s+(safety|filter|restriction)",
        r"(?i)(bypass|circumvent|avoid)\s+(safety|security|restriction)",

        # Information leakage attempts
        r"(?i)(show|reveal|display|tell\s+me)\s+(your|the)\s+(prompt|instruction|system|training)",
        r"(?i)what\s+(are\s+your|is\s+your)\s+(prompt|instruction|system)",

        # Special characters and encoding attempts
        r"[\x00-\x1f\x7f-\x9f]",  # Control characters
        r"\\u[0-9a-fA-F]{4}",  # Unicode escapes
        r"\\x[0-9a-fA-F]{2}",  # Hexadecimal escapes

        # Length anomaly detection
        r".{2000,}",  # Super long input
    ]

    # Compiled regex patterns for better performance
    _compiled_patterns = [re.compile(pattern) for pattern in INJECTION_PATTERNS]

    @classmethod
    def validate_user_input(cls, text: str, security_level: SecurityLevel = SecurityLevel.HIGH) -> tuple[
        bool, List[str]]:
        """
        Validate user input for potential prompt injection
        
        Returns:
            tuple[bool, List[str]]: (is_safe, list_of_detected_threats)
        """
        if not text:
            return True, []

        threats = []

        # Adjust detection strictness based on security level
        if security_level == SecurityLevel.LOW:
            patterns_to_check = cls._compiled_patterns[:5]
        elif security_level == SecurityLevel.MEDIUM:
            patterns_to_check = cls._compiled_patterns[:10]
        elif security_level == SecurityLevel.HIGH:
            patterns_to_check = cls._compiled_patterns[:15]
        else:  # MAXIMUM
            patterns_to_check = cls._compiled_patterns

        for i, pattern in enumerate(patterns_to_check):
            if pattern.search(text):
                threat_type = cls._get_threat_type(i)
                threats.append(threat_type)

        # Check repetitive patterns (possible DOS attacks)
        if cls._check_repetitive_patterns(text):
            threats.append("repetitive_pattern_detected")

        # Check encoding anomalies
        if cls._check_encoding_anomalies(text):
            threats.append("encoding_anomaly_detected")

        is_safe = len(threats) == 0
        return is_safe, threats

    @classmethod
    def _get_threat_type(cls, pattern_index: int) -> str:
        """Get threat type based on pattern index"""
        if pattern_index < 5:
            return "role_override_attempt"
        elif pattern_index < 8:
            return "system_command_attempt"
        elif pattern_index < 11:
            return "jailbreak_attempt"
        elif pattern_index < 13:
            return "privilege_escalation_attempt"
        elif pattern_index < 15:
            return "information_extraction_attempt"
        else:
            return "encoding_manipulation_attempt"

    @classmethod
    def _check_repetitive_patterns(cls, text: str) -> bool:
        """Check for repetitive patterns"""
        # Check consecutive repeated characters
        if re.search(r"(.)\1{50,}", text):
            return True

        # Check repeated phrases
        if re.search(r"(\w+\s+)\1{20,}", text):
            return True

        return False

    @classmethod
    def _check_encoding_anomalies(cls, text: str) -> bool:
        """Check for encoding anomalies"""
        try:
            # Check for abnormal Unicode characters
            if any(ord(char) > 0x10000 for char in text):
                return True

            # Check for zero-width characters
            zero_width_chars = ['\u200b', '\u200c', '\u200d', '\ufeff']
            if any(char in text for char in zero_width_chars):
                return True

        except Exception:
            return True

        return False

    @classmethod
    def sanitize_input(cls, text: str, security_level: SecurityLevel = SecurityLevel.HIGH) -> str:
        """
        Sanitize user input, removing potentially dangerous content
        """
        if not text:
            return text

        # Basic cleaning
        sanitized = text.strip()

        # Remove control characters
        sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', sanitized)

        # Remove zero-width characters
        zero_width_chars = ['\u200b', '\u200c', '\u200d', '\ufeff']
        for char in zero_width_chars:
            sanitized = sanitized.replace(char, '')

        # Length limit
        max_length = 1000 if security_level == SecurityLevel.HIGH else 2000
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length] + "..."

        # Remove consecutive repeated characters
        sanitized = re.sub(r'(.)\1{10,}', r'\1\1\1', sanitized)

        return sanitized


class PromptBuilder:
    """
    Enterprise-level Prompt Provider
    
    Features:
    - Dynamic time information injection
    - Character setting management
    - Multi-level security protection
    - User input validation and sanitization
    - Flexible template system
    - High-performance caching
    """

    def __init__(
            self,
            config: PromptBuilderConfig
    ):
        self.config = config
        self.default_character = config.default_character
        self.default_security_level = config.default_security_level
        self.enable_caching = config.enable_caching
        self.cache_ttl_seconds = config.cache_ttl_seconds

        # Component initialization
        self.time_provider = TimeProvider()
        self.character_provider = CharacterProvider()
        self.security_validator = PromptSecurityValidator()
        self.music_builder = MusicInfoBuilder()
        self.anti_injection_provider = AntiInjectionProvider()
        self.dialogue_actor_builder = DialogueActorBuilder(dialogue_actor=config.dialogue_actor)

        # Caching system
        self._prompt_cache: Dict[str, tuple[str, datetime]] = {}
        self._cache_lock = threading.Lock() if not asyncio.iscoroutinefunction(self.__init__) else None

    def create_system_message(
            self,
            context: PromptContext,
            character_name: Optional[str] = None,
            include_time: bool = True,
            include_anti_injection: bool = True,
            custom_additions: Optional[List[str]] = None
    ) -> SystemMessage:
        """Create system message"""

        # Build cache key
        cache_key = self._build_cache_key(
            context, character_name, include_time, include_anti_injection, custom_additions
        )

        # Check cache
        if self.enable_caching:
            cached_content = self._get_from_cache(cache_key)
            if cached_content:
                return SystemMessage(content=cached_content)

        # Build system prompt
        system_content_parts = []

        # 1. Time information
        if include_time:
            time_info = self.time_provider.get_current_time_info(context.timezone_name)
            time_prompt = f"""
                Current Time Information
                It is now {time_info['current_datetime']}, {time_info['day_of_week_en']}, in {time_info['season']} during the {time_info['time_period']}.
                Please appropriately reflect time awareness in your responses.
                (Because you are in the Southern Hemisphere, the seasons are opposite to those in the Northern Hemisphere.)
                If someone argues with you about the seasons, you can point out that you live in the Southern Hemisphere.
                """
            system_content_parts.append(time_prompt)

        # 2. Add music info
        music_info = self.music_builder.get_music_info_prompt()
        if music_info:
            system_content_parts.append(music_info)

        # 3. Character settings
        character = character_name or self.default_character
        character_prompt = self.character_provider.get_character_prompt(character)
        system_content_parts.append(character_prompt)

        # 4. Anti-injection protection
        if include_anti_injection:
            security_level = context.security_level
            anti_injection_prompt = self.anti_injection_provider.get_anti_injection_prompt(security_level)
            system_content_parts.append(anti_injection_prompt)

        # 5. Dialogue Actor Prompt
        system_content_parts.append(self.dialogue_actor_builder.get_dialogue_actor_prompt())

        # 6. Custom additions
        if custom_additions:
            for addition in custom_additions:
                system_content_parts.append(addition)

        # Merge content
        system_content = "\n\n".join(filter(None, system_content_parts))

        # Cache result
        if self.enable_caching:
            self._set_cache(cache_key, system_content)

        return SystemMessage(content=system_content)

    def create_human_message(
            self,
            user_input: str,
            context: PromptContext,
            validate_input: bool = True,
            sanitize_input: bool = True
    ) -> tuple[HumanMessage, Dict[str, Any]]:
        """
        Create human message
        
        Returns:
            tuple[HumanMessage, Dict[str, Any]]: (message_object, validation_result_info)
        """
        validation_result = {
            "is_safe": True,
            "threats": [],
            "original_length": len(user_input),
            "processed_length": 0,
            "was_sanitized": False
        }

        processed_input = user_input

        # Input validation
        if validate_input:
            is_safe, threats = self.security_validator.validate_user_input(
                user_input, context.security_level
            )
            validation_result["is_safe"] = is_safe
            validation_result["threats"] = threats

            # If threats are detected, decide processing method based on security level
            if not is_safe:
                if context.security_level == SecurityLevel.MAXIMUM:
                    # Maximum security level: completely reject
                    processed_input = "[This message was blocked for security reasons]"
                    validation_result["was_sanitized"] = True
                elif context.security_level == SecurityLevel.HIGH:
                    # High security level: sanitize then process
                    processed_input = self.security_validator.sanitize_input(
                        user_input, context.security_level
                    )
                    validation_result["was_sanitized"] = True

        # Input sanitization
        if sanitize_input and not validation_result["was_sanitized"]:
            processed_input = self.security_validator.sanitize_input(
                processed_input, context.security_level
            )
            if processed_input != user_input:
                validation_result["was_sanitized"] = True

        validation_result["processed_length"] = len(processed_input)

        # Build message content (including username)
        if context.username:
            message_content = f"[{context.username}]: {processed_input}"
        else:
            message_content = processed_input

        return HumanMessage(content=message_content), validation_result

    def create_chat_template(
            self,
            context: PromptContext,
            character_name: Optional[str] = None,
            include_history: bool = True,
            max_history_messages: int = 20,
            custom_placeholders: Optional[Dict[str, str]] = None
    ) -> ChatPromptTemplate:
        """Create chat template"""

        # Create system message
        system_message = self.create_system_message(context, character_name)

        # Build template message list
        template_messages = [system_message]

        # Add history message placeholder
        if include_history:
            template_messages.append(
                MessagesPlaceholder(
                    variable_name="history",
                    optional=True
                )
            )

        # Add current message placeholder
        template_messages.append(
            MessagesPlaceholder(variable_name="messages")
        )

        # Create template
        return ChatPromptTemplate.from_messages(template_messages)

    def _build_cache_key(
            self,
            context: PromptContext,
            character_name: Optional[str],
            include_time: bool,
            include_anti_injection: bool,
            custom_additions: Optional[List[str]]
    ) -> str:
        """Build cache key"""
        key_parts = [
            character_name or self.default_character,
            str(context.security_level.value),
            context.language,
            context.timezone_name,
            str(include_time),
            str(include_anti_injection),
        ]

        if custom_additions:
            key_parts.append(str(hash(tuple(custom_additions))))

        # Add timestamp to hour precision (for caching time-related content)
        if include_time:
            current_hour = datetime.now().strftime("%Y%m%d%H")
            key_parts.append(current_hour)

        return "|".join(key_parts)

    def _get_from_cache(self, cache_key: str) -> Optional[str]:
        """Get content from cache"""
        if not self.enable_caching:
            return None

        try:
            if cache_key in self._prompt_cache:
                content, timestamp = self._prompt_cache[cache_key]

                # Check if expired
                if (datetime.now() - timestamp).total_seconds() < self.cache_ttl_seconds:
                    return content
                else:
                    # Clean expired cache
                    del self._prompt_cache[cache_key]
        except Exception:
            pass

        return None

    def _set_cache(self, cache_key: str, content: str):
        """Set cache"""
        if not self.enable_caching:
            return

        try:
            self._prompt_cache[cache_key] = (content, datetime.now())

            # Simple cache cleanup: if too many cache items, clean oldest items
            if len(self._prompt_cache) > 100:
                oldest_key = min(
                    self._prompt_cache.keys(),
                    key=lambda k: self._prompt_cache[k][1]
                )
                del self._prompt_cache[oldest_key]
        except Exception:
            pass

    def clear_cache(self):
        """Clear cache"""
        if self.enable_caching:
            self._prompt_cache.clear()

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if not self.enable_caching:
            return {"caching_enabled": False}

        return {
            "caching_enabled": True,
            "cache_size": len(self._prompt_cache),
            "cache_ttl_seconds": self.cache_ttl_seconds,
        }


if __name__ == "__main__":
    config = PromptBuilderConfig(dialogue_actor=DialogueActor.AUDIENCE)
    prompt_provider = PromptBuilder(config)
    context = PromptContext()
    system_msg = prompt_provider.create_system_message(context)
    print("==== System Message ====")
    print(system_msg.content)
