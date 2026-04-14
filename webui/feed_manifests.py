"""加载 feed 目录下各脚本的 SKILL_MANIFEST（用于表单生成）。"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from .paths import SKILL_ROOT

# 与 SKILL.md / 仓库中脚本一致；顺序即 UI 分组展示顺序
FEED_SCRIPT_PATHS: list[tuple[str, str]] = [
    ("feed-read", "scripts/feed/read/get_guild_feeds.py"),
    ("feed-read", "scripts/feed/read/get_channel_timeline_feeds.py"),
    ("feed-read", "scripts/feed/read/get_feed_detail.py"),
    ("feed-read", "scripts/feed/read/get_feed_comments.py"),
    ("feed-read", "scripts/feed/read/get_next_page_replies.py"),
    ("feed-read", "scripts/feed/read/search_guild_feeds.py"),
    ("feed-read", "scripts/feed/read/get_feed_share_url.py"),
    ("feed-read", "scripts/feed/read/get_notices.py"),
    ("feed-write", "scripts/feed/write/publish_feed.py"),
    ("feed-write", "scripts/feed/write/alter_feed.py"),
    ("feed-write", "scripts/feed/write/del_feed.py"),
    ("feed-write", "scripts/feed/write/do_comment.py"),
    ("feed-write", "scripts/feed/write/do_reply.py"),
    ("feed-write", "scripts/feed/write/do_like.py"),
    ("feed-write", "scripts/feed/write/do_feed_prefer.py"),
    ("feed-write", "scripts/feed/write/upload_image.py"),
    ("feed-op", "scripts/feed/operation/channel_qa_responder.py"),
    ("feed-op", "scripts/feed/operation/auto_clean_channel_feeds.py"),
]


def _load_module(rel: str):
    path = SKILL_ROOT / rel
    name = "feed_" + rel.replace("/", "_").replace(".py", "").replace("\\", "_")
    # 与「python path/to/script.py」一致：脚本所在目录在 sys.path 中（write 下脚本依赖 _feed_common 等）
    script_dir = str(path.resolve().parent)
    inserted = False
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
        inserted = True
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"无法加载: {path}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        if inserted and sys.path and sys.path[0] == script_dir:
            sys.path.pop(0)


def load_feed_tools() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for category, rel in FEED_SCRIPT_PATHS:
        try:
            mod = _load_module(rel)
            manifest = getattr(mod, "SKILL_MANIFEST", None)
            if not isinstance(manifest, dict):
                continue
            out.append(
                {
                    "kind": "feed",
                    "id": rel,
                    "category": category,
                    "manifest": manifest,
                }
            )
        except Exception as exc:  # noqa: BLE001 — 展示用，收集错误
            out.append(
                {
                    "kind": "feed",
                    "id": rel,
                    "category": category,
                    "load_error": str(exc),
                }
            )
    return out
