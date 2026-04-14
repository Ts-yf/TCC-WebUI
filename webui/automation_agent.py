"""带 function calling 的自动化对话：解析 tool_calls 并执行 Skill 脚本。"""

from __future__ import annotations

import json
from typing import Any

from webui.openai_client import chat_completion
from webui.scheduler_service import get_openai_settings
from webui.skill_tooling import OPENAI_TOOL_DEFINITIONS, execute_skill_tool

MAX_TOOL_ROUNDS = 12


def _assistant_message_for_history(msg: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"role": "assistant"}
    if "content" in msg:
        out["content"] = msg.get("content")
    if msg.get("tool_calls"):
        out["tool_calls"] = msg["tool_calls"]
    return out


def run_automation_agent_loop(
    *,
    user_content: str,
    system_content: str,
    use_tools: bool = True,
    max_rounds: int = MAX_TOOL_ROUNDS,
) -> tuple[dict[str, Any] | None, str | None]:
    """
    返回 (result, error)。
    result: final_content, tool_trace(list), messages 长度摘要
    """
    key, base, model = get_openai_settings()
    if not key:
        return None, "未配置 OPENAI_API_KEY（请在本页写入项目根目录 .env）"

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]
    tools = OPENAI_TOOL_DEFINITIONS if use_tools else None
    tool_trace: list[dict[str, Any]] = []

    for _ in range(max_rounds):
        parsed, err = chat_completion(
            api_key=key,
            base_url=base,
            model=model,
            messages=messages,
            tools=tools,
            tool_choice="auto" if tools else None,
        )
        if err:
            return None, err
        if not isinstance(parsed, dict):
            return None, "模型响应格式异常"

        choices = parsed.get("choices")
        if not isinstance(choices, list) or not choices:
            return None, "模型未返回 choices"

        choice0 = choices[0]
        msg = choice0.get("message")
        if not isinstance(msg, dict):
            return None, "模型未返回 message"

        messages.append(_assistant_message_for_history(msg))

        tool_calls = msg.get("tool_calls")
        if tool_calls and isinstance(tool_calls, list):
            for tc in tool_calls:
                if not isinstance(tc, dict):
                    continue
                tid = tc.get("id") or ""
                fn = tc.get("function") or {}
                fname = (fn.get("name") or "") if isinstance(fn, dict) else ""
                fargs = fn.get("arguments") if isinstance(fn, dict) else ""
                raw_result = execute_skill_tool(fname, fargs)
                tool_trace.append(
                    {
                        "name": fname,
                        "arguments": fargs if isinstance(fargs, str) else json.dumps(fargs, ensure_ascii=False),
                        "result_preview": raw_result[:1500],
                    }
                )
                messages.append({"role": "tool", "tool_call_id": tid, "content": raw_result})
            continue

        content = msg.get("content")
        if isinstance(content, str) and content.strip():
            return {
                "final_content": content.strip(),
                "tool_trace": tool_trace,
                "rounds_used": len(tool_trace) + 1,
            }, None

        finish = choice0.get("finish_reason")
        if finish == "stop":
            return {
                "final_content": (content or "").strip() if isinstance(content, str) else "",
                "tool_trace": tool_trace,
                "rounds_used": len(tool_trace) + 1,
            }, None

        return None, f"模型未返回可解析内容（finish_reason={finish!r}）"

    return None, f"超过工具调用轮次上限（{max_rounds}）"
