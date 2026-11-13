"""Opportunity records (scholarships, funded programmes, PhD positions) and their evaluation.

Claude reads official pages and writes records; this module validates them and decides,
deterministically, whether each one fits the applicant. No model is involved here.
"""
from __future__ import annotations

import copy
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from . import countries, profile as prof, registry, store

TYPES = ["scholarship", "admission_funding", "phd_position", "nomination_fellowship"]
SOURCE_KINDS = ["official", "authorized_administrator", "discovery"]
DEADLINE_TYPES = ["fixed", "rolling", "unknown", "closed", "not_open"]
METHODS = ["web_form", "university_portal", "job_portal", "admission_portal", "email", "pdf",
           "nomination", "unknown"]
BASES = ["open", "citizenship", "residence", "citizenship_and_residence", "citizenship_or_residence"]
DUAL_POLICIES = ["any_eligible", "all_must_be_eligible"]
OPS = ["eq", "neq", "in", "not_in", "contains", "contains_any", "gte", "lte", "truthy", "falsy"]
BUCKETS = ["eligible", "needs_confirmation", "upcoming", "near_miss", "ineligible", "expired",
           "unverified", "rejected"]
AGENT_METHODS = {"web_form", "university_portal", "job_portal", "admission_portal"}
STALE_DAYS = 14
APPLY_FRESH_DAYS = 7

# --------------------------------------------------------------------------- storage


def path():
    return store.data_file("opportunities.json")


def load_all() -> dict[str, dict[str, Any]]:
    data = store.load_json(path(), None) or {"version": 1, "items": {}}
    return data.get("items", {})


def save_all(items: dict[str, dict[str, Any]]) -> None:
    store.save_json(path(), {"version": 1, "items": items})


def find(items: dict[str, dict[str, Any]], key: str) -> dict[str, Any] | None:
    if key in items:
        return items[key]
    matches = [v for k, v in items.items() if k.startswith(key)]
    return matches[0] if len(matches) == 1 else None


def make_id(sponsor: str, title: str) -> str:
    return f"{store.slug(f'{sponsor} {title}', 40)}-{store.text_hash(f'{sponsor}|{title}'.casefold())[:6]}"

# ------------------------------------------------------------------------ validation


def _https(value: Any, field: str, errors: list[str], required: bool = False) -> str | None:
    if value in (None, ""):
        if required:
            errors.append(f"{field} is required")
        return None
    text = str(value).strip()
    if not text.startswith("https://") or any(c.isspace() for c in text):
        errors.append(f"{field} must be an https:// URL without spaces")
        return None
    return text


def _bool_or_none(value: Any, field: str, errors: list[str]) -> bool | None:
    if value is None or isinstance(value, bool):
        return value
    errors.append(f"{field} must be true, false or null")
    return None


def source_proof(rec: dict[str, Any]) -> tuple[str | None, str | None]:
    host = registry.host_of(rec.get("official_url", ""))
    kind = rec.get("source_kind")
    if kind == "discovery":
        return "discovery", None
    if registry.is_discovery(host):
        return None, ("official_url is on a listing/aggregator site. Find the sponsor's own page, "
                      "or store it with source_kind 'discovery' as a lead.")
    if registry.find_source(host):
        return "registry", None
    if registry.find_job_portal(host):
        return "job_portal", None
    authority = rec.get("authority_url")
    if not authority:
        return None, ("official_url is not on a registered domain: add authority_url, a page on "
                      "the sponsor's own site showing it runs this programme.")
    ahost = registry.host_of(authority)
    if registry.is_discovery(ahost):
        return None, "authority_url cannot be a listing/aggregator site"
    if kind == "official":
        if registry.same_site(host, ahost):
            return "sponsor_domain", None
        return None, "for an official record, authority_url must be on the same site as official_url"
    if kind == "authorized_administrator":
        if not registry.same_site(host, ahost):
            return "authorized_by_sponsor", None
        return None, "authority_url must be on the sponsor's own (different) site and name the administrator"
    return None, "unknown source_kind"


