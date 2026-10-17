"""Settings come from environment variables (or a .env file next to app.py).

Nothing secret lives in the code.  See .env.example for the full list.
"""
from __future__ import annotations

import os
from pathlib import Path

try:  # optional: load a local .env during development
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except Exception:  # pragma: no cover
    pass


def _get(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


REPORT_YEAR = int(_get("REPORT_YEAR", "2027"))
OUTPUT_DIR = Path(_get("OUTPUT_DIR", "generated_reports"))
VEDIC_ASTRO_API_KEY = _get("VEDIC_ASTRO_API_KEY")

DB = {"host": _get("DB_HOST"), "port": int(_get("DB_PORT", "3306") or 3306), "user": _get("DB_USER"),
      "password": _get("DB_PASSWORD"), "database": _get("DB_NAME")}
DB_QUEUE_TABLE = _get("DB_QUEUE_TABLE", "love_report_queue")     # the table the 2026 service wrote to
DB_ORDERS_TABLE = _get("DB_ORDERS_TABLE", "checkout_orders")

SMTP = {"host": _get("SMTP_HOST", "smtp.gmail.com"), "port": int(_get("SMTP_PORT", "465") or 465),
        "username": _get("SMTP_USERNAME"), "password": _get("SMTP_PASSWORD").replace(" ", ""),
        "from_address": _get("SMTP_FROM") or _get("SMTP_USERNAME")}
MAX_ATTACHMENT_MB = float(_get("MAX_ATTACHMENT_MB", "18"))        # Gmail refuses ~25 MB after encoding
ALLOW_SAMPLE_CONTENT = _get("ALLOW_SAMPLE_CONTENT") == "1"                # testing only
API_TOKEN = _get("API_TOKEN")                                      # if set, callers must send X-Api-Token


def chart_provider():
    """The configured chart source, or None when no API key is set (requests must then carry a chart)."""
    if not VEDIC_ASTRO_API_KEY:
        return None
    from .providers import VedicAstroProvider
    return VedicAstroProvider(VEDIC_ASTRO_API_KEY)
