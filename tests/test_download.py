"""The e-mail button: a private link to the PDF, with a cover picture inline."""
import json
import smtplib
import time

import pytest

import mailer
from report import config


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DOWNLOAD_DIR", tmp_path / "dl")
    monkeypatch.setattr(config, "PUBLIC_BASE_URL", "https://example.test")
    monkeypatch.setitem(config.SMTP, "username", "u")
    monkeypatch.setitem(config.SMTP, "password", "p")
    monkeypatch.setitem(config.SMTP, "from_address", "noreply@example.test")
    monkeypatch.setitem(config.SMTP, "port", 587)
    sent = []

    class Fake:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def starttls(self, **k): pass
        def login(self, *a): pass
        def send_message(self, m): sent.append(m)

    monkeypatch.setattr(smtplib, "SMTP", Fake)
    pdf = tmp_path / "r.pdf"
    pdf.write_bytes(b"%PDF-1.4 test")
    return pdf, sent


def test_mail_has_button_link_and_no_attachment(env):
    pdf, sent = env
    mailer.send_report("a@b.co", "Nishant", 2027, pdf)
    m = sent[0]
    html = m.get_body(("html",)).get_content()
    assert "Download Now" in html and "https://example.test/d/" in html and "NISHANT" in html
    assert not any(p.get_content_type() == "application/pdf" for p in m.walk())


def test_cover_is_inline_and_removed_after_sending(env):
    pdf, sent = env
    pdf.with_suffix(".jpg").write_bytes(b"\xff\xd8\xff jpeg")
    mailer.send_report("a@b.co", "Nishant", 2027, pdf)
    assert "cid:cover" in sent[0].get_body(("html",)).get_content()
    assert any(p.get_content_type() == "image/jpeg" and p["Content-ID"] == "<cover>" for p in sent[0].walk())
    assert not pdf.with_suffix(".jpg").exists()


def test_link_downloads_the_pdf_and_bad_or_expired_links_do_not(env):
    import app
    pdf, sent = env
    mailer.send_report("a@b.co", "Nishant", 2027, pdf)
    path = "/d/" + sent[0].get_body(("html",)).get_content().split("/d/")[1].split('"')[0]
    c = app.app.test_client()
    r = c.get(path)
    assert r.status_code == 200 and r.data == b"%PDF-1.4 test" and "Nishant_Margdarshak_2027.pdf" in r.headers["Content-Disposition"]
    assert c.get("/d/" + "A" * 32).status_code == 404 and c.get("/d/short").status_code == 404
    assert c.get("/d/..%2Fetc%2Fpasswd").status_code == 404
    meta = next(config.DOWNLOAD_DIR.glob("*.json"))
    meta.write_text(json.dumps({"filename": "x.pdf", "expires": time.time() - 1}))
    assert c.get(path).status_code == 410
    assert mailer.purge_expired() == 1 and not list(config.DOWNLOAD_DIR.iterdir())
