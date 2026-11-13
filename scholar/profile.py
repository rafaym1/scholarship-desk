"""Applicant profile: schema, validation, sensitive-data refusal and derived facts.

The profile is stored in data/profile.json as flat dotted keys plus lists of rows.
Passwords, SIN/SSN, passport numbers, bank and card details are refused outright:
the person types those into forms themselves.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from . import countries, store

LEVELS = ["undergraduate", "masters", "phd", "postdoc"]
REGIONS = ["europe", "north_america", "australia", "scandinavia"]
RESIDENCE_STATUS = [
    "citizen", "permanent_resident", "study_permit", "work_permit", "visitor",
    "refugee_or_protected", "other",
]
DOC_TYPES = [
    "cv", "transcript", "degree_certificate", "language_certificate", "research_proposal",
    "writing_sample", "recommendation_letter", "portfolio", "photo", "publication",
    "cover_letter", "motivation_letter", "passport_scan", "id_document", "other",
]
# Identity documents are uploaded by the person, never by the agent.
HANDOFF_DOC_TYPES = {"passport_scan", "id_document"}

SYNONYMS = {
    "master": "masters", "msc": "masters", "ma": "masters", "mphil": "masters",
    "research_masters": "masters", "doctorate": "phd", "doctoral": "phd", "ph_d": "phd",
    "postdoctoral": "postdoc", "post_doc": "postdoc", "bachelor": "undergraduate",
    "bachelors": "undergraduate", "nordic": "scandinavia", "nordics": "scandinavia",
    "na": "north_america", "oceania": "australia", "pr": "permanent_resident",
    "student_visa": "study_permit", "student_permit": "study_permit",
}


def F(label: str, type: str = "text", **extra: Any) -> dict[str, Any]:
    return {"label": label, "type": type, **extra}


SCALARS: dict[str, dict[str, Any]] = {
    "identity.first_name": F("Given / first name"),
    "identity.middle_name": F("Middle name(s)"),
    "identity.last_name": F("Family / last name"),
    "identity.preferred_name": F("Preferred name"),
    "identity.date_of_birth": F("Date of birth (YYYY-MM-DD)", "date"),
    "identity.gender": F("Gender (optional)"),
    "identity.email": F("Email for applications", "email"),
    "identity.phone": F("Phone with country code", "phone"),
    "identity.address_line1": F("Street address"),
    "identity.address_line2": F("Address line 2"),
    "identity.city": F("City"),
    "identity.region": F("Province / state"),
    "identity.postal_code": F("Postal code"),
    "identity.address_country": F("Country of address", "country"),
    "identity.country_of_birth": F("Country of birth", "country"),
    "identity.citizenships": F("Every citizenship you hold", "country_list"),
    "identity.country_of_residence": F("Country you live in now", "country"),
    "identity.residence_status": F("Your status there", "choice", choices=RESIDENCE_STATUS),
    "identity.linkedin": F("LinkedIn URL", "url"),
    "identity.website": F("Website / Google Scholar URL", "url"),
    "target.levels": F("Levels you are applying for", "choice_list", choices=LEVELS),
    "target.fields": F("Fields of study", "list"),
    "target.keywords": F("Research / topic keywords", "list"),
    "target.start_term": F("Intended start (YYYY-MM)", "month"),
    "target.regions": F("Regions to search", "choice_list", choices=REGIONS),
    "target.countries_exclude": F("Countries you do not want", "country_list"),
    "target.universities": F("Universities you are targeting", "list"),
    "target.full_funding_only": F("Only show fully funded options?", "bool"),
    "target.research_interests": F("Research interests, in your words", "long_text"),
    "consent.identity_search": F("OK to use your nationality in web searches?", "bool"),
    "narrative.motivation": F("Why this field / degree (your words)", "long_text"),
    "narrative.career_goals": F("Career goals (your words)", "long_text"),
    "narrative.research_statement": F("Research experience and ideas", "long_text"),
    "narrative.leadership": F("Leadership examples", "long_text"),
    "narrative.challenge": F("A challenge you overcame", "long_text"),
    "narrative.impact": F("Impact on your community / home country", "long_text"),
    "narrative.other": F("Anything else worth telling funders", "long_text"),
}

_MONTH = "month"
LISTS: dict[str, dict[str, dict[str, Any]]] = {
    "residence": {
        "country": F("Country", "country", required=True),
        "from": F("From (YYYY-MM)", _MONTH, required=True),
        "to": F("To (YYYY-MM, blank = still there)", _MONTH),
        "status": F("Status", "choice", choices=RESIDENCE_STATUS),
    },
    "education": {
        "institution": F("Institution", required=True),
        "country": F("Country", "country"),
        "degree": F("Degree, e.g. BSc Computer Science", required=True),
        "field": F("Field"),
        "start": F("Start (YYYY-MM)", _MONTH),
        "end": F("End or expected end (YYYY-MM)", _MONTH),
        "status": F("Status", "choice", choices=["completed", "in_progress", "withdrawn"]),
        "gpa": F("GPA / grade number", "number"),
        "gpa_scale": F("GPA scale maximum, e.g. 4.0 or 100", "number"),
        "grade_text": F("Grade as written, e.g. First Class / 3.7 of 4.0"),
        "honours": F("Honours / distinctions"),
        "thesis_title": F("Thesis title"),
        "supervisor": F("Supervisor"),
        "language_of_instruction": F("Language of instruction"),
    },
    "tests": {
        "exam": F("Exam, e.g. IELTS Academic, TOEFL iBT, GRE", required=True),
        "score": F("Overall score", "number", required=True),
        "date": F("Test date", "date"),
        "expires": F("Expiry date", "date"),
        "subscores": F("Sub-scores as written"),
    },
    "experience": {
        "organization": F("Organization", required=True),
        "role": F("Role", required=True),
        "start": F("Start (YYYY-MM)", _MONTH, required=True),
        "end": F("End (YYYY-MM, blank = current)", _MONTH),
        "country": F("Country", "country"),
        "fte": F("Full-time fraction, 1 = full time", "number"),
        "description": F("What you did and achieved", "long_text"),
    },
    "publications": {
        "title": F("Title", required=True),
        "venue": F("Journal / conference"),
        "year": F("Year", "number"),
        "authors": F("Authors as listed"),
        "doi": F("DOI"),
        "url": F("URL", "url"),
        "status": F("Status", "choice",
                    choices=["published", "accepted", "submitted", "in_preparation"]),
    },
    "awards": {
        "name": F("Award", required=True),
        "year": F("Year", "number"),
        "issuer": F("Issuer"),
        "description": F("Description", "long_text"),
    },
    "activities": {
        "name": F("Activity", required=True),
        "role": F("Role"),
        "start": F("Start (YYYY-MM)", _MONTH),
        "end": F("End (YYYY-MM)", _MONTH),
        "description": F("Description", "long_text"),
    },
    "references": {
        "name": F("Referee name", required=True),
        "title": F("Title / position"),
        "institution": F("Institution"),
        "email": F("Email", "email"),
        "phone": F("Phone", "phone"),
        "relationship": F("How they know you"),
        "notes": F("Notes (topics they can speak to)", "long_text"),
    },
    "languages": {
        "language": F("Language", required=True),
        "level": F("Level", "choice",
                   choices=["native", "fluent", "advanced", "intermediate", "basic"]),
        "certificate": F("Certificate"),
    },
    "documents": {
        "type": F("Document type", "choice", choices=DOC_TYPES, required=True),
        "path": F("File path", required=True),
        "label": F("Label, e.g. 'CV - research focus'"),
    },
}

SEARCH_REQUIRED = [
    "target.levels", "target.fields", "target.regions", "target.start_term",
    "identity.citizenships", "identity.country_of_residence",
]
APPLY_REQUIRED = [
    "identity.first_name", "identity.last_name", "identity.date_of_birth", "identity.email",
    "identity.phone", "identity.address_line1", "identity.city", "identity.postal_code",
    "identity.address_country", "identity.citizenships", "identity.country_of_residence",
]

# --------------------------------------------------------------------------- storage


def path() -> Path:
    return store.data_file("profile.json")


def empty() -> dict[str, Any]:
    return {"version": 1, "values": {}, "lists": {name: [] for name in LISTS}, "skipped": [],
            "updated": None}


def load() -> dict[str, Any]:
    data = store.load_json(path(), None) or empty()
    data.setdefault("values", {})
    data.setdefault("skipped", [])
    lists = data.setdefault("lists", {})
    for name in LISTS:
        lists.setdefault(name, [])
    return data


def save(profile: dict[str, Any]) -> None:
    profile["updated"] = store.now_iso()
    store.save_json(path(), profile)

# --------------------------------------------------------------------- sensitive data

_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_SIN = re.compile(r"\b\d{3}[ -]\d{3}[ -]\d{3}\b")
_CARD = re.compile(r"(?<![\w.])(?:\d[ -]?){12,18}\d(?![\w.])")
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")
_PASSWORD = re.compile(r"(?i)\b(password|passcode|passwd|pin)\s*(is|:|=)")
_PASSPORT = re.compile(r"(?i)\bpassport\s*(no\.?|number|num|#)\s*[:=]?\s*[A-Z0-9]{6,}")


def _luhn(digits: str) -> bool:
    total = 0
    for index, char in enumerate(reversed(digits)):
        n = int(char)
        if index % 2:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def sensitive_reason(text: str) -> str | None:
    """Why a value must not be stored, or None. Used for profile values and agent logs."""
    if not isinstance(text, str) or not text:
        return None
    if _SSN.search(text):
        return "looks like a Social Security number"
    if _SIN.search(text):
        return "looks like a Social Insurance Number"
    for match in _CARD.finditer(text):
        digits = re.sub(r"\D", "", match.group())
        if 13 <= len(digits) <= 19 and _luhn(digits):
            return "looks like a payment card number"
    if _IBAN.search(text):
        return "looks like a bank account (IBAN)"
    if _PASSWORD.search(text):
        return "looks like a password or PIN"
    if _PASSPORT.search(text):
        return "looks like a passport number"
    return None

# ------------------------------------------------------------------------ validation


def _norm_choice(raw: str) -> str:
    text = str(raw).strip().casefold().replace("'", "").replace("’", "")
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return SYNONYMS.get(text, text)


def _split_list(raw: Any) -> list[str]:
    if isinstance(raw, list):
        items = raw
    else:
        text = str(raw).strip()
        if text.startswith("["):
            try:
                items = json.loads(text)
            except json.JSONDecodeError:
                items = [text]
        else:
            items = re.split(r";|\n" if ";" in text or "\n" in text else r",", text)
    return [str(item).strip() for item in items if str(item).strip()]


def validate_value(spec: dict[str, Any], raw: Any) -> tuple[Any, str | None]:
    kind = spec["type"]
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None, "empty value (use 'skip' to record that you prefer not to answer)"
    text = raw.strip() if isinstance(raw, str) else raw

    if kind in ("text", "long_text"):
        limit = 500 if kind == "text" else 20000
        value = str(text)
        if len(value) > limit:
            return None, f"too long ({len(value)} characters; limit {limit})"
    elif kind == "email":
        value = str(text)
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            return None, "not a valid email address"
    elif kind == "phone":
        value = str(text)
        if not re.fullmatch(r"\+?[0-9][0-9 ()./-]{5,24}", value):
            return None, "not a valid phone number (include the country code, e.g. +1 250 555 0100)"
        return value, None  # digits in phone numbers would trip the card check
    elif kind == "url":
        value = str(text)
        if not re.fullmatch(r"https?://\S+", value):
            return None, "URL must start with https:// and contain no spaces"
    elif kind == "date":
        parsed = store.parse_date(text)
        if not parsed or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(text)):
            return None, "use the format YYYY-MM-DD"
        value = parsed.isoformat()
    elif kind == "month":
        value = str(text)
        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", value):
            return None, "use the format YYYY-MM"
    elif kind == "number":
        cleaned = re.sub(r"[,$\s]", "", str(text))
        try:
            number = float(cleaned)
        except ValueError:
            return None, "not a number"
        value = int(number) if number.is_integer() else number
        return value, None
    elif kind == "bool":
        lowered = str(text).casefold()
        if lowered in ("yes", "y", "true", "1"):
            return True, None
        if lowered in ("no", "n", "false", "0"):
            return False, None
        return None, "answer yes or no"
    elif kind == "choice":
        value = _norm_choice(text)
        if value not in spec["choices"]:
            return None, f"choose one of: {', '.join(spec['choices'])}"
    elif kind == "choice_list":
        items = [_norm_choice(item) for item in _split_list(text)]
        bad = [item for item in items if item not in spec["choices"]]
        if bad or not items:
            return None, f"choose from: {', '.join(spec['choices'])}"
        value = sorted(set(items), key=items.index)
    elif kind == "list":
        value = _split_list(text)
        if not value:
            return None, "empty list"
        if any(len(item) > 200 for item in value):
            return None, "list items must be under 200 characters"
    elif kind == "country":
        value, error = countries.validate_name(str(text))
        if error:
            return None, error
    elif kind == "country_list":
        value = []
        for item in _split_list(text):
            name, error = countries.validate_name(item)
            if error:
                return None, error
            if name not in value:
                value.append(name)
        if not value:
            return None, "empty list"
    else:  # pragma: no cover - schema error
        return None, f"unknown field type {kind}"

    for item in value if isinstance(value, list) else [value]:
        reason = sensitive_reason(str(item))
        if reason:
            return None, (f"NOT SAVED: {reason}. Never store IDs, passwords or bank details; "
                          "you will type those into forms yourself.")
    return value, None

# ------------------------------------------------------------------------- mutation


def _fail(error: str) -> dict[str, Any]:
    return {"ok": False, "saved": False, "error": error}


def set_value(profile: dict[str, Any], key: str, raw: Any) -> dict[str, Any]:
    spec = SCALARS.get(key)
    if not spec:
        return _fail(f"unknown key '{key}'. Run 'profile keys' to see valid keys.")
    value, error = validate_value(spec, raw)
    if error:
        return _fail(error)
    profile["values"][key] = value
    if key in profile["skipped"]:
        profile["skipped"].remove(key)
    return {"ok": True, "saved": True, "key": key, "value": value}


def unset_value(profile: dict[str, Any], key: str) -> dict[str, Any]:
    if key not in SCALARS:
        return _fail(f"unknown key '{key}'")
    existed = profile["values"].pop(key, None) is not None
    return {"ok": True, "key": key, "removed": existed}


def skip(profile: dict[str, Any], key: str) -> dict[str, Any]:
    if key not in SCALARS:
        return _fail(f"unknown key '{key}'")
    profile["values"].pop(key, None)
    if key not in profile["skipped"]:
        profile["skipped"].append(key)
    return {"ok": True, "key": key, "skipped": True}


def _validate_row(name: str, fields: dict[str, Any], partial: bool) -> tuple[dict[str, Any], str | None]:
    schema = LISTS[name]
    row: dict[str, Any] = {}
    for field, raw in fields.items():
        spec = schema.get(field)
        if not spec:
            return {}, f"unknown field '{field}' for {name}. Valid: {', '.join(schema)}"
        if raw is None or (isinstance(raw, str) and raw.strip() == ""):
            row[field] = None
            continue
        value, error = validate_value(spec, raw)
        if error:
            return {}, f"{field}: {error}"
        row[field] = value
    if not partial:
        missing = [f for f, spec in schema.items() if spec.get("required") and not row.get(f)]
        if missing:
            return {}, f"missing required field(s): {', '.join(missing)}"
    return row, None


def list_add(profile: dict[str, Any], name: str, fields: dict[str, Any]) -> dict[str, Any]:
    if name not in LISTS:
        return _fail(f"unknown list '{name}'. Lists: {', '.join(LISTS)}")
    if name == "documents":
        return _fail("use 'profile doc-add TYPE PATH' to register documents")
    row, error = _validate_row(name, fields, partial=False)
    if error:
        return _fail(error)
    rows = profile["lists"][name]
    row["id"] = max([r.get("id", 0) for r in rows] + [0]) + 1
    rows.append({k: v for k, v in row.items() if v is not None})
    return {"ok": True, "saved": True, "list": name, "row": rows[-1]}


def list_update(profile: dict[str, Any], name: str, row_id: int, fields: dict[str, Any]) -> dict[str, Any]:
    if name not in LISTS or name == "documents":
        return _fail(f"cannot update list '{name}'")
    rows = profile["lists"][name]
    target = next((r for r in rows if r.get("id") == row_id), None)
    if not target:
        return _fail(f"no row {row_id} in {name}")
    patch, error = _validate_row(name, fields, partial=True)
    if error:
        return _fail(error)
    for key, value in patch.items():
        if value is None:
            target.pop(key, None)
        else:
            target[key] = value
    return {"ok": True, "saved": True, "list": name, "row": target}


def list_remove(profile: dict[str, Any], name: str, row_id: int) -> dict[str, Any]:
    if name not in LISTS:
        return _fail(f"unknown list '{name}'")
    rows = profile["lists"][name]
    kept = [r for r in rows if r.get("id") != row_id]
    if len(kept) == len(rows):
        return _fail(f"no row {row_id} in {name}")
    profile["lists"][name] = kept
    return {"ok": True, "list": name, "removed": row_id}


def doc_add(profile: dict[str, Any], doc_type: str, file_path: str, label: str | None = None) -> dict[str, Any]:
    kind = _norm_choice(doc_type)
    if kind not in DOC_TYPES:
        return _fail(f"document type must be one of: {', '.join(DOC_TYPES)}")
    file = Path(file_path).expanduser()
    if not file.is_absolute():
        file = (store.home() / file) if (store.home() / file).exists() else file.resolve()
    if not file.is_file():
        return _fail(f"file not found: {file_path}")
    if label and sensitive_reason(label):
        return _fail("label contains sensitive data")
    stored = store.relative_to_home(file)
    rows = profile["lists"]["documents"]
    existing = next((r for r in rows if r.get("path") == stored), None)
    info = {"type": kind, "path": stored, "label": label or file.stem,
            "sha256": store.file_sha256(file), "size": file.stat().st_size,
            "added": store.now_iso()}
    if existing:
        existing.update(info)
        row = existing
    else:
        info["id"] = max([r.get("id", 0) for r in rows] + [0]) + 1
        rows.append(info)
        row = info
    note = None
    if kind in HANDOFF_DOC_TYPES:
        note = "Identity documents are never uploaded by the agent; you will upload this yourself."
    return {"ok": True, "saved": True, "document": row, "note": note}

# --------------------------------------------------------------------------- reading


def keys(section: str | None = None) -> list[dict[str, Any]]:
    out = []
    for key, spec in SCALARS.items():
        if section and not key.startswith(section + "."):
            continue
        out.append({"key": key, "label": spec["label"], "type": spec["type"],
                    **({"choices": spec["choices"]} if "choices" in spec else {})})
    if not section or section == "lists":
        for name, schema in LISTS.items():
            out.append({"list": name, "fields": {f: s["label"] for f, s in schema.items()}})
    return out


def _filled(profile: dict[str, Any], key: str) -> bool:
    value = profile["values"].get(key)
    return value not in (None, "", [])


def status(profile: dict[str, Any]) -> dict[str, Any]:
    lists = profile["lists"]
    docs = lists.get("documents", [])
    doc_types = {d.get("type") for d in docs}
    missing_search = [k for k in SEARCH_REQUIRED if not _filled(profile, k)]
    missing_apply = [k for k in APPLY_REQUIRED if not _filled(profile, k)]
    if not lists.get("education"):
        missing_apply.append("list:education")
    # Only a CV is needed for every application. Transcripts, certificates etc. are asked for per
    # application: the document check blocks the ones whose call requires a file that isn't here.
    if "cv" not in doc_types:
        missing_apply.append("document:cv")
    sections: dict[str, dict[str, int]] = {}
    for key in SCALARS:
        section = key.split(".")[0]
        bucket = sections.setdefault(section, {"filled": 0, "total": 0, "skipped": 0})
        bucket["total"] += 1
        bucket["filled"] += int(_filled(profile, key))
        bucket["skipped"] += int(key in profile["skipped"])
    total = sum(s["total"] for s in sections.values())
    done = sum(s["filled"] + s["skipped"] for s in sections.values())
    return {
        "ok": True,
        "search_ready": not missing_search,
        "apply_ready": not missing_apply,
        "missing_for_search": missing_search,
        "missing_for_apply": missing_apply,
        "sections": sections,
        "lists": {name: len(rows) for name, rows in lists.items()},
        "documents_by_type": {t: sum(1 for d in docs if d.get("type") == t) for t in sorted(doc_types)},
        "completeness_percent": round(100 * done / total) if total else 0,
        "updated": profile.get("updated"),
    }


def display_summary(profile: dict[str, Any]) -> dict[str, Any]:
    """Small, non-sensitive summary for the dashboard header."""
    values = profile["values"]
    return {
        "name": values.get("identity.preferred_name") or values.get("identity.first_name"),
        "levels": values.get("target.levels", []),
        "regions": values.get("target.regions", []),
        "fields": values.get("target.fields", []),
        "citizenships": values.get("identity.citizenships", []),
        "residence": values.get("identity.country_of_residence"),
        "start_term": values.get("target.start_term"),
        "completeness_percent": status(profile)["completeness_percent"],
    }

# ------------------------------------------------------------------------- web editing


def schema() -> dict[str, Any]:
    """Field labels, types and choices for the dashboard's Profile forms."""
    return {
        "scalars": [{"key": key, **spec} for key, spec in SCALARS.items()],
        "lists": {name: [{"field": field, **spec} for field, spec in fields.items()]
                  for name, fields in LISTS.items() if name != "documents"},
    }


def web_view() -> dict[str, Any]:
    """Everything the Profile tab shows. Served only to the local dashboard."""
    profile = load()
    return {"ok": True, "values": profile["values"], "skipped": profile["skipped"],
            "lists": {name: rows for name, rows in profile["lists"].items() if name != "documents"},
            "schema": schema(), "status": status(profile)}


def web_edit(body: dict[str, Any]) -> dict[str, Any]:
    """Apply one edit from the dashboard and save it, with the same validation as the CLI.

    ops: set {key, value} (empty value clears it) | skip {key} |
         add {list, fields} | update {list, id, fields} | remove {list, id}
    Removing a document only unregisters it; the file stays in documents/.
    """
    profile = load()
    op = body.get("op")
    name = str(body.get("list", ""))
    if op == "set":
        key, value = str(body.get("key", "")), body.get("value")
        empty = value is None or value == [] or (isinstance(value, str) and not value.strip())
        result = unset_value(profile, key) if empty else set_value(profile, key, value)
    elif op == "skip":
        result = skip(profile, str(body.get("key", "")))
    elif op == "add":
        result = list_add(profile, name, dict(body.get("fields") or {}))
    elif op in ("update", "remove"):
        try:
            row_id = int(body.get("id"))
        except (TypeError, ValueError):
            return _fail("missing row id")
        result = (list_update(profile, name, row_id, dict(body.get("fields") or {})) if op == "update"
                  else list_remove(profile, name, row_id))
    else:
        return _fail("unknown profile operation")
    if result.get("ok"):
        save(profile)
        result["status"] = status(profile)
    return result

# ----------------------------------------------------------------------- derived facts


def _month_index(text: str | None, fallback: date) -> int:
    if text and re.fullmatch(r"\d{4}-\d{2}", text):
        year, month = text.split("-")
        return int(year) * 12 + int(month) - 1
    return fallback.year * 12 + fallback.month - 1


def degree_rank(text: str) -> int:
    t = str(text).casefold()
    if re.search(r"\b(ph\.?\s?d|dphil|doctor|doctorate|doctoral)", t):
        return 3
    if re.search(r"\b(master|m\.?sc|m\.?a\b|m\.?eng|mba|m\.?phil|m\.?res|llm|m\.?s\b|masc|m\.?ed\b|m\.?tech)", t):
        return 2
    if re.search(r"\b(bachelor|b\.?sc|b\.?a\b|b\.?eng|b\.?s\b|bcom|llb|undergrad|honours|b\.?tech|bba|bcs|b\.?ed\b)", t):
        return 1
    return 0


RANK_NAMES = {0: "none", 1: "bachelors", 2: "masters", 3: "phd"}


def exam_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(name).casefold()).strip("_")


def residence_months(profile: dict[str, Any], country: str, within_years: int, on: date) -> int | None:
    """Months spent living in `country` during the last `within_years` years (None = no history)."""
    rows = profile["lists"].get("residence", [])
    if not rows:
        return None
    target = countries.canonical(country)
    end = on.year * 12 + on.month - 1          # current month (inclusive)
    window_start = end - within_years * 12 + 1  # first month inside the window
    total = 0
    for row in rows:
        if countries.canonical(row.get("country", "")) != target:
            continue
        first = _month_index(row.get("from"), on)
        last = _month_index(row.get("to"), on) if row.get("to") else end  # "to" month is inclusive
        total += max(0, min(last, end) - max(first, window_start) + 1)
    return total


def facts(profile: dict[str, Any], on: date | None = None) -> dict[str, Any]:
    on = on or store.today()
    out: dict[str, Any] = dict(profile["values"])
    lists = profile["lists"]

    dob = store.parse_date(out.get("identity.date_of_birth"))
    if dob:
        out["derived.age"] = on.year - dob.year - ((on.month, on.day) < (dob.month, dob.day))

    education = lists.get("education", [])
    completed = [e for e in education if e.get("status", "completed") == "completed"]
    ranks = [degree_rank(e.get("degree", "")) for e in completed]
    out["derived.highest_degree"] = RANK_NAMES[max(ranks)] if ranks else "none"
    out["derived.has_masters"] = any(r >= 2 for r in ranks) if ranks else False
    current = [e for e in education if e.get("status") == "in_progress"]
    if current:
        out["derived.current_degree"] = RANK_NAMES[max(degree_rank(e.get("degree", "")) for e in current)]
    out["derived.degree_countries"] = sorted({e["country"] for e in education if e.get("country")})

    graded = [e for e in education if e.get("gpa") is not None and e.get("gpa_scale")]
    if graded:
        latest = max(graded, key=lambda e: (e.get("end") or e.get("start") or ""))
        out["derived.gpa_percent"] = round(100 * float(latest["gpa"]) / float(latest["gpa_scale"]), 2)
        if float(latest["gpa_scale"]) == 4.0:
            out["derived.gpa_4"] = float(latest["gpa"])

    finished = [e for e in completed if e.get("end")]
    if finished:
        last_end = max(_month_index(e["end"], on) for e in finished)
        out["derived.years_since_last_degree"] = round((on.year * 12 + on.month - 1 - last_end) / 12, 1)

    # Months are inclusive ("Jun–Aug" = 3); an ongoing job counts up to last month, not this one.
    # Many calls ask for experience *after* the first degree, so that is counted separately,
    # starting the month after that degree ended (internships during study don't count there).
    first_end = min((_month_index(e["end"], on) for e in finished), default=None)
    months = after_degree = 0.0
    current = on.year * 12 + on.month - 1
    for job in lists.get("experience", []):
        start = _month_index(job.get("start"), on)
        last = _month_index(job["end"], on) if job.get("end") else current - 1
        fte = float(job.get("fte") or 1)
        months += max(0, last - start + 1) * fte
        if first_end is not None:
            after_degree += max(0, last - max(start, first_end + 1) + 1) * fte
    out["derived.work_months"] = round(months, 1)
    if first_end is not None:
        out["derived.work_months_after_degree"] = round(after_degree, 1)

    for test in lists.get("tests", []):
        key = exam_key(test.get("exam", ""))
        if not key:
            continue
        for name in {key, key.split("_")[0]}:
            fact = f"derived.score.{name}"
            score = test.get("score")
            if score is not None and (fact not in out or score > out[fact]):
                out[fact] = score

    out["derived.publications_count"] = len(lists.get("publications", []))
    out["derived.languages"] = [l["language"] for l in lists.get("languages", []) if l.get("language")]
    return out


KNOWN_DERIVED = {
    "derived.age", "derived.highest_degree", "derived.has_masters", "derived.current_degree",
    "derived.degree_countries", "derived.gpa_percent", "derived.gpa_4",
    "derived.years_since_last_degree", "derived.work_months", "derived.work_months_after_degree",
    "derived.publications_count",
    "derived.languages",
}


def is_known_fact(field: str) -> bool:
    return field in SCALARS or field in KNOWN_DERIVED or field.startswith("derived.score.")
