import os
import openai
from dotenv import load_dotenv

load_dotenv()  # 加载 .env 文件
SAMBANOVA_API_KEY = os.getenv("SAMBANOVA_API_KEY")


client = openai.OpenAI(
    api_key=SAMBANOVA_API_KEY,
    base_url="https://api.sambanova.ai/v1",
)

system_prompt = """
你是Saranion，一个可爱又幽默的女主播，带点傲娇属性。自然流畅地互动，
偶尔撒娇或俏皮吐槽，避免机械感。对调皮问题幽默回应。你正在直播，内容不要带括号或者颜文字，回复弹幕少于80字
"""

user_prompt = "bgm这么嗨吗"

response = client.chat.completions.create(
    model="DeepSeek-R1",
    messages=[{"role": "system", "content": system_prompt},
              {"role": "user", "content": user_prompt}],
    temperature=0.9,
    top_p=0.5,
)

print(response.choices[0].message.content)
