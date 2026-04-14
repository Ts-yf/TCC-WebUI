"""供面板上传评论图：复用 scripts/feed/write/_upload_util._upload_file_paths。"""

from __future__ import annotations

import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
FEED_WRITE = SKILL_ROOT / "scripts" / "feed" / "write"


def upload_comment_images(guild_id: str, channel_id: str, local_paths: list[str]) -> tuple[list[dict], str | None]:
    """
    上传本地图片，转换为 do_comment 的 images[] 结构。
    返回 (images_list, error_message)。
    """
    if not local_paths:
        return [], None
    sys.path.insert(0, str(FEED_WRITE))
    try:
        from _upload_util import _upload_file_paths  # noqa: E402
    except ImportError as exc:
        return [], f"无法加载上传模块: {exc}"

    try:
        gi = int(str(guild_id).strip())
        ci = int(str(channel_id).strip())
    except (TypeError, ValueError):
        return [], "guild_id / channel_id 必须为整数"

    entries = [{"file_path": p} for p in local_paths]
    uploaded, err = _upload_file_paths(entries, gi, ci, "abort")
    if err:
        return [], str(err)
    out: list[dict] = []
    for d in uploaded:
        if not isinstance(d, dict):
            continue
        tid = str(d.get("task_id") or d.get("md5") or "")
        url = str(d.get("url") or "")
        if not url:
            return [], "上传成功但未解析到图片 CDN URL"
        out.append(
            {
                "picId": tid,
                "picUrl": url,
                "imageMD5": str(d.get("md5") or ""),
                "width": int(d.get("width") or 0),
                "height": int(d.get("height") or 0),
                "orig_size": int(d.get("orig_size") or 0),
                "is_orig": True,
                "is_gif": False,
            }
        )
    return out, None
