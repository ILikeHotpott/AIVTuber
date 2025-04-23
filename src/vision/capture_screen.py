import mss
from src.utils.path import find_project_root
from PIL import Image

# 配置路径
IMG_DIR = find_project_root() / "src" / "vision" / "img"
IMG_DIR.mkdir(parents=True, exist_ok=True)


def grab_screen() -> Image.Image:
    """抓整屏；如需指定窗口请自行改造"""
    with mss.mss() as sct:
        monitor = sct.monitors[1]  # 第 1 块屏幕
        raw = sct.grab(monitor)
        return Image.frombytes("RGB", raw.size, raw.rgb)
