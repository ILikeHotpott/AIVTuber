import base64, os
from io import BytesIO
from typing import List, Dict, Any
from PIL import Image
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage


def _encode_img(img: Image.Image) -> str:
    """JPEG→Base64 data-url，先缩到宽512"""
    if img.width > 512:
        h = int(img.height * 512 / img.width)
        img = img.resize((512, h), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


class VisionLLMProxy:
    """Gemini 1.5 Flash 多模态封装"""

    def __init__(self,
                 model_name: str = "gemini-1.5-flash",
                 temperature: float = .4,
                 max_tokens: int = 256,
                 top_k: int = 10,
                 top_p: float = .95
                 ) -> None:
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=temperature,
            max_output_tokens=max_tokens,
            top_k=top_k,
            top_p=top_p,
            google_api_key=os.getenv("GOOGLE_API_KEY"),
        )

    def ask(self, prompt: List[Dict[str, Any]]) -> str:
        # prompt 是 langchain 的 content list
        resp = self.llm.invoke([HumanMessage(content=prompt)])
        return resp.content.strip()

    # 工具方法：图片 + 文本
    def ask_image(self, img: Image.Image, text: str) -> str:
        parts = [{"type": "text", "text": text},
                 {"type": "image_url", "image_url": _encode_img(img)}]
        return self.ask(parts)
