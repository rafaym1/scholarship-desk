"""Backward planning: from each deadline, work out 'start by' dates and the tasks due.

Lead times are defaults you can override in data/lead_times.json.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from . import store

DEFAULT_LEAD_DAYS = {
    "references": 42,             # ask referees about six weeks ahead
    "language_test": 35,          # book a test and receive results
    "translations": 21,           # certified translations
    "supervisor_contact": 30,     # research degrees: agree a supervisor first
    "admission_application": 10,  # finish the university application before its deadline
    "essays": 10,                 # draft, review and approve answers
    "documents": 7,               # gather, convert and check files
    "recon_apply": 4,             # portal walk-through, agent run, your final review
}

ACTIVE_STATUSES = {"shortlisted", "preparing", "ready", "applying", "needs_you", "awaiting_submit_ok"}


def lead_times() -> dict[str, int]:
    custom = store.load_json(store.data_file("lead_times.json"), {}) or {}
    merged = dict(DEFAULT_LEAD_DAYS)
    merged.update({k: int(v) for k, v in custom.items() if k in DEFAULT_LEAD_DAYS})
    return merged


def urgency(start_by: date | None, today: date) -> str:
    if not start_by:
        return "unknown"
    days = (start_by - today).days
    if days < 0:
        return "overdue"
    if days <= 7:
        return "this_week"
    if days <= 30:
        return "soon"
    return "later"


def plan(entry: dict[str, Any], profile: dict[str, Any], tracked: dict[str, Any] | None,
         today: date | None = None, leads: dict[str, int] | None = None) -> dict[str, Any]:
    today = today or store.today()
    leads = leads or lead_times()
    rec, ev = entry["record"], entry["evaluation"]
    done = set((tracked or {}).get("tasks_done", []))

    candidates = [store.parse_date(ev["deadline"]["date"]), store.parse_date(ev["internal_deadline"]["date"])]
    anchors = [d for d in candidates if d]
    deadline = min(anchors) if anchors else None
    admission_deadline = store.parse_date(ev["admission"]["deadline"]) if ev["admission"]["required"] else None

    tasks: list[dict[str, Any]] = []

    def add(key: str, label: str, anchor: date | None, lead_key: str) -> None:
        if not anchor:
            return
        due = anchor - timedelta(days=leads[lead_key])
        tasks.append({"key": key, "label": label, "due": due.isoformat(), "done": key in done,
                      "days_left": (due - today).days})

    app = rec.get("application", {})
    if admission_deadline:
        add("admission", "Submit the university/programme application", admission_deadline,
            "admission_application")
    if app.get("supervisor_required"):
        add("supervisor", "Agree a supervisor (send outreach emails)", deadline, "supervisor_contact")
    if app.get("references"):
        add("references", f"Ask {app['references']} referee(s) and send them a brief", deadline, "references")

    facts_tests = {k for k in _profile_exam_keys(profile)}
    for req in ev.get("requirements", []):
        if req["field"].startswith("derived.score.") and req["result"] in ("fail", "unknown"):
            exam = req["field"].split(".", 2)[2].upper()
            label = f"Book / retake {exam} ({req['text']})" if exam.lower() not in facts_tests or req["result"] == "fail" \
                else f"Confirm {exam} score meets: {req['text']}"
            add(f"test_{exam.lower()}", label, deadline, "language_test")
    if app.get("translations_required"):
        add("translations", "Get certified translations", deadline, "translations")

    have_docs = {d.get("type") for d in profile["lists"].get("documents", [])}
    missing = [d for d in app.get("documents", []) if d not in have_docs]
    if missing:
        names = {"recommendation_letter": "reference letters", "language_certificate": "English test result",
                 "motivation_letter": "statement of purpose", "passport_scan": "passport scan"}
        readable = ", ".join(names.get(d, d.replace("_", " ")) for d in missing)
        add("documents", f"Prepare documents: {readable}", deadline, "documents")
    elif app.get("documents"):
        add("documents", "Run the document check", deadline, "documents")
    questions = app.get("questions") or []
    if questions:
        add("essays", f"Draft and approve {len(questions)} answer(s)", deadline, "essays")
    if ev["apply_mode"] == "agent":
        add("apply", "Portal recon, agent fills it, you approve the submit", deadline, "recon_apply")
    elif ev["apply_mode"] in ("manual", "unknown"):
        add("apply", "Submit it yourself (agent cannot apply here)", deadline, "recon_apply")
    elif ev["apply_mode"] == "nomination":
        add("apply", "Ask your university's graduate office about the nomination process", deadline,
            "references")

    open_tasks = [t for t in tasks if not t["done"]]
    start_by = min((store.parse_date(t["due"]) for t in open_tasks), default=None)
    if start_by is None and deadline and not tasks:
        start_by = deadline - timedelta(days=leads["recon_apply"])
    return {
        "deadline": deadline.isoformat() if deadline else None,
        "start_by": start_by.isoformat() if start_by else None,
        "start_in_days": (start_by - today).days if start_by else None,
        "urgency": urgency(start_by, today),
        "tasks": sorted(tasks, key=lambda t: t["due"]),
    }


def _profile_exam_keys(profile: dict[str, Any]) -> set[str]:
    from .profile import exam_key
    keys = set()
    for test in profile["lists"].get("tests", []):
        key = exam_key(test.get("exam", ""))
        keys.add(key)
        keys.add(key.split("_")[0])
    return keys


def week_view(rows: list[dict[str, Any]], today: date | None = None) -> dict[str, Any]:
    """Tasks due within 7 days (or overdue) for opportunities you are pursuing, plus
    eligible ones you haven't decided on whose start-by date is close."""
    today = today or store.today()
    horizon = today + timedelta(days=7)
    tasks, undecided = [], []
    for row in rows:
        status = row["tracker"].get("status", "found")
        timeline = row["timeline"]
        if status in ACTIVE_STATUSES:
            for task in timeline["tasks"]:
                if not task["done"] and store.parse_date(task["due"]) <= horizon:
                    tasks.append({**task, "id": row["id"], "title": row["record"]["title"]})
        elif status == "found" and row["evaluation"]["bucket"] in ("eligible", "needs_confirmation") \
                and timeline["start_in_days"] is not None and timeline["start_in_days"] <= 14:
            undecided.append({"id": row["id"], "title": row["record"]["title"],
                              "start_by": timeline["start_by"], "deadline": timeline["deadline"]})
    tasks.sort(key=lambda t: t["due"])
    undecided.sort(key=lambda u: u["start_by"])
    return {"tasks": tasks, "undecided": undecided}
