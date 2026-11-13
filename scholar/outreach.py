"""Supervisor outreach tracker (PhD and research master's).

Claude suggests well-matched supervisors and drafts emails; you send them (or approve
sending). A weekly cap keeps outreach specific rather than mass mail.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from . import profile as prof, store

STATUSES = ["suggested", "drafted", "sent", "replied_positive", "replied_negative", "no_reply", "dropped"]
WEEKLY_CAP = 5


def path():
    return store.data_file("outreach.json")


def load() -> list[dict[str, Any]]:
    return (store.load_json(path(), {}) or {}).get("contacts", [])


def save(rows: list[dict[str, Any]]) -> None:
    store.save_json(path(), {"contacts": rows})


def add(contact: dict[str, Any]) -> dict[str, Any]:
    required = ("name", "institution", "profile_url", "match")
    missing = [k for k in required if not contact.get(k)]
    if missing:
        return {"ok": False, "error": f"missing: {', '.join(missing)}"}
    if not str(contact["profile_url"]).startswith("https://"):
        return {"ok": False, "error": "profile_url must be the supervisor's official https:// page"}
    rows = load()
    if any(r["profile_url"] == contact["profile_url"] for r in rows):
        return {"ok": True, "note": "already tracked"}
    cid = f"s{max([int(r['id'][1:]) for r in rows] + [0]) + 1}"
    rows.append({"id": cid, "name": contact["name"][:200], "institution": contact["institution"][:200],
                 "country": contact.get("country"), "email": contact.get("email"),
                 "profile_url": contact["profile_url"], "match": contact["match"][:1000],
                 "opp_id": contact.get("opp_id"), "status": "suggested", "added": store.now_iso(),
                 "history": []})
    save(rows)
    return {"ok": True, "id": cid}


def update(cid: str, status: str, note: str = "", draft_path: str | None = None) -> dict[str, Any]:
    if status not in STATUSES:
        return {"ok": False, "error": f"status must be one of {STATUSES}"}
    if prof.sensitive_reason(note):
        return {"ok": False, "error": "note contains sensitive data"}
    rows = load()
    row = next((r for r in rows if r["id"] == cid), None)
    if not row:
        return {"ok": False, "error": f"no contact {cid}"}
    warning = None
    if status == "sent":
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        recent = sum(1 for r in rows for h in r["history"]
                     if h["status"] == "sent" and datetime.fromisoformat(h["at"]) > week_ago)
        if recent >= WEEKLY_CAP:
            warning = (f"{recent} emails already sent this week; fewer, more specific emails get "
                       "better replies")
        row["sent_at"] = store.now_iso()
    row["status"] = status
    if draft_path:
        row["draft_path"] = draft_path
    row["history"].append({"at": store.now_iso(), "status": status, "note": note[:500]})
    save(rows)
    return {"ok": True, "id": cid, "status": status, "warning": warning}
