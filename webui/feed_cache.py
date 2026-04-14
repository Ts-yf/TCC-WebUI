"""频道帖子时间线 + 评论摘要本地缓存，供自动化任务快速拼 prompt。"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from webui.paths import SKILL_ROOT
from webui.runner import run_script

CACHE_DIR = SKILL_ROOT / ".tcc_feed_cache"
SCRIPT_TIMEOUT = 360


def _extract_feed_payload(j: Any) -> dict[str, Any] | None:
    if not isinstance(j, dict):
        return None
    if j.get("success") is True and isinstance(j.get("data"), dict):
        return j["data"]
    if j.get("code") == 0 and isinstance(j.get("data"), dict):
        return j["data"]
    return None


def cache_path_for(guild_id: str, channel_id: str) -> Path:
    return CACHE_DIR / f"{guild_id}_{channel_id}.json"


def load_feed_cache(guild_id: str, channel_id: str) -> dict[str, Any] | None:
    p = cache_path_for(guild_id, channel_id)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _summarize_comments_for_prompt(comments: list[dict[str, Any]], limit: int = 8) -> list[str]:
    lines: list[str] = []
    for c in comments[:limit]:
        if not isinstance(c, dict):
            continue
        cid = c.get("comment_id") or ""
        body = c.get("content")
        if isinstance(body, dict):
            text = str(body.get("text") or body)[:200]
        else:
            text = str(body or "")[:200]
        lines.append(
            f"  - comment_id={cid} author={c.get('author') or ''} "
            f"likes={c.get('like_count', 0)} text={text}"
        )
        reps = c.get("replies_preview") or []
        if isinstance(reps, list) and reps:
            for r in reps[:2]:
                if not isinstance(r, dict):
                    continue
                lines.append(
                    f"    · reply_id={r.get('reply_id') or ''} author={r.get('author') or ''} "
                    f"{str(r.get('content') or '')[:120]}"
                )
    return lines


def format_cache_snapshot_for_prompt(snapshot: dict[str, Any]) -> str:
    feeds = snapshot.get("feeds") or []
    if not isinstance(feeds, list):
        return "（缓存无 feeds）"
    blocks: list[str] = []
    for i, f in enumerate(feeds, 1):
        if not isinstance(f, dict):
            continue
        fid = f.get("feed_id") or ""
        title = f.get("title") or ""
        snip = f.get("content_snippet") or ""
        author = f.get("author") or ""
        aid = f.get("author_id") or ""
        ct = f.get("create_time") or ""
        ctr = f.get("create_time_raw")
        pc = f.get("prefer_count", f.get("comment_count"))
        cc = f.get("comment_count")
        head = (
            f"[{i}] feed_id={fid}\n"
            f"    title={str(title)[:200]}\n"
            f"    author={author} author_id={aid}\n"
            f"    create_time={ct} create_time_raw={ctr}\n"
            f"    prefer_count={pc} comment_count={cc}\n"
            f"    snippet={str(snip)[:500]}"
        )
        cmt = f.get("_cached_comments") or []
        if isinstance(cmt, list) and cmt:
            head += "\n    comments_preview:\n" + "\n".join(_summarize_comments_for_prompt(cmt))
        blocks.append(head)
    if not blocks:
        return "（缓存中暂无帖子）"
    meta = f"guild_id={snapshot.get('guild_id')} channel_id={snapshot.get('channel_id')} " f"captured={snapshot.get('fetched_at_iso') or ''}\n\n"
    return meta + "\n\n".join(blocks)


def refresh_feed_cache(
    guild_id: str,
    channel_id: str,
    count: int,
    *,
    comments_for_top_n: int = 3,
    comment_page_size: int = 10,
) -> tuple[dict[str, Any] | None, str | None]:
    """拉取时间线；对前 N 条帖子拉一页评论写入缓存文件。返回 (snapshot, error)。"""
    out = run_script(
        "scripts/feed/read/get_channel_timeline_feeds.py",
        {"guild_id": guild_id, "channel_id": channel_id, "count": count},
        timeout=SCRIPT_TIMEOUT,
    )
    j = out.get("json")
    data = _extract_feed_payload(j)
    if data is None:
        err = (out.get("stderr") or "").strip() or "拉取帖子失败"
        if isinstance(j, dict) and j.get("error"):
            err = str(j.get("error"))
        return None, err
    feeds = data.get("feeds") or []
    if not isinstance(feeds, list):
        feeds = []
    n = max(0, min(int(comments_for_top_n), len(feeds)))
    for idx in range(n):
        feed = feeds[idx]
        if not isinstance(feed, dict):
            continue
        feed_dict = feed
        fid = str(feed_dict.get("feed_id") or "").strip()
        if not fid:
            continue
        cout = run_script(
            "scripts/feed/read/get_feed_comments.py",
            {
                "feed_id": fid,
                "guild_id": guild_id,
                "channel_id": channel_id,
                "page_size": min(max(1, int(comment_page_size)), 20),
                "reply_list_num": 3,
                "rank_type": 2,
            },
            timeout=SCRIPT_TIMEOUT,
        )
        cj = cout.get("json")
        cdata = _extract_feed_payload(cj)
        if cdata and isinstance(cdata.get("comments"), list):
            feed_dict["_cached_comments"] = cdata["comments"]
        else:
            feed_dict["_cached_comments"] = []
            feed_dict["_cached_comments_error"] = (
                (cout.get("stderr") or "").strip()
                or (isinstance(cj, dict) and cj.get("error"))
                or "comments_fetch_failed"
            )

    snapshot: dict[str, Any] = {
        "guild_id": guild_id,
        "channel_id": channel_id,
        "fetched_at": time.time(),
        "fetched_at_iso": datetime.now().isoformat(timespec="seconds"),
        "feeds": feeds,
        "feed_attch_info": data.get("feed_attch_info"),
        "is_finish": data.get("is_finish"),
    }
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    dest = cache_path_for(guild_id, channel_id)
    try:
        dest.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        return None, f"写入缓存失败: {exc}"
    return snapshot, None
