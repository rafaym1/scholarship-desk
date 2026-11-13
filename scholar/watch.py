"""Daily watcher: zero-token change detection on a list of pages, plus the link inbox.

Run it with `python -m scholar watch run`: Windows schedules it via setup.ps1 -DailyWatch
(scripts/daily-watch.bat); on Mac/Linux use cron (see the README). It fetches each
watched page once, compares it with the last snapshot and queues only the new lines.
Claude's daily run then reads just those changes instead of searching the web again.
"""
from __future__ import annotations

import re
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlsplit

from . import store

USER_AGENT = "Mozilla/5.0 (compatible; scholar-watch/0.1; personal scholarship tracker; one visit per day)"
KINDS = ["portal_search", "funding_page", "not_open_yet", "deadline_page"]
MAX_BYTES = 3_000_000
VOLATILE = re.compile(
    r"(\b\d+\s+(seconds?|minutes?|mins?|hours?|days?|weeks?)\s+ago\b|\b\d{1,2}:\d{2}(:\d{2})?\b|"
    r"cookie|copyright|©|\bviews?\b\s*\d+|\d+\s+views?)", re.I)


class _TextAndLinks(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "template", "iframe"}

    def __init__(self, base: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base = base
        self.depth = 0
        self.lines: list[str] = []
        self._buf: list[str] = []
        self._href: str | None = None
        self._link_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP:
            self.depth += 1
        elif tag == "a":
            href = dict(attrs).get("href")
            if href and not href.startswith(("#", "javascript:", "mailto:")):
                self._href = urljoin(self.base, href)
                self._link_text = []
        elif tag in ("p", "div", "li", "tr", "br", "h1", "h2", "h3", "h4", "section", "article"):
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP and self.depth:
            self.depth -= 1
        elif tag == "a" and self._href:
            text = " ".join(" ".join(self._link_text).split())
            if len(text) > 3:
                self.lines.append(f"LINK: {text} -> {self._href}")
            self._href = None
        elif tag in ("p", "div", "li", "tr", "h1", "h2", "h3", "h4", "section", "article"):
            self._flush()

    def handle_data(self, data: str) -> None:
        if self.depth:
            return
        self._buf.append(data)
        if self._href is not None:
            self._link_text.append(data)

    def _flush(self) -> None:
        text = " ".join(" ".join(self._buf).split())
        if len(text) > 2:
            self.lines.append(text)
        self._buf = []

    def result(self) -> list[str]:
        self._flush()
        seen, out = set(), []
        for line in self.lines:
            if line not in seen:
                seen.add(line)
                out.append(line[:500])
        return out


def extract_lines(html: str, base_url: str) -> list[str]:
    parser = _TextAndLinks(base_url)
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        pass
    return parser.result()

# ---------------------------------------------------------------------- storage


def _watch_path():
    return store.data_file("watch.json")


def pages() -> list[dict[str, Any]]:
    return (store.load_json(_watch_path(), {}) or {}).get("pages", [])


def _save_pages(rows: list[dict[str, Any]]) -> None:
    store.save_json(_watch_path(), {"pages": rows})


def _changes_path():
    return store.data_file("watch_changes.json")


def changes(include_processed: bool = False) -> list[dict[str, Any]]:
    rows = (store.load_json(_changes_path(), {}) or {}).get("changes", [])
    return rows if include_processed else [c for c in rows if not c.get("processed")]


def _save_changes(rows: list[dict[str, Any]]) -> None:
    store.save_json(_changes_path(), {"changes": rows[-500:]})


def _valid_url(url: str) -> bool:
    parts = urlsplit(url)
    return parts.scheme == "https" and bool(parts.hostname) and " " not in url


def add(url: str, label: str, kind: str, opp_id: str | None = None) -> dict[str, Any]:
    if not _valid_url(url):
        return {"ok": False, "error": "watch URLs must be https:// and contain no spaces"}
    if kind not in KINDS:
        return {"ok": False, "error": f"kind must be one of {KINDS}"}
    rows = pages()
    if any(p["url"] == url for p in rows):
        return {"ok": True, "note": "already watched"}
    page_id = f"w{max([int(p['id'][1:]) for p in rows] + [0]) + 1}"
    rows.append({"id": page_id, "url": url, "label": label[:200], "kind": kind, "opp_id": opp_id,
                 "added": store.now_iso(), "failures": 0, "needs_browser": False})
    _save_pages(rows)
    return {"ok": True, "id": page_id}


def remove(page_id: str) -> dict[str, Any]:
    rows = pages()
    kept = [p for p in rows if p["id"] != page_id]
    _save_pages(kept)
    return {"ok": len(kept) != len(rows), "removed": page_id}


def mark_processed(change_ids: list[str]) -> dict[str, Any]:
    rows = changes(include_processed=True)
    hit = 0
    for row in rows:
        if row["id"] in change_ids or "all" in change_ids:
            if not row.get("processed"):
                row["processed"] = store.now_iso()
                hit += 1
    _save_changes(rows)
    return {"ok": True, "marked": hit}

# ------------------------------------------------------------------------ fetching


def fetch(url: str) -> tuple[str | None, str | None]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"})
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            raw = response.read(MAX_BYTES)
            charset = response.headers.get_content_charset() or "utf-8"
            return raw.decode(charset, errors="replace"), None
    except urllib.error.HTTPError as err:
        return None, f"HTTP {err.code}"
    except Exception as err:
        return None, f"{type(err).__name__}: {err}"[:200]


def run(only: list[str] | None = None) -> dict[str, Any]:
    rows = pages()
    snap_dir = store.data_dir() / "watch_snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    queue = changes(include_processed=True)
    next_change = max([int(c["id"][1:]) for c in queue if c["id"][1:].isdigit()] + [0]) + 1
    last_host_visit: dict[str, float] = {}
    summary = {"checked": 0, "changed": 0, "failed": 0, "needs_browser": 0, "new_lines": 0}

    for page in rows:
        if only and page["id"] not in only:
            continue
        host = urlsplit(page["url"]).hostname or ""
        wait = 1.5 - (time.monotonic() - last_host_visit.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        html, error = fetch(page["url"])
        last_host_visit[host] = time.monotonic()
        page["last_checked"] = store.now_iso()
        summary["checked"] += 1
        if error:
            page["failures"] = page.get("failures", 0) + 1
            page["last_error"] = error
            if page["failures"] >= 2 or "CERTIFICATE" in error or error.startswith("HTTP 403"):
                page["needs_browser"] = True
            summary["failed"] += 1
            continue
        page["failures"] = 0
        page["last_error"] = None
        lines = extract_lines(html, page["url"])
        snap = snap_dir / f"{page['id']}.txt"
        previous = snap.read_text(encoding="utf-8").splitlines() if snap.exists() else None
        snap.write_text("\n".join(lines), encoding="utf-8")
        if previous is None:
            first = page["kind"] in ("portal_search", "funding_page")
            added = [l for l in lines if l.startswith("LINK:")][:200] if first else []
            removed = 0
        else:
            old = set(previous)
            added = [l for l in lines if l not in old and not VOLATILE.search(l)]
            removed = len(old - set(lines))
        if previous is not None and not added:
            continue
        if previous is None and not added:
            continue
        queue.append({"id": f"c{next_change}", "page_id": page["id"], "url": page["url"],
                      "label": page["label"], "kind": page["kind"], "opp_id": page.get("opp_id"),
                      "detected": store.now_iso(), "first_run": previous is None,
                      "added_lines": added[:200], "removed_count": removed, "processed": None})
        next_change += 1
        summary["changed"] += 1
        summary["new_lines"] += len(added)

    summary["needs_browser"] = sum(1 for p in rows if p.get("needs_browser"))
    _save_pages(rows)
    _save_changes(queue)
    store.save_json(store.data_file("watch_last_run.json"), {"at": store.now_iso(), **summary})
    return {"ok": True, **summary, "pending_changes": len([c for c in queue if not c.get("processed")])}


def last_run() -> dict[str, Any] | None:
    return store.load_json(store.data_file("watch_last_run.json"), None)

# --------------------------------------------------------------------------- inbox


def _inbox_path():
    return store.data_file("inbox.json")


def inbox(include_done: bool = False) -> list[dict[str, Any]]:
    rows = (store.load_json(_inbox_path(), {}) or {}).get("links", [])
    return rows if include_done else [r for r in rows if r.get("status") == "queued"]


def inbox_add(url: str, note: str = "") -> dict[str, Any]:
    url = url.strip()
    if not _valid_url(url):
        return {"ok": False, "error": "paste a full https:// link"}
    rows = inbox(include_done=True)
    if any(r["url"] == url and r["status"] == "queued" for r in rows):
        return {"ok": True, "note": "already queued"}
    link_id = f"l{max([int(r['id'][1:]) for r in rows] + [0]) + 1}"
    rows.append({"id": link_id, "url": url, "note": note[:500], "added": store.now_iso(),
                 "status": "queued", "result": None})
    store.save_json(_inbox_path(), {"links": rows})
    return {"ok": True, "id": link_id}


def inbox_mark(link_id: str, status: str, result: str = "") -> dict[str, Any]:
    if status not in ("queued", "processed", "rejected", "removed"):
        return {"ok": False, "error": "status must be queued, processed, rejected or removed"}
    rows = inbox(include_done=True)
    hit = next((r for r in rows if r["id"] == link_id), None)
    if not hit:
        return {"ok": False, "error": f"no link {link_id}"}
    hit["status"] = status
    hit["result"] = result[:500]
    hit["updated"] = store.now_iso()
    store.save_json(_inbox_path(), {"links": rows})
    return {"ok": True}