def _validate_country_rule(raw: Any, errors: list[str]) -> dict[str, Any] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        errors.append("country_rule must be an object")
        return None
    rule = dict(raw)
    if rule.get("basis") not in BASES:
        errors.append(f"country_rule.basis must be one of {BASES}")
    for key in ("include", "exclude"):
        values = rule.get(key) or []
        if not isinstance(values, list):
            errors.append(f"country_rule.{key} must be a list")
            continue
        _, unknown = countries.expand(values)
        if unknown:
            errors.append(f"country_rule.{key} has unrecognised names: {unknown}. Use country "
                          "names or groups @eu @eea @eu_eea_ch @efta @nordic.")
        rule[key] = values
    if rule.get("dual_citizenship") not in (None, *DUAL_POLICIES):
        errors.append(f"country_rule.dual_citizenship must be null or one of {DUAL_POLICIES}")
    statuses = rule.get("residence_statuses")
    if statuses is not None and (not isinstance(statuses, list) or
                                 any(s not in prof.RESIDENCE_STATUS for s in statuses)):
        errors.append(f"country_rule.residence_statuses must list values from {prof.RESIDENCE_STATUS}")
    host_res = rule.get("host_residence")
    if host_res is not None:
        if not isinstance(host_res, dict) or not isinstance(host_res.get("max_months"), (int, float)) \
                or not isinstance(host_res.get("within_years"), (int, float)):
            errors.append("country_rule.host_residence needs numeric max_months and within_years")
    if rule.get("list_url"):
        rule["list_url"] = _https(rule["list_url"], "country_rule.list_url", errors)
    if not rule.get("quote"):
        errors.append("country_rule.quote is required: copy the sponsor's eligibility wording")
    return rule


def _validate_requirements(raw: Any, errors: list[str]) -> list[dict[str, Any]]:
    if raw in (None, []):
        return []
    if not isinstance(raw, list):
        errors.append("requirements must be a list")
        return []
    out = []
    for index, req in enumerate(raw):
        if not isinstance(req, dict):
            errors.append(f"requirements[{index}] must be an object")
            continue
        field, op = req.get("field"), req.get("op")
        if not field or not prof.is_known_fact(field):
            errors.append(f"requirements[{index}].field '{field}' is not a profile key or derived fact")
        if op not in OPS:
            errors.append(f"requirements[{index}].op must be one of {OPS}")
        if op not in ("truthy", "falsy") and "value" not in req:
            errors.append(f"requirements[{index}] needs a value")
        if not req.get("text"):
            errors.append(f"requirements[{index}].text is required (the sponsor's wording)")
        out.append({"field": field, "op": op, "value": req.get("value"), "text": req.get("text", ""),
                    "hard": bool(req.get("hard", True)), "fixable": bool(req.get("fixable", False))})
    return out


def _validate_questions(raw: Any, errors: list[str]) -> list[dict[str, Any]]:
    out = []
    for index, q in enumerate(raw or []):
        if isinstance(q, str):
            q = {"prompt": q}
        if not isinstance(q, dict) or not q.get("prompt"):
            errors.append(f"application.questions[{index}] needs a prompt")
            continue
        unit = q.get("unit") or "words"
        if unit not in ("words", "characters"):
            errors.append(f"application.questions[{index}].unit must be words or characters")
        limit = q.get("limit")
        if limit is not None and not isinstance(limit, int):
            errors.append(f"application.questions[{index}].limit must be a whole number or null")
        out.append({"qid": q.get("qid") or f"q{index + 1}", "prompt": str(q["prompt"]).strip(),
                    "limit": limit, "unit": unit, "category": q.get("category"),
                    "required": q.get("required", True)})
    return out


def validate(raw: dict[str, Any], today: date | None = None) -> tuple[dict[str, Any], list[str], list[str]]:
    """Return (clean record, errors, warnings)."""
    today = today or store.today()
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(raw, dict):
        return {}, ["record must be a JSON object"], []
    rec: dict[str, Any] = copy.deepcopy(raw)

    for field in ("title", "sponsor"):
        if not str(rec.get(field, "")).strip():
            errors.append(f"{field} is required")
        rec[field] = str(rec.get(field, "")).strip()
    if rec.get("type") not in TYPES:
        errors.append(f"type must be one of {TYPES}")
    levels = rec.get("levels")
    if not isinstance(levels, list) or not levels or any(l not in prof.LEVELS for l in levels):
        errors.append(f"levels must be a non-empty list from {prof.LEVELS}")
    if rec.get("region") not in prof.REGIONS:
        errors.append(f"region must be one of {prof.REGIONS}")
    hosts = rec.get("host_countries")
    if not isinstance(hosts, list) or not hosts:
        errors.append("host_countries must be a non-empty list")
    else:
        for name in hosts:
            if name not in ("Multiple", "European Union", "Nordic") and not countries.canonical(name):
                warnings.append(f"host country '{name}' not recognised")
    if rec.get("source_kind") not in SOURCE_KINDS:
        errors.append(f"source_kind must be one of {SOURCE_KINDS}")
    rec["official_url"] = _https(rec.get("official_url"), "official_url", errors, required=True)
    rec["apply_url"] = _https(rec.get("apply_url"), "apply_url", errors)
    rec["authority_url"] = _https(rec.get("authority_url"), "authority_url", errors)

    verified = store.parse_date(rec.get("verified_at"))
    if not verified:
        errors.append("verified_at (YYYY-MM-DD, the day you read the official page) is required")
    elif verified > today:
        errors.append("verified_at cannot be in the future")

    deadline = rec.get("deadline") or {}
    if deadline.get("type") not in DEADLINE_TYPES:
        errors.append(f"deadline.type must be one of {DEADLINE_TYPES}")
    if deadline.get("date") and not store.parse_date(deadline["date"]):
        errors.append("deadline.date must be YYYY-MM-DD")
    if deadline.get("type") == "fixed" and not deadline.get("date"):
        errors.append("a fixed deadline needs deadline.date")
    if deadline.get("timezone"):
        try:
            ZoneInfo(deadline["timezone"])
        except Exception:
            if tz_data_available():
                errors.append(f"deadline.timezone '{deadline['timezone']}' is not an IANA zone like Europe/Oslo")
            else:
                errors.append(f"deadline.timezone: {TZDATA_HINT}")
    if deadline.get("opens") and not store.parse_date(deadline["opens"]):
        errors.append("deadline.opens must be YYYY-MM-DD")
    rec["deadline"] = deadline

    for block in ("admission", "internal_deadline"):
        part = rec.get(block)
        if part is None:
            continue
        if not isinstance(part, dict):
            errors.append(f"{block} must be an object")
            continue
        key = "deadline" if block == "admission" else "date"
        if part.get(key) and not store.parse_date(part[key]):
            errors.append(f"{block}.{key} must be YYYY-MM-DD")
        if block == "admission" and part.get("url"):
            part["url"] = _https(part["url"], "admission.url", errors)

    fees = rec.get("fees") or {}
    rec["fees"] = {k: _bool_or_none(fees.get(k), f"fees.{k}", errors)
                   for k in ("scholarship_fee", "is_loan", "is_lottery", "application_fee")}
    # application_fee: anything the applicant pays to apply (university application, admission
    # portal, handling fee). Normal and paid by the applicant, unlike a scholarship fee.
    for key in ("application_fee_amount", "application_fee_note"):
        value = fees.get(key)
        if value in (None, ""):
            rec["fees"][key] = None
        elif not isinstance(value, str) or len(value) > 200:
            errors.append(f"fees.{key} must be a short text (max 200 characters)")
            rec["fees"][key] = None
        else:
            rec["fees"][key] = value.strip()

    amount = rec.get("amount") or {}
    if not isinstance(amount, dict):
        errors.append("amount must be an object")
        amount = {}
    for flag in ("full_funding", "covers_tuition", "stipend"):
        amount[flag] = _bool_or_none(amount.get(flag), f"amount.{flag}", errors)
    rec["amount"] = amount

    if rec.get("source_kind") != "discovery":
        if rec.get("country_rule") is None:
            errors.append("country_rule is required for official records (use basis 'open' when "
                          "any nationality may apply, and quote the page)")
    rec["country_rule"] = _validate_country_rule(rec.get("country_rule"), errors)
    rec["requirements"] = _validate_requirements(rec.get("requirements"), errors)

    application = rec.get("application") or {}
    if application.get("method") not in METHODS:
        errors.append(f"application.method must be one of {METHODS}")
    application["questions"] = _validate_questions(application.get("questions"), errors)
    docs = application.get("documents") or []
    if not isinstance(docs, list):
        errors.append("application.documents must be a list")
        docs = []
    application["documents"] = docs
    refs = application.get("references")
    if refs is not None and not isinstance(refs, int):
        errors.append("application.references must be a whole number or null")
    rec["application"] = application

    for key in ("uncertainties", "obligations", "fields"):
        value = rec.get(key) or []
        if not isinstance(value, list):
            errors.append(f"{key} must be a list")
            value = []
        rec[key] = [str(v) for v in value]

    if rec.get("source_kind") in ("official", "authorized_administrator") and rec.get("official_url"):
        proof, problem = source_proof(rec)
        if problem:
            errors.append(problem)
        rec["source_proof"] = proof
    else:
        rec["source_proof"] = "discovery"

    for key in ("evidence",):
        if rec.get(key) is not None and not isinstance(rec[key], dict):
            errors.append(f"{key} must be an object")

    for text_field in ("title", "sponsor", "notes"):
        reason = prof.sensitive_reason(str(rec.get(text_field) or ""))
        if reason:
            errors.append(f"{text_field} {reason}")

    if not errors:
        rec["id"] = rec.get("id") or make_id(rec["sponsor"], rec["title"])
    return rec, errors, warnings


def add(raws: list[dict[str, Any]], today: date | None = None) -> dict[str, Any]:
    items = load_all()
    results = []
    for raw in raws:
        rec, errors, warnings = validate(raw, today)
        if errors:
            results.append({"ok": False, "title": raw.get("title") if isinstance(raw, dict) else None,
                            "errors": errors, "warnings": warnings})
            continue
        existing = items.get(rec["id"])
        rec["first_seen"] = existing.get("first_seen") if existing else store.now_iso()
        rec["last_updated"] = store.now_iso()
        items[rec["id"]] = rec
        results.append({"ok": True, "id": rec["id"], "updated": bool(existing), "warnings": warnings})
    save_all(items)
    return {"ok": all(r["ok"] for r in results), "results": results}


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def patch(opp_id: str, changes: dict[str, Any], today: date | None = None) -> dict[str, Any]:
    items = load_all()
    rec = find(items, opp_id)
    if not rec:
        return {"ok": False, "error": f"no opportunity '{opp_id}'"}
    merged = _deep_merge(rec, changes)
    merged["id"] = rec["id"]
    clean, errors, warnings = validate(merged, today)
    if errors:
        return {"ok": False, "errors": errors}
    clean["first_seen"] = rec.get("first_seen")
    clean["last_updated"] = store.now_iso()
    items[rec["id"]] = clean
    save_all(items)
    return {"ok": True, "id": rec["id"], "warnings": warnings}


def remove(opp_id: str) -> dict[str, Any]:
    items = load_all()
    rec = find(items, opp_id)
    if not rec:
        return {"ok": False, "error": f"no opportunity '{opp_id}'"}
    del items[rec["id"]]
    save_all(items)
    return {"ok": True, "removed": rec["id"]}

# ------------------------------------------------------------------------ evaluation


def _items(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [v for v in value if str(v).strip()]
    return [value]


def _norm(value: Any) -> str:
    text = " ".join(str(value).casefold().split())
    canon = countries.canonical(text)
    return canon or text


def evaluate_requirement(req: dict[str, Any], facts: dict[str, Any]) -> bool | None:
    value = facts.get(req["field"])
    op = req["op"]
    if value is None or value == "" or value == []:
        return None
    if op in ("truthy", "falsy"):
        truth = value if isinstance(value, bool) else str(value).casefold() in ("true", "yes", "1")
        return truth if op == "truthy" else not truth
    if op in ("gte", "lte"):
        try:
            number, expected = float(value), float(req["value"])
        except (TypeError, ValueError):
            return None
        return number >= expected if op == "gte" else number <= expected
    expected_raw = req["value"] if isinstance(req["value"], list) else [req["value"]]
    have = [_norm(v) for v in _items(value)]
    if op in ("contains", "contains_any"):
        terms = [str(t).casefold() for t in expected_raw]
        return any(t in h for h in have for t in terms)
    expanded, _ = countries.expand([v for v in expected_raw if str(v).startswith("@")])
    expected = {_norm(v) for v in expected_raw if not str(v).startswith("@")} | expanded
    hit = any(h in expected for h in have)
    if op in ("eq", "in"):
        return hit
    return not hit  # neq, not_in


def _passes(values: set[str], include: set[str], exclude: set[str]) -> bool:
    if include and not values & include:
        return False
    if exclude and values & exclude:
        return False
    return True


def check_country(rule: dict[str, Any] | None, profile: dict[str, Any], facts: dict[str, Any],
                  hosts: list[str], on: date) -> dict[str, Any]:
    out: dict[str, Any] = {"status": "unclear", "reasons": []}
    if not rule:
        out["reasons"].append("Country eligibility has not been recorded from the official page yet.")
        return out
    out["quote"] = rule.get("quote")
    out["list_url"] = rule.get("list_url")
    include, _ = countries.expand(rule.get("include") or [])
    exclude, _ = countries.expand(rule.get("exclude") or [])
    cits = {c for c in (countries.canonical(x) for x in facts.get("identity.citizenships") or []) if c}
    residence = countries.canonical(facts.get("identity.country_of_residence") or "")
    basis = rule.get("basis")

    def citizenship_result() -> bool | None:
        if not cits:
            out["reasons"].append("Add your citizenship(s) to the profile.")
            return None
        if len(cits) == 1:
            return _passes(cits, include, exclude)
        any_ok = any(_passes({c}, include, exclude) for c in cits)
        all_ok = all(_passes({c}, include, exclude) for c in cits)
        policy = rule.get("dual_citizenship")
        if any_ok == all_ok:
            return any_ok
        if policy == "any_eligible":
            return any_ok
        if policy == "all_must_be_eligible":
            return all_ok
        out["reasons"].append("You hold more than one citizenship and only some qualify; the page "
                              "does not say how dual citizens are treated. Ask the sponsor.")
        return None

    def residence_result() -> bool | None:
        if not residence:
            out["reasons"].append("Add your country of residence to the profile.")
            return None
        if not _passes({residence}, include, exclude):
            return False
        statuses = rule.get("residence_statuses")
        if statuses:
            status = facts.get("identity.residence_status")
            if not status:
                out["reasons"].append("Add your residence status (e.g. study permit, PR) to the profile.")
                return None
            return status in statuses
        return True

    if basis == "open":
        result: bool | None = True
    elif basis == "citizenship":
        result = citizenship_result()
    elif basis == "residence":
        result = residence_result()
    elif basis == "citizenship_and_residence":
        a, b = citizenship_result(), residence_result()
        result = False if False in (a, b) else (None if None in (a, b) else True)
    else:  # citizenship_or_residence
        a, b = citizenship_result(), residence_result()
        result = True if True in (a, b) else (None if None in (a, b) else False)

    host_rule = rule.get("host_residence")
    if result is not False and host_rule:
        for host in hosts:
            if not countries.canonical(host):
                continue
            months = prof.residence_months(profile, host, int(host_rule["within_years"]), on)
            if months is None:
                out["reasons"].append("Add where you have lived (residence history) to check the "
                                      "host-country residence rule.")
                if result is True:
                    result = None
                break
            if months > host_rule["max_months"]:
                out["reasons"].append(f"You lived in {host} {months} months in the last "
                                      f"{host_rule['within_years']} years; the limit is "
                                      f"{host_rule['max_months']}.")
                result = False
                break

    if result is True:
        out["status"] = "eligible"
    elif result is False:
        out["status"] = "ineligible"
        if not out["reasons"]:
            basis_text = {"citizenship": "citizenship", "residence": "country of residence"}.get(basis, basis)
            out["reasons"].append(f"Your {basis_text} is not covered by the sponsor's country rule.")
    return out


TZDATA_HINT = ("time zone data is missing on this computer, so deadlines can't be checked in the sponsor's "
               "time zone. Run: python -m pip install tzdata  (needed on Windows; Mac and Linux have it built in)")


def tz_data_available() -> bool:
    """zoneinfo reads the system's time zone files; Windows has none, so it needs the tzdata package."""
    try:
        ZoneInfo("Europe/London")
        return True
    except Exception:
        return False


def _local_today(timezone_name: str | None, now: datetime) -> date:
    if timezone_name:
        try:
            return now.astimezone(ZoneInfo(timezone_name)).date()
        except Exception:
            pass
    return now.astimezone().date()


def evaluate(rec: dict[str, Any], profile: dict[str, Any], now: datetime | None = None,
             facts: dict[str, Any] | None = None) -> dict[str, Any]:
    now = now or datetime.now().astimezone()
    today = now.astimezone().date()
    facts = facts if facts is not None else prof.facts(profile, today)
    reasons: list[str] = []
    open_items: list[str] = []
    gaps: list[str] = []

    # Scope: what the applicant asked to see.
    scope_notes = []
    regions = facts.get("target.regions") or []
    if regions and rec.get("region") not in regions:
        scope_notes.append("outside your selected regions")
    excluded = {countries.canonical(c) for c in facts.get("target.countries_exclude") or []}
    if excluded & {countries.canonical(h) for h in rec.get("host_countries", [])}:
        scope_notes.append("in a country you excluded")
    if facts.get("target.full_funding_only") and rec.get("amount", {}).get("full_funding") is False:
        scope_notes.append("not fully funded")

    # Deadlines.
    dl = rec.get("deadline", {})
    dl_date = store.parse_date(dl.get("date"))
    local = _local_today(dl.get("timezone"), now)
    days_left = (dl_date - local).days if dl_date else None
    admission = rec.get("admission") or {}
    adm_date = store.parse_date(admission.get("deadline"))
    adm_days = (adm_date - today).days if adm_date else None
    internal = rec.get("internal_deadline") or {}
    int_date = store.parse_date(internal.get("date"))
    int_days = (int_date - today).days if int_date else None

    # Requirements.
    req_results = []
    hard_fail_fixed, hard_fail_fixable, unknown = [], [], []
    level_ok = None
    wanted = set(facts.get("target.levels") or [])
    if wanted:
        level_ok = bool(wanted & set(rec.get("levels", [])))
    for req in rec.get("requirements", []):
        result = evaluate_requirement(req, facts)
        label = "pass" if result else ("unknown" if result is None else "fail")
        req_results.append({**req, "result": label})
        if not req["hard"]:
            continue
        if result is False:
            (hard_fail_fixable if req["fixable"] else hard_fail_fixed).append(req["text"])
        elif result is None:
            unknown.append(req["text"])

    country = check_country(rec.get("country_rule"), profile, facts, rec.get("host_countries", []), today)
    fees = rec.get("fees", {})
    verified = store.parse_date(rec.get("verified_at"))
    verified_days = (today - verified).days if verified else None

    # Classification, most decisive first.
    if fees.get("scholarship_fee") or fees.get("is_loan") or fees.get("is_lottery"):
        bucket = "rejected"
        if fees.get("scholarship_fee"):
            reasons.append("Charges a fee to apply for the scholarship (a common scam sign).")
        if fees.get("is_loan"):
            reasons.append("It is a loan, not a scholarship.")
        if fees.get("is_lottery"):
            reasons.append("It is a draw / sweepstakes.")
    elif rec.get("source_kind") == "discovery":
        bucket = "unverified"
        reasons.append("Only seen on a listing site; not yet confirmed on the sponsor's own page.")
    elif dl.get("type") == "closed" or (days_left is not None and days_left < 0):
        bucket = "expired"
        reasons.append("The deadline has passed." if dl.get("type") != "closed"
                       else "The sponsor says applications are closed.")
    elif admission.get("required") and adm_days is not None and adm_days < 0:
        bucket = "expired"
        reasons.append("The admission deadline that this funding depends on has passed.")
    elif country["status"] == "ineligible" or level_ok is False or hard_fail_fixed:
        bucket = "ineligible"
        if country["status"] == "ineligible":
            reasons.extend(country["reasons"])
        if level_ok is False:
            reasons.append(f"Offered for {', '.join(rec.get('levels', []))}, not your target level.")
        reasons.extend(f"Fails: {text}" for text in hard_fail_fixed)
    elif hard_fail_fixable:
        bucket = "near_miss"
        gaps.extend(hard_fail_fixable)
    elif dl.get("type") == "not_open":
        bucket = "upcoming"
        reasons.append("Not open yet" + (f"; opens {dl['opens']}." if dl.get("opens") else "."))
    else:
        if country["status"] == "unclear":
            open_items.extend(country["reasons"] or ["Country eligibility is unclear."])
        open_items.extend(f"Can't check yet: {text}" for text in unknown)
        open_items.extend(f"Sponsor detail unclear: {u}" for u in rec.get("uncertainties", []))
        for key, label in (("scholarship_fee", "that there is no fee to apply for the scholarship"),
                           ("is_loan", "that it is not a loan"),
                           ("is_lottery", "that it is not a draw")):
            if fees.get(key) is None:
                open_items.append(f"Confirm {label}.")
        if dl.get("type") in ("unknown", "rolling") and not dl_date:
            open_items.append("No firm deadline published.")
        if level_ok is None:
            open_items.append("Set your target levels in the profile.")
        bucket = "needs_confirmation" if open_items else "eligible"

    if bucket not in ("rejected", "unverified", "expired") and dl_date and not dl.get("timezone"):
        open_items.append("Deadline time zone not stated; treat it as the sponsor's local time.")
    stale = verified_days is not None and verified_days > STALE_DAYS
    if stale and bucket in ("eligible", "needs_confirmation", "upcoming", "near_miss"):
        open_items.append(f"Last checked {verified_days} days ago; re-verify before applying.")

    method = rec.get("application", {}).get("method")
    if bucket not in ("eligible", "needs_confirmation"):
        apply_mode = "none"
    elif rec.get("type") == "nomination_fellowship" or method == "nomination":
        apply_mode = "nomination"
    elif method in AGENT_METHODS and rec.get("apply_url"):
        apply_mode = "agent"
    elif method in ("email", "pdf"):
        apply_mode = "manual"
    else:
        apply_mode = "unknown"

    return {
        "bucket": bucket,
        "reasons": reasons,
        "open_items": open_items,
        "gaps": gaps,
        "country": country,
        "requirements": req_results,
        "in_scope": not scope_notes,
        "scope_notes": scope_notes,
        "deadline": {"date": dl.get("date"), "type": dl.get("type"), "timezone": dl.get("timezone"),
                     "days_left": days_left, "opens": dl.get("opens")},
        "admission": {"required": bool(admission.get("required")), "deadline": admission.get("deadline"),
                      "days_left": adm_days, "url": admission.get("url"),
                      "fee_note": admission.get("fee_note")},
        "internal_deadline": {"date": internal.get("date"), "days_left": int_days,
                              "note": internal.get("note")},
        "verified_days_ago": verified_days,
        "fresh_for_apply": verified_days is not None and verified_days <= APPLY_FRESH_DAYS,
        "apply_mode": apply_mode,
        "fee": application_fee(rec),
    }


def application_fee(rec: dict[str, Any]) -> dict[str, Any]:
    """'fee' / 'no_fee' / 'unknown' for what the applicant pays to apply, for labels."""
    fees = rec.get("fees") or {}
    flag = fees.get("application_fee")
    status = "fee" if flag is True else "no_fee" if flag is False else "unknown"
    note = fees.get("application_fee_note") or (rec.get("admission") or {}).get("fee_note")
    return {"status": status, "amount": fees.get("application_fee_amount"), "note": note}


def evaluate_all(profile: dict[str, Any], items: dict[str, dict[str, Any]] | None = None,
                 now: datetime | None = None) -> list[dict[str, Any]]:
    items = load_all() if items is None else items
    now = now or datetime.now().astimezone()
    facts = prof.facts(profile, now.astimezone().date())
    out = [{"id": rid, "record": rec, "evaluation": evaluate(rec, profile, now, facts)}
           for rid, rec in items.items()]
    order = {b: i for i, b in enumerate(BUCKETS)}
    out.sort(key=lambda e: (order[e["evaluation"]["bucket"]],
                            e["evaluation"]["deadline"]["days_left"]
                            if e["evaluation"]["deadline"]["days_left"] is not None else 10**6,
                            e["record"]["title"]))
    return out


def template() -> dict[str, Any]:
    """An annotated example record for Claude to copy."""
    return {
        "title": "Example Government Scholarship for International Master's Students",
        "sponsor": "Example Agency",
        "type": "scholarship  (scholarship | admission_funding | phd_position | nomination_fellowship)",
        "levels": ["masters"],
        "region": "scandinavia  (europe | north_america | australia | scandinavia)",
        "host_countries": ["Sweden"],
        "fields": ["any"],
        "source_kind": "official  (official | authorized_administrator | discovery)",
        "official_url": "https://sponsor.example/scholarship-page",
        "apply_url": "https://sponsor.example/apply",
        "authority_url": "null unless the domain is not in the registry; then a sponsor page proving ownership",
        "verified_at": "YYYY-MM-DD (today, when you read the page)",
        "amount": {"text": "Tuition fees + SEK 12,000/month living allowance (copy wording)",
                   "full_funding": True, "covers_tuition": True, "stipend": True},
        "deadline": {"type": "fixed  (fixed | rolling | unknown | closed | not_open)",
                     "date": "YYYY-MM-DD", "timezone": "Europe/Stockholm", "opens": None},
        "admission": {"required": True, "deadline": "YYYY-MM-DD", "url": "https://...",
                      "fee_note": "University application fee, paid by you"},
        "internal_deadline": {"date": None, "note": "University nomination deadline if any"},
        "country_rule": {
            "basis": "citizenship  (open | citizenship | residence | citizenship_and_residence | citizenship_or_residence)",
            "include": ["Pakistan", "India", "... exact list from the sponsor, or groups like @eu"],
            "exclude": ["@eea"],
            "dual_citizenship": "null | any_eligible | all_must_be_eligible (only if the page says)",
            "residence_statuses": None,
            "host_residence": {"max_months": 12, "within_years": 5},
            "quote": "Exact eligibility sentence from the official page",
            "list_url": "https://sponsor.example/eligible-countries",
        },
        "requirements": [
            {"field": "derived.score.ielts", "op": "gte", "value": 6.5, "hard": True, "fixable": True,
             "text": "IELTS Academic 6.5 overall"},
            {"field": "derived.work_months", "op": "gte", "value": 24, "hard": True, "fixable": True,
             "text": "At least 2 years of work experience"},
            {"field": "derived.has_masters", "op": "falsy", "hard": True, "fixable": False,
             "text": "Must not already hold a master's degree"},
        ],
        "obligations": ["Return to home country for 2 years after the award (if stated)"],
        "fees": {"scholarship_fee": False, "is_loan": False, "is_lottery": False,
                 "application_fee": "true if you pay anything to apply (university application, admission "
                                    "portal, uni-assist), false only if the page says it's free, else null",
                 "application_fee_amount": "e.g. 'CAD 135' as written, or null",
                 "application_fee_note": "e.g. 'UBC graduate application fee; waivers for some countries'"},
        "application": {"method": "web_form  (web_form | university_portal | job_portal | admission_portal | email | pdf | nomination | unknown)",
                        "platform": "e.g. varbi, jobbnorge, universityadmissions, sponsor-portal",
                        "requires_account": True,
                        "documents": ["cv", "transcript", "language_certificate"],
                        "references": 2,
                        "questions": [{"prompt": "Describe your leadership experience", "limit": 300,
                                       "unit": "words", "category": "leadership"}]},
        "evidence": {"amount": "short quote", "deadline": "short quote", "eligibility": "short quote",
                     "application": "short quote"},
        "uncertainties": ["Real doubts only, e.g. 'Page lists 2026 dates; 2027 call not yet published'"],
        "notes": "Optional page-backed notes",
        "found_via": "discover | watch | link",
    }
