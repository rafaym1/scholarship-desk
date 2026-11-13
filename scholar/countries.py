"""Country names, aliases and groups used for eligibility rules.

Matching is done on canonical lower-case names. Unknown names are reported, never
silently accepted, because a misspelled country in a deny-list would wrongly pass.
"""
from __future__ import annotations

import difflib
import re
from typing import Iterable

COUNTRIES = [
    "Afghanistan", "Albania", "Algeria", "Andorra", "Angola", "Antigua and Barbuda",
    "Argentina", "Armenia", "Australia", "Austria", "Azerbaijan", "Bahamas", "Bahrain",
    "Bangladesh", "Barbados", "Belarus", "Belgium", "Belize", "Benin", "Bhutan", "Bolivia",
    "Bosnia and Herzegovina", "Botswana", "Brazil", "Brunei", "Bulgaria", "Burkina Faso",
    "Burundi", "Cabo Verde", "Cambodia", "Cameroon", "Canada", "Central African Republic",
    "Chad", "Chile", "China", "Colombia", "Comoros", "Republic of the Congo",
    "Democratic Republic of the Congo", "Costa Rica", "Cote d'Ivoire", "Croatia", "Cuba",
    "Cyprus", "Czech Republic", "Denmark", "Djibouti", "Dominica", "Dominican Republic",
    "Ecuador", "Egypt", "El Salvador", "Equatorial Guinea", "Eritrea", "Estonia", "Eswatini",
    "Ethiopia", "Fiji", "Finland", "France", "Gabon", "Gambia", "Georgia", "Germany", "Ghana",
    "Greece", "Grenada", "Guatemala", "Guinea", "Guinea-Bissau", "Guyana", "Haiti",
    "Honduras", "Hungary", "Iceland", "India", "Indonesia", "Iran", "Iraq", "Ireland",
    "Israel", "Italy", "Jamaica", "Japan", "Jordan", "Kazakhstan", "Kenya", "Kiribati",
    "Kuwait", "Kyrgyzstan", "Laos", "Latvia", "Lebanon", "Lesotho", "Liberia", "Libya",
    "Liechtenstein", "Lithuania", "Luxembourg", "Madagascar", "Malawi", "Malaysia",
    "Maldives", "Mali", "Malta", "Marshall Islands", "Mauritania", "Mauritius", "Mexico",
    "Micronesia", "Moldova", "Monaco", "Mongolia", "Montenegro", "Morocco", "Mozambique",
    "Myanmar", "Namibia", "Nauru", "Nepal", "Netherlands", "New Zealand", "Nicaragua",
    "Niger", "Nigeria", "North Korea", "North Macedonia", "Norway", "Oman", "Pakistan",
    "Palau", "Panama", "Papua New Guinea", "Paraguay", "Peru", "Philippines", "Poland",
    "Portugal", "Qatar", "Romania", "Russia", "Rwanda", "Saint Kitts and Nevis",
    "Saint Lucia", "Saint Vincent and the Grenadines", "Samoa", "San Marino",
    "Sao Tome and Principe", "Saudi Arabia", "Senegal", "Serbia", "Seychelles",
    "Sierra Leone", "Singapore", "Slovakia", "Slovenia", "Solomon Islands", "Somalia",
    "South Africa", "South Korea", "South Sudan", "Spain", "Sri Lanka", "Sudan", "Suriname",
    "Sweden", "Switzerland", "Syria", "Tajikistan", "Tanzania", "Thailand", "Timor-Leste",
    "Togo", "Tonga", "Trinidad and Tobago", "Tunisia", "Turkey", "Turkmenistan", "Tuvalu",
    "Uganda", "Ukraine", "United Arab Emirates", "United Kingdom", "United States",
    "Uruguay", "Uzbekistan", "Vanuatu", "Venezuela", "Vietnam", "Yemen", "Zambia",
    "Zimbabwe",
    # Non-member states and territories that appear on scholarship country lists.
    "Vatican City", "Palestine", "Taiwan", "Kosovo", "Hong Kong", "Macau",
    # Overseas territories listed separately by some sponsors (e.g. Commonwealth scholarships).
    "Anguilla", "Bermuda", "British Virgin Islands", "Cayman Islands", "Falkland Islands",
    "Gibraltar", "Montserrat", "Pitcairn Islands", "Saint Helena", "Turks and Caicos Islands",
    "Puerto Rico", "Greenland", "Faroe Islands", "Aruba", "Curacao", "New Caledonia",
    "French Polynesia",
]

ALIASES = {
    "usa": "united states", "us": "united states", "u.s.": "united states",
    "u.s.a.": "united states", "united states of america": "united states",
    "america": "united states",
    "uk": "united kingdom", "u.k.": "united kingdom", "great britain": "united kingdom",
    "britain": "united kingdom", "england": "united kingdom", "scotland": "united kingdom",
    "wales": "united kingdom", "northern ireland": "united kingdom",
    "holland": "netherlands", "the netherlands": "netherlands",
    "czechia": "czech republic", "cape verde": "cabo verde",
    "ivory coast": "cote d'ivoire", "côte d'ivoire": "cote d'ivoire",
    "swaziland": "eswatini", "burma": "myanmar", "macedonia": "north macedonia",
    "east timor": "timor-leste", "türkiye": "turkey", "turkiye": "turkey",
    "holy see": "vatican city", "russian federation": "russia",
    "republic of korea": "south korea", "korea, republic of": "south korea",
    "korea": "south korea", "dprk": "north korea",
    "democratic people's republic of korea": "north korea",
    "iran, islamic republic of": "iran", "islamic republic of iran": "iran",
    "syrian arab republic": "syria", "lao pdr": "laos",
    "lao people's democratic republic": "laos", "viet nam": "vietnam",
    "republic of moldova": "moldova", "united republic of tanzania": "tanzania",
    "plurinational state of bolivia": "bolivia", "brunei darussalam": "brunei",
    "federated states of micronesia": "micronesia", "the gambia": "gambia",
    "the bahamas": "bahamas", "congo": "republic of the congo",
    "congo-brazzaville": "republic of the congo", "dr congo": "democratic republic of the congo",
    "drc": "democratic republic of the congo",
    "congo-kinshasa": "democratic republic of the congo",
    "state of palestine": "palestine", "palestinian territories": "palestine",
    "uae": "united arab emirates", "ksa": "saudi arabia", "hong kong sar": "hong kong",
    "macao": "macau", "slovak republic": "slovakia",
}

EU = [
    "Austria", "Belgium", "Bulgaria", "Croatia", "Cyprus", "Czech Republic", "Denmark",
    "Estonia", "Finland", "France", "Germany", "Greece", "Hungary", "Ireland", "Italy",
    "Latvia", "Lithuania", "Luxembourg", "Malta", "Netherlands", "Poland", "Portugal",
    "Romania", "Slovakia", "Slovenia", "Spain", "Sweden",
]
NORDIC = ["Denmark", "Finland", "Iceland", "Norway", "Sweden"]
EEA = EU + ["Iceland", "Liechtenstein", "Norway"]
EFTA = ["Iceland", "Liechtenstein", "Norway", "Switzerland"]

GROUPS = {
    "@eu": EU,
    "@eea": EEA,
    "@eu_eea_ch": EEA + ["Switzerland"],
    "@efta": EFTA,
    "@nordic": NORDIC,
}

_CANON = {name.casefold(): name for name in COUNTRIES}


def _clean(name: str) -> str:
    return re.sub(r"\s+", " ", str(name).strip().casefold())


def canonical(name: str) -> str | None:
    """Return the canonical lower-case country name, or None when unknown."""
    key = _clean(name)
    key = ALIASES.get(key, key)
    return key if key in _CANON else None


def display(name: str) -> str:
    key = canonical(name)
    return _CANON[key] if key else str(name)


def suggest(name: str) -> list[str]:
    pool = list(_CANON) + list(ALIASES)
    hits = difflib.get_close_matches(_clean(name), pool, n=3, cutoff=0.75)
    out: list[str] = []
    for hit in hits:
        shown = _CANON[ALIASES.get(hit, hit)]
        if shown not in out:
            out.append(shown)
    return out


def expand(values: Iterable[str]) -> tuple[set[str], list[str]]:
    """Expand group tokens (@eu, @eea, ...) and canonicalise. Returns (names, unknown)."""
    names: set[str] = set()
    unknown: list[str] = []
    for value in values:
        token = _clean(value)
        if token in GROUPS:
            names.update(n.casefold() for n in GROUPS[token])
            continue
        canon = canonical(value)
        if canon:
            names.add(canon)
        else:
            unknown.append(str(value))
    return names, unknown


def validate_name(name: str) -> tuple[str | None, str | None]:
    """(display name, error)."""
    canon = canonical(name)
    if canon:
        return _CANON[canon], None
    hint = suggest(name)
    tip = f" Did you mean: {', '.join(hint)}?" if hint else ""
    return None, f"'{name}' is not a recognised country name (use the country, not the nationality).{tip}"
