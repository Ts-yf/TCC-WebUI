"""定时拉取频道帖子并调用 OpenAI；定时提示词任务。状态持久化在项目根 JSON。"""

from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from webui.dotenv_kv import read_dotenv_value
from webui.feed_cache import format_cache_snapshot_for_prompt, refresh_feed_cache
from webui.openai_client import chat_completion, normalize_openai_base_url
from webui.paths import DOTENV_PATH, SKILL_ROOT
from webui.runner import run_script

JOBS_FILE = SKILL_ROOT / ".tcc_webui_jobs.json"
LOG_MAX = 300

OPENAI_KEY_ENV = "OPENAI_API_KEY"
OPENAI_BASE_ENV = "OPENAI_BASE_URL"
OPENAI_MODEL_ENV = "OPENAI_MODEL"

SKILL_CONTEXT_AUTOMATION_ZH = (
    "【腾讯频道自动化 · 托管模式】\n"
    "- QQ AI Connect 鉴权 token 在项目根目录 .env 的 QQ_AI_CONNECT_TOKEN；严禁在回复中输出 token。\n"
    "- 你已获授权：无需人工逐条审批，宿主程序会根据你的 function calling 立即执行本仓库 Skill 脚本，并把工具返回的 JSON 原样回传给你。\n"
    "- 若任务涉及帖子点赞、评论或发帖，必须调用工具完成；禁止仅用自然语言让用户去 Web 里手动操作（除非上下文明示缺少 feed_id、create_time_raw 等必填字段）。\n"
    "- 工具说明：tcc_feed_prefer = 帖子点赞/取消赞（action 1/3）；tcc_feed_comment = 对帖发表顶层评论；tcc_publish_feed = 在子频道发新帖。\n"
    "- 参数须与提供的缓存数据一致：feed_id、create_time_raw、guild_id、channel_id、author_id 等一律从缓存摘录，勿编造。\n"
)

# 兼容旧 import 名（OpenAI 测试接口等）
SKILL_CONTEXT_ZH = SKILL_CONTEXT_AUTOMATION_ZH


