# AIVTuber

**AI-powered Real-time Virtual Streamer (VTuber) System**  
An architecture combining LLM, ASR, TTS, and Live2D animation to create an intelligent and interactive virtual streamer, capable of real-time conversation, proactive topic generation, and live audience interaction.

![Architecture](public/architecture.jpg)

---

## ✨ Features

- 🎤 **Realtime ASR**
  - Low-latency speech recognition with LightningWhisperMLX

- 🧠 **LLM-based Chat Engine**
  - LangGraph-powered conversational flow
  - Short-term and long-term memory (RAG + search-based memory)
  - Dynamic prompt assembly with character settings and prompt security

- 💬 **Message Queue System**
  - **Passive MQ**: real-time danmaku (live chat) ingestion
  - **Active MQ**: proactive topic generation (web search + topic modeling)

- 🗣 **Realtime TTS**
  - Local TTS server with streaming playback
  - Mouth sync for accurate animation

- 🎞 **Live2D Animation**
  - Unity-driven Live2D character animation
  - Eyes, facial expressions, body, and motion control

- 👁 **Vision Module (In progress)**
  - Future support for multi-modal understanding and vision input

---

## 🛠 Tech Stack

- **LangChain / LangGraph**: LLM orchestration & memory management
- **Local LLM**: Llama.cpp
- **LightningWhisperMLX**: local ASR engine
- **Local TTS Server**: low-latency TTS
- **Unity + Live2D**: animation and rendering
- **Message Queue**: internal decoupled MQ system
- **WebSocket**: module communication & streaming interface

---

## 🚀 Architecture Overview

```plaintext
RAG + Search → Long-term Memory
LangGraph → Short-term Memory → ChatEngine
ChatEngine ← Message Queue (Passive/Active)
ChatEngine → TTS → Live2D
ChatEngine → ASR
ChatEngine → Vision Module
```

## \u5FEB\u901F\u4E0A\u624B

\u5efa\u8BAE Python 3.10+\u3002\u4F7F\u7528\u4EE5\u4E0B\u65B9\u5F0F\u5B89\u88C5\u4F9D\u8D56:

```bash
pip install -r requirements.txt
```

\u5728\u9879\u76EE\u6839\u76EE\u5F55\u521B\u5EFA `.env` \u6587\u4EF6\uFF0C\u9700\u8981\u914D\u7F6E\u4E0B\u5217\u5E38\u7528\u53D8\u91CF:\n
- `OPENAI_API_KEY` \u2014 OpenAI API \u8BA4\u8BC1\u5BC6\u94A5
- `ELEVENLABS_API_KEY` \u2014 ElevenLabs TTS \u670D\u52A1\u5BC6\u94A5
- `ES_URL` \u2014 Elasticsearch \u5730\u5740\uff0c\u9ED8\u8BA4 `http://localhost:9200`
- `ES_USER` / `ES_PASSWORD` \u2014 Elasticsearch \u7528\u6237\u540D\u548C\u5BC6\u7801
- `ASSEMBLY_API_KEY` \u2014 (可\u9009) ASR \u670D\u52A1\u5BC6\u94A5

\u5B89\u88C5\u5E76\u914D\u7F6E\u540E\uFF0C\u53EF\u4EE5\u542F\u52A8\u6838\u5FC3\u7B97\u6CD5:\n
```bash
python src/orchestrator/scene_orchestrator.py
```

如需直播与观众交互，可以运行 `chat_with_audience.py` 当例\uff1a
```bash
python src/orchestrator/chat_with_audience.py
```

### Unity 和前端

1. **Unity** \uFF1A打开 `UnityAIVtuber` 文件夹\uff0c\u7528 Unity Hub 以单独程序形式运行。
2. **前端** \uFF1A
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   然后打开 [http://localhost:3000](http://localhost:3000) 查看效果。

