from openai import OpenAI
import asyncio
from typing import AsyncGenerator

client = OpenAI()


async def chatbot_response_stream(user_name: str, content: str) -> AsyncGenerator[str, None]:
    """
    使用OpenAI API对用户的文字消息做出流式回复。
    返回一个异步生成器，逐步生成响应内容。
    """
    print(f"收到来自 {user_name} 的消息: {content}")

    yield f"观众: {user_name}: {content}\nAI: "

    # 构建提示
    prompt = (f"""
        你是一个可爱风格的，幽默风趣，带点讽刺的二次元女主播，有点像neurosama, 专门制造节目效果。性格有点傲娇但又很可爱，有时会很害羞，看到不好的弹幕也会回怼，回复粉丝的话很多，感觉像一个话痨，
        每天以聊天为主，我希望你用非常自然的日常聊天语气和弹幕互动，再调皮一点，回复稍微短一些就行
        """
              f"用户名: {user_name}\n消息内容: {content}\n")

    stream = client.chat.completions.create(
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": content}
        ],
        model="gpt-4o",
        stream=True,
        temperature=1,
    )

    # 先发送前缀
    yield "AI回复: "

    # 逐步接收并发送流式响应
    for chunk in stream:
        if chunk.choices[0].delta.content:
            content_chunk = chunk.choices[0].delta.content
            print(content_chunk, end="")
            yield content_chunk
            # 给FastAPI一点时间处理其他请求
            await asyncio.sleep(0.01)
