"""Per-application brief, CV choice and answer drafts, with deterministic checks.

Claude writes drafts; you approve or edit them in the dashboard. The apply agent only
ever pastes approved text.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import library, opportunity as opp, profile as prof, store


SAFE_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,99}")


def _dir(opp_id: str) -> Path:
    # Opportunity ids are slugs (see opportunity.make_id); anything else could point outside data/drafts.
    if not isinstance(opp_id, str) or not SAFE_ID.fullmatch(opp_id):
        raise ValueError("bad opportunity id")
    path = store.data_dir() / "drafts" / opp_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def brief(opp_id: str) -> dict[str, Any] | None:
    return store.load_json(_dir(opp_id) / "brief.json", None)


def answers(opp_id: str) -> dict[str, Any]:
    return store.load_json(_dir(opp_id) / "answers.json", {}) or {}


def count_words(text: str) -> int:
    return len(re.findall(r"\b\w[\w'’-]*\b", text))


def set_brief(opp_id: str, data: dict[str, Any]) -> dict[str, Any]:
    items = opp.load_all()
    rec = opp.find(items, opp_id)
    if not rec:
        return {"ok": False, "error": f"no opportunity '{opp_id}'"}
    errors: list[str] = []
    questions = data.get("questions") or rec.get("application", {}).get("questions") or []
    questions = opp._validate_questions(questions, errors)
    cv = data.get("cv_choice")
    if cv is not None:
        profile = prof.load()
        cvs = {d["path"] for d in profile["lists"]["documents"] if d.get("type") == "cv"}
        if cv.get("path") not in cvs:
            errors.append("cv_choice.path must be one of your registered CVs")
        if not cv.get("reason"):
            errors.append("cv_choice.reason is required (one line on why this CV fits)")
    if errors:
        return {"ok": False, "errors": errors}
    out = {
        "opp_id": rec["id"],
        "questions": questions,
        "criteria": list(data.get("criteria", [])),
        "cv_choice": cv,
        "ai_policy": data.get("ai_policy"),
        "notes": data.get("notes"),
        "updated": store.now_iso(),
    }
    store.save_json(_dir(rec["id"]) / "brief.json", out)
    return {"ok": True, "opp_id": rec["id"], "questions": len(questions)}


def check_text(text: str, question: dict[str, Any], rec: dict[str, Any],
               others: list[dict[str, Any]]) -> dict[str, Any]:
    words = count_words(text)
    chars = len(text)
    limit = question.get("limit")
    unit = question.get("unit", "words")
    used = words if unit == "words" else chars
    over = bool(limit) and used > limit
    own = f"{rec.get('title', '')} {rec.get('sponsor', '')}".casefold()
    foreign = []
    for other in others:
        for name in (other.get("title", ""), other.get("sponsor", "")):
            if len(name) >= 6 and name.casefold() not in own and name.casefold() in text.casefold():
                foreign.append(name)
    placeholders = re.findall(r"\[(?:insert|todo|tbd|name|x+)[^\]]*\]|\bTODO\b|\bXXX\b", text, re.I)
    sensitive = prof.sensitive_reason(text)
    return {"words": words, "characters": chars, "limit": limit, "unit": unit, "over_limit": over,
            "other_scholarship_names": sorted(set(foreign)), "placeholders": placeholders,
            "sensitive": sensitive, "empty": not text.strip()}


def _blocking(checks: dict[str, Any]) -> list[str]:
    problems = []
    if checks["empty"]:
        problems.append("answer is empty")
    if checks["over_limit"]:
        problems.append(f"over the limit ({checks['words'] if checks['unit'] == 'words' else checks['characters']}"
                        f"/{checks['limit']} {checks['unit']})")
    if checks["placeholders"]:
        problems.append(f"placeholder text left in: {checks['placeholders']}")
    if checks["sensitive"]:
        problems.append(f"contains sensitive data ({checks['sensitive']})")
    return problems


def _question(opp_id: str, qid: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str | None]:
    b = brief(opp_id)
    if not b:
        return None, None, "no brief yet: run /tailor first"
    question = next((q for q in b["questions"] if q["qid"] == qid), None)
    if not question:
        return b, None, f"no question '{qid}' in the brief"
    return b, question, None


def put_answer(opp_id: str, qid: str, text: str, sources: list[str] | None = None,
               by: str = "claude") -> dict[str, Any]:
    items = opp.load_all()
    rec = opp.find(items, opp_id)
    if not rec:
        return {"ok": False, "error": f"no opportunity '{opp_id}'"}
    _, question, error = _question(rec["id"], qid)
    if error:
        return {"ok": False, "error": error}
    known = {f["id"] for f in library.facts()}
    unknown = [s for s in (sources or []) if s not in known]
    if unknown:
        return {"ok": False, "error": f"unknown fact ids: {unknown}"}
    others = [r for k, r in items.items() if k != rec["id"]]
    checks = check_text(text, question, rec, others)
    data = answers(rec["id"])
    data[qid] = {"text": text, "sources": sources or [], "status": "draft", "checks": checks,
                 "by": by, "updated": store.now_iso(), "feedback": data.get(qid, {}).get("feedback")}
    store.save_json(_dir(rec["id"]) / "answers.json", data)
    return {"ok": True, "qid": qid, "checks": checks, "blocking": _blocking(checks)}


def approve(opp_id: str, qid: str, edited_text: str | None = None) -> dict[str, Any]:
    items = opp.load_all()
    rec = opp.find(items, opp_id)
    if not rec:
        return {"ok": False, "error": f"no opportunity '{opp_id}'"}
    b, question, error = _question(rec["id"], qid)
    if error:
        return {"ok": False, "error": error}
    data = answers(rec["id"])
    entry = data.get(qid)
    if edited_text is not None:
        entry = {"text": edited_text, "sources": (entry or {}).get("sources", []), "by": "you"}
    if not entry:
        return {"ok": False, "error": "nothing drafted for this question yet"}
    others = [r for k, r in items.items() if k != rec["id"]]
    checks = check_text(entry["text"], question, rec, others)
    problems = _blocking(checks)
    if problems:
        return {"ok": False, "error": "cannot approve: " + "; ".join(problems), "checks": checks}
    entry.update({"status": "approved", "checks": checks, "approved_hash": store.text_hash(entry["text"]),
                  "approved_at": store.now_iso(), "updated": store.now_iso()})
    data[qid] = entry
    store.save_json(_dir(rec["id"]) / "answers.json", data)
    library.record_answer({"opp_id": rec["id"], "qid": qid, "prompt": question["prompt"],
                           "category": question.get("category"), "text": entry["text"],
                           "words": checks["words"], "approved_at": entry["approved_at"],
                           "cv": (b.get("cv_choice") or {}).get("path")})
    return {"ok": True, "qid": qid, "warnings": checks["other_scholarship_names"]}


def request_changes(opp_id: str, qid: str, feedback: str) -> dict[str, Any]:
    data = answers(opp_id)
    if qid not in data:
        return {"ok": False, "error": "nothing drafted for this question yet"}
    data[qid]["status"] = "changes_requested"
    data[qid]["feedback"] = feedback[:2000]
    data[qid]["updated"] = store.now_iso()
    store.save_json(_dir(opp_id) / "answers.json", data)
    return {"ok": True, "qid": qid}


def status(opp_id: str) -> dict[str, Any]:
    b = brief(opp_id)
    data = answers(opp_id)
    if not b:
        return {"has_brief": False, "total": 0, "approved": 0, "all_approved": False,
                "changes_requested": 0, "cv_choice": None}
    total = len([q for q in b["questions"] if q.get("required", True)])
    approved = 0
    for q in b["questions"]:
        entry = data.get(q["qid"])
        if entry and entry.get("status") == "approved" and \
                entry.get("approved_hash") == store.text_hash(entry.get("text", "")):
            approved += int(q.get("required", True))
    return {
        "has_brief": True, "total": total, "approved": approved,
        "all_approved": approved >= total,
        "changes_requested": sum(1 for e in data.values() if e.get("status") == "changes_requested"),
        "cv_choice": b.get("cv_choice"),
    }


def full(opp_id: str) -> dict[str, Any]:
    return {"brief": brief(opp_id), "answers": answers(opp_id), "status": status(opp_id)}


def approved_hashes(opp_id: str) -> dict[str, str]:
    return {qid: e["approved_hash"] for qid, e in answers(opp_id).items() if e.get("status") == "approved"}
