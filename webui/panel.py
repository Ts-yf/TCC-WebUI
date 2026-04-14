"""内容管理向导式面板 API：均通过 run_script 调用现有脚本。"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import Any

from flask import Blueprint, jsonify, request

from webui.runner import run_script

bp = Blueprint("panel", __name__)


def _extract_payload(j: dict | None) -> tuple[Any, str | None]:
    if not j:
        return None, "脚本无 JSON 输出"
    if j.get("success") is True:
        return j.get("data"), None
    if j.get("success") is False:
        return None, j.get("error") or "业务失败"
    if j.get("code") == 0:
        return j.get("data"), None
    if j.get("code") is not None:
        return None, j.get("msg") or str(j.get("code"))
    return j, None


def _run(rel: str, params: dict[str, Any]) -> dict[str, Any]:
    out = run_script(rel, params)
    j = out.get("json")
    data, err = _extract_payload(j if isinstance(j, dict) else None)
    rc = out.get("returncode")
    if err is None and rc not in (0, None):
        err = (out.get("stderr") or "").strip() or f"进程退出码 {rc}"
    if err is None and data is None and not j:
        err = (out.get("stderr") or "").strip() or "无 JSON 输出"
    return {
        "script": rel,
        "returncode": rc,
        "stderr": out.get("stderr"),
        "parse_error": out.get("parse_error"),
        "data": data,
        "error": err,
        "raw_json": j,
    }


_GID_RE = re.compile(r"^\d{1,32}$")


def _check_gid(gid: str) -> bool:
    return bool(gid and _GID_RE.match(gid))


@bp.get("/api/panel/my-guilds")
def api_my_guilds():
    r = _run("scripts/manage/read/get_my_join_guild_info.py", {})
    if r["error"]:
        return jsonify({"ok": False, **r}), 400
    d = r["data"] if isinstance(r["data"], dict) else {}
    flat: list[dict[str, Any]] = []
    for bucket, label in (
        ("created_guilds", "我创建的"),
        ("managed_guilds", "我管理的"),
        ("joined_guilds", "我加入的"),
    ):
        for g in d.get(bucket) or []:
            if not isinstance(g, dict):
                continue
            gid = _guild_id_from_item(g)
            if not gid:
                continue
            inner = _guild_inner(g)
            name = _guild_name(inner)
            role = inner.get("role") or ""
            flat.append(
                {
                    "guild_id": gid,
                    "name": name or f"频道 {gid}",
                    "bucket": bucket,
                    "bucket_label": label,
                    "role": role,
                    "share_url": inner.get("share_url") or "",
                }
            )
    return jsonify(
        {
            "ok": True,
            "guilds": flat,
            "summary": {
                "total_count": d.get("total_count"),
                "created_guilds_count": d.get("created_guilds_count"),
                "managed_guilds_count": d.get("managed_guilds_count"),
                "joined_guilds_count": d.get("joined_guilds_count"),
            },
            "raw": r,
        }
    )


def _guild_id_from_item(guild: dict) -> str:
    inner = guild
    for k in ("msgGuildInfo", "msg_guild_info", "guildInfo", "guild_info"):
        if isinstance(guild.get(k), dict):
            inner = guild[k]
            break
    return str(
        guild.get("uint64GuildId")
        or guild.get("uint64_guild_id")
        or inner.get("uint64GuildId")
        or inner.get("uint64_guild_id")
        or ""
    )


def _guild_inner(guild: dict) -> dict:
    for k in ("msgGuildInfo", "msg_guild_info", "guildInfo", "guild_info"):
        if isinstance(guild.get(k), dict):
            return guild[k]
    return guild


def _guild_name(inner: dict) -> str:
    for k in ("bytesGuildName", "bytes_guild_name", "guildName", "guild_name", "name"):
        v = inner.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


@bp.get("/api/panel/guild/<guild_id>/channels")
def api_guild_channels(guild_id: str):
    if not _check_gid(guild_id):
        return jsonify({"ok": False, "error": "无效的 guild_id"}), 400
    r = _run("scripts/manage/read/get_guild_channel_list.py", {"guild_id": guild_id})
    if r["error"]:
        return jsonify({"ok": False, **r}), 400
    return jsonify({"ok": True, **r})


@bp.get("/api/panel/guild/<guild_id>/home-feeds")
def api_home_feeds(guild_id: str):
    if not _check_gid(guild_id):
        return jsonify({"ok": False, "error": "无效的 guild_id"}), 400
    get_type = int(request.args.get("get_type") or 2)
    params: dict[str, Any] = {"guild_id": guild_id, "get_type": get_type, "count": int(request.args.get("count") or 20)}
    if request.args.get("sort_option"):
        params["sort_option"] = int(request.args["sort_option"])
    if request.args.get("feed_attach_info"):
        params["feed_attach_info"] = request.args["feed_attach_info"]
    r = _run("scripts/feed/read/get_guild_feeds.py", params)
    if r["error"]:
        return jsonify({"ok": False, **r}), 400
    return jsonify({"ok": True, **r})


@bp.get("/api/panel/guild/<guild_id>/channel/<channel_id>/feeds")
def api_channel_feeds(guild_id: str, channel_id: str):
    if not _check_gid(guild_id) or not _check_gid(channel_id):
        return jsonify({"ok": False, "error": "无效的 id"}), 400
    params: dict[str, Any] = {
        "guild_id": guild_id,
        "channel_id": channel_id,
        "count": int(request.args.get("count") or 20),
    }
    if request.args.get("sort_option"):
        params["sort_option"] = int(request.args["sort_option"])
    if request.args.get("feed_attch_info"):
        params["feed_attch_info"] = request.args["feed_attch_info"]
    r = _run("scripts/feed/read/get_channel_timeline_feeds.py", params)
    if r["error"]:
        return jsonify({"ok": False, **r}), 400
    return jsonify({"ok": True, **r})


@bp.get("/api/panel/feed/detail")
def api_feed_detail():
    guild_id = (request.args.get("guild_id") or "").strip()
    feed_id = (request.args.get("feed_id") or "").strip()
    if not feed_id:
        return jsonify({"ok": False, "error": "缺少 feed_id"}), 400
    params: dict[str, Any] = {"feed_id": feed_id}
    if guild_id:
        params["guild_id"] = guild_id
    if request.args.get("channel_id"):
        params["channel_id"] = request.args["channel_id"]
    if request.args.get("author_id"):
        params["author_id"] = request.args["author_id"]
    if request.args.get("create_time"):
        params["create_time"] = request.args["create_time"]
    r = _run("scripts/feed/read/get_feed_detail.py", params)
    if r["error"]:
        return jsonify({"ok": False, **r}), 400
    return jsonify({"ok": True, **r})


@bp.get("/api/panel/feed/comments")
def api_feed_comments():
    feed_id = (request.args.get("feed_id") or "").strip()
    if not feed_id:
        return jsonify({"ok": False, "error": "缺少 feed_id"}), 400
    params: dict[str, Any] = {"feed_id": feed_id}
    if request.args.get("guild_id"):
        params["guild_id"] = request.args["guild_id"]
    if request.args.get("channel_id"):
        params["channel_id"] = request.args["channel_id"]
    if request.args.get("page_size"):
        params["page_size"] = int(request.args["page_size"])
    if request.args.get("rank_type"):
        params["rank_type"] = int(request.args["rank_type"])
    if request.args.get("attach_info"):
        params["attach_info"] = request.args["attach_info"]
    r = _run("scripts/feed/read/get_feed_comments.py", params)
    if r["error"]:
        return jsonify({"ok": False, **r}), 400
    return jsonify({"ok": True, **r})


@bp.post("/api/panel/feed/comment")
def api_feed_comment():
    body = request.get_json(silent=True) or {}
    r = _run("scripts/feed/write/do_comment.py", body)
    if r["error"]:
        return jsonify({"ok": False, **r}), 400
    return jsonify({"ok": True, **r})


@bp.post("/api/panel/feed/prefer")
def api_feed_prefer():
    body = request.get_json(silent=True) or {}
    r = _run("scripts/feed/write/do_feed_prefer.py", body)
    if r["error"]:
        return jsonify({"ok": False, **r}), 400
    return jsonify({"ok": True, **r})


@bp.post("/api/panel/feed/like")
def api_feed_like():
    body = request.get_json(silent=True) or {}
    r = _run("scripts/feed/write/do_like.py", body)
    if r["error"]:
        return jsonify({"ok": False, **r}), 400
    return jsonify({"ok": True, **r})


@bp.post("/api/panel/feed/publish")
def api_feed_publish():
    body = request.get_json(silent=True) or {}
    r = _run("scripts/feed/write/publish_feed.py", body)
    if r["error"]:
        return jsonify({"ok": False, **r}), 400
    return jsonify({"ok": True, **r})


@bp.post("/api/panel/feed/delete")
def api_feed_delete():
    """删除帖子 del_feed（需 guild_id、channel_id、feed_id、create_time）。"""
    body = request.get_json(silent=True) or {}
    r = _run("scripts/feed/write/del_feed.py", body)
    if r["error"]:
        return jsonify({"ok": False, **r}), 400
    return jsonify({"ok": True, **r})


@bp.post("/api/panel/feed/alter")
def api_feed_alter():
    """修改帖子 alter_feed（需 guild_id、channel_id、feed_id、create_time、feed_type）。"""
    body = request.get_json(silent=True) or {}
    r = _run("scripts/feed/write/alter_feed.py", body)
    if r["error"]:
        return jsonify({"ok": False, **r}), 400
    return jsonify({"ok": True, **r})


# ── manage-guild：搜索 / 解析链接 / 加入 ─────────────────────────────


@bp.post("/api/panel/search-content")
def api_search_content():
    body = request.get_json(silent=True) or {}
    r = _run("scripts/manage/read/search_guild_content.py", body)
    if r["error"]:
        return jsonify({"ok": False, **r}), 400
    return jsonify({"ok": True, **r})


@bp.post("/api/panel/share-info")
def api_share_info():
    body = request.get_json(silent=True) or {}
    r = _run("scripts/manage/read/get_share_info.py", body)
    if r["error"]:
        return jsonify({"ok": False, **r}), 400
    return jsonify({"ok": True, **r})


@bp.post("/api/panel/join-guild")
def api_join_guild():
    body = request.get_json(silent=True) or {}
    r = _run("scripts/manage/write/join_guild.py", body)
    if r["error"]:
        return jsonify({"ok": False, **r}), 400
    return jsonify({"ok": True, **r})


@bp.get("/api/panel/guild/<guild_id>/join-setting")
def api_join_setting(guild_id: str):
    if not _check_gid(guild_id):
        return jsonify({"ok": False, "error": "无效的 guild_id"}), 400
    r = _run("scripts/manage/read/get_join_guild_setting.py", {"guild_id": guild_id})
    if r["error"]:
        return jsonify({"ok": False, **r}), 400
    return jsonify({"ok": True, **r})


# ── manage-member ────────────────────────────────────────────────────


@bp.get("/api/panel/guild/<guild_id>/members")
def api_guild_members(guild_id: str):
    if not _check_gid(guild_id):
        return jsonify({"ok": False, "error": "无效的 guild_id"}), 400
    params: dict[str, Any] = {"guild_id": guild_id}
    tok = (request.args.get("next_page_token") or "").strip()
    if tok:
        params["next_page_token"] = tok
    r = _run("scripts/manage/read/get_guild_member_list.py", params)
    if r["error"]:
        return jsonify({"ok": False, **r}), 400
    return jsonify({"ok": True, **r})


@bp.post("/api/panel/member/search")
def api_member_search():
    body = request.get_json(silent=True) or {}
    r = _run("scripts/manage/read/guild_member_search.py", body)
    if r["error"]:
        return jsonify({"ok": False, **r}), 400
    return jsonify({"ok": True, **r})


@bp.post("/api/panel/member/kick")
def api_member_kick():
    body = request.get_json(silent=True) or {}
    r = _run("scripts/manage/write/kick_guild_member.py", body)
    if r["error"]:
        return jsonify({"ok": False, **r}), 400
    return jsonify({"ok": True, **r})


@bp.post("/api/panel/member/shutup")
def api_member_shutup():
    body = request.get_json(silent=True) or {}
    r = _run("scripts/manage/write/modify_member_shut_up.py", body)
    if r["error"]:
        return jsonify({"ok": False, **r}), 400
    return jsonify({"ok": True, **r})


# ── feed：频道内搜帖 ────────────────────────────────────────────────


@bp.post("/api/panel/guild-feeds/search")
def api_guild_feeds_search():
    body = request.get_json(silent=True) or {}
    r = _run("scripts/feed/read/search_guild_feeds.py", body)
    if r["error"]:
        return jsonify({"ok": False, **r}), 400
    return jsonify({"ok": True, **r})


# ── 媒体：评论图上传 / 发帖 multipart ─────────────────────────────


@bp.post("/api/panel/comment/upload-image")
def api_comment_upload_image():
    guild_id = (request.form.get("guild_id") or "").strip()
    channel_id = (request.form.get("channel_id") or "").strip()
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"ok": False, "error": "缺少图片文件"}), 400
    if not guild_id or not channel_id:
        return jsonify({"ok": False, "error": "缺少 guild_id 或 channel_id"}), 400
    td = Path(tempfile.mkdtemp(prefix="tcc_cmtimg_"))
    dest = td / f.filename
    f.save(str(dest))
    from webui.panel_media import upload_comment_images  # noqa: WPS433

    imgs, err = upload_comment_images(guild_id, channel_id, [str(dest.resolve())])
    if err:
        return jsonify({"ok": False, "error": err}), 400
    return jsonify({"ok": True, "images": imgs})


@bp.post("/api/panel/feed/publish-media")
def api_publish_media():
    """发帖：支持多图（image_0…）与视频（video_0…）及可选封面 video_cover_0…"""
    guild_id = (request.form.get("guild_id") or "").strip()
    channel_id = (request.form.get("channel_id") or "").strip()
    feed_type = int(request.form.get("feed_type") or 1)
    title = (request.form.get("title") or "").strip()
    content = (request.form.get("content") or "").strip()
    on_upload_error = (request.form.get("on_upload_error") or "abort").strip()
    is_markdown = request.form.get("is_markdown", "true").lower() == "true"

    params: dict[str, Any] = {
        "guild_id": guild_id,
        "channel_id": channel_id,
        "feed_type": feed_type,
        "content": content,
        "on_upload_error": on_upload_error,
        "is_markdown": is_markdown,
    }
    if title:
        params["title"] = title

    file_paths: list[str] = []
    for key in sorted(request.files.keys()):
        if not key.startswith("image_"):
            continue
        f = request.files[key]
        if not f or not f.filename:
            continue
        td = Path(tempfile.mkdtemp(prefix="tcc_pubimg_"))
        dest = td / f.filename
        f.save(str(dest))
        file_paths.append(str(dest.resolve()))

    video_paths: list[dict[str, Any]] = []
    for key in sorted(request.files.keys()):
        if key.startswith("video_cover_"):
            continue
        if not key.startswith("video_"):
            continue
        f = request.files[key]
        if not f or not f.filename:
            continue
        suffix = key.replace("video_", "", 1)
        td = Path(tempfile.mkdtemp(prefix="tcc_pubvid_"))
        dest = td / f.filename
        f.save(str(dest))
        entry: dict[str, Any] = {"file_path": str(dest.resolve())}
        ck = f"video_cover_{suffix}"
        if ck in request.files:
            cf = request.files[ck]
            if cf and cf.filename:
                ctd = Path(tempfile.mkdtemp(prefix="tcc_pubcov_"))
                cdest = ctd / cf.filename
                cf.save(str(cdest))
                entry["cover_path"] = str(cdest.resolve())
        video_paths.append(entry)

    if file_paths:
        params["file_paths"] = file_paths
    if video_paths:
        params["video_paths"] = video_paths

    r = _run("scripts/feed/write/publish_feed.py", params)
    if r["error"]:
        return jsonify({"ok": False, **r}), 400
    return jsonify({"ok": True, **r})
