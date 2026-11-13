"""Weekly search plan for /discover, built from the profile and the source registry.

Queries never contain grades, test scores, names, birth dates or contact details.
Nationality is used only when the profile has consent.identity_search = yes.
"""
from __future__ import annotations

from datetime import date
from itertools import zip_longest
from typing import Any

from . import registry, store

COUNTRIES_BY_REGION = {
    "europe": ["United Kingdom", "Germany", "Netherlands", "France", "Switzerland", "Ireland",
               "Belgium", "Austria", "Italy", "Spain", "Poland", "Hungary"],
    "north_america": ["Canada", "United States"],
    "australia": ["Australia"],
    "scandinavia": ["Norway", "Sweden", "Denmark", "Finland", "Iceland"],
}
LEVEL_WORDS = {"masters": "master's", "phd": "PhD", "undergraduate": "undergraduate",
               "postdoc": "postdoctoral"}
PHD_JOB_COUNTRIES = {"Norway", "Sweden", "Denmark", "Finland", "Netherlands", "Switzerland",
                     "Belgium", "Germany", "Austria"}


def generate(profile: dict[str, Any], max_queries: int = 80, today: date | None = None) -> dict[str, Any]:
    today = today or store.today()
    values = profile["values"]
    levels = values.get("target.levels") or []
    regions = values.get("target.regions") or list(COUNTRIES_BY_REGION)
    fields = values.get("target.fields") or []
    keywords = values.get("target.keywords") or []
    start = values.get("target.start_term")
    year = int(start[:4]) if start else today.year + 1
    field = fields[0] if fields else ""
    topic = " ".join(x for x in [field, keywords[0] if keywords else ""] if x).strip()
    warnings = []
    if not levels:
        return {"ok": False, "error": "set target.levels in the profile first"}
    if not fields:
        warnings.append("No field of study set; queries will be generic.")

    by_region: dict[str, list[dict[str, Any]]] = {r: [] for r in regions}
    first: list[dict[str, Any]] = []

    def q(text: str, kind: str, region: str | None, priority: int, lead: bool = False, **extra: Any) -> None:
        """lead=True goes to the front (programmes, portals, your universities); the rest is
        interleaved region by region so every region gets coverage within the cap."""
        item = {"text": " ".join(text.split()), "kind": kind, "region": region, "priority": priority, **extra}
        (first if lead or region not in by_region else by_region[region]).append(item)

    level_words = [LEVEL_WORDS[l] for l in levels if l in LEVEL_WORDS]
    if "masters" in levels and "europe" in regions:
        q(f"Erasmus Mundus joint master {field} scholarship {year} intake", "programme", "europe", 1, lead=True)
    if "phd" in levels and ("europe" in regions or "scandinavia" in regions):
        q(f"Marie Sklodowska-Curie doctoral network PhD positions {topic} {year}", "programme", "europe", 1,
          lead=True)

    for source in registry.sources_for(regions, levels, fields):
        words = " ".join(LEVEL_WORDS[l] for l in levels if l in source.get("levels", []))
        if source["kind"] == "university":
            text = f"{source['name']} {words} scholarships funding international students {field} {year}"
        else:
            text = f"{source['name']} {words} scholarship {year} international applicants eligibility deadline"
        q(text, "registry", source["region"], 1, source=source["name"], domain=source["domains"][0])

    if "phd" in levels:
        for portal in registry.load()["job_portals"]:
            if portal["region"] in regions:
                q(f"{portal['name']} PhD research fellow {topic}", "phd_jobs", portal["region"], 1,
                  lead=True, domain=portal["domains"][0])

    for region in regions:
        for country in COUNTRIES_BY_REGION.get(region, []):
            for words in level_words:
                q(f"fully funded {words} scholarship {country} international students {field} {year}",
                  "country", region, 2, country=country)
            # Universities' own awards (tuition waiver + living allowance, excellence scholarships,
            # funded research degrees) are a large share of full funding and aren't in the registry.
            for words in level_words:
                q(f"university {words} excellence scholarship international students {country} {field} "
                  f"tuition waiver living allowance {year}", "university_scholarship", region, 2, country=country)
            if "phd" in levels and country in PHD_JOB_COUNTRIES:
                q(f"funded PhD position {topic} {country} {year} apply", "phd_jobs", region, 2, country=country)
        if "masters" in levels and region == "north_america":
            q(f"funded thesis-based master's {field} Canada stipend international students {year}",
              "research_masters", region, 2)
        if "phd" in levels and region == "north_america":
            q(f"{field} PhD fully funded international students admitted with bachelor's degree "
              f"United States Canada direct-entry {year}", "university", region, 2)
        if "masters" in levels and region == "australia":
            q(f"MPhil research master's scholarship {field} Australia international {year}",
              "research_masters", region, 2)

    for university in values.get("target.universities") or []:
        for words in level_words:
            q(f"{university} {words} funding scholarships international students {field}", "university", None, 1,
              lead=True)

    if values.get("consent.identity_search"):
        for citizenship in values.get("identity.citizenships") or []:
            for region in regions:
                hosts = ", ".join(COUNTRIES_BY_REGION.get(region, [])[:3])
                q(f"scholarships for students from {citizenship} {' '.join(level_words)} {hosts} {year}",
                  "identity", region, 2)
    elif values.get("identity.citizenships"):
        warnings.append("Nationality-specific searches skipped (consent.identity_search is not 'yes').")

    for region, items in by_region.items():
        # Within a region: two official-source queries, then one broader query, and so on.
        sources = [i for i in items if i["kind"] == "registry"]
        general = [i for i in items if i["kind"] != "registry"]
        mixed: list[dict[str, Any]] = []
        while sources or general:
            mixed.extend(sources[:2])
            sources = sources[2:]
            if general:
                mixed.append(general.pop(0))
        by_region[region] = mixed

    ordered = list(first)
    for group in zip_longest(*by_region.values()):
        ordered.extend(item for item in group if item)
    seen, out = set(), []
    for item in ordered:
        key = item["text"].casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
        if len(out) >= max_queries:
            break
    for index, item in enumerate(out, 1):
        item["id"] = f"q{index:03d}"
        item["done"] = False
    plan = {"generated": store.now_iso(), "queries": out, "warnings": warnings}
    store.save_json(store.data_file("queries.json"), plan)
    return {"ok": True, "count": len(out), "warnings": warnings}


def load() -> dict[str, Any]:
    return store.load_json(store.data_file("queries.json"), {"queries": []}) or {"queries": []}


def pending(limit: int = 10) -> list[dict[str, Any]]:
    return [q for q in load()["queries"] if not q.get("done")][:limit]


def mark_done(ids: list[str]) -> dict[str, Any]:
    plan = load()
    hit = 0
    for item in plan["queries"]:
        if item["id"] in ids:
            item["done"] = True
            hit += 1
    store.save_json(store.data_file("queries.json"), plan)
    remaining = sum(1 for item in plan["queries"] if not item.get("done"))
    return {"ok": True, "marked": hit, "remaining": remaining}
