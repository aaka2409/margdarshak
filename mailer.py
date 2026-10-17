"""Send the finished PDF by e-mail (SMTP).  Credentials come from the environment, never from code."""
from __future__ import annotations

import re
import smtplib
import unicodedata
import ssl
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


def render_body(full_name: str, year: int) -> str:
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html"]))
    return env.get_template("report_email.html").render(full_name=full_name, year=year)


def send_report(to_email: str, full_name: str, year: int, pdf_path: Path | str) -> None:
    smtp = config.SMTP
    if not (smtp["username"] and smtp["password"]):
        raise MailError("SMTP_USERNAME / SMTP_PASSWORD are not set")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", to_email or ""):
        raise MailError(f"'{to_email}' is not a valid e-mail address")
    pdf_path = Path(pdf_path)
    size_mb = pdf_path.stat().st_size / 1_048_576
    if size_mb > config.MAX_ATTACHMENT_MB:
        raise MailError(f"the PDF is {size_mb:.1f} MB, over the {config.MAX_ATTACHMENT_MB:g} MB attachment limit")

    msg = EmailMessage()
    msg["Subject"] = f"Your {year} Prediction Report is Ready!"
    msg["From"] = smtp["from_address"]
    msg["To"] = to_email
    msg.set_content(f"Your {year} report is attached.\nPlease open the HTML version of this e-mail for the best experience.")
    msg.add_alternative(render_body(full_name, year), subtype="html")
    msg.add_attachment(pdf_path.read_bytes(), maintype="application", subtype="pdf",
                       filename=f"{_safe(full_name)}_Margdarshak_{year}.pdf")
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
