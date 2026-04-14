"""OpenAI function tools → 调用 scripts/feed/write 脚本。"""

from __future__ import annotations

import json
from typing import Any

from webui.runner import run_script

SCRIPT_TIMEOUT = 360

# OpenAI Chat Completions `tools` 格式
OPENAI_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "tcc_feed_prefer",
            "description": (
                "给帖子点赞或取消点赞（对应 Skill do_feed_prefer）。"
                "action=1 点赞，action=3 取消点赞。"
                "feed_id、guild_id、channel_id 须与上下文缓存中的帖子一致。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "feed_id": {"type": "string", "description": "帖子 ID"},
                    "action": {"type": "integer", "description": "1=点赞，3=取消点赞"},
                    "guild_id": {"type": "string", "description": "频道 ID"},
                    "channel_id": {"type": "string", "description": "子频道 ID"},
                },
                "required": ["feed_id", "action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tcc_feed_comment",
            "description": (
                "对帖子发表顶层评论（对应 Skill do_comment，comment_type=1）。"
                "feed_create_time 必须为缓存中该帖的 create_time_raw（秒级时间戳字符串）。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "feed_id": {"type": "string"},
                    "feed_create_time": {"type": "string", "description": "秒级时间戳字符串"},
                    "content": {"type": "string", "description": "评论正文"},
                    "guild_id": {"type": "string"},
                    "channel_id": {"type": "string"},
                },
                "required": ["feed_id", "feed_create_time", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tcc_publish_feed",
            "description": (
                "在指定子频道发表新帖（对应 Skill publish_feed）。"
                "feed_type=1 短贴无标题；feed_type=2 长贴必须带 title。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "guild_id": {"type": "string"},
                    "channel_id": {"type": "string"},
                    "content": {"type": "string"},
                    "feed_type": {"type": "integer", "description": "1=短贴 2=长贴"},
                    "title": {"type": "string", "description": "长贴标题"},
                },
                "required": ["guild_id", "channel_id", "content", "feed_type"],
            },
        },
    },
]


def _script_result_summary(script_out: dict[str, Any]) -> dict[str, Any]:
    j = script_out.get("json")
    rc = script_out.get("returncode")
    err = (script_out.get("stderr") or "").strip()
    if isinstance(j, dict):
        return {"returncode": rc, "json": j, "stderr": err or None}
    return {"returncode": rc, "json": j, "stderr": err or None, "parse_error": script_out.get("parse_error")}


def execute_skill_tool(name: str, arguments: str | dict[str, Any] | None) -> str:
    """执行工具，返回给模型看的 JSON 字符串。"""
    if isinstance(arguments, str):
        try:
            args = json.loads(arguments or "{}")
        except json.JSONDecodeError as exc:
            return json.dumps({"success": False, "error": f"参数 JSON 无效: {exc}"}, ensure_ascii=False)
    else:
        args = dict(arguments or {})

    try:
        if name == "tcc_feed_prefer":
            params: dict[str, Any] = {
                "feed_id": str(args["feed_id"]),
                "action": int(args["action"]),
            }
            if args.get("guild_id"):
                params["guild_id"] = str(args["guild_id"])
            if args.get("channel_id"):
                params["channel_id"] = str(args["channel_id"])
            out = run_script("scripts/feed/write/do_feed_prefer.py", params, timeout=SCRIPT_TIMEOUT)
            return json.dumps(_script_result_summary(out), ensure_ascii=False)

        if name == "tcc_feed_comment":
            params = {
                "feed_id": str(args["feed_id"]),
                "feed_create_time": str(args["feed_create_time"]),
                "comment_type": 1,
                "content": str(args.get("content") or ""),
            }
            if args.get("guild_id"):
                params["guild_id"] = str(args["guild_id"])
            if args.get("channel_id"):
                params["channel_id"] = str(args["channel_id"])
            out = run_script("scripts/feed/write/do_comment.py", params, timeout=SCRIPT_TIMEOUT)
            return json.dumps(_script_result_summary(out), ensure_ascii=False)

        if name == "tcc_publish_feed":
            params = {
                "guild_id": str(args["guild_id"]),
                "channel_id": str(args["channel_id"]),
                "content": str(args.get("content") or ""),
                "feed_type": int(args.get("feed_type") or 1),
            }
            if params["feed_type"] == 2:
                params["title"] = str(args.get("title") or "").strip() or "无标题"
            out = run_script("scripts/feed/write/publish_feed.py", params, timeout=SCRIPT_TIMEOUT)
            return json.dumps(_script_result_summary(out), ensure_ascii=False)
    except KeyError as exc:
        return json.dumps({"success": False, "error": f"缺少参数: {exc}"}, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False)

    return json.dumps({"success": False, "error": f"未知工具: {name}"}, ensure_ascii=False)
