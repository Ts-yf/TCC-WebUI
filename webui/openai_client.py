"""OpenAI 兼容 Chat Completions（urllib，无额外依赖）。"""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from typing import Any


def normalize_openai_base_url(raw: str) -> str:
    u = (raw or "").strip().rstrip("/")
    if not u:
        return "https://api.openai.com/v1"
    if not u.endswith("/v1"):
        u = f"{u}/v1"
    return u


def chat_completion(
    *,
    api_key: str,
    base_url: str,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    tool_choice: Any | None = None,
    timeout: int = 600,
) -> tuple[Any | None, str | None]:
    """返回 (parsed_json, error_message)。支持 tools + tool_choice。"""
    url = normalize_openai_base_url(base_url) + "/chat/completions"
    body_obj: dict[str, Any] = {"model": model, "messages": messages}
    if tools:
        body_obj["tools"] = tools
        body_obj["tool_choice"] = "auto" if tool_choice is None else tool_choice
    body = json.dumps(body_obj, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except OSError:
            detail = str(exc)
        return None, f"HTTP {exc.code}: {detail[:2000]}"
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)
    try:
        return json.loads(raw), None
    except json.JSONDecodeError:
        return None, "响应不是合法 JSON"
