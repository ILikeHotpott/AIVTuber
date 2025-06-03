"""
Multi-User Chat Service
Integrates memory management and prompt provider to provide a complete multi-user chat solution

Author: Assistant
Date: 2025-01-10
"""

import asyncio
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate

from src.memory.multi_user.user_memory_manager import (
    UserMemoryManager, 
    create_user_memory_manager,
    MemoryType, 
    MessagePriority
)
from src.prompt.providers.prompt_provider import (
    PromptProvider, 
    PromptContext, 
    SecurityLevel,
    create_prompt_provider
)


class ChatServiceMode(Enum):
    """Chat service mode"""
    PERSONAL_ONLY = "personal_only"    # Personal memory only
    GENERAL_ONLY = "general_only"      # General memory only  
    HYBRID = "hybrid"                  # Hybrid mode (recommended)


@dataclass
class ChatRequest:
    """Chat request data model"""
    user_id: str
    username: str
    message: str
    language: str = "English"
    timezone_name: str = "Australia/Adelaide"
    security_level: SecurityLevel = SecurityLevel.HIGH
    character_name: Optional[str] = None
    priority: MessagePriority = MessagePriority.NORMAL
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatResponse:
    """Chat response data model"""
    response_message: str
    user_id: str
    username: str
    is_safe: bool
    security_warnings: List[str] = field(default_factory=list)
    processing_time_ms: int = 0
    memory_stats: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ServiceStats:
    """Service statistics"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_response_time_ms: float = 0.0
    total_users: int = 0
    active_users_24h: int = 0
    memory_usage: Dict[str, Any] = field(default_factory=dict)
    security_incidents: Dict[str, int] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class MultiUserChatService:
    """
    Enterprise-level Multi-User Chat Service
    
    Features:
    - Integrated memory management (personal + general)
    - Intelligent prompt generation
    - Security protection and input validation
    - Performance monitoring and statistics
    - High concurrency support
    - Flexible configuration options
    """
    
    def __init__(
        self,
        mode: ChatServiceMode = ChatServiceMode.HYBRID,
        memory_manager: Optional[UserMemoryManager] = None,
        prompt_provider: Optional[PromptProvider] = None,
        default_character: str = "default",
        default_security_level: SecurityLevel = SecurityLevel.HIGH,
        enable_stats: bool = True,
        **kwargs
    ):
        self.mode = mode
        self.default_character = default_character
        self.default_security_level = default_security_level
        self.enable_stats = enable_stats
        
        # Initialize memory manager
        self.memory_manager = memory_manager or create_user_memory_manager(
            storage_type="memory",
            **kwargs
        )
        
        # Initialize Prompt provider
        self.prompt_provider = prompt_provider or create_prompt_provider(
            character_name=default_character,
            security_level=default_security_level,
            **kwargs
        )
        
        # Statistics
        self._stats = ServiceStats()
        self._stats_lock = asyncio.Lock()
        self._response_times: List[float] = []
        
        # Performance monitoring
        self._start_time = datetime.now(timezone.utc)
        
        print(f"[MultiUserChatService] Initialized in {mode.value} mode")
    
    async def process_chat_request(
        self,
        request: ChatRequest,
        llm_callback: Optional[callable] = None
    ) -> ChatResponse:
        """
        Process chat request
        
        Args:
            request: Chat request
            llm_callback: LLM callback function (prompt_template, context) -> response_text
        
        Returns:
            ChatResponse: Chat response
        """
        start_time = datetime.now()
        
        try:
            # Update statistics
            if self.enable_stats:
                await self._increment_stat("total_requests")
            
            # 1. Create Prompt context
            context = PromptContext(
                user_id=request.user_id,
                username=request.username,
                language=request.language,
                timezone_name=request.timezone_name,
                security_level=request.security_level,
                metadata=request.metadata
            )
            
            # 2. Validate and sanitize user input
            human_message, validation_result = self.prompt_provider.create_human_message(
                request.message, context
            )
            
            # 3. Check security
            if not validation_result["is_safe"]:
                if request.security_level == SecurityLevel.MAXIMUM:
                    # Maximum security level: direct rejection
                    return ChatResponse(
                        response_message="Sorry, your message contains inappropriate content and cannot be processed.",
                        user_id=request.user_id,
                        username=request.username,
                        is_safe=False,
                        security_warnings=validation_result["threats"],
                        processing_time_ms=self._get_processing_time(start_time)
                    )
                
                # Record security incidents
                if self.enable_stats:
                    await self._record_security_incident(validation_result["threats"])
            
            # 4. Retrieve memory history
            personal_history = []
            general_history = []
            
            if self.mode in [ChatServiceMode.PERSONAL_ONLY, ChatServiceMode.HYBRID]:
                personal_history = await self.memory_manager.get_personal_langchain_messages(
                    request.user_id, limit=20
                )
            
            if self.mode in [ChatServiceMode.GENERAL_ONLY, ChatServiceMode.HYBRID]:
                general_history = await self.memory_manager.get_general_langchain_messages(
                    limit=30
                )
            
            # 5. Build chat template
            chat_template = self.prompt_provider.create_chat_template(
                context=context,
                character_name=request.character_name or self.default_character,
                include_history=True
            )
            
            # 6. Prepare history messages
            combined_history = self._combine_histories(personal_history, general_history)
            
            # 7. Call LLM
            if llm_callback:
                response_text = await self._call_llm_async(
                    llm_callback, chat_template, combined_history, [human_message]
                )
            else:
                response_text = "Sorry, LLM service is temporarily unavailable."
            
            # 8. Save messages to memory
            await self._save_messages_to_memory(
                request, human_message, response_text, context
            )
            
            # 9. Update statistics
            processing_time = self._get_processing_time(start_time)
            if self.enable_stats:
                await self._update_stats_success(processing_time)
            
            # 10. Build response
            memory_stats = await self.memory_manager.get_user_message_count(request.user_id)
            
            return ChatResponse(
                response_message=response_text,
                user_id=request.user_id,
                username=request.username,
                is_safe=validation_result["is_safe"],
                security_warnings=validation_result["threats"],
                processing_time_ms=processing_time,
                memory_stats=memory_stats,
                metadata={
                    "was_sanitized": validation_result["was_sanitized"],
                    "original_length": validation_result["original_length"],
                    "processed_length": validation_result["processed_length"]
                }
            )
            
        except Exception as e:
            # Error handling
            processing_time = self._get_processing_time(start_time)
            if self.enable_stats:
                await self._increment_stat("failed_requests")
            
            print(f"[MultiUserChatService] Error processing request: {e}")
            
            return ChatResponse(
                response_message="Sorry, an error occurred while processing your request. Please try again later.",
                user_id=request.user_id,
                username=request.username,
                is_safe=True,
                processing_time_ms=processing_time,
                metadata={"error": str(e)}
            )
    
    async def _call_llm_async(
        self,
        llm_callback: callable,
        chat_template: ChatPromptTemplate,
        history: List[BaseMessage],
        messages: List[BaseMessage]
    ) -> str:
        """Call LLM asynchronously"""
        try:
            # If callback is a coroutine function, call directly
            if asyncio.iscoroutinefunction(llm_callback):
                return await llm_callback(chat_template, history, messages)
            else:
                # If it's a synchronous function, run in thread pool
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None, llm_callback, chat_template, history, messages
                )
        except Exception as e:
            print(f"[MultiUserChatService] LLM callback error: {e}")
            return "Sorry, I cannot respond properly right now. Please try again later."
    
    def _combine_histories(
        self,
        personal_history: List[BaseMessage],
        general_history: List[BaseMessage]
    ) -> List[BaseMessage]:
        """Combine personal and general history records"""
        if self.mode == ChatServiceMode.PERSONAL_ONLY:
            return personal_history[-20:] if personal_history else []
        elif self.mode == ChatServiceMode.GENERAL_ONLY:
            return general_history[-20:] if general_history else []
        else:  # HYBRID
            # Hybrid mode: prioritize personal memory, supplement with general memory
            combined = personal_history[-15:] if personal_history else []
            
            # Add some recent general memory
            if general_history:
                # Avoid duplicates: only add general messages not in personal memory
                recent_general = general_history[-10:]
                for msg in recent_general:
                    if msg not in combined:
                        combined.append(msg)
            
            # Sort by time and limit quantity
            return combined[-20:]
    
    async def _save_messages_to_memory(
        self,
        request: ChatRequest,
        human_message: HumanMessage,
        response_text: str,
        context: PromptContext
    ):
        """Save messages to memory system"""
        try:
            from langchain_core.messages import AIMessage
            ai_message = AIMessage(content=response_text)
            
            if self.mode in [ChatServiceMode.PERSONAL_ONLY, ChatServiceMode.HYBRID]:
                await self.memory_manager.add_personal_message(
                    request.user_id, human_message, request.username, request.priority
                )
                await self.memory_manager.add_personal_message(
                    request.user_id, ai_message, "assistant", request.priority
                )
            
            if self.mode in [ChatServiceMode.GENERAL_ONLY, ChatServiceMode.HYBRID]:
                await self.memory_manager.add_general_message(
                    request.user_id, human_message, request.username, request.priority
                )
                await self.memory_manager.add_general_message(
                    request.user_id, ai_message, "assistant", request.priority
                )
                
        except Exception as e:
            print(f"[MultiUserChatService] Error saving to memory: {e}")
    
    def _get_processing_time(self, start_time: datetime) -> int:
        """Get processing time (milliseconds)"""
        return int((datetime.now() - start_time).total_seconds() * 1000)
    
    async def _increment_stat(self, stat_name: str):
        """Increment statistics counter"""
        async with self._stats_lock:
            current_value = getattr(self._stats, stat_name, 0)
            setattr(self._stats, stat_name, current_value + 1)
    
    async def _update_stats_success(self, processing_time: int):
        """Update success statistics"""
        async with self._stats_lock:
            self._stats.successful_requests += 1
            self._response_times.append(processing_time)
            
            # Keep recent 1000 response time records
            if len(self._response_times) > 1000:
                self._response_times = self._response_times[-1000:]
            
            # Calculate average response time
            if self._response_times:
                self._stats.average_response_time_ms = sum(self._response_times) / len(self._response_times)
    
    async def _record_security_incident(self, threats: List[str]):
        """Record security incidents"""
        async with self._stats_lock:
            for threat in threats:
                current_count = self._stats.security_incidents.get(threat, 0)
                self._stats.security_incidents[threat] = current_count + 1
    
    async def get_service_stats(self) -> ServiceStats:
        """Get service statistics"""
        async with self._stats_lock:
            # Update memory statistics
            memory_stats = await self.memory_manager.get_stats()
            self._stats.total_users = memory_stats.total_users
            self._stats.active_users_24h = memory_stats.active_users_24h
            self._stats.memory_usage = {
                "personal_messages": memory_stats.total_personal_messages,
                "general_messages": memory_stats.total_general_messages,
                "most_active_user": memory_stats.most_active_user,
                "average_messages_per_user": memory_stats.average_messages_per_user
            }
            self._stats.last_updated = datetime.now(timezone.utc)
            
            return self._stats
    
    async def clear_user_memory(
        self,
        user_id: str,
        memory_type: Optional[MemoryType] = None
    ) -> Dict[str, int]:
        """Clear user memory"""
        result = {}
        
        if memory_type is None or memory_type == MemoryType.PERSONAL:
            personal_deleted = await self.memory_manager.delete_user_messages(
                user_id, MemoryType.PERSONAL
            )
            result["personal_deleted"] = personal_deleted
        
        if memory_type is None or memory_type == MemoryType.GENERAL:
            # Note: clearing general memory affects all users
            general_deleted = await self.memory_manager.clear_general_memory()
            result["general_deleted"] = general_deleted
        
        return result
    
    async def get_user_conversation_history(
        self,
        user_id: str,
        limit: int = 50,
        include_general: bool = True
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get user conversation history"""
        result = {}
        
        # Personal history
        personal_messages = await self.memory_manager.get_personal_messages(
            user_id, limit=limit
        )
        result["personal_history"] = [msg.to_dict() for msg in personal_messages]
        
        # General history (if needed)
        if include_general:
            general_messages = await self.memory_manager.get_general_messages(
                limit=limit
            )
            result["general_history"] = [msg.to_dict() for msg in general_messages]
        
        return result
    
    def switch_mode(self, new_mode: ChatServiceMode):
        """Switch service mode"""
        if new_mode == self.mode:
            print(f"[MultiUserChatService] Already in {new_mode.value} mode")
            return
        
        print(f"[MultiUserChatService] Switching from {self.mode.value} to {new_mode.value} mode")
        self.mode = new_mode
    
    async def close(self):
        """Close service"""
        print("[MultiUserChatService] Closing...")
        
        # Close memory manager
        if self.memory_manager:
            await self.memory_manager.close()
        
        # Clear cache
        if self.prompt_provider:
            self.prompt_provider.clear_cache()
        
        print("[MultiUserChatService] Closed successfully")


# Convenience functions
async def create_simple_chat_request(
    user_id: str,
    username: str,
    message: str,
    **kwargs
) -> ChatRequest:
    """Create simple chat request"""
    return ChatRequest(
        user_id=user_id,
        username=username,
        message=message,
        **kwargs
    )


# Factory function
def create_multi_user_chat_service(
    mode: str = "hybrid",
    character_name: str = "default",
    security_level: str = "high",
    **kwargs
) -> MultiUserChatService:
    """Factory function to create multi-user chat service"""
    
    # Convert enums
    mode_enum = ChatServiceMode(mode.lower())
    security_enum = SecurityLevel[security_level.upper()]
    
    return MultiUserChatService(
        mode=mode_enum,
        default_character=character_name,
        default_security_level=security_enum,
        **kwargs
    ) 