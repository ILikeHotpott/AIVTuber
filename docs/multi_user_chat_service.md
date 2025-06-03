# Multi-User Chat Service Documentation

## Overview

The Multi-User Chat Service is an enterprise-level chat management system designed for virtual host projects. It integrates intelligent memory management, dynamic prompt generation, security protection, and high-performance concurrent processing to provide a complete multi-user chat solution.

### Key Features

- **Intelligent Memory Management**: Personal and shared memory spaces, automatic cleanup mechanism
- **Dynamic Prompt Generation**: Time-aware, role consistency, security protection
- **Enterprise-Level Security**: Input validation, injection protection, rate limiting, permission management
- **Performance Monitoring**: Real-time statistics, resource monitoring, exception tracking
- **High Concurrency**: Asynchronous processing, connection pooling, cache optimization

## Core Features

### 1. Intelligent Memory Management

- **Personal Memory**: Each user has independent chat memory
- **General Memory**: Shared memory space for all users
- **Automatic Cleanup**: Regular cleanup of old messages based on time and capacity limits
- **Thread Safety**: All memory operations are asynchronous and thread-safe

### 2. Dynamic Prompt Generation

- **Time Awareness**: Automatically generates current time information (Adelaide timezone)
- **Role Setting**: Supports flexible character and role configuration
- **Security Protection**: Built-in prompt injection detection and prevention
- **Multi-language Support**: Supports English and other languages

### 3. Enterprise-Level Security

- **Input Validation**: Comprehensive validation and sanitization of user input
- **Injection Protection**: Detection and blocking of prompt injection attacks
- **Rate Limiting**: Configurable rate limiting per user and globally
- **Fine-grained Permissions**: Multi-level security configuration (LOW, NORMAL, HIGH, MAXIMUM)

### 4. Performance Monitoring

- **Real-time Statistics**: User count, message count, response time monitoring
- **Resource Monitoring**: Memory usage, database performance tracking
- **Exception Tracking**: Detailed error logging and security incident recording

## Quick Start

### 1. Environment Configuration

Copy the environment configuration file and edit it:

```bash
cp config/multi_user_service.env.example .env
```

Configure necessary environment variables:

```bash
# Enable multi-user service
USE_MULTI_USER_SERVICE=true

# OpenAI API configuration
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE=https://api.openai.com/v1
MODEL_NAME=gpt-4o-mini

# Time zone configuration
DEFAULT_TIMEZONE=Australia/Adelaide
DEFAULT_LANGUAGE=English
```

### 2. Basic Usage

```python
from src.chatbot.llama.chat_engine import ChatEngine
from src.prompt.builders.prompt_builder import SecurityLevel

# Get chat engine instance
chat_engine = ChatEngine.get_instance()

# Send chat message
response = await chat_engine.stream_chat_multi_user(
   user_id="user_001",
   username="Alice",
   message="Hello! How are you today?",
   language="English",
   security_level=SecurityLevel.HIGH
)

print(f"Assistant: {response}")
```

### 3. Run Demo

```bash
python src/examples/multi_user_chat_example.py
```

## Architecture Design

### Core Components

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   ChatEngine    │───▶│ MultiUserChatSvc │───▶│  PromptProvider │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │ UserMemoryManager│
                       └──────────────────┘
```

### Data Flow

1. **Request Reception**: ChatEngine receives multi-user chat request
2. **Input Validation**: PromptProvider validates and sanitizes user input
3. **Memory Retrieval**: UserMemoryManager retrieves relevant chat history
4. **Prompt Generation**: Generate intelligent prompts with context
5. **LLM Processing**: Call language model for response generation
6. **Memory Storage**: Save conversation to appropriate memory space
7. **Response Return**: Return formatted response to user

## API Reference

### ChatEngine.stream_chat_multi_user()

```python
async def stream_chat_multi_user(
    self,
    user_id: str,                           # User unique identifier
    username: str,                          # User display name
    message: str,                           # User message content
    language: str = "English",              # Language setting
    security_level: SecurityLevel = SecurityLevel.HIGH,  # Security level
    character_name: Optional[str] = None    # Character name (optional)
) -> str:
    """
    Multi-user chat interface
    
    Returns: Assistant response text
    """
```

### Service Statistics

```python
# Get service statistics
stats = await chat_engine.get_user_stats()

# Statistics include:
# - total_users: Total number of users
# - active_users_24h: Active users in last 24 hours
# - total_messages: Total message count
# - average_response_time: Average response time
```

## Configuration Options

### Memory Management

```bash
# Memory capacity limits
MAX_PERSONAL_MESSAGES_PER_USER=500
MAX_GENERAL_MESSAGES=1000

# Automatic cleanup
MEMORY_CLEANUP_INTERVAL_HOURS=24
OLD_MESSAGE_THRESHOLD_DAYS=30
```

### Performance Configuration

```bash
# Concurrency settings
MAX_CONCURRENT_REQUESTS=50
REQUEST_TIMEOUT_SECONDS=30

# Cache configuration
ENABLE_RESPONSE_CACHE=true
CACHE_TTL_SECONDS=300
```

### Security Configuration

```bash
# Input validation
ENABLE_INPUT_VALIDATION=true
MAX_MESSAGE_LENGTH=2000

# Rate limiting
RATE_LIMIT_PER_USER=60
RATE_LIMIT_GLOBAL=1000

# Security level
DEFAULT_SECURITY_LEVEL=high
```

## Best Practices

### 1. Security Levels

- **LOW**: Basic filtering, suitable for trusted environments
- **NORMAL**: Standard security checks, general use
- **HIGH**: Strict validation, recommended for production
- **MAXIMUM**: Highest security, zero tolerance for risks

### 2. Input Validation

```python
# Good practice: specify appropriate security level
response = await chat_engine.stream_chat_multi_user(
    user_id="user_001",
    username="Alice",
    message=user_input,
    security_level=SecurityLevel.HIGH  # Use high security level
)
```

### 3. Rate Limiting

- Configure reasonable rate limits based on usage patterns
- Monitor rate limit metrics to adjust thresholds
- Implement graceful degradation for rate-limited users

## Performance Optimization

### 1. Memory Management

- Regularly clean up old conversation history
- Set appropriate memory limits based on available resources
- Use database indices for faster memory retrieval

### 2. Caching Strategy

- Enable response caching for frequently asked questions
- Set appropriate cache TTL based on content freshness requirements
- Monitor cache hit rates and adjust cache size accordingly

### 3. Concurrent Processing

- Use connection pooling for database operations
- Implement async processing for better scalability
- Monitor resource usage and adjust concurrency limits

## Troubleshooting

### Common Issues

1. **High Memory Usage**
   - Solution: Reduce memory limits, increase cleanup frequency

2. **Slow Response Times**
   - Solution: Enable caching, optimize database queries, increase concurrency

3. **Security Alerts**
   - Solution: Review security logs, adjust security levels, update filtering rules

### Debug Mode

Enable debug mode for detailed logging:

```bash
DEBUG_MODE=true
LOG_LEVEL=DEBUG
ENABLE_PERFORMANCE_LOGGING=true
```

## Version History

### v1.0.0 (2025-01-10)

**Initial Release**
- Multi-user memory management system
- Intelligent prompt generation with Adelaide timezone support
- Enterprise-level security features
- Performance monitoring and statistics
- Complete English documentation and examples

**Features Included:**
- Personal and general memory spaces
- Time-aware prompt generation (Adelaide timezone)
- Multi-level security validation
- Async high-concurrency processing
- Comprehensive configuration options
- Complete usage examples and documentation

## License and Contribution

This project follows the MIT license. We welcome contributions and feedback to help improve the service.

For questions or suggestions, please submit an issue or contact the development team. 