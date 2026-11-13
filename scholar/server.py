"""Local dashboard server. Listens on 127.0.0.1 only; nothing is exposed to the network.

Write requests must be same-origin JSON with an X-Scholar header, so other websites
open in your browser cannot change anything here.
"""
from __future__ import annotations

import json
import mimetypes
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from . import (applications, doccheck, drafts, library, opportunity as opp, outreach,
               profile as prof, store, timeline, uploads, watch)

DASHBOARD = store.ROOT / "dashboard"
STATIC = {"/": "index.html", "/index.html": "index.html", "/app.js": "app.js", "/styles.css": "styles.css"}
MAX_BODY = 256_000
MAX_UPLOAD_BODY = uploads.MAX_BYTES * 4 // 3 + 64_000  # base64 file plus the JSON around it
CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
       "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")


def _draft_items(opp_id: str) -> list[dict[str, Any]]:
    """One line per drafted question for the Overview's Drafts module."""
    b = drafts.brief(opp_id)
    if not b:
        return []
    answers = drafts.answers(opp_id)
    out = []
    for q in b.get("questions", []):
        a = answers.get(q.get("qid"), {})
        out.append({"qid": q.get("qid"), "prompt": str(q.get("prompt", ""))[:140],
                    "status": a.get("status") or ("draft" if a.get("text") else "not_drafted"),
                    "words": (a.get("checks") or {}).get("words"), "limit": q.get("limit")})
    return out


