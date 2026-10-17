"""Run with:  python -m pytest -q   (the render test takes ~10 s)"""
import json
from pathlib import Path

import pytest

import report
from report.astro import mulank

ROOT = Path(__file__).resolve().parent.parent


def test_mulank():
    assert mulank("16/01/2002") == 7 and mulank("29/05/1990") == 2 and mulank("09/09/1999") == 9


def test_pack_is_complete():
    errors, _ = report.ContentPack(ROOT / "content", 2027).validate()
    assert errors == []


def test_reference_report_renders_in_strict_mode(tmp_path):
    req = json.load(open(ROOT / "fixtures" / "reference_aquarius.json"))
    res = report.generate(req, 2027, tmp_path / "r.pdf", allow_sample=True)
    assert res["pages"] >= 90 and (tmp_path / "r.pdf").stat().st_size > 100_000


def test_real_content_is_not_flagged_as_sample():
    assert not report.ContentPack(ROOT / "content", 2027).meta.get("sample")


def test_sample_text_is_refused_for_customers(tmp_path):
    import shutil
    root = tmp_path / "content"
    shutil.copytree(ROOT / "content" / "2027", root / "2027")
    yj = root / "2027" / "year.json"
    meta = json.loads(yj.read_text())
    meta["sample"] = True
    yj.write_text(json.dumps(meta))
    req = json.load(open(ROOT / "fixtures" / "reference_aquarius.json"))
    with pytest.raises(report.ContentError):
        report.generate(req, 2027, tmp_path / "r.pdf", content_root=root)
