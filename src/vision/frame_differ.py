import time
import numpy as np
from typing import Optional
from PIL import Image, ImageOps, ImageChops


class FrameDiffer:
    """最小帧差检测：差异阈值 + 冷却时间"""

    def __init__(self,
                 min_diff: float = 0.05,
                 cooldown: float = 2.0,
                 downscale: tuple[int, int] = (320, 180)
                 ) -> None:
        self.min_diff = min_diff
        self.cooldown = cooldown
        self.downscale = downscale
        self._prev: Optional[Image.Image] = None
        self._last_ts = 0.0

    def _pre(self, img: Image.Image) -> Image.Image:
        img = img.resize(self.downscale, Image.BILINEAR)
        return ImageOps.grayscale(img)

    def should_process(self, img: Image.Image) -> bool:
        now = time.time()
        if self._prev is None:
            self._prev, self._last_ts = self._pre(img), now
            return True

        cur = self._pre(img)
        diff = ImageChops.difference(self._prev, cur)
        score = np.asarray(diff, np.float32).mean() / 255.0
        self._prev = cur

        if score >= self.min_diff and now - self._last_ts >= self.cooldown:
            self._last_ts = now
            return True
        return False
