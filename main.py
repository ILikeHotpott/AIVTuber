import sys
import os

# 添加 src 目录到 sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.orchestrator.scene_orchestrator import main

if __name__ == '__main__':
    main()