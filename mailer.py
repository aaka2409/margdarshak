"""E-mail the customer a private download link to the finished PDF (SMTP).  Credentials come from the environment, never from code."""
from __future__ import annotations

import json
import re
import secrets
import shutil
import smtplib
import ssl
import time
import unicodedata
from urllib.parse import quote
from email.message import EmailMessage
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from report import config

TEMPLATES = Path(__file__).resolve().parent / "email_templates"


class MailError(Exception):
    pass


def _safe(name: str) -> str:
    """File-name-safe version of the customer's name (letters of any language, digits, - and _)."""
    keep = "".join(c if (unicodedata.category(c)[0] in "LMN" or c in "-_") else "_" for c in (name or "User").strip())
    return re.sub(r"_+", "_", keep).strip("_") or "User"


def render_body(full_name: str, year: int, download_url: str = "#") -> str:
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html"]))
    return env.get_template("report_email.html").render(full_name=(full_name or "").strip(), year=year, download_url=download_url,
                                                        days=config.DOWNLOAD_DAYS)


def publish(pdf_path: Path | str, full_name: str, year: int) -> str:
    """Put a copy of the PDF where the e-mail button can reach it; return the private link.

    The link carries a random 192-bit token, so only the person who got the e-mail can open it.
    """
    token = secrets.token_urlsafe(24)
    config.DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(str(pdf_path), config.DOWNLOAD_DIR / f"{token}.pdf")
    name = f"{_safe(full_name)}_Margdarshak_{year}.pdf"
    (config.DOWNLOAD_DIR / f"{token}.json").write_text(json.dumps({"filename": name, "expires": time.time() + config.DOWNLOAD_DAYS * 86400}))
    return f"{config.PUBLIC_BASE_URL}/d/{token}/{quote(name)}"


def purge_expired() -> int:
    """Delete downloads past their date.  Returns how many were removed."""
    n, now = 0, time.time()
    for meta in config.DOWNLOAD_DIR.glob("*.json"):
        try:
            if json.loads(meta.read_text()).get("expires", 0) < now:
                meta.with_suffix(".pdf").unlink(missing_ok=True)
                meta.unlink(missing_ok=True)
                n += 1
        except (OSError, ValueError):
            continue
    return n


def send_report(to_email: str, full_name: str, year: int, pdf_path: Path | str) -> None:
    smtp = config.SMTP
    if not (smtp["username"] and smtp["password"]):
        raise MailError("SMTP_USERNAME / SMTP_PASSWORD are not set")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", to_email or ""):
        raise MailError(f"'{to_email}' is not a valid e-mail address")
    pdf_path = Path(pdf_path)
    url = publish(pdf_path, full_name, year)

    msg = EmailMessage()
    msg["Subject"] = f"Your Margdarshak {year} Report is Ready!"
    msg["From"] = smtp["from_address"]
    msg["To"] = to_email
    msg.set_content(f"Hello {full_name},\n\nYour Margdarshak {year} report is ready.\nDownload it here: {url}\n\n"
                    f"This private link stays active for {config.DOWNLOAD_DAYS} days.\n\nTeam Astro Diva Pratihast\n"
                    "support@divapratihast.com | +91 9311620907\n")
    msg.add_alternative(render_body(full_name, year, url), subtype="html")
    try:
        if smtp["port"] == 465:
            with smtplib.SMTP_SSL(smtp["host"], smtp["port"], context=ssl.create_default_context(), timeout=300) as s:
                s.login(smtp["username"], smtp["password"])
                s.send_message(msg)
        else:
            with smtplib.SMTP(smtp["host"], smtp["port"], timeout=300) as s:
                s.starttls(context=ssl.create_default_context())
                s.login(smtp["username"], smtp["password"])
                s.send_message(msg)
    except (smtplib.SMTPException, OSError) as exc:
        raise MailError(f"could not send to {to_email}: {exc}") from exc
