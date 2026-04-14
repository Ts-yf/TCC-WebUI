"""
腾讯频道社区 Skill — 本地 Web 控制台。

运行（在仓库根目录）:
  python -m webui.app

默认首页为「内容管理面板」(`/`)，脚本参数控制台在 `/console`。

Token 与 OpenAI 密钥保存在仓库根目录 `.env`（通过环境变量 QQ_AI_CONNECT_DOTENV，与 scripts 一致）。

内容管理页内路由：`#/automation/openai`（OpenAI 配置）、`#/automation/jobs`（定时拉帖/定时提示词）。

所有能力均通过子进程调用 `scripts/` 下对应脚本（stdin JSON），不在参数中传 token。
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, url_for

_WEB_ROOT = Path(__file__).resolve().parent
_REPO_ROOT = _WEB_ROOT.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from webui.feed_manifests import load_feed_tools  # noqa: E402
from webui.manage_registry import load_manage_tools  # noqa: E402
from webui.paths import DOTENV_PATH, SKILL_ROOT, ensure_dotenv_env  # noqa: E402
from webui.panel import bp as panel_bp  # noqa: E402
from webui.runner import run_script  # noqa: E402
from webui.automation import bp as automation_bp  # noqa: E402
from webui.scheduler_service import load_jobs_from_disk, start_scheduler  # noqa: E402

app = Flask(
    __name__,
    template_folder=str(_WEB_ROOT / "templates"),
    static_folder=str(_WEB_ROOT / "static"),
)
# 接口 JSON 直接输出中文，避免 \uXXXX 转义
app.json.ensure_ascii = False
app.register_blueprint(panel_bp)
app.register_blueprint(automation_bp)

load_jobs_from_disk()
start_scheduler()


@app.route("/")
def index():
    """内容管理面板为主页。"""
    return render_template("panel.html")


@app.route("/console")
def script_console():
    """原脚本参数控制台。"""
    return render_template("index.html")


@app.route("/panel")
def panel_legacy():
    return redirect(url_for("index"), code=302)


@app.get("/api/config")
def api_config():
    ensure_dotenv_env()
    return jsonify(
        {
            "dotenvPath": str(DOTENV_PATH.resolve()),
            "tokenHelpUrl": "https://connect.qq.com/ai",
            "skillRoot": str(SKILL_ROOT.resolve()),
        }
    )


@app.get("/api/tools")
def api_tools():
    feed = load_feed_tools()
    manage = [{"kind": "manage", **t} for t in load_manage_tools()]
    return jsonify({"feed": feed, "manage": manage})


@app.post("/api/token")
def api_token():
    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()
    if not token:
        return jsonify({"ok": False, "error": "token 不能为空"}), 400
    ensure_dotenv_env()
    sys.path.insert(0, str(SKILL_ROOT / "scripts" / "manage"))
    from common import persist_token_to_dotenv_and_mcporter  # noqa: E402

    try:
        result = persist_token_to_dotenv_and_mcporter(token)
    except SystemExit:
        return jsonify({"ok": False, "error": "写入失败（见服务端日志）"}), 500
    except Exception as exc:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(exc)}), 500
    return jsonify({"ok": True, "result": result})


@app.post("/api/verify")
def api_verify():
    """调用 verify 脚本（不写敏感信息）。"""
    out = run_script("scripts/manage/read/verify_qq_ai_connect_token.py", {})
    return jsonify(out)


def _parse_params_value(raw: str) -> dict:
    if not raw or not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"params 不是合法 JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("params 必须是 JSON 对象")
    return data


@app.post("/api/run")
def api_run():
    """执行脚本：application/json 或 multipart（文件字段名 = 参数名，如 image_path）。"""
    tool = ""
    params: dict = {}

    if request.content_type and "multipart/form-data" in request.content_type:
        tool = (request.form.get("tool") or "").strip()
        try:
            params = _parse_params_value(request.form.get("params") or "{}")
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        for key, storage in request.files.items():
            if not storage or not storage.filename:
                continue
            td = Path(tempfile.mkdtemp(prefix="tcc_webui_"))
            dest = td / storage.filename
            storage.save(str(dest))
            params[key] = str(dest.resolve())
    else:
        data = request.get_json(silent=True) or {}
        tool = (data.get("tool") or "").strip()
        params = data.get("params") if isinstance(data.get("params"), dict) else {}

    if not tool:
        return jsonify({"ok": False, "error": "缺少 tool（脚本路径）"}), 400
    if "token" in params:
        return jsonify({"ok": False, "error": "禁止在参数中传 token"}), 400

    rel = tool.replace("\\", "/")
    if not rel.startswith("scripts/"):
        return jsonify({"ok": False, "error": "非法 tool 路径"}), 400
    if ".." in rel:
        return jsonify({"ok": False, "error": "非法路径"}), 400

    out = run_script(rel, params)
    return jsonify({"ok": True, "tool": rel, "result": out})


if __name__ == "__main__":
    ensure_dotenv_env()
    print("主页（内容管理） http://127.0.0.1:8765/  ·  脚本控制台 http://127.0.0.1:8765/console  ·  Token: " + str(DOTENV_PATH.resolve()))
    app.run(host="0.0.0.0", port=8765, debug=False)
