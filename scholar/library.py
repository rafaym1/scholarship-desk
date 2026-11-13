"""The writer's library: CV cards, fact bank, writing-voice sample and approved answers.

Claude builds these once from your documents (/ingest) so later applications reuse a
compact library instead of re-reading every PDF.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import profile as prof, store


def lib_dir() -> Path:
    path = store.data_dir() / "library"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _load(name: str, key: str) -> list[dict[str, Any]]:
    return (store.load_json(lib_dir() / name, {}) or {}).get(key, [])


def _save(name: str, key: str, rows: list[dict[str, Any]]) -> None:
    store.save_json(lib_dir() / name, {key: rows})


def cv_cards() -> list[dict[str, Any]]:
    return _load("cv_cards.json", "cards")


def facts() -> list[dict[str, Any]]:
    return _load("facts.json", "facts")


def answers() -> list[dict[str, Any]]:
    return _load("answers.json", "answers")


def voice() -> str:
    path = lib_dir() / "voice.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def changed_documents(profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Registered documents that are new or edited since the last /ingest."""
    ingested = store.load_json(lib_dir() / "ingested.json", {}) or {}
    out = []
    for doc in profile["lists"].get("documents", []):
        file = store.resolve_path(doc["path"])
        if not file.exists():
            out.append({"path": doc["path"], "type": doc["type"], "status": "missing_on_disk"})
            continue
        sha = store.file_sha256(file)
        if doc["path"] not in ingested:
            out.append({"path": doc["path"], "type": doc["type"], "status": "new"})
        elif ingested[doc["path"]] != sha:
            out.append({"path": doc["path"], "type": doc["type"], "status": "changed"})
    return out


def mark_ingested(paths: list[str]) -> dict[str, Any]:
    ingested = store.load_json(lib_dir() / "ingested.json", {}) or {}
    done = []
    for stored in paths:
        file = store.resolve_path(stored)
        if file.exists():
            ingested[stored] = store.file_sha256(file)
            done.append(stored)
    store.save_json(lib_dir() / "ingested.json", ingested)
    return {"ok": True, "marked": done}


def add_cv_cards(cards: list[dict[str, Any]], profile: dict[str, Any]) -> dict[str, Any]:
    registered = {d["path"]: d for d in profile["lists"].get("documents", []) if d.get("type") == "cv"}
    existing = {c["path"]: c for c in cv_cards()}
    errors = []
    for card in cards:
        stored = card.get("path")
        if stored not in registered:
            errors.append(f"{stored}: not a registered CV (use 'profile doc-add cv PATH' first)")
            continue
        if not card.get("summary") or not card.get("focus"):
            errors.append(f"{stored}: a CV card needs 'summary' and 'focus'")
            continue
        existing[stored] = {
            "path": stored, "label": registered[stored].get("label"),
            "sha256": registered[stored].get("sha256"),
            "focus": list(card.get("focus", [])),            # e.g. research, industry, leadership
            "pages": card.get("pages"),
            "format": card.get("format"),                   # e.g. academic, europass, 2-page
            "strengths": list(card.get("strengths", [])),
            "best_for": list(card.get("best_for", [])),     # e.g. phd_position, leadership scholarships
            "summary": str(card["summary"]),
            "updated": store.now_iso(),
        }
    _save("cv_cards.json", "cards", list(existing.values()))
    return {"ok": not errors, "errors": errors, "cards": len(existing)}


def _norm(text: str) -> str:
    return re.sub(r"\W+", " ", text.casefold()).strip()


def add_facts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    bank = facts()
    seen = {_norm(f["text"]) for f in bank}
    next_id = max([int(f["id"][1:]) for f in bank if f.get("id", "f0")[1:].isdigit()] + [0]) + 1
    added, errors = [], []
    for row in rows:
        text = str(row.get("text", "")).strip()
        source = str(row.get("source", "")).strip()
        if not text or not source:
            errors.append(f"fact needs 'text' and 'source': {text[:60]}")
            continue
        reason = prof.sensitive_reason(text)
        if reason:
            errors.append(f"fact not saved ({reason})")
            continue
        if _norm(text) in seen:
            continue
        fact = {"id": f"f{next_id}", "text": text, "source": source,
                "tags": list(row.get("tags", [])), "date": row.get("date"),
                "category": row.get("category")}
        bank.append(fact)
        seen.add(_norm(text))
        added.append(fact["id"])
        next_id += 1
    _save("facts.json", "facts", bank)
    return {"ok": not errors, "added": added, "errors": errors, "total": len(bank)}


def remove_fact(fact_id: str) -> dict[str, Any]:
    bank = facts()
    kept = [f for f in bank if f["id"] != fact_id]
    _save("facts.json", "facts", kept)
    return {"ok": len(kept) != len(bank), "removed": fact_id}


def save_voice(text: str) -> dict[str, Any]:
    (lib_dir() / "voice.md").write_text(text, encoding="utf-8")
    return {"ok": True, "characters": len(text)}


def record_answer(entry: dict[str, Any]) -> None:
    rows = answers()
    rows = [r for r in rows if not (r.get("opp_id") == entry["opp_id"] and r.get("qid") == entry["qid"])]
    rows.append(entry)
    _save("answers.json", "answers", rows)


def summary(profile: dict[str, Any]) -> dict[str, Any]:
    return {"cv_cards": len(cv_cards()), "facts": len(facts()), "approved_answers": len(answers()),
            "voice_sample": bool(voice()), "documents_needing_ingest": changed_documents(profile)}
