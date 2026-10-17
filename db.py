"""Optional order-system bookkeeping (MySQL), same tables the 2026 service used.

If DB_HOST is not set every function is a no-op, so the engine also runs on a laptop with no database.
A database error is logged and never stops a report from being delivered.
"""
from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from report import config

log = logging.getLogger("margdarshak.db")
IST = ZoneInfo("Asia/Kolkata")


def _now() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")


def enabled() -> bool:
    return bool(config.DB["host"] and config.DB["database"])


def _run(sql: str, params: tuple, want_id: bool = False):
    if not enabled():
        return None
    try:
        import mysql.connector
        conn = mysql.connector.connect(**config.DB)
        try:
            cur = conn.cursor()
            cur.execute(sql, params)
            conn.commit()
            return cur.lastrowid if want_id else True
        finally:
            conn.close()
    except Exception as exc:       # noqa: BLE001 - bookkeeping must never break delivery
        log.error("database call failed: %s", exc)
        return None


def start_job(data: dict) -> int | None:
    """Insert a queue row (status 0 = working) and return its id."""
    return _run(f"INSERT INTO {config.DB_QUEUE_TABLE} (user_id, full_name, recipient_email, status, updated_at, created_at) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (data.get("user_id"), data.get("name"), data.get("email"), 0, None, _now()), want_id=True)


def finish_job(job_id: int | None, status: int) -> None:
    """status: 1 = delivered, -1 = failed."""
    if job_id is not None:
        _run(f"UPDATE {config.DB_QUEUE_TABLE} SET status = %s, updated_at = %s WHERE id = %s", (status, _now(), job_id))


def mark_order(user_id, done: int = 1) -> None:
    if user_id is not None:
        _run(f"UPDATE {config.DB_ORDERS_TABLE} SET report_done = %s, report_submit_at = %s WHERE id = %s",
             (done, _now(), user_id))
