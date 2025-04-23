import time
import mss
from pathlib import Path
from src.utils.path import find_project_root

# 配置路径
IMG_DIR = find_project_root() / "src" / "vision" / "img"
IMG_DIR.mkdir(parents=True, exist_ok=True)


def capture_fullscreen_images(count: int = 1, interval: int = 5):
    while True:
        with mss.mss() as sct:
            for i in range(1, count + 1):
                filepath = IMG_DIR / f"img{i}.png"
                sct.shot(output=str(filepath))
                print(f"[截图] 已保存：{filepath}")
                time.sleep(interval)


if __name__ == "__main__":
    capture_fullscreen_images()
