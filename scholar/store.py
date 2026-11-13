"""Local storage helpers.

Everything personal lives under data/, documents/ and submitted/ (all git-ignored).
Set SCHOLAR_HOME to point the whole app at another folder (tests do this).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


def home() -> Path:
    override = os.environ.get("SCHOLAR_HOME")
    return Path(override) if override else ROOT


def _dir(name: str) -> Path:
    path = home() / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def data_dir() -> Path:
    return _dir("data")


def documents_dir() -> Path:
    return _dir("documents")


def submitted_dir() -> Path:
    return _dir("submitted")


def playbooks_dir() -> Path:
    return _dir("playbooks")


def data_file(name: str) -> Path:
    return data_dir() / name


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def now_iso() -> str:
    return now_utc().isoformat()


def today() -> date:
    return datetime.now().date()


def load_json(path: Path, default: Any = None) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return default
    if not text.strip():
        return default
    return json.loads(text)


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, indent=1, ensure_ascii=False, sort_keys=True) + "\n"
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    try:
        os.chmod(path, 0o600)  # best effort; meaningful on POSIX
    except OSError:
        pass


def canonical_hash(value: Any) -> str:
    blob = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def slug(text: str, limit: int = 48) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")
    return cleaned[:limit].strip("-") or "item"


def parse_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return None


def relative_to_home(path: Path) -> str:
    """Store paths relative to the project when possible so a copy keeps working."""
    try:
        return path.resolve().relative_to(home().resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def resolve_path(stored: str) -> Path:
    path = Path(stored)
    return path if path.is_absolute() else home() / path
