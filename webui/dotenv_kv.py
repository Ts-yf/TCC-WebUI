"""读写项目根目录 .env 中的键值（与 QQ token 写入方式一致，不破坏其它行）。"""

from __future__ import annotations

from pathlib import Path


def read_dotenv_value(path: Path, key: str) -> str | None:
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("export "):
            s = s[7:].strip()
        val = None
        for sep in (f"{key}=", f"{key} ="):
            if s.startswith(sep):
                val = s[len(sep) :].strip()
                break
        if val is None:
            continue
        if val.startswith('"') and val.endswith('"') and len(val) >= 2:
            inner = val[1:-1]
            val = inner.replace("\\\\", "\\").replace('\\"', '"')
        elif val.startswith("'") and val.endswith("'") and len(val) >= 2:
            val = val[1:-1]
        val = val.strip()
        return val or None
    return None


def write_dotenv_value(path: Path, key: str, value: str) -> None:
    if "\n" in value or "\r" in value:
        raise ValueError(f"{key} 不能包含换行符")
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    new_line = f'{key}="{escaped}"'
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if path.is_file():
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise OSError(f"读取 {path} 失败: {exc}") from exc
    out: list[str] = []
    replaced = False
    for line in lines:
        s = line.strip()
        if not s:
            out.append(line)
            continue
        if s.startswith("#"):
            out.append(line)
            continue
        t = s
        if t.startswith("export "):
            t = t[7:].strip()
        if t.startswith(f"{key}=") or t.startswith(f"{key} ="):
            if not replaced:
                out.append(new_line)
                replaced = True
            continue
        out.append(line)
    if not replaced:
        if out and out[-1].strip():
            out.append("")
        out.append(new_line)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def remove_dotenv_key(path: Path, key: str) -> None:
    if not path.is_file():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    out: list[str] = []
    for line in lines:
        s = line.strip()
        t = s[7:].strip() if s.startswith("export ") else s
        if t.startswith(f"{key}=") or t.startswith(f"{key} ="):
            continue
        out.append(line)
    path.write_text("\n".join(out) + ("\n" if out else ""), encoding="utf-8")
