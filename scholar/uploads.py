"""Files uploaded from the dashboard: saved into documents/ and registered in the profile.

Only common document formats are accepted, and the file's first bytes must match its
extension, so a renamed executable or a mislabelled file is refused.
"""
from __future__ import annotations

import base64
import binascii
import os
import re
from pathlib import Path
from typing import Any

from . import profile as prof, store

MAX_BYTES = 15 * 1024 * 1024
# Extension -> required leading bytes (None = plain text, checked separately).
ALLOWED: dict[str, bytes | None] = {
    ".pdf": b"%PDF",
    ".docx": b"PK\x03\x04",
    ".png": b"\x89PNG",
    ".jpg": b"\xff\xd8\xff",
    ".jpeg": b"\xff\xd8\xff",
    ".txt": None,
    ".md": None,
}
_BAD_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}


def _fail(message: str, **extra: Any) -> dict[str, Any]:
    return {"ok": False, "error": message, **extra}


def clean_name(name: str) -> str | None:
    """A safe file name inside documents/: no folders, no characters Windows forbids."""
    base = Path(str(name).replace("\\", "/")).name
    base = _BAD_CHARS.sub("_", base).strip().strip(".")
    stem, ext = os.path.splitext(base)
    stem = stem.strip()
    if not stem or stem.lower() in _RESERVED:
        return None
    return stem[:120] + ext.lower()


def save(filename: str, data_b64: str, doc_type: str, label: str | None = None,
         replace: bool = False) -> dict[str, Any]:
    name = clean_name(filename or "")
    if not name:
        return _fail("That file name can't be used. Rename the file and try again.")
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED:
        return _fail("Only PDF, Word (.docx), PNG/JPG images and text files can be uploaded. "
                     "Save other formats (e.g. .doc) as PDF first.")
    if doc_type not in prof.DOC_TYPES:
        return _fail(f"Pick a document type ({', '.join(prof.DOC_TYPES)}).")
    label = (label or "").strip() or None
    if label and prof.sensitive_reason(label):
        return _fail("The label looks like it contains a sensitive number; use a plain description.")
    try:
        raw = base64.b64decode(data_b64 or "", validate=True)
    except (binascii.Error, ValueError):
        return _fail("The file didn't arrive intact. Try again.")
    if not raw:
        return _fail("The file is empty.")
    if len(raw) > MAX_BYTES:
        return _fail(f"The file is larger than {MAX_BYTES // (1024 * 1024)} MB.")
    magic = ALLOWED[ext]
    if magic is not None and not raw.startswith(magic):
        return _fail(f"This doesn't look like a real {ext} file.")
    if magic is None:
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError:
            return _fail("Text files must be UTF-8.")

    folder = store.documents_dir()
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / name
    existed = target.exists()
    if existed and not replace:
        return _fail(f"A file named '{name}' is already in your documents. Replace it?", exists=True, name=name)
    part = target.with_name(target.name + ".part")
    part.write_bytes(raw)
    os.replace(part, target)

    profile = prof.load()
    result = prof.doc_add(profile, doc_type, str(target), label)
    if not result.get("ok"):
        return result
    prof.save(profile)
    return {"ok": True, "document": result["document"], "replaced": existed, "note": result.get("note")}


def listing(profile: dict[str, Any], changed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Registered documents for the dashboard, with whether the writer has read them."""
    status = {d["path"]: d["status"] for d in changed}
    out = []
    for doc in profile["lists"].get("documents", []):
        out.append({
            "id": doc.get("id"),
            "name": Path(doc.get("path", "")).name,
            "path": doc.get("path"),
            "type": doc.get("type"),
            "label": doc.get("label"),
            "size": doc.get("size"),
            "added": doc.get("added"),
            "status": status.get(doc.get("path"), "read"),
        })
    return out
