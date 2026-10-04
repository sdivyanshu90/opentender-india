"""Deterministic Indian state/district inference for tenders whose source does not name a state.

Central/PSU portals (CPPP) and GeM do not carry a state, so they would never match the state
filter. This module infers it from text already in the record, precision first:

* never overrides a state set by an adapter (callers only ask when state is empty);
* evidence is a PIN code (India Post circles), then whole-word place names (districts/cities, a few
  well-known institutions) and finally explicit state names, in titles, locations and authority chains;
* a state is returned only when ALL strong evidence points to exactly one state; conflicting or
  ambiguous evidence returns None;
* names that are also common words/given names (Kalyan, Sagar, Delhi as a head-office address) are
  "weak" and never decide on their own; 2-letter codes (MH, KL) are ignored on purpose.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from scrapers.core import geo_data as gd


@dataclass(frozen=True)
class GeoTag:
    state: str
    district: str | None
    evidence: tuple[str, ...]  # e.g. ("pincode", "place:pune")


# Maharashtra districts (post-renaming names) and cities that belong to exactly one district.
MH_DISTRICT_OF: dict[str, str] = {
    **{d.lower(): d for d in (
        "Pune", "Nagpur", "Nashik", "Thane", "Solapur", "Kolhapur", "Amravati", "Akola", "Latur", "Nanded",
        "Jalgaon", "Satara", "Sangli", "Ratnagiri", "Raigad", "Palghar", "Chandrapur", "Wardha", "Yavatmal",
        "Gondia", "Bhandara", "Gadchiroli", "Washim", "Buldhana", "Hingoli", "Parbhani", "Jalna", "Beed",
        "Dhule", "Nandurbar", "Sindhudurg")},
    "mumbai": "Mumbai", "bombay": "Mumbai", "mumbai suburban": "Mumbai Suburban",
    "poona": "Pune", "pimpri chinchwad": "Pune", "pimpri": "Pune", "lonavala": "Pune", "lonavla": "Pune",
    "talegaon": "Pune", "baramati": "Pune", "dehu road": "Pune", "khadakwasla": "Pune",
    "nasik": "Nashik", "deolali": "Nashik", "malegaon": "Nashik",
    "kalyan": "Thane", "dombivli": "Thane", "bhiwandi": "Thane", "ulhasnagar": "Thane",
    "ambernath": "Thane", "badlapur": "Thane",
    "chhatrapati sambhajinagar": "Chhatrapati Sambhajinagar", "sambhajinagar": "Chhatrapati Sambhajinagar",
    "osmanabad": "Dharashiv", "dharashiv": "Dharashiv",
    "ahmednagar": "Ahilyanagar", "ahmadnagar": "Ahilyanagar", "ahilyanagar": "Ahilyanagar",
    "panvel": "Raigad", "alibag": "Raigad", "khopoli": "Raigad", "nhava sheva": "Raigad",
    "vasai": "Palghar", "virar": "Palghar", "tarapur": "Palghar",
    "shirdi": "Ahilyanagar", "pandharpur": "Solapur", "karad": "Satara", "miraj": "Sangli",
    "ichalkaranji": "Kolhapur", "bhusawal": "Jalgaon", "kamptee": "Nagpur", "chiplun": "Ratnagiri",
    "gondiya": "Gondia", "sawantwadi": "Sindhudurg", "kudal": "Sindhudurg",
    "trombay": "Mumbai Suburban", "mulund": "Mumbai Suburban", "bandra": "Mumbai Suburban",
    "andheri": "Mumbai Suburban", "chembur": "Mumbai Suburban", "kurla": "Mumbai Suburban",
    "powai": "Mumbai Suburban", "worli": "Mumbai", "colaba": "Mumbai",
}

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_PIN_KEYWORD = re.compile(r"\bpin\s*(?:code)?\s*(?:no\.?)?\s*[:\-\u2013.]?\s*(\d{3}\s?\d{3})(?!\d)")
# looser forms ("Nagpur - 440030", "Pune, 411001") also look like tender numbers, so they only count
# when they agree with a place/state name found in the text.
_PIN_LOOSE = re.compile(r"[a-z)]\s*[,\-\u2013]\s*(\d{3}\s?\d{3})(?!\d)")


def _norm(text: str) -> str:
    return " " + _NON_ALNUM.sub(" ", text.lower().replace("&", " and ")).strip() + " "


@lru_cache(maxsize=1)
def _tables():
    kinds: dict[str, tuple[str, tuple[str, ...]]] = {}  # name -> (kind, states)
    place_states: dict[str, set[str]] = {}
    for state, names in gd.PLACES.items():
        for n in names:
            place_states.setdefault(n, set()).add(state)
    for n, states in place_states.items():
        if len(states) > 1:
            kinds[n] = ("ambiguous", tuple(sorted(states)))
        else:
            kinds[n] = ("weak" if n in gd.WEAK_PLACES else "place", tuple(states))
    for state, names in gd.STATE_NAMES.items():
        for n in names:
            kinds[n] = ("state", (state,))
    for n, st in gd.ALIASES.items():
        kinds[n] = ("alias", (st,))
    for n, states in gd.AMBIGUOUS_PLACES.items():
        kinds[n] = ("ambiguous", tuple(states))
    # a weak flag also applies to state-less lookups, e.g. "delhi" listed as STATE_NAMES variant
    for n in gd.WEAK_PLACES:
        if n in kinds and kinds[n][0] == "place":
            kinds[n] = ("weak", kinds[n][1])
    for n in gd.VILLAGE_PRONE:
        if n in kinds and kinds[n][0] == "place":
            kinds[n] = ("village", kinds[n][1])
    alts = sorted(kinds, key=len, reverse=True)
    pattern = re.compile(r"(?<![a-z0-9])(?:" + "|".join(re.escape(a) for a in alts) + r")(?![a-z0-9])")
    neutral = [_norm(p).strip() for p in gd.NEUTRAL_PHRASES]
    neutral_re = re.compile(r"(?<![a-z0-9])(?:" + "|".join(re.escape(p) for p in neutral) + r")(?![a-z0-9])")
    return kinds, pattern, neutral_re


def state_from_pincode(pin: str) -> str | None:
    """India Post PIN -> state/UT, or None when the circle is mixed/unknown."""
    digits = re.sub(r"\s", "", pin or "")
    if not re.fullmatch(r"[1-9]\d{5}", digits):
        return None
    n = int(digits)
    if digits.startswith("160"):
        return "Chandigarh" if n <= 160036 else "Punjab"
    if digits.startswith("396"):
        return "Dadra and Nagar Haveli and Daman and Diu" if 396210 <= n <= 396240 else "Gujarat"
    if digits.startswith("68255"):
        return "Lakshadweep"
    if digits[:3] in gd.PIN_PREFIX_3:
        return gd.PIN_PREFIX_3[digits[:3]]
    return gd.PIN_PREFIX_2.get(digits[:2])


def _pincodes(texts: list[str], pattern: re.Pattern[str]) -> list[str]:
    found: list[str] = []
    for t in texts:
        found += [m.group(1).replace(" ", "") for m in pattern.finditer(t.lower())]
    return found


def infer_from_text(
    work_texts: list[str], org_texts: list[str] | None = None, pincode: str | None = None
) -> GeoTag | None:
    """Core inference.

    work_texts: where the work is (title, location). org_texts: who buys (authority chain), whose
    head/regional office city is weaker evidence. pincode: the explicit geography.pincode, if any.
    """
    kinds, pattern, neutral_re = _tables()
    work_texts = [t for t in work_texts if t]
    org_texts = [t for t in (org_texts or []) if t]
    all_texts = work_texts + org_texts

    village_fields: dict[str, set[int]] = {}  # state -> indexes of fields with a village-prone hit

    def scan(texts: list[str], offset: int) -> tuple[dict[str, set[str]], list[str], dict[str, set[str]]]:
        strong: dict[str, set[str]] = {}
        village: dict[str, set[str]] = {}
        places: list[str] = []
        for i, t in enumerate(texts):
            norm = neutral_re.sub(" ", _norm(t))
            for m in pattern.finditer(norm):
                name = m.group(0)
                kind, states = kinds[name]
                if kind in ("weak", "ambiguous"):
                    continue  # only ever consistent with, never evidence for, a state
                if kind == "village":
                    village.setdefault(states[0], set()).add(f"place:{name}")
                    village_fields.setdefault(states[0], set()).add(offset + i)
                    continue
                strong.setdefault(states[0], set()).add(f"{kind}:{name}")
                if kind == "place":
                    places.append(name)
        return strong, places, village

    work, work_places, work_village = scan(work_texts, 0)
    org, org_places, org_village = scan(org_texts, len(work_texts))
    for st, fields in village_fields.items():  # promoted by agreement of two independent fields
        if len(fields) >= 2:
            for src, vill, plist in ((work, work_village, work_places), (org, org_village, org_places)):
                for ev in vill.get(st, ()):
                    src.setdefault(st, set()).add(ev)
                    plist.append(ev.split(":", 1)[1])
    named = {s for s in (*work, *org)}

    explicit = ([pincode] if pincode else []) + _pincodes(all_texts, _PIN_KEYWORD)
    loose = _pincodes(all_texts, _PIN_LOOSE)
    explicit_states = {state_from_pincode(p) for p in explicit} - {None}
    if len(explicit_states) > 1:
        return None
    pin_state = next(iter(explicit_states), None)
    if pin_state is None:  # a loose pin counts only when a name in the text agrees with it
        agreeing = {state_from_pincode(p) for p in loose} & named
        if len(agreeing) == 1:
            pin_state = next(iter(agreeing))

    evidence: list[str] = []
    places: list[str] = []
    if pin_state is not None:
        chosen = pin_state  # PIN code outranks names (road/village names often collide)
        evidence.append("pincode")
        evidence += sorted(e for d in (work, org) for e in d.get(chosen, ()))
        places = [p for p in work_places + org_places if kinds[p][1][0] == chosen]
    elif len(work) == 1 and (not org or set(org) == set(work) or _org_is_place_only(org)):
        # the work location decides; an authority's regional-office city is weaker than the title
        chosen = next(iter(work))
        evidence = sorted(next(iter(work.values())))
        places = [p for p in work_places if kinds[p][1][0] == chosen]
    elif not work and len(org) == 1:
        chosen = next(iter(org))
        evidence = sorted(next(iter(org.values())))
        places = [p for p in org_places if kinds[p][1][0] == chosen]
    else:
        return None  # nothing, only weak names, or conflicting evidence

    district = None
    if chosen == "Maharashtra" and places and all(p in MH_DISTRICT_OF for p in places):
        found = {MH_DISTRICT_OF[p] for p in places}
        if len(found) == 1:
            district = next(iter(found))
    return GeoTag(chosen, district, tuple(evidence))


def _org_is_place_only(org: dict[str, set[str]]) -> bool:
    """True when the authority's evidence consists of city/district hits only (no state names/aliases)."""
    return all(e.startswith("place:") for evs in org.values() for e in evs)


def infer_geography(tender) -> GeoTag | None:
    """Infer geography for a CanonicalTender whose geography.state is empty (else returns None)."""
    geo = tender.geography
    if geo.state:
        return None
    org = tender.organization
    work = [tender.procurement.title, geo.location_text, geo.city, geo.district]
    authority = [org.authority, org.ministry, org.department, org.organization, org.division]
    return infer_from_text(work, authority, geo.pincode)
