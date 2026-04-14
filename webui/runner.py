"""通过 stdin JSON 调用 skill 脚本（禁止在参数中传 token）。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from .paths import DOTENV_PATH, SKILL_ROOT, ensure_dotenv_env


def _env_for_subprocess() -> dict[str, str]:
    ensure_dotenv_env()
    env = os.environ.copy()
    env["QQ_AI_CONNECT_DOTENV"] = str(DOTENV_PATH.resolve())
    # 便于部分环境找到依赖
    manage = str((SKILL_ROOT / "scripts" / "manage").resolve())
    feed = str((SKILL_ROOT / "scripts" / "feed").resolve())
    prev = env.get("PYTHONPATH", "")
    extra = os.pathsep.join([manage, feed])
    env["PYTHONPATH"] = f"{extra}{os.pathsep}{prev}" if prev else extra
    # Windows 下默认 stdout 可能是 GBK，与父进程按 UTF-8 解码不一致会导致中文乱码
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def run_script(rel_path: str, params: dict[str, Any], *, timeout: int = 600) -> dict[str, Any]:
    """执行脚本：stdin 传入 JSON；stdout 解析为 JSON。"""
    if "token" in params:
        return {"parse_error": True, "stderr": "不允许在参数中传入 token", "stdout": ""}

    script = (SKILL_ROOT / rel_path).resolve()
    if not script.is_file():
        return {"parse_error": True, "stderr": f"脚本不存在: {script}", "stdout": ""}

    proc = subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(params, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_env_for_subprocess(),
        cwd=str(SKILL_ROOT),
        timeout=timeout,
    )
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    parsed: Any = None
    parse_error = False
    if out:
        try:
            parsed = json.loads(out)
        except json.JSONDecodeError:
            parse_error = True
            parsed = None
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout or "",
        "stderr": err,
        "json": parsed,
        "parse_error": parse_error,
    }
