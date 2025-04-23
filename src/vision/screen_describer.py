import os
import time
import base64
from io import BytesIO
from pathlib import Path
from typing import List, Union, Optional

import numpy as np
from PIL import Image, ImageChops, ImageOps, ImageGrab
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_IMG_DIR = ROOT / "src" / "vision" / "img"
ImageInputType = Union[str, Path, Image.Image]


class FrameDiffer:
    """最小可用的帧差异检测器"""

    def __init__(
            self,
            min_diff: float = 0.12,  # 差异阈值 (0~1)
            cooldown: float = 2.0,  # 连续触发最短间隔(s)
            downscale_size: tuple[int, int] = (320, 180),
    ):
        self.min_diff = min_diff
        self.cooldown = cooldown
        self.downscale_size = downscale_size
        self._prev_frame: Optional[Image.Image] = None
        self._last_trigger_ts: float = 0.0

    def _preprocess(self, img: Image.Image) -> Image.Image:
        """降分辨率 + 灰度"""
        img = img.resize(self.downscale_size, Image.BILINEAR)
        img = ImageOps.grayscale(img)
        return img

    def should_process(self, img: Image.Image) -> bool:
        now = time.time()
        if self._prev_frame is None:
            self._prev_frame = self._preprocess(img)
            self._last_trigger_ts = now
            return True  # 第 1 帧直接送出

        cur = self._preprocess(img)
        diff_img = ImageChops.difference(self._prev_frame, cur)
        diff_arr = np.asarray(diff_img, dtype=np.float32) / 255.0
        diff_score = diff_arr.mean()  # 0~1，越大差异越大

        if diff_score >= self.min_diff and (now - self._last_trigger_ts) >= self.cooldown:
            self._prev_frame = cur
            self._last_trigger_ts = now
            return True

        # 保存当前帧，便于下一次比较
        self._prev_frame = cur
        return False


class ScreenDescriber:
    def __init__(
            self,
            model: str = "gemini-2.0-flash",
            prompt: str = "请描述以下屏幕截图中的主要活动, 100字以内",
            min_diff: float = 0.12,
            cooldown: float = 2.0,
    ):
        self.model = model
        self.prompt = prompt
        self.differ = FrameDiffer(min_diff=min_diff, cooldown=cooldown)

    # ---------- 内部工具 ----------
    def _to_data_url(self, image: Image.Image) -> str:
        buf = BytesIO()
        image.save(buf, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

    def _load_img(self, item: ImageInputType) -> Image.Image:
        if isinstance(item, Path):
            item = str(item)

        if isinstance(item, Image.Image):
            return item
        elif isinstance(item, str):
            if item.startswith(("http://", "https://")):
                import requests
                resp = requests.get(item, timeout=5)
                resp.raise_for_status()
                return Image.open(BytesIO(resp.content))
            return Image.open(item)
        else:
            raise TypeError("不支持的图片类型")

    # ---------- 对外接口 ----------
    def describe_images(self, inputs: List[ImageInputType], prompt: str | None = None) -> str | None:
        images = [self._load_img(i) for i in inputs]

        # Diff / Filter：如果首张图（代表最新帧）无需处理就直接返回 None
        if not self.differ.should_process(images[0]):
            return None

        llm = ChatGoogleGenerativeAI(model=self.model)
        prompt = prompt or self.prompt

        image_parts = [
            {"type": "image_url", "image_url": self._to_data_url(img)} for img in images
        ]
        message = HumanMessage(content=[{"type": "text", "text": prompt}, *image_parts])

        response = llm.invoke([message])
        return response.content


# ------------------ DEMO: 实时截图测试 ------------------
if __name__ == "__main__":

    describer = ScreenDescriber(min_diff=0.05, cooldown=3.0)

    print("开始实时截图，每3秒检测一次变化...（Ctrl+C 停止）")
    while True:
        try:
            screenshot = ImageGrab.grab()
            caption = describer.describe_images([screenshot])
            if caption:
                print(f"[触发] {caption}")
            else:
                print("[略过] 当前画面变化不足")
            time.sleep(1)  # 控制检测频率
        except KeyboardInterrupt:
            print("\n用户中断，结束测试。")
            break
