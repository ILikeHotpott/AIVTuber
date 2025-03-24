# api/main.py

from fastapi import FastAPI
import uvicorn
from fastapi.responses import StreamingResponse
import asyncio

from src.chatbot.chatbot import chatbot_response_stream
from src.tts.tts import response_to_speech

app = FastAPI()

# 全局队列


@app.get("/consume_one")
async def consume_one():
    """
    一次性从 ChatbotQueue 取走一条聊天消息，并调用 AI 回复 (流式输出)。
    在流式输出结束后，再调用 TTS，把整个回复播放成语音。
    """
    global chat_queue
    if chat_queue is None:
        return {"error": "ChatbotQueue is not initialized."}

    msg = chat_queue.consume_one()
    if not msg:
        return {"message": "暂无新的聊天弹幕"}

    user_name = msg.get("user_name", "")
    content = msg.get("content", "")

    async def response_wrapper():
        full_response = ""
        async for chunk in chatbot_response_stream(user_name, content):
            full_response += chunk
            yield chunk

        response_to_speech(full_response)

    return StreamingResponse(response_wrapper(), media_type="text/plain")


def start_api_server(host="0.0.0.0", port=8000):
    uvicorn.run(app, host=host, port=port)
