import os

from elevenlabs import stream
from elevenlabs.client import ElevenLabs
from dotenv import load_dotenv

load_dotenv()

client = ElevenLabs(
    api_key=os.getenv("ELEVENLABS_API_KEY"),
)

audio_stream = client.text_to_speech.convert_as_stream(
    text="""
    清晨的城市被薄雾轻轻拥抱，街角早餐铺飘来油条豆浆的香气。地铁里人潮涌动，耳机里播放着熟悉的旋律。
    阳光逐渐穿破高楼缝隙，照亮奔忙的身影，平凡日子里，藏着生活最真实的温柔。
    """,
    voice_id="3dzAIUMHTjZ3rBtqKgXb",
    model_id="eleven_multilingual_v2"
)

stream(audio_stream)