def build_state() -> dict[str, Any]:
    profile = prof.load()
    tracker = applications.load()
    leads = timeline.lead_times()
    rows = []
    for entry in opp.evaluate_all(profile):
        tracked = tracker.get(entry["id"], {"status": "found", "seen": False, "tasks_done": [],
                                            "history": [], "notes": ""})
        check = doccheck.last(entry["id"])
        rows.append({
            "id": entry["id"],
            "record": entry["record"],
            "evaluation": entry["evaluation"],
            "tracker": {**{k: v for k, v in tracked.items() if k != "history"},
                        "history": tracked.get("history", [])[-8:]},
            "timeline": timeline.plan(entry, profile, tracked, leads=leads),
            "drafts": drafts.status(entry["id"]),
            "draft_items": _draft_items(entry["id"]),
            "doccheck": {"ok": check["ok"], "errors": check["errors"], "warnings": check["warnings"],
                         "checked_at": check["checked_at"]} if check else None,
        })
    status = prof.status(profile)
    changed = library.changed_documents(profile)
    return {
        "generated": store.now_iso(),
        "profile": prof.display_summary(profile),
        "profile_status": {k: status[k] for k in ("search_ready", "apply_ready", "missing_for_search",
                                                  "missing_for_apply", "completeness_percent")},
        "rows": rows,
        "week": timeline.week_view(rows),
        "stats": applications.stats(),
        "watch": {"last_run": watch.last_run(), "pending_changes": len(watch.changes()),
                  "pages": len(watch.pages()),
                  "needs_browser": [p["label"] for p in watch.pages() if p.get("needs_browser")]},
        "inbox": watch.inbox(include_done=True)[-60:],
        "library": {k: v for k, v in library.summary(profile).items() if k != "documents_needing_ingest"}
        | {"documents_needing_ingest": len(changed)},
        "documents": uploads.listing(profile, changed),
        "doc_types": prof.DOC_TYPES,
        "outreach": [{k: r.get(k) for k in ("id", "name", "institution", "country", "profile_url",
                                            "match", "status", "sent_at", "opp_id")} for r in outreach.load()],
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "scholar/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:  # keep the console quiet
        return

    # ---------------------------------------------------------------- helpers
    def _allowed_hosts(self) -> set[str]:
        port = self.server.server_address[1]
        return {f"127.0.0.1:{port}", f"localhost:{port}"}

    def _headers(self, status: int, content_type: str, length: int) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def _json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._headers(status, "application/json; charset=utf-8", len(body))
        self.wfile.write(body)

    def _host_ok(self) -> bool:
        if self.headers.get("Host") not in self._allowed_hosts():
            self._json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "bad host"})
            return False
        return True

    # ------------------------------------------------------------------- GET
    def do_GET(self) -> None:  # noqa: N802
        if not self._host_ok():
            return
        path = urlsplit(self.path).path
        try:
            if path in STATIC:
                file = DASHBOARD / STATIC[path]
                data = file.read_bytes()
                ctype = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
                if ctype.startswith("text/") or ctype.endswith("javascript"):
                    ctype += "; charset=utf-8"
                self._headers(HTTPStatus.OK, ctype, len(data))
                self.wfile.write(data)
            elif path == "/api/state":
                self._json(HTTPStatus.OK, build_state())
            elif path == "/api/profile":
                self._json(HTTPStatus.OK, prof.web_view())
            elif path.startswith("/api/drafts/"):
                self._json(HTTPStatus.OK, drafts.full(unquote(path.split("/", 3)[3])))
            elif path.startswith("/submitted/"):
                self._serve_submitted(unquote(path[len("/submitted/"):]))
            else:
                self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})
        except ValueError as err:
            self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(err)})
        except Exception as err:  # pragma: no cover - surfaced to the page
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(err)})

    def _serve_submitted(self, rel: str) -> None:
        base = store.submitted_dir().resolve()
        target = (base / rel).resolve()
        if base not in target.parents or not target.is_file():
            self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})
            return
        data = target.read_bytes()
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if target.suffix in (".md", ".json", ".txt"):
            ctype = "text/plain; charset=utf-8"
        self._headers(HTTPStatus.OK, ctype, len(data))
        self.wfile.write(data)

    # ------------------------------------------------------------------ POST
    def do_POST(self) -> None:  # noqa: N802
        if not self._host_ok():
            return
        origin = self.headers.get("Origin")
        if origin and origin.replace("http://", "") not in self._allowed_hosts():
            self._json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "cross-site request refused"})
            return
        if self.headers.get("Sec-Fetch-Site") not in (None, "same-origin", "none"):
            self._json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "cross-site request refused"})
            return
        if self.headers.get("X-Scholar") != "1" or \
                not (self.headers.get("Content-Type") or "").startswith("application/json"):
            self._json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "missing dashboard headers"})
            return
        path = urlsplit(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        if length > (MAX_UPLOAD_BODY if path == "/api/upload" else MAX_BODY):
            self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"ok": False, "error": "too large"})
            return
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "bad JSON"})
            return
        try:
            result = self._route(path, body)
        except Exception as err:  # pragma: no cover
            result = {"ok": False, "error": str(err)}
        self._json(HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST, result)

    def _route(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        if path == "/api/action":
            return applications.user_action(str(body.get("id", "")), str(body.get("action", "")),
                                            body.get("payload") or {})
        if path == "/api/seen_all":
            items = applications.load()
            for rid in opp.load_all():
                applications.entry(items, rid)["seen"] = True
            applications.save(items)
            return {"ok": True}
        if path == "/api/draft":
            opp_id, qid, op = str(body.get("id", "")), str(body.get("qid", "")), body.get("op")
            if op == "approve":
                return drafts.approve(opp_id, qid)
            if op == "edit_approve":
                return drafts.approve(opp_id, qid, edited_text=str(body.get("text", "")))
            if op == "request_changes":
                return drafts.request_changes(opp_id, qid, str(body.get("feedback", "")))
            return {"ok": False, "error": "unknown draft operation"}
        if path == "/api/inbox":
            if body.get("op") == "add":
                return watch.inbox_add(str(body.get("url", "")), str(body.get("note", "")))
            if body.get("op") == "remove":
                return watch.inbox_mark(str(body.get("link_id", "")), "removed", "removed by you")
            return {"ok": False, "error": "unknown inbox operation"}
        if path == "/api/outreach":
            return outreach.update(str(body.get("id", "")), str(body.get("status", "")),
                                   str(body.get("note", "")))
        if path == "/api/profile":
            return prof.web_edit(body)
        if path == "/api/upload":
            return uploads.save(str(body.get("name", "")), str(body.get("data", "")),
                                str(body.get("type", "")), str(body.get("label", "")),
                                bool(body.get("replace")))
        return {"ok": False, "error": "not found"}


def make_server(port: int = 8765) -> ThreadingHTTPServer:
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def serve(port: int = 8765, open_browser: bool = False) -> None:
    try:
        httpd = make_server(port)
    except OSError:
        url = f"http://127.0.0.1:{port}/"
        print(f"Dashboard already running at {url}")
        if open_browser:
            webbrowser.open(url)
        return
    url = f"http://127.0.0.1:{port}/"
    print(f"Scholarship dashboard running at {url}  (close this window to stop it)")
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
