"""Registry of official sources, PhD job portals, admission portals and discovery sites."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

PATH = Path(__file__).with_name("registry.json")
USER_AGENT = "scholar-registry-check/0.1 (personal scholarship tracker)"

# Two-part public suffixes common among our sources. Good enough to compare sponsor domains.
_MULTI_SUFFIX = {
    "co.uk", "ac.uk", "gov.uk", "org.uk", "com.au", "edu.au", "gov.au", "org.au", "net.au",
    "gc.ca", "gouv.qc.ca", "co.nz", "ac.nz", "govt.nz", "gov.pl", "admin.ch", "ec.europa.eu",
    "edu.pk", "gov.pk", "ac.in", "gov.in", "edu.cn", "ac.jp",
}

FIELD_TAGS = {
    "health": ["medic", "health", "nursing", "pharma", "clinical", "epidemiol", "biomed", "dent"],
    "life_sciences": ["biolog", "life science", "biochem", "genetic", "neuro", "biotech",
                      "ecolog", "molecular", "microbio", "bioinformatic"],
    "natural_sciences_engineering": ["engineer", "physics", "chemistry", "computer", "comput",
                                     "math", "statistic", "data", "artificial intelligence",
                                     " ai", "machine learning", "geolog", "environment",
                                     "earth", "software", "electr", "mechan", "civil"],
    "social_sciences_humanities": ["econom", "politic", "sociolog", "psycholog", "history",
                                   "law", "humanit", "literature", "education", "anthropolog",
                                   "philosoph", "social", "linguist", "art", "business",
                                   "management", "geograph", "public policy", "development"],
}


@lru_cache(maxsize=1)
def load() -> dict[str, Any]:
    return json.loads(PATH.read_text(encoding="utf-8"))


def host_of(url: str) -> str:
    host = (urlsplit(str(url)).hostname or "").casefold()
    return host[4:] if host.startswith("www.") else host


def host_matches(host: str, domain: str) -> bool:
    domain = domain.casefold()
    return host == domain or host.endswith("." + domain)


def base_domain(host: str) -> str:
    parts = host.split(".")
    for size in (3, 2):
        if len(parts) > size and ".".join(parts[-size:]) in _MULTI_SUFFIX:
            return ".".join(parts[-(size + 1):])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def same_site(a: str, b: str) -> bool:
    return bool(a and b) and base_domain(a) == base_domain(b)


def find_source(host: str) -> dict[str, Any] | None:
    for entry in load()["sources"]:
        if any(host_matches(host, d) for d in entry["domains"]):
            return entry
    return None


def find_job_portal(host: str) -> dict[str, Any] | None:
    for entry in load()["job_portals"]:
        if any(host_matches(host, d) for d in entry["domains"]):
            return entry
    return None


def find_admission_portal(host: str) -> dict[str, Any] | None:
    for entry in load()["admission_portals"]:
        if any(host_matches(host, d) for d in entry["domains"]):
            return entry
    return None


def is_discovery(host: str) -> bool:
    return any(host_matches(host, d) for d in load()["discovery_domains"])


def field_tags(fields: Iterable[str]) -> set[str]:
    text = " " + " ".join(f.casefold() for f in fields) + " "
    return {tag for tag, words in FIELD_TAGS.items() if any(w in text for w in words)}


def sources_for(regions: Iterable[str] | None = None, levels: Iterable[str] | None = None,
                fields: Iterable[str] | None = None) -> list[dict[str, Any]]:
    regions = set(regions or [])
    levels = set(levels or [])
    tags = field_tags(fields or [])
    out = []
    for entry in load()["sources"]:
        if regions and entry["region"] not in regions:
            continue
        if levels and not levels & set(entry.get("levels", [])):
            continue
        restricted = set(entry.get("fields", []))
        if restricted and tags and not restricted & tags:
            continue
        out.append(entry)
    return out


def _probe(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            final = response.geturl()
            return {"url": url, "status": response.status, "final_url": final,
                    "seconds": round(time.monotonic() - started, 1)}
    except urllib.error.HTTPError as err:
        return {"url": url, "status": err.code, "error": f"HTTP {err.code}"}
    except Exception as err:  # DNS, TLS, timeout
        return {"url": url, "status": None, "error": f"{type(err).__name__}: {err}"[:200]}


def check(workers: int = 8) -> dict[str, Any]:
    """Probe every registry URL. 401/403/429 count as reachable (bot protection)."""
    data = load()
    entries = [(e["name"], e["url"], e["domains"]) for e in
               data["sources"] + data["job_portals"] + data["admission_portals"]]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda item: _probe(item[1]), entries))
    # Parallel probing can trip local DNS limits; retry failures one at a time.
    for index, result in enumerate(results):
        if result.get("status") is None and "CERTIFICATE" not in result.get("error", ""):
            results[index] = _probe(entries[index][1])
    ok, blocked, broken, moved, browser_only = [], [], [], [], []
    for (name, url, domains), result in zip(entries, results):
        result["name"] = name
        status = result.get("status")
        if status is None and ("CERTIFICATE" in result.get("error", "") or "timed out" in result.get("error", "")):
            browser_only.append(result)  # real browsers cope; Python's TLS store or bot filters don't
            continue
        if status and 200 <= status < 400:
            final_host = host_of(result.get("final_url", url))
            if not any(host_matches(final_host, d) for d in domains):
                result["warning"] = f"redirected off-domain to {final_host}"
                moved.append(result)
            else:
                ok.append(result)
        elif status in (401, 403, 429, 503):
            blocked.append(result)
        else:
            broken.append(result)
    return {"ok": True, "checked": len(entries), "reachable": len(ok),
            "bot_protected": [r["name"] for r in blocked],
            "browser_only": [{"name": r["name"], "error": r.get("error")} for r in browser_only],
            "redirected_off_domain": moved, "broken": broken}
