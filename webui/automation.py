"""OpenAI .env 配置与定时任务 API。"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from webui.dotenv_kv import read_dotenv_value, remove_dotenv_key, write_dotenv_value
from webui.openai_client import chat_completion, normalize_openai_base_url
from webui.paths import DOTENV_PATH, ensure_dotenv_env
from webui.scheduler_service import (
    OPENAI_BASE_ENV,
    OPENAI_KEY_ENV,
    OPENAI_MODEL_ENV,
    SKILL_CONTEXT_AUTOMATION_ZH,
    append_log,
    get_openai_settings,
    replace_jobs,
    run_openai_task,
    snapshot_jobs,
    snapshot_logs,
    start_scheduler,
)

bp = Blueprint("automation", __name__, url_prefix="")


def _mask_key(key: str | None) -> dict[str, object]:
    if not key:
        return {"configured": False, "hint": ""}
    tail = key[-4:] if len(key) >= 4 else "****"
    return {"configured": True, "hint": f"…{tail}"}


@bp.get("/api/automation/openai")
def api_openai_get():
    ensure_dotenv_env()
    path = DOTENV_PATH
    key = read_dotenv_value(path, OPENAI_KEY_ENV)
    base = read_dotenv_value(path, OPENAI_BASE_ENV) or ""
    model = read_dotenv_value(path, OPENAI_MODEL_ENV) or "gpt-4o-mini"
    return jsonify(
        {
            "ok": True,
            "dotenvPath": str(path.resolve()),
            "baseUrl": base or "https://api.openai.com/v1",
            "model": model,
            **_mask_key(key),
        }
    )


@bp.post("/api/automation/openai")
def api_openai_post():
    ensure_dotenv_env()
    data = request.get_json(silent=True) or {}
    path = DOTENV_PATH
    api_key = (data.get("api_key") or "").strip()
    base_url = (data.get("base_url") or "").strip()
    model = (data.get("model") or "").strip()

    if api_key:
        write_dotenv_value(path, OPENAI_KEY_ENV, api_key)
    elif data.get("clear_api_key") is True:
        remove_dotenv_key(path, OPENAI_KEY_ENV)

    if base_url:
        write_dotenv_value(path, OPENAI_BASE_ENV, normalize_openai_base_url(base_url))
    if model:
        write_dotenv_value(path, OPENAI_MODEL_ENV, model)

    key = read_dotenv_value(path, OPENAI_KEY_ENV)
    return jsonify({"ok": True, **_mask_key(key)})


@bp.post("/api/automation/openai/test")
def api_openai_test():
    ensure_dotenv_env()
    data = request.get_json(silent=True) or {}
    msg = (data.get("message") or "回复 OK 即可。").strip()
    key, base, model = get_openai_settings()
    if not key:
        return jsonify({"ok": False, "error": "未配置 OPENAI_API_KEY"}), 400
    from webui.scheduler_service import SKILL_CONTEXT_ZH

    messages = [
        {"role": "system", "content": SKILL_CONTEXT_ZH},
        {"role": "user", "content": msg},
    ]
    parsed, err = chat_completion(api_key=key, base_url=base, model=model, messages=messages, timeout=600)
    if err:
        return jsonify({"ok": False, "error": err}), 400
    content = ""
    if isinstance(parsed, dict):
        ch = parsed.get("choices")
        if isinstance(ch, list) and ch:
            m = ch[0].get("message") or {}
            content = m.get("content") or ""
    return jsonify({"ok": True, "reply": content, "raw": parsed})


@bp.get("/api/automation/jobs")
def api_jobs_get():
    return jsonify({"ok": True, **snapshot_jobs()})


@bp.post("/api/automation/jobs")
def api_jobs_post():
    data = request.get_json(silent=True) or {}
    interval = data.get("interval_jobs") if isinstance(data.get("interval_jobs"), list) else []
    timed = data.get("timed_jobs") if isinstance(data.get("timed_jobs"), list) else []
    errs, _warn = replace_jobs(interval, timed)
    if errs:
        return jsonify({"ok": False, "errors": errs}), 400
    start_scheduler()
    return jsonify({"ok": True, **snapshot_jobs()})


@bp.get("/api/automation/logs")
def api_logs():
    lim = int(request.args.get("limit") or 80)
    return jsonify({"ok": True, "lines": snapshot_logs(min(lim, 200))})


@bp.post("/api/automation/jobs/run-once")
def api_run_once():
    """先写入本地缓存（时间线+评论），再携带缓存与提示词调用模型；可选自动执行工具。"""
    from webui.automation_agent import run_automation_agent_loop
    from webui.feed_cache import (
        cache_path_for,
        format_cache_snapshot_for_prompt,
        load_feed_cache,
        refresh_feed_cache,
    )

    ensure_dotenv_env()
    data = request.get_json(silent=True) or {}
    gid = str(data.get("guild_id") or "").strip()
    cid = str(data.get("channel_id") or "").strip()
    prompt = str(data.get("prompt") or "").strip()
    count = int(data.get("feed_count") or 10)
    refresh_cache = data.get("refresh_cache", True)
    execute_tools = data.get("execute_tools", True)
    comments_top_n = int(data.get("comments_for_top_n") or 3)
    if not gid.isdigit() or not cid.isdigit():
        return jsonify({"ok": False, "error": "guild_id / channel_id 须为数字"}), 400
    count = max(1, min(50, count))
    comments_top_n = max(0, min(10, comments_top_n))

    if refresh_cache:
        snap, ferr = refresh_feed_cache(
            gid,
            cid,
            count,
            comments_for_top_n=comments_top_n,
        )
        if ferr:
            return jsonify({"ok": False, "error": ferr}), 400
    else:
        snap = load_feed_cache(gid, cid)
        if not snap:
            return jsonify(
                {
                    "ok": False,
                    "error": "无本地缓存，请将 refresh_cache 设为 true 先拉取，或先跑一次间隔任务。",
                }
            ), 400

    blob = format_cache_snapshot_for_prompt(snap)
    user_body = (
        f"频道 guild_id={gid} 子频道 channel_id={cid}。\n"
        f"以下为本地缓存的帖子与评论摘要：\n\n{blob}\n\n"
        f"【用户自定义任务】\n{prompt or '（无）'}"
    )

    if execute_tools:
        res, oerr = run_automation_agent_loop(
            user_content=user_body,
            system_content=SKILL_CONTEXT_AUTOMATION_ZH,
            use_tools=True,
        )
        if oerr:
            return jsonify({"ok": False, "error": oerr}), 400
        append_log("INFO", "run-once OK (tools)")
        return jsonify(
            {
                "ok": True,
                "cachePath": str(cache_path_for(gid, cid)),
                "cachedAt": snap.get("fetched_at_iso"),
                "feeds_preview": blob[:4000],
                "reply": (res or {}).get("final_content"),
                "tool_trace": (res or {}).get("tool_trace") or [],
            }
        )

    reply, oerr = run_openai_task(user_content=user_body, user_system_extra="")
    if oerr:
        return jsonify({"ok": False, "error": oerr}), 400
    append_log("INFO", "run-once OK (no tools)")
    return jsonify(
        {
            "ok": True,
            "cachePath": str(cache_path_for(gid, cid)),
            "cachedAt": snap.get("fetched_at_iso"),
            "feeds_preview": blob[:4000],
            "reply": reply,
            "tool_trace": [],
        }
    )
