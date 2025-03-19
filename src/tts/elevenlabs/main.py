import os

from elevenlabs import stream
from elevenlabs.client import ElevenLabs
from dotenv import load_dotenv

load_dotenv()

client = ElevenLabs(
    api_key=os.getenv("ELEVENLABS_API_KEY"),
)

audio_stream = client.text_to_speech.convert_as_stream(
    text="微风轻拂，湖面泛起涟漪，倒映着霞光如诗。远山含黛，云雾缭绕，宛若人间仙境。繁花摇曳，暗香浮动，落英点缀小径，步步生辉。此刻，天地静谧，心随风远，流连忘返。",
    voice_id="3dzAIUMHTjZ3rBtqKgXb",
    model_id="eleven_multilingual_v2"
)

stream(audio_stream)
