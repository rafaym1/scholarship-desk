"""Application tracker and approval gates.

The order is enforced in code: readiness -> start -> (needs_you <-> applying) ->
review -> your submit approval (bound to the exact review) -> submitted -> outcome.
The agent must only run `approve-submit` after you said yes in chat.
"""
from __future__ import annotations

import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

from . import doccheck, drafts, opportunity as opp, profile as prof, store

STATUSES = ["found", "shortlisted", "preparing", "ready", "applying", "needs_you",
            "awaiting_submit_ok", "submitted", "manual", "dismissed"]
OUTCOMES = ["pending", "interview", "shortlisted", "offer_won", "waitlisted", "rejected", "withdrawn"]
ACTIVE = {"preparing", "ready", "applying", "needs_you", "awaiting_submit_ok"}


def path() -> Path:
    return store.data_file("tracker.json")


def load() -> dict[str, dict[str, Any]]:
    return (store.load_json(path(), {}) or {}).get("items", {})


def save(items: dict[str, dict[str, Any]]) -> None:
    store.save_json(path(), {"version": 1, "items": items})


def entry(items: dict[str, dict[str, Any]], opp_id: str) -> dict[str, Any]:
    return items.setdefault(opp_id, {"status": "found", "seen": False, "notes": "",
                                     "tasks_done": [], "history": [], "gate": {}})


def _log(item: dict[str, Any], event: str, detail: str = "") -> None:
    item["history"].append({"at": store.now_iso(), "event": event, "detail": detail[:300]})
    item["history"] = item["history"][-200:]


def _resolve(opp_id: str) -> tuple[dict[str, Any] | None, str | None]:
    rec = opp.find(opp.load_all(), opp_id)
    return (rec, None) if rec else (None, f"no opportunity '{opp_id}'")

# --------------------------------------------------------------- dashboard actions


