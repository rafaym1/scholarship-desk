"""Command line used by the Claude skills (and by you). Every command prints JSON.

    python -m scholar status
    python -m scholar serve --open
    python -m scholar profile set identity.citizenships "Pakistan"
    python -m scholar opp add record.json
    ...  run  python -m scholar -h  or  python -m scholar <group> -h
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any

from . import (applications, doccheck, drafts, library, opportunity as opp, outreach,
               profile as prof, queries, registry, store, timeline, watch)


def emit(value: Any) -> int:
    print(json.dumps(value, indent=1, ensure_ascii=False, default=str))
    return 0 if not isinstance(value, dict) or value.get("ok", True) else 1


def read_json(source: str) -> Any:
    text = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8-sig")
    return json.loads(text)


def pairs(items: list[str]) -> dict[str, str]:
    out = {}
    for item in items:
        if "=" not in item:
            raise SystemExit(f"expected field=value, got '{item}'")
        key, value = item.split("=", 1)
        out[key.strip()] = value
    return out


def docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml").decode("utf-8", errors="replace")
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<w:tab/>", "\t", xml)
    text = re.sub(r"<[^>]+>", "", xml)
    for entity, char in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&apos;", "'")):
        text = text.replace(entity, char)
    return re.sub(r"\n{3,}", "\n\n", text).strip()

# ----------------------------------------------------------------------- commands


def cmd_status(_: argparse.Namespace) -> int:
    profile = prof.load()
    rows = opp.evaluate_all(profile)
    tracker = applications.load()
    buckets: dict[str, int] = {}
    for row in rows:
        buckets[row["evaluation"]["bucket"]] = buckets.get(row["evaluation"]["bucket"], 0) + 1
    active = [{"id": rid, "status": t["status"], "waiting_for": t.get("waiting_for")}
              for rid, t in tracker.items() if t.get("status") in applications.ACTIVE | {"shortlisted"}]
    status = prof.status(profile)
    if not opp.tz_data_available():
        return emit({"ok": False, "error": opp.TZDATA_HINT})
    return emit({
        "ok": True,
        "profile": {k: status[k] for k in ("search_ready", "apply_ready", "missing_for_search",
                                           "missing_for_apply", "completeness_percent")},
        "opportunities": len(rows), "by_bucket": buckets, "active_applications": active,
        "watch": {"pages": len(watch.pages()), "pending_changes": len(watch.changes()),
                  "last_run": watch.last_run()},
        "inbox_queued": len(watch.inbox()),
        "library": library.summary(profile),
        "pending_queries": len(queries.pending(1000)),
    })


def cmd_serve(args: argparse.Namespace) -> int:
    from . import server
    server.serve(args.port, args.open)
    return 0


def cmd_profile(args: argparse.Namespace) -> int:
    p = prof.load()
    action = args.action
    if action == "status":
        return emit(prof.status(p))
    if action == "summary":
        return emit({"ok": True, **prof.display_summary(p)})
    if action == "keys":
        return emit({"ok": True, "keys": prof.keys(args.args[0] if args.args else None)})
    if action == "show":
        section = args.section
        values = {k: v for k, v in p["values"].items() if not section or k.startswith(section + ".")}
        lists = p["lists"] if not section or section == "lists" else {}
        return emit({"ok": True, "values": values, "lists": lists, "skipped": p["skipped"]})
    if action == "list-show":
        return emit({"ok": True, "rows": p["lists"].get(args.args[0], [])})
    if action == "docs":
        return emit({"ok": True, "documents": p["lists"]["documents"]})
    if action == "facts":
        return emit({"ok": True, "facts": prof.facts(p)})
    if action == "set":
        key, value = args.args[0], " ".join(args.args[1:])
        result = prof.set_value(p, key, value)
    elif action == "unset":
        result = prof.unset_value(p, args.args[0])
    elif action == "skip":
        result = prof.skip(p, args.args[0])
    elif action == "list-add":
        result = prof.list_add(p, args.args[0], pairs(args.args[1:]))
    elif action == "list-update":
        result = prof.list_update(p, args.args[0], int(args.args[1]), pairs(args.args[2:]))
    elif action == "list-remove":
        result = prof.list_remove(p, args.args[0], int(args.args[1]))
    elif action == "doc-add":
        result = prof.doc_add(p, args.args[0], args.args[1], args.label)
    else:
        return emit({"ok": False, "error": f"unknown profile action {action}"})
    if result.get("ok"):
        prof.save(p)
    return emit(result)


def _row_brief(row: dict[str, Any], tracker: dict[str, Any]) -> dict[str, Any]:
    ev = row["evaluation"]
    return {"id": row["id"], "title": row["record"]["title"], "bucket": ev["bucket"],
            "country": ev["country"]["status"], "deadline": ev["deadline"]["date"],
            "days_left": ev["deadline"]["days_left"], "apply_mode": ev["apply_mode"],
            "in_scope": ev["in_scope"], "status": tracker.get(row["id"], {}).get("status", "found")}


def cmd_opp(args: argparse.Namespace) -> int:
    action = args.action
    if action == "template":
        return emit({"ok": True, "template": opp.template(),
                     "groups": ["@eu", "@eea", "@eu_eea_ch", "@efta", "@nordic"],
                     "requirement_fields": sorted(prof.KNOWN_DERIVED) + ["derived.score.<exam>"] + list(prof.SCALARS)})
    if action == "add":
        data = read_json(args.args[0])
        return emit(opp.add(data if isinstance(data, list) else [data]))
    if action == "patch":
        return emit(opp.patch(args.args[0], read_json(args.args[1])))
    if action == "remove":
        return emit(opp.remove(args.args[0]))
    profile = prof.load()
    tracker = applications.load()
    if action == "list":
        rows = opp.evaluate_all(profile)
        if args.bucket:
            rows = [r for r in rows if r["evaluation"]["bucket"] == args.bucket]
        if not args.all:
            rows = [r for r in rows if r["evaluation"]["in_scope"]]
        return emit({"ok": True, "count": len(rows), "items": [_row_brief(r, tracker) for r in rows]})
    if action == "show":
        rec = opp.find(opp.load_all(), args.args[0])
        if not rec:
            return emit({"ok": False, "error": "not found"})
        entry = {"id": rec["id"], "record": rec, "evaluation": opp.evaluate(rec, profile)}
        return emit({"ok": True, **entry,
                     "timeline": timeline.plan(entry, profile, tracker.get(rec["id"])),
                     "tracker": tracker.get(rec["id"], {"status": "found"}),
                     "drafts": drafts.status(rec["id"]), "doccheck": doccheck.last(rec["id"])})
    return emit({"ok": False, "error": f"unknown opp action {action}"})


def cmd_registry(args: argparse.Namespace) -> int:
    if args.action == "check":
        return emit(registry.check())
    data = registry.load()
    sources = [s for s in data["sources"] if not args.region or s["region"] == args.region]
    return emit({"ok": True, "sources": sources, "job_portals": data["job_portals"],
                 "admission_portals": data["admission_portals"],
                 "discovery_domains": data["discovery_domains"]})


def cmd_queries(args: argparse.Namespace) -> int:
    if args.action == "generate":
        return emit(queries.generate(prof.load(), args.max))
    if args.action == "next":
        return emit({"ok": True, "queries": queries.pending(args.n)})
    if args.action == "done":
        return emit(queries.mark_done(args.args))
    return emit({"ok": False, "error": "unknown queries action"})


def cmd_watch(args: argparse.Namespace) -> int:
    a = args.action
    if a == "run":
        return emit(watch.run(args.args or None))
    if a == "add":
        return emit(watch.add(args.args[0], args.label or args.args[0], args.kind, args.opp))
    if a == "list":
        return emit({"ok": True, "pages": watch.pages()})
    if a == "remove":
        return emit(watch.remove(args.args[0]))
    if a == "changes":
        return emit({"ok": True, "changes": watch.changes()})
    if a == "processed":
        return emit(watch.mark_processed(args.args))
    if a == "inbox":
        return emit({"ok": True, "links": watch.inbox()})
    if a == "inbox-add":
        return emit(watch.inbox_add(args.args[0], args.note or ""))
    if a == "inbox-mark":
        return emit(watch.inbox_mark(args.args[0], args.args[1], args.result or ""))
    return emit({"ok": False, "error": "unknown watch action"})


def cmd_library(args: argparse.Namespace) -> int:
    a = args.action
    p = prof.load()
    if a == "status":
        return emit({"ok": True, **library.summary(p)})
    if a == "changed":
        return emit({"ok": True, "documents": library.changed_documents(p)})
    if a == "mark-ingested":
        return emit(library.mark_ingested(args.args))
    if a == "add-cv-cards":
        data = read_json(args.args[0])
        return emit(library.add_cv_cards(data if isinstance(data, list) else [data], p))
    if a == "add-facts":
        data = read_json(args.args[0])
        return emit(library.add_facts(data if isinstance(data, list) else [data]))
    if a == "facts":
        rows = library.facts()
        if args.tag:
            rows = [f for f in rows if args.tag in f.get("tags", []) or args.tag == f.get("category")]
        return emit({"ok": True, "facts": rows})
    if a == "cv-cards":
        return emit({"ok": True, "cards": library.cv_cards()})
    if a == "remove-fact":
        return emit(library.remove_fact(args.args[0]))
    if a == "voice":
        return emit(library.save_voice(Path(args.args[0]).read_text(encoding="utf-8")))
    if a == "show-voice":
        return emit({"ok": True, "voice": library.voice()})
    if a == "answers":
        rows = library.answers()
        if args.tag:
            rows = [r for r in rows if r.get("category") == args.tag]
        return emit({"ok": True, "answers": rows})
    return emit({"ok": False, "error": "unknown library action"})


def cmd_drafts(args: argparse.Namespace) -> int:
    a = args.action
    if a == "brief":
        return emit(drafts.set_brief(args.args[0], read_json(args.args[1])))
    if a == "put":
        text = Path(args.args[2]).read_text(encoding="utf-8-sig").strip()
        sources = [s for s in (args.sources or "").split(",") if s]
        return emit(drafts.put_answer(args.args[0], args.args[1], text, sources))
    if a == "show":
        return emit({"ok": True, **drafts.full(args.args[0])})
    if a == "status":
        return emit({"ok": True, **drafts.status(args.args[0])})
    if a == "approve":
        return emit(drafts.approve(args.args[0], args.args[1]))
    return emit({"ok": False, "error": "unknown drafts action"})


def cmd_docs(args: argparse.Namespace) -> int:
    if args.action == "check":
        return emit(doccheck.check(args.args[0]))
    if args.action == "merge":
        return emit(doccheck.merge(args.args[1:], args.args[0]))
    if args.action == "text":
        path = Path(args.args[0])
        if path.suffix.lower() == ".docx":
            return emit({"ok": True, "text": docx_text(path)})
        return emit({"ok": True, "text": path.read_text(encoding="utf-8", errors="replace")})
    return emit({"ok": False, "error": "unknown docs action"})


def cmd_app(args: argparse.Namespace) -> int:
    a, rest = args.action, args.args
    if a == "readiness":
        return emit(applications.readiness(rest[0]))
    if a == "prepare":
        return emit(applications.prepare(rest[0]))
    if a == "override":
        return emit(applications.override(rest[0], args.reason or ""))
    if a == "start":
        return emit(applications.start(rest[0]))
    if a == "log":
        return emit(applications.log_event(rest[0], rest[1], args.detail or ""))
    if a == "needs-you":
        return emit(applications.needs_you(rest[0], args.reason or ""))
    if a == "resume":
        return emit(applications.resume(rest[0]))
    if a == "stop":
        return emit(applications.stop(rest[0], args.reason or ""))
    if a == "review":
        return emit(applications.review(rest[0], args.file))
    if a == "approve-submit":
        return emit(applications.approve_submit(rest[0], args.hash))
    if a == "submitted":
        return emit(applications.submitted(rest[0], args.confirmation or "", args.files or []))
    if a == "shortlist":
        return emit(applications.user_action(rest[0], "shortlist"))
    if a == "stats":
        return emit({"ok": True, **applications.stats()})
    if a == "show":
        rec = opp.find(opp.load_all(), rest[0])
        return emit({"ok": bool(rec), "tracker": applications.load().get(rec["id"]) if rec else None})
    return emit({"ok": False, "error": "unknown app action"})


def cmd_outreach(args: argparse.Namespace) -> int:
    if args.action == "add":
        data = read_json(args.args[0])
        results = [outreach.add(c) for c in (data if isinstance(data, list) else [data])]
        return emit({"ok": all(r["ok"] for r in results), "results": results})
    if args.action == "list":
        return emit({"ok": True, "contacts": outreach.load()})
    if args.action == "update":
        return emit(outreach.update(args.args[0], args.args[1], args.note or "", args.draft))
    return emit({"ok": False, "error": "unknown outreach action"})


def cmd_week(_: argparse.Namespace) -> int:
    profile = prof.load()
    tracker = applications.load()
    rows = []
    for entry in opp.evaluate_all(profile):
        tracked = tracker.get(entry["id"], {"status": "found"})
        rows.append({**entry, "tracker": tracked, "timeline": timeline.plan(entry, profile, tracked)})
    return emit({"ok": True, **timeline.week_view(rows)})

# ------------------------------------------------------------------------- parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m scholar", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="group", required=True)

    sub.add_parser("status", help="overview of everything").set_defaults(func=cmd_status)
    s = sub.add_parser("serve", help="run the dashboard")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--open", action="store_true", help="open it in your browser")
    s.set_defaults(func=cmd_serve)
    sub.add_parser("week", help="tasks due this week").set_defaults(func=cmd_week)

    def group(name: str, func: Any, actions: list[str], help_text: str) -> argparse.ArgumentParser:
        g = sub.add_parser(name, help=help_text)
        g.add_argument("action", choices=actions)
        g.add_argument("args", nargs="*")
        g.set_defaults(func=func)
        return g

    g = group("profile", cmd_profile, ["status", "summary", "keys", "show", "set", "unset", "skip",
                                       "list-add", "list-update", "list-remove", "list-show", "doc-add",
                                       "docs", "facts"], "your profile")
    g.add_argument("--section")
    g.add_argument("--label")
    g = group("opp", cmd_opp, ["template", "add", "patch", "remove", "list", "show"], "opportunities")
    g.add_argument("--bucket", choices=opp.BUCKETS)
    g.add_argument("--all", action="store_true", help="include out-of-scope ones")
    g = group("registry", cmd_registry, ["list", "check"], "official source registry")
    g.add_argument("--region")
    g = group("queries", cmd_queries, ["generate", "next", "done"], "weekly search plan")
    g.add_argument("--max", type=int, default=80)
    g.add_argument("--n", type=int, default=10)
    g = group("watch", cmd_watch, ["run", "add", "list", "remove", "changes", "processed", "inbox",
                                   "inbox-add", "inbox-mark"], "daily watcher and link inbox")
    g.add_argument("--label")
    g.add_argument("--kind", default="funding_page", choices=watch.KINDS)
    g.add_argument("--opp")
    g.add_argument("--note")
    g.add_argument("--result")
    g = group("library", cmd_library, ["status", "changed", "mark-ingested", "add-cv-cards", "add-facts",
                                       "facts", "cv-cards", "remove-fact", "voice", "show-voice", "answers"],
              "CV cards, fact bank, voice, approved answers")
    g.add_argument("--tag")
    g = group("drafts", cmd_drafts, ["brief", "put", "show", "status", "approve"], "application drafts")
    g.add_argument("--sources", help="comma-separated fact ids")
    group("docs", cmd_docs, ["check", "merge", "text"], "document checks and text extraction")
    g = group("app", cmd_app, ["readiness", "prepare", "override", "start", "log", "needs-you", "resume",
                               "stop", "review", "approve-submit", "submitted", "shortlist", "stats", "show"],
              "application tracker and approval gates")
    g.add_argument("--reason")
    g.add_argument("--detail")
    g.add_argument("--file")
    g.add_argument("--hash")
    g.add_argument("--confirmation")
    g.add_argument("--files", nargs="*")
    g = group("outreach", cmd_outreach, ["add", "list", "update"], "supervisor outreach")
    g.add_argument("--note")
    g.add_argument("--draft")
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:
            pass
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (IndexError, FileNotFoundError, json.JSONDecodeError, ValueError) as err:
        return emit({"ok": False, "error": f"{type(err).__name__}: {err}"})
