"""Document checker: formats, sizes, page limits and expiries, before anything is uploaded.

Upload rules come from portal recon (application.upload_rules). Without them, each
required document type is checked for existence and basic sanity.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import drafts, opportunity as opp, profile as prof, store


def pdf_pages(path: Path) -> tuple[int | None, bool]:
    """(page count, approximate?)"""
    try:
        from pypdf import PdfReader  # optional dependency
        return len(PdfReader(str(path)).pages), False
    except ImportError:
        data = path.read_bytes()
        count = len(re.findall(rb"/Type\s*/Page(?![s\w])", data))
        return (count or None), True
    except Exception:
        return None, True


def _pick(profile: dict[str, Any], doc_type: str, cv_path: str | None) -> dict[str, Any] | None:
    docs = [d for d in profile["lists"].get("documents", []) if d.get("type") == doc_type]
    if doc_type == "cv" and cv_path:
        chosen = next((d for d in docs if d["path"] == cv_path), None)
        if chosen:
            return chosen
    return max(docs, key=lambda d: d.get("added") or "", default=None)


def result_path(opp_id: str) -> Path:
    path = store.data_dir() / "doccheck"
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{opp_id}.json"


def check(opp_id: str) -> dict[str, Any]:
    items = opp.load_all()
    rec = opp.find(items, opp_id)
    if not rec:
        return {"ok": False, "error": f"no opportunity '{opp_id}'"}
    profile = prof.load()
    app = rec.get("application", {})
    rules = app.get("upload_rules") or [{"slot": t, "type": t} for t in app.get("documents", [])]
    cv_choice = (drafts.status(rec["id"]).get("cv_choice") or {}).get("path")
    deadline = store.parse_date(rec.get("deadline", {}).get("date"))

    rows, errors, warnings, chosen = [], [], [], []
    for rule in rules:
        doc_type = rule.get("type") or "other"
        slot = rule.get("slot") or doc_type
        row: dict[str, Any] = {"slot": slot, "type": doc_type, "required": rule.get("required", True)}
        if doc_type in prof.HANDOFF_DOC_TYPES:
            row["status"] = "you_upload"
            row["note"] = "Identity document: you upload this yourself."
            rows.append(row)
            continue
        doc = _pick(profile, doc_type, cv_choice)
        if not doc:
            row["status"] = "missing"
            (errors if row["required"] else warnings).append(f"{slot}: no '{doc_type}' document registered")
            rows.append(row)
            continue
        file = store.resolve_path(doc["path"])
        row.update({"path": doc["path"], "label": doc.get("label")})
        if not file.exists():
            row["status"] = "missing"
            errors.append(f"{slot}: file not found on disk ({doc['path']})")
            rows.append(row)
            continue
        sha = store.file_sha256(file)
        chosen.append([doc["path"], sha])
        problems = []
        if sha != doc.get("sha256"):
            warnings.append(f"{slot}: file changed since it was registered; re-run 'profile doc-add' "
                            "and /ingest so the writer sees the new version")
        ext = file.suffix.lower().lstrip(".")
        formats = [f.lower().lstrip(".") for f in rule.get("formats") or []]
        if formats and ext not in formats:
            problems.append(f"format .{ext} not accepted (allowed: {', '.join(formats)})")
        size_mb = round(file.stat().st_size / 1_048_576, 2)
        row["size_mb"] = size_mb
        if rule.get("max_mb") and size_mb > float(rule["max_mb"]):
            problems.append(f"{size_mb} MB is over the {rule['max_mb']} MB limit")
        if ext == "pdf":
            with file.open("rb") as handle:
                if handle.read(5) != b"%PDF-":
                    problems.append("not a valid PDF file")
            pages, approx = pdf_pages(file)
            row["pages"] = pages
            row["pages_approximate"] = approx
            if rule.get("max_pages") and pages and pages > int(rule["max_pages"]):
                problems.append(f"{pages} pages is over the {rule['max_pages']}-page limit")
        elif not formats:
            warnings.append(f"{slot}: .{ext} file; most portals want PDF")
        row["status"] = "problem" if problems else "ok"
        if problems:
            row["problems"] = problems
            errors.extend(f"{slot}: {p}" for p in problems)
        rows.append(row)

    for test in profile["lists"].get("tests", []):
        expires = store.parse_date(test.get("expires"))
        if expires and deadline and expires < deadline:
            warnings.append(f"{test['exam']} result expires {expires.isoformat()}, before the deadline")

    result = {"ok": not errors, "opp_id": rec["id"], "items": rows, "errors": errors,
              "warnings": warnings, "checked_at": store.now_iso(),
              "docs_hash": store.canonical_hash({"docs": chosen, "rules": rules})}
    store.save_json(result_path(rec["id"]), result)
    return result


def last(opp_id: str) -> dict[str, Any] | None:
    return store.load_json(result_path(opp_id), None)


def current_docs_hash(opp_id: str) -> str | None:
    """Recompute what check() would hash now, without saving, to detect changes after a check."""
    previous = last(opp_id)
    if not previous:
        return None
    chosen = []
    for item in previous["items"]:
        if item.get("path"):
            file = store.resolve_path(item["path"])
            if file.exists():
                chosen.append([item["path"], store.file_sha256(file)])
    rec = opp.find(opp.load_all(), opp_id) or {}
    app = rec.get("application", {})
    rules = app.get("upload_rules") or [{"slot": t, "type": t} for t in app.get("documents", [])]
    return store.canonical_hash({"docs": chosen, "rules": rules})


def merge(inputs: list[str], output: str) -> dict[str, Any]:
    try:
        from pypdf import PdfWriter
    except ImportError:
        return {"ok": False, "error": "merging needs pypdf: run  python -m pip install pypdf"}
    writer = PdfWriter()
    for item in inputs:
        file = Path(item)
        if not file.is_file():
            return {"ok": False, "error": f"not found: {item}"}
        writer.append(str(file))
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as handle:
        writer.write(handle)
    return {"ok": True, "output": str(out), "pages": pdf_pages(out)[0]}