@dataclass
class IntervalJob:
    id: str
    enabled: bool
    guild_id: str
    channel_id: str
    interval_seconds: int
    prompt: str
    feed_count: int = 15
    last_run_at: float | None = None
    last_error: str | None = None

    def to_json(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    @staticmethod
    def from_json(d: dict[str, Any]) -> IntervalJob:
        return IntervalJob(
            id=str(d.get("id") or uuid.uuid4()),
            enabled=bool(d.get("enabled", True)),
            guild_id=str(d.get("guild_id") or "").strip(),
            channel_id=str(d.get("channel_id") or "").strip(),
            interval_seconds=max(30, int(d.get("interval_seconds") or 300)),
            prompt=str(d.get("prompt") or ""),
            feed_count=max(1, min(50, int(d.get("feed_count") or 15))),
            last_run_at=float(d["last_run_at"]) if d.get("last_run_at") is not None else None,
            last_error=(str(d["last_error"]) if d.get("last_error") else None),
        )


@dataclass
class TimedJob:
    id: str
    enabled: bool
    time_hhmm: str
    prompt: str
    last_fired_day: str | None = None
    last_error: str | None = None

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_json(d: dict[str, Any]) -> TimedJob:
        return TimedJob(
            id=str(d.get("id") or uuid.uuid4()),
            enabled=bool(d.get("enabled", True)),
            time_hhmm=str(d.get("time_hhmm") or "09:00").strip(),
            prompt=str(d.get("prompt") or ""),
            last_fired_day=(str(d["last_fired_day"]) if d.get("last_fired_day") else None),
            last_error=(str(d["last_error"]) if d.get("last_error") else None),
        )


def _log_lines() -> list[str]:
    return _state.logs


def append_log(level: str, message: str) -> None:
    lines = _log_lines()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {message}"
    lines.append(line)
    while len(lines) > LOG_MAX:
        lines.pop(0)


class _State:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.interval_jobs: list[IntervalJob] = []
        self.timed_jobs: list[TimedJob] = []
        self.logs: list[str] = []
        self.thread: threading.Thread | None = None
        self.stop = threading.Event()


_state = _State()


def load_jobs_from_disk() -> None:
    if not JOBS_FILE.is_file():
        return
    try:
        raw = json.loads(JOBS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(raw, dict):
        return
    ij = [IntervalJob.from_json(x) for x in (raw.get("interval_jobs") or []) if isinstance(x, dict)]
    tj = [TimedJob.from_json(x) for x in (raw.get("timed_jobs") or []) if isinstance(x, dict)]
    with _state.lock:
        _state.interval_jobs = ij
        _state.timed_jobs = tj


def save_jobs_to_disk_unlocked() -> None:
    data = {
        "interval_jobs": [j.to_json() for j in _state.interval_jobs],
        "timed_jobs": [j.to_json() for j in _state.timed_jobs],
    }
    JOBS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def save_jobs_to_disk() -> None:
    with _state.lock:
        save_jobs_to_disk_unlocked()


def get_openai_settings() -> tuple[str | None, str, str]:
    path = DOTENV_PATH
    key = read_dotenv_value(path, OPENAI_KEY_ENV)
    base = read_dotenv_value(path, OPENAI_BASE_ENV) or "https://api.openai.com/v1"
    model = read_dotenv_value(path, OPENAI_MODEL_ENV) or "gpt-4o-mini"
    return key, normalize_openai_base_url(base), model


def _extract_feed_payload(j: Any) -> dict[str, Any] | None:
    if not isinstance(j, dict):
        return None
    if j.get("success") is True and isinstance(j.get("data"), dict):
        return j["data"]
    if j.get("code") == 0 and isinstance(j.get("data"), dict):
        return j["data"]
    return None


def fetch_channel_feeds_text(guild_id: str, channel_id: str, count: int) -> tuple[str | None, str | None]:
    out = run_script(
        "scripts/feed/read/get_channel_timeline_feeds.py",
        {"guild_id": guild_id, "channel_id": channel_id, "count": count},
        timeout=360,
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
        return "（无 feeds 列表）", None
    lines: list[str] = []
    for i, f in enumerate(feeds[:count], 1):
        if not isinstance(f, dict):
            continue
        fid = f.get("feed_id") or f.get("id") or f.get("uint64FeedId") or ""
        title = f.get("title") or f.get("bytesTitle") or ""
        summary = f.get("content_snippet") or f.get("summary") or f.get("content") or ""
        if isinstance(summary, dict):
            summary = json.dumps(summary, ensure_ascii=False)[:500]
        lines.append(f"{i}. feed_id={fid} title={str(title)[:200]} summary={str(summary)[:400]}")
    if not lines:
        return "（本页暂无帖子摘要）", None
    return "\n".join(lines), None


def _message_content(resp: Any) -> str:
    if not isinstance(resp, dict):
        return str(resp)
    ch = resp.get("choices")
    if isinstance(ch, list) and ch:
        msg = ch[0].get("message") or {}
        c = msg.get("content")
        if isinstance(c, str):
            return c
    return json.dumps(resp, ensure_ascii=False)[:4000]


def run_openai_task(*, user_content: str, user_system_extra: str) -> tuple[str | None, str | None]:
    key, base, model = get_openai_settings()
    if not key:
        return None, "未配置 OPENAI_API_KEY（请在本页写入项目根目录 .env）"
    system = SKILL_CONTEXT_ZH + "\n" + (user_system_extra.strip() or "请根据用户数据完成任务。")
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]
    parsed, err = chat_completion(
        api_key=key,
        base_url=base,
        model=model,
        messages=messages,
        timeout=600,
    )
    if err:
        return None, err
    return _message_content(parsed), None


def _tick_interval_job(job: IntervalJob) -> None:
    from webui.automation_agent import run_automation_agent_loop

    now = time.time()
    if job.last_run_at is not None and (now - job.last_run_at) < job.interval_seconds:
        return
    snap, err = refresh_feed_cache(
        job.guild_id,
        job.channel_id,
        job.feed_count,
        comments_for_top_n=3,
    )
    if err:
        job.last_error = err
        append_log("ERROR", f"interval {job.id}: {err}")
        job.last_run_at = now
        return
    blob = format_cache_snapshot_for_prompt(snap)
    user_body = (
        f"频道 guild_id={job.guild_id} 子频道 channel_id={job.channel_id}。\n"
        f"以下为本地缓存的帖子与评论摘要：\n\n{blob}\n\n"
        f"【用户自定义任务】\n{job.prompt.strip() or '（无）'}"
    )
    res, oerr = run_automation_agent_loop(
        user_content=user_body,
        system_content=SKILL_CONTEXT_AUTOMATION_ZH,
        use_tools=True,
    )
    if oerr:
        job.last_error = oerr
        append_log("ERROR", f"interval {job.id} OpenAI: {oerr[:500]}")
    else:
        job.last_error = None
        tail = (res or {}).get("final_content") or ""
        append_log("INFO", f"interval {job.id} OK: {tail[:300]}")
    job.last_run_at = now


def _tick_timed_job(job: TimedJob) -> None:
    from webui.automation_agent import run_automation_agent_loop

    raw = job.time_hhmm.strip()
    parts = raw.replace("：", ":").split(":")
    if len(parts) != 2:
        return
    try:
        h, m = int(parts[0]), int(parts[1])
    except ValueError:
        return
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    if now.hour != h or now.minute != m:
        return
    if job.last_fired_day == today:
        return
    job.last_fired_day = today
    user_body = job.prompt.strip() or "请根据系统说明执行今日定时任务。"
    res, oerr = run_automation_agent_loop(
        user_content=user_body,
        system_content=SKILL_CONTEXT_AUTOMATION_ZH,
        use_tools=True,
    )
    if oerr:
        job.last_error = oerr
        append_log("ERROR", f"timed {job.id}: {oerr[:500]}")
    else:
        job.last_error = None
        tail = (res or {}).get("final_content") or ""
        append_log("INFO", f"timed {job.id} OK: {tail[:300]}")


def _worker_loop() -> None:
    load_jobs_from_disk()
    append_log("INFO", "调度线程已启动")
    while not _state.stop.is_set():
        with _state.lock:
            ij = list(_state.interval_jobs)
            tj = list(_state.timed_jobs)
        for job in ij:
            if not job.enabled:
                continue
            if not job.guild_id or not job.channel_id:
                continue
            try:
                with _state.lock:
                    ref = next((x for x in _state.interval_jobs if x.id == job.id), None)
                if ref:
                    _tick_interval_job(ref)
            except Exception as exc:  # noqa: BLE001
                append_log("ERROR", f"interval {job.id} exception: {exc}")
        for job in tj:
            if not job.enabled:
                continue
            try:
                with _state.lock:
                    ref = next((x for x in _state.timed_jobs if x.id == job.id), None)
                if ref:
                    _tick_timed_job(ref)
            except Exception as exc:  # noqa: BLE001
                append_log("ERROR", f"timed {job.id} exception: {exc}")
        with _state.lock:
            save_jobs_to_disk_unlocked()
        for _ in range(10):
            if _state.stop.is_set():
                break
            time.sleep(1)


def start_scheduler() -> None:
    with _state.lock:
        if _state.thread and _state.thread.is_alive():
            return
        _state.stop.clear()
        _state.thread = threading.Thread(target=_worker_loop, name="tcc_webui_scheduler", daemon=True)
        _state.thread.start()


def stop_scheduler() -> None:
    _state.stop.set()


def replace_jobs(interval: list[dict[str, Any]], timed: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    """校验并替换内存中的任务；返回 (errors, warnings)。"""
    errors: list[str] = []
    ij: list[IntervalJob] = []
    tj: list[TimedJob] = []
    seen_i = set()
    seen_t = set()
    for d in interval:
        if not isinstance(d, dict):
            continue
        jid = str(d.get("id") or "").strip() or str(uuid.uuid4())
        if jid in seen_i:
            jid = str(uuid.uuid4())
        seen_i.add(jid)
        g = str(d.get("guild_id") or "").strip()
        c = str(d.get("channel_id") or "").strip()
        if not g.isdigit() or not c.isdigit():
            errors.append(f"间隔任务 {jid}: guild_id / channel_id 须为数字字符串")
            continue
        sec = int(d.get("interval_seconds") or 300)
        if sec < 30:
            errors.append(f"间隔任务 {jid}: interval_seconds 不得小于 30")
            continue
        lra = d.get("last_run_at")
        lra_f = float(lra) if lra is not None else None
        ij.append(
            IntervalJob(
                id=jid,
                enabled=bool(d.get("enabled", True)),
                guild_id=g,
                channel_id=c,
                interval_seconds=sec,
                prompt=str(d.get("prompt") or ""),
                feed_count=max(1, min(50, int(d.get("feed_count") or 15))),
                last_run_at=lra_f,
                last_error=(str(d["last_error"]) if d.get("last_error") else None),
            )
        )
    for d in timed:
        if not isinstance(d, dict):
            continue
        jid = str(d.get("id") or "").strip() or str(uuid.uuid4())
        if jid in seen_t:
            jid = str(uuid.uuid4())
        seen_t.add(jid)
        hm = str(d.get("time_hhmm") or "09:00").strip().replace("：", ":")
        ps = hm.split(":")
        if len(ps) != 2:
            errors.append(f"定时任务 {jid}: time_hhmm 须为 HH:MM")
            continue
        try:
            hh, mm = int(ps[0]), int(ps[1])
        except ValueError:
            errors.append(f"定时任务 {jid}: time_hhmm 非法")
            continue
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            errors.append(f"定时任务 {jid}: 时间超出范围")
            continue
        tj.append(
            TimedJob(
                id=jid,
                enabled=bool(d.get("enabled", True)),
                time_hhmm=f"{hh:02d}:{mm:02d}",
                prompt=str(d.get("prompt") or ""),
                last_fired_day=d.get("last_fired_day"),
                last_error=d.get("last_error"),
            )
        )
    if errors:
        return errors, []
    with _state.lock:
        _state.interval_jobs = ij
        _state.timed_jobs = tj
        save_jobs_to_disk_unlocked()
    return [], []


def snapshot_jobs() -> dict[str, Any]:
    with _state.lock:
        return {
            "interval_jobs": [j.to_json() for j in _state.interval_jobs],
            "timed_jobs": [j.to_json() for j in _state.timed_jobs],
        }


def snapshot_logs(limit: int = 80) -> list[str]:
    lines = _log_lines()
    return lines[-limit:] if limit else list(lines)
