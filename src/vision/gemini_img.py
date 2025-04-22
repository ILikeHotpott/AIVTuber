from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from PIL import Image
import requests
from io import BytesIO
from pathlib import Path
import base64
from dotenv import load_dotenv
from src.utils.path import find_project_root

ROOT = find_project_root()
load_dotenv()


def analyze_image_with_gemini(image_input, prompt="中文描述这张图片", api_key="AIzaSyD-jOV0pdM1uuqEFyTfZbd-3MjzR7YHK-g"):
    if isinstance(image_input, Path):
        image_input = str(image_input)

    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=api_key)

    if isinstance(image_input, str):
        if image_input.startswith(("http://", "https://")):
            response = requests.get(image_input)
            image = Image.open(BytesIO(response.content))
        else:
            image = Image.open(image_input)
    elif isinstance(image_input, Image.Image):
        image = image_input
    else:
        raise ValueError("不支持的图片格式，请输入文件路径、URL或PIL图像对象")

    # ✅ 转为 base64 的 data URL
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    img_data_url = f"data:image/png;base64,{img_base64}"

    message = HumanMessage(
        content=[
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": img_data_url}
        ]
    )

    response = llm.invoke([message])
    return response.content


# 用法示例
img_path = ROOT / "src" / "vision" / "img" / "img1.png"
result = analyze_image_with_gemini(img_path, "图片中有哪些主要元素？")
print(result)
