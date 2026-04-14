"""Skill 根目录与本地 Token 路径（当前项目目录下的 .env）。"""

from pathlib import Path

WEBUI_ROOT = Path(__file__).resolve().parent
SKILL_ROOT = WEBUI_ROOT.parent
DOTENV_PATH = SKILL_ROOT / ".env"


def ensure_dotenv_env() -> None:
    """让 manage/common 与所有脚本从项目根目录读取 QQ_AI_CONNECT_TOKEN。"""
    import os

    os.environ["QQ_AI_CONNECT_DOTENV"] = str(DOTENV_PATH.resolve())