def user_action(opp_id: str, action: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Actions the dashboard may perform. Submit approval is deliberately not one of them."""
    payload = payload or {}
    rec, error = _resolve(opp_id)
    if error:
        return {"ok": False, "error": error}
    items = load()
    item = entry(items, rec["id"])
    status = item["status"]
    if action == "seen":
        item["seen"] = True
    elif action == "shortlist":
        if status not in ("found", "dismissed"):
            return {"ok": False, "error": f"already {status}"}
        item["status"] = "shortlisted"
        _log(item, "shortlisted")
    elif action == "unshortlist":
        if status != "shortlisted":
            return {"ok": False, "error": f"status is {status}"}
        item["status"] = "found"
        _log(item, "unshortlisted")
    elif action == "dismiss":
        if status == "submitted":
            return {"ok": False, "error": "already submitted"}
        item["status"] = "dismissed"
        _log(item, "dismissed", str(payload.get("reason", "")))
    elif action == "restore":
        if status != "dismissed":
            return {"ok": False, "error": f"status is {status}"}
        item["status"] = "found"
        _log(item, "restored")
    elif action == "applied_myself":
        if status == "submitted":
            return {"ok": False, "error": "already submitted"}
        item["status"] = "submitted"
        item["submitted_at"] = store.now_iso()
        item["submitted_by"] = "you"
        item["confirmation"] = str(payload.get("confirmation", ""))[:200]
        item.setdefault("outcome", {"result": "pending"})
        _log(item, "submitted_by_you", item["confirmation"])
    elif action == "outcome":
        result = payload.get("result")
        if result not in OUTCOMES:
            return {"ok": False, "error": f"result must be one of {OUTCOMES}"}
        if status != "submitted":
            return {"ok": False, "error": "record an outcome only after submitting"}
        item["outcome"] = {"result": result, "date": store.now_iso()[:10],
                           "note": str(payload.get("note", ""))[:1000]}
        _log(item, "outcome", result)
    elif action == "note":
        note = str(payload.get("note", ""))[:5000]
        reason = prof.sensitive_reason(note)
        if reason:
            return {"ok": False, "error": f"not saved: {reason}"}
        item["notes"] = note
    elif action == "task":
        key = str(payload.get("key", ""))
        done = set(item["tasks_done"])
        done.add(key) if payload.get("done") else done.discard(key)
        item["tasks_done"] = sorted(done)
    else:
        return {"ok": False, "error": f"unknown action '{action}'"}
    save(items)
    return {"ok": True, "id": rec["id"], "status": item["status"]}

# ------------------------------------------------------------------ agent actions


def readiness(opp_id: str) -> dict[str, Any]:
    rec, error = _resolve(opp_id)
    if error:
        return {"ok": False, "error": error}
    profile = prof.load()
    ev = opp.evaluate(rec, profile)
    item = load().get(rec["id"], {})
    blockers: list[str] = []
    override = item.get("override")

    if ev["bucket"] in ("expired", "rejected", "unverified"):
        blockers.append(f"opportunity is {ev['bucket']}: {'; '.join(ev['reasons'])}")
    elif ev["bucket"] in ("ineligible", "near_miss") and not override:
        blockers.append(f"opportunity is {ev['bucket']} ({'; '.join(ev['reasons'] or ev['gaps'])}). "
                        "Only if you decide to apply anyway: app override ID --reason ...")
    elif ev["bucket"] == "upcoming":
        blockers.append("applications are not open yet")
    if ev["apply_mode"] not in ("agent", "none") and ev["bucket"] in ("eligible", "needs_confirmation"):
        blockers.append(f"apply mode is '{ev['apply_mode']}': the agent cannot submit this one")
    if not ev["fresh_for_apply"]:
        blockers.append(f"re-verify the official page first (last checked {ev['verified_days_ago']} days ago)")
    if rec.get("fees", {}).get("scholarship_fee") is not False:
        blockers.append("confirm on the official page that there is no fee to apply for the scholarship")
    missing = prof.status(profile)["missing_for_apply"]
    if missing:
        blockers.append(f"profile is missing: {', '.join(missing)}")

    app = rec.get("application", {})
    d = drafts.status(rec["id"])
    if app.get("questions") or d["has_brief"]:
        if not d["has_brief"]:
            blockers.append("no brief yet: run /tailor")
        elif not d["all_approved"]:
            blockers.append(f"answers approved: {d['approved']}/{d['total']}")
    if "cv" in app.get("documents", []) and not (d.get("cv_choice") or {}).get("path"):
        blockers.append("no CV chosen yet: run /tailor")
    if app.get("documents") or app.get("upload_rules"):
        result = doccheck.last(rec["id"])
        if not result:
            blockers.append("document check not run yet")
        elif not result["ok"]:
            blockers.append("document check failed: " + "; ".join(result["errors"][:3]))
        elif doccheck.current_docs_hash(rec["id"]) != result["docs_hash"]:
            blockers.append("documents changed since the last document check: run it again")
    if app.get("references"):
        refs = len(profile["lists"].get("references", []))
        if refs < app["references"]:
            blockers.append(f"needs {app['references']} referees; profile has {refs}")

    packet = {
        "record": {k: rec.get(k) for k in ("id", "official_url", "apply_url", "deadline", "application")},
        "answers": drafts.approved_hashes(rec["id"]),
        "cv": (d.get("cv_choice") or {}).get("path"),
        "docs": (doccheck.last(rec["id"]) or {}).get("docs_hash"),
        "profile": store.canonical_hash(profile["values"]),
        "references": [r.get("email") for r in profile["lists"].get("references", [])],
    }
    return {"ok": True, "id": rec["id"], "ready": not blockers, "blockers": blockers,
            "packet_hash": store.canonical_hash(packet), "apply_mode": ev["apply_mode"],
            "bucket": ev["bucket"], "open_items": ev["open_items"], "override": override}


def _transition(opp_id: str, allowed_from: set[str], to: str, event: str, detail: str = "",
                extra: dict[str, Any] | None = None) -> dict[str, Any]:
    rec, error = _resolve(opp_id)
    if error:
        return {"ok": False, "error": error}
    items = load()
    item = entry(items, rec["id"])
    if item["status"] not in allowed_from:
        return {"ok": False, "error": f"status is '{item['status']}'; this step needs one of {sorted(allowed_from)}"}
    reason = prof.sensitive_reason(detail)
    if reason:
        return {"ok": False, "error": f"log text not saved: {reason}"}
    item["status"] = to
    if extra:
        item.update(extra)
    _log(item, event, detail)
    save(items)
    return {"ok": True, "id": rec["id"], "status": to}


def prepare(opp_id: str) -> dict[str, Any]:
    return _transition(opp_id, {"found", "shortlisted", "manual", "ready"}, "preparing", "preparing")


def override(opp_id: str, reason: str) -> dict[str, Any]:
    rec, error = _resolve(opp_id)
    if error:
        return {"ok": False, "error": error}
    items = load()
    item = entry(items, rec["id"])
    item["override"] = {"reason": reason[:500], "at": store.now_iso()}
    _log(item, "eligibility_override", reason)
    save(items)
    return {"ok": True, "id": rec["id"]}


def start(opp_id: str) -> dict[str, Any]:
    ready = readiness(opp_id)
    if not ready.get("ok"):
        return ready
    if not ready["ready"]:
        return {"ok": False, "error": "not ready", "blockers": ready["blockers"]}
    return _transition(ready["id"], {"found", "shortlisted", "preparing", "ready", "manual"}, "applying",
                       "agent_started", extra={"gate": {"packet_hash": ready["packet_hash"],
                                                        "started_at": store.now_iso()}})


def log_event(opp_id: str, event: str, detail: str = "") -> dict[str, Any]:
    rec, error = _resolve(opp_id)
    if error:
        return {"ok": False, "error": error}
    reason = prof.sensitive_reason(detail)
    if reason:
        return {"ok": False, "error": f"not logged: {reason}. Log field names, never values."}
    items = load()
    _log(entry(items, rec["id"]), event, detail)
    save(items)
    return {"ok": True}


def needs_you(opp_id: str, reason: str) -> dict[str, Any]:
    return _transition(opp_id, {"applying"}, "needs_you", "needs_you", reason, {"waiting_for": reason[:300]})


def resume(opp_id: str) -> dict[str, Any]:
    return _transition(opp_id, {"needs_you"}, "applying", "resumed", extra={"waiting_for": None})


def stop(opp_id: str, reason: str) -> dict[str, Any]:
    """Agent gives up; the dashboard shows the reason and the link so you can apply yourself."""
    return _transition(opp_id, {"preparing", "ready", "applying", "needs_you", "awaiting_submit_ok"},
                       "manual", "agent_stopped", reason, {"stop_reason": reason[:500]})


def review(opp_id: str, review_file: str) -> dict[str, Any]:
    file = Path(review_file)
    if not file.is_file():
        return {"ok": False, "error": f"review file not found: {review_file}"}
    text = file.read_text(encoding="utf-8")
    reason = prof.sensitive_reason(text)
    if reason:
        return {"ok": False, "error": f"review summary must not contain sensitive values ({reason})"}
    rec, error = _resolve(opp_id)
    if error:
        return {"ok": False, "error": error}
    keep = store.data_dir() / "reviews" / f"{rec['id']}.md"
    keep.parent.mkdir(parents=True, exist_ok=True)
    keep.write_text(text, encoding="utf-8")
    review_hash = store.text_hash(text)
    items = load()
    gate = dict(entry(items, rec["id"]).get("gate", {}))
    gate.update({"review_hash": review_hash, "review_file": store.relative_to_home(keep),
                 "submit_approved_at": None})
    result = _transition(rec["id"], {"applying"}, "awaiting_submit_ok", "review_ready",
                         extra={"gate": gate})
    if result["ok"]:
        result["review_hash"] = review_hash
    return result


def approve_submit(opp_id: str, review_hash: str) -> dict[str, Any]:
    rec, error = _resolve(opp_id)
    if error:
        return {"ok": False, "error": error}
    items = load()
    item = entry(items, rec["id"])
    gate = item.get("gate", {})
    if item["status"] != "awaiting_submit_ok":
        return {"ok": False, "error": f"status is '{item['status']}', not awaiting_submit_ok"}
    if review_hash != gate.get("review_hash"):
        return {"ok": False, "error": "review hash does not match the review you were shown"}
    current = readiness(rec["id"])
    if current.get("packet_hash") != gate.get("packet_hash"):
        return {"ok": False, "error": "answers, documents or profile changed since the agent started; "
                                      "re-run the review"}
    gate["submit_approved_at"] = store.now_iso()
    item["gate"] = gate
    _log(item, "submit_approved_by_you")
    save(items)
    return {"ok": True, "id": rec["id"], "approved": True}


def submitted(opp_id: str, confirmation: str, files: list[str] | None = None) -> dict[str, Any]:
    rec, error = _resolve(opp_id)
    if error:
        return {"ok": False, "error": error}
    items = load()
    item = entry(items, rec["id"])
    if item["status"] != "awaiting_submit_ok" or not item.get("gate", {}).get("submit_approved_at"):
        return {"ok": False, "error": "submission was not approved by you first"}
    folder = store.submitted_dir() / rec["id"]
    folder.mkdir(parents=True, exist_ok=True)
    copied = []
    for name in files or []:
        source = Path(name)
        if source.is_file():
            shutil.copy2(source, folder / source.name)
            copied.append(source.name)
    review_file = item["gate"].get("review_file")
    if review_file and store.resolve_path(review_file).exists():
        shutil.copy2(store.resolve_path(review_file), folder / "review.md")
        copied.append("review.md")
    d = drafts.full(rec["id"])
    approved = {qid: e["text"] for qid, e in d["answers"].items() if e.get("status") == "approved"}
    summary = {"record": rec, "confirmation": confirmation, "submitted_at": store.now_iso(),
               "cv": (d["status"].get("cv_choice") or {}), "answers": approved,
               "questions": (d["brief"] or {}).get("questions", []),
               "documents": (doccheck.last(rec["id"]) or {}).get("items", []), "files": copied}
    store.save_json(folder / "summary.json", summary)
    lines = [f"# {rec['title']}", f"Sponsor: {rec['sponsor']}", f"Submitted: {summary['submitted_at']}",
             f"Confirmation: {confirmation}", ""]
    for q in summary["questions"]:
        lines += [f"## {q['prompt']}", approved.get(q["qid"], "(no answer)"), ""]
    (folder / "answers.md").write_text("\n".join(lines), encoding="utf-8")
    item.update({"status": "submitted", "submitted_at": summary["submitted_at"], "submitted_by": "agent",
                 "confirmation": confirmation[:200], "snapshot": store.relative_to_home(folder),
                 "cv_used": summary["cv"].get("path")})
    item.setdefault("outcome", {"result": "pending"})
    _log(item, "submitted", confirmation)
    save(items)
    return {"ok": True, "id": rec["id"], "snapshot": str(folder), "files": copied}


def stats() -> dict[str, Any]:
    items = load()
    by_result: dict[str, int] = defaultdict(int)
    by_cv: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    positive = {"interview", "shortlisted", "offer_won"}
    for item in items.values():
        if item.get("status") != "submitted":
            continue
        result = (item.get("outcome") or {}).get("result", "pending")
        by_result[result] += 1
        cv = item.get("cv_used") or "unknown"
        by_cv[cv]["submitted"] += 1
        by_cv[cv]["positive"] += int(result in positive)
        by_cv[cv]["won"] += int(result == "offer_won")
    return {"submitted": sum(by_result.values()), "by_result": dict(by_result),
            "by_cv": {k: dict(v) for k, v in by_cv.items()}}
