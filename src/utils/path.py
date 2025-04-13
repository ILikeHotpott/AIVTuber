from pathlib import Path


def find_project_root(marker_files=[".git", "pyproject.toml", "requirements.txt"]):
    path = Path(__file__).resolve()
    while path != path.parent:
        if any((path / marker).exists() for marker in marker_files):
            return path
        path = path.parent
    raise FileNotFoundError("⚠️ 无法自动识别项目根目录")