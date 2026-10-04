"""Deterministic state/district inference: precision first, adapter-set state never overridden."""

from __future__ import annotations

import gzip
import json
from datetime import datetime, timedelta

import pytest
from typer.testing import CliRunner

import cli
from scrapers.core.dates import IST
from scrapers.core.geo import infer_from_text, infer_geography, state_from_pincode
from scrapers.core.models import CanonicalTender
from scrapers.core.store import TenderStore


def state(*work, org=(), pin=None):
    tag = infer_from_text(list(work), list(org), pin)
    return tag.state if tag else None


@pytest.mark.parametrize(
    ("pin", "expected"),
    [
        ("400001", "Maharashtra"), ("411001", "Maharashtra"), ("440030", "Maharashtra"), ("444601", "Maharashtra"),
        ("403001", "Goa"), ("110001", "Delhi"), ("682001", "Kerala"), ("560001", "Karnataka"),
        ("500001", "Telangana"), ("520001", "Andhra Pradesh"), ("800001", "Bihar"), ("834001", "Jharkhand"),
        ("248001", "Uttarakhand"), ("226001", "Uttar Pradesh"), ("194101", "Ladakh"), ("160017", "Chandigarh"),
        ("160055", "Punjab"), ("396230", "Dadra and Nagar Haveli and Daman and Diu"), ("395001", "Gujarat"),
        ("605001", None), ("244001", None), ("012345", None), ("40001", None), ("999999", None),
    ],
)
def test_pincode_circles(pin, expected):
    assert state_from_pincode(pin) == expected


def test_pincode_outranks_a_colliding_name():
    assert state("Operation and Maintenance, Chhindwara Road, Nagpur - 440030") == "Maharashtra"
    assert state("Office premises", pin="411001") == "Maharashtra"
    assert state("Supply at campus. Pin code: 400 076") == "Maharashtra"


def test_loose_pin_needs_agreeing_name():
    assert state("Tender GAIL-110025 supply") is None
    assert state("Pune, 411001") == "Maharashtra"


@pytest.mark.parametrize(
    "text",
    [
        "Kalyan Jewellers showroom fitout",
        "Road works at Kalyan village near the market",
        "Kalyan Singh Memorial hall",
        "Renovation at Thaneermukham bund road",  # contains the substring "thane"
        "Thanniyam gram panchayat",
        "MH-12 vehicle spares",  # 2-letter codes are ignored
        "Supply of tubes MH",
        "Punjab National Bank ATM maintenance",  # nation-wide bank names are not geography
        "Bank of Maharashtra branch furnishing",
        "Tender for Bank of Baroda stationery",
    ],
)
def test_tricky_text_is_not_tagged(text):
    assert state(text) is None


def test_kalyan_in_kerala_context_is_kerala():
    assert state("Kalyan colony road, Kasaragod, Kerala") == "Kerala"
    assert state("Kalyan village road, Kasaragod") == "Kerala"
    assert state("Kalyan, Maharashtra") == "Maharashtra"


@pytest.mark.parametrize(
    ("text", "district"),
    [
        ("Repair works at Aurangabad, Maharashtra", None),
        ("Works at Chhatrapati Sambhajinagar MIDC", "Chhatrapati Sambhajinagar"),
        ("Hostel at Osmanabad", "Dharashiv"),
        ("Hostel at Dharashiv", "Dharashiv"),
        ("Office building Ahmednagar", "Ahilyanagar"),
        ("Office building Ahilyanagar", "Ahilyanagar"),
        ("Supply at Navi Mumbai", None),
        ("Godown at Nasik", "Nashik"),
    ],
)
def test_maharashtra_renamed_districts_and_cities(text, district):
    tag = infer_from_text([text])
    assert tag is not None and tag.state == "Maharashtra"
    assert tag.district == district


def test_bare_aurangabad_is_ambiguous():
    assert state("Road at Aurangabad") is None  # Bihar and Maharashtra both have one


@pytest.mark.parametrize(
    "city",
    ["Mumbai", "Pune", "Nagpur", "Nashik", "Thane", "Solapur", "Kolhapur", "Amravati", "Akola", "Latur", "Nanded",
     "Jalgaon", "Satara", "Sangli", "Ratnagiri", "Raigad", "Palghar", "Chandrapur", "Wardha", "Yavatmal", "Gondia",
     "Bhandara", "Gadchiroli", "Washim", "Buldhana", "Hingoli", "Parbhani", "Jalna", "Beed", "Dhule", "Nandurbar",
     "Sindhudurg"],
)
def test_all_priority_maharashtra_districts(city):
    assert state(f"Civil works at {city}") == "Maharashtra"
    assert state(f"Civil works at {city.upper()}") == "Maharashtra"


def test_multi_state_text_is_ambiguous():
    assert state("Supply from Pune to Chennai") is None
    assert state("Works in Maharashtra and Gujarat") is None
    assert state("Madhya Pradesh Power Generating Company works at Pune") is None


def test_weak_names_never_decide_alone():
    assert state("Kalyan") is None
    assert state("New Delhi head office", org=["Ministry X, New Delhi"]) is None


def test_authority_chain_and_regional_office_rules():
    assert state("Interior furnishing of branch", org=["Union Bank of India › Regional office Kolkata-UBoI"]) == (
        "West Bengal"
    )
    # work location in the title beats the regional-office city
    assert state("Premises at Lamphel, Imphal", org=["Union Bank › Regional office Kolkata-UBoI"]) == "Manipur"
    # but a state named in the authority conflicting with the title is not guessed
    assert state("Repair at Sirmour Himachal", org=["Madhya Pradesh Power Generating Company"]) is None


def test_village_prone_names_need_two_fields():
    assert state("Road at Sultanpur block") is None
    assert state("Road at Sultanpur", org=["Sultanpur Municipal Council"]) == "Uttar Pradesh"


@pytest.mark.parametrize(
    ("work", "org", "expected"),
    [
        ("Rural development works", ["Rural Development and Panchayat Raj Department Maharashtra"], "Maharashtra"),
        ("Sports mats", ["Sports and Youth Affairs Department Haryana"], "Haryana"),
        ("Supply of medicine", ["Municipal Corporation of Greater Mumbai (MCGM)"], "Maharashtra"),
        ("Dredging", ["Jawaharlal Nehru Port Authority"], "Maharashtra"),
        ("Works at JNPT", [], "Maharashtra"),
        ("Equipment", ["IIT Bombay"], "Maharashtra"),
        ("Hull blocks", ["Mazagon Dock Shipbuilders Limited"], "Maharashtra"),
        ("Printing", ["India Security Press, Nashik"], "Maharashtra"),
        ("Isotope lab", ["BARC Trombay"], "Maharashtra"),
        ("Coal", ["WCL Nagpur Area"], "Maharashtra"),
        ("Pumps", ["Central Railway Mumbai CSMT"], "Maharashtra"),
        ("Crude", ["Bharat Petroleum Mumbai Refinery"], "Maharashtra"),
        ("Dry dock", ["Hindustan Shipyard Limited"], "Andhra Pradesh"),
    ],
)
def test_departments_and_institutions(work, org, expected):
    assert state(work, org=org) == expected


def _tender(**geo):
    now = datetime.now(IST)
    return CanonicalTender(
        canonical_id=f"{abs(hash(json.dumps(geo))) % 10**20:024x}",
        identity={"source": "cppp_epublish", "source_portal": "https://eprocure.gov.in", "source_tender_id": "t1"},
        procurement={"title": "Works at Pune"},
        organization={"authority": "Some Dept"},
        geography=geo,
        dates={"bid_submission_end": now + timedelta(days=5)},
        status="active",
        provenance={"official_source_url": "https://eprocure.gov.in/t", "scraped_at": now, "first_seen_at": now,
                    "last_seen_at": now, "parser_version": "t", "content_hash": "x"},
    )


def test_adapter_state_is_never_overridden():
    assert infer_geography(_tender(state="Kerala")) is None  # title says Pune, adapter said Kerala
    tag = infer_geography(_tender())
    assert tag is not None and tag.state == "Maharashtra" and tag.district == "Pune"


def test_build_index_marks_inferred_state_only(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setattr(cli, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(cli, "STATUS_DIR", tmp_path / "status")
    store = TenderStore(tmp_path / "data")
    inferred = _tender()
    kept = _tender(state="Kerala", city="x")
    kept.canonical_id = f"{7:024x}"
    inferred.canonical_id = f"{8:024x}"
    for t in (inferred, kept):
        store.upsert(t)
    store.commit_state()
    assert CliRunner().invoke(cli.app, ["build-index"]).exit_code == 0
    docs = {d["id"]: d for d in json.loads(gzip.decompress((tmp_path / "data/indexes/search-docs.json.gz").read_bytes()))}
    assert docs[f"{8:024x}"]["state"] == "Maharashtra" and docs[f"{8:024x}"]["state_inferred"] is True
    assert docs[f"{7:024x}"]["state"] == "Kerala" and "state_inferred" not in docs[f"{7:024x}"]
    # the stored record itself is untouched
    assert TenderStore(tmp_path / "data").existing(f"{8:024x}").geography.state is None
