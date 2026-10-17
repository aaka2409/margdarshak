"""Durable job queue for report orders (SQLite, one file, no extra service).

Why: rendering a report takes ~20 s of CPU and a whole Chromium, so the HTTP request must NOT do it.
The API only writes a row here and answers at once; separate worker processes take rows and build the PDFs.

Guarantees
  * a job is claimed by exactly one worker (claim runs in one BEGIN IMMEDIATE transaction)
  * a worker that dies mid-job loses its lease and the job goes back in the queue
  * failures retry with a growing delay, then end as 'failed' (never lost, never retried forever)
  * the same order (same idempotency key, e.g. user_id) is never queued twice
  * the customer's details are erased from the row as soon as the job is delivered

Limits: SQLite is for ONE machine (the API and its workers share the file).  For several machines, swap this
module for MySQL/Postgres with `SELECT ... FOR UPDATE SKIP LOCKED`; the function names below are the whole interface.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(os.environ.get("QUEUE_DB", "queue.db"))
MAX_ATTEMPTS = int(os.environ.get("JOB_MAX_ATTEMPTS", "4"))
BACKOFF_S = (30, 120, 600)            # wait before retry 2, 3, 4...
QUEUED, RUNNING, DONE, FAILED = "queued", "running", "done", "failed"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  idem_key      TEXT UNIQUE,
  year          INTEGER NOT NULL,
  payload       TEXT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'queued',
  attempts      INTEGER NOT NULL DEFAULT 0,
  run_after     REAL NOT NULL DEFAULT 0,
  lease_until   REAL NOT NULL DEFAULT 0,
  worker        TEXT,
  pdf_path      TEXT,
  pages         INTEGER,
  error         TEXT,
  created_at    REAL NOT NULL,
  updated_at    REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS jobs_pick ON jobs (status, run_after);
"""


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    c = sqlite3.connect(str(path or DB_PATH), timeout=30, isolation_level=None)   # autocommit; we open transactions
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
    c.execute("PRAGMA busy_timeout=30000")
    c.executescript(_SCHEMA)
    return c


@contextmanager
def tx(conn: sqlite3.Connection):
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise


def enqueue(conn, payload: dict, year: int, idem_key: str | None = None) -> tuple[int, bool]:
    """Add an order.  Returns (job_id, created).  A repeated idem_key returns the existing job (created=False)."""
    now = time.time()
    with tx(conn):
        if idem_key:
            row = conn.execute("SELECT id FROM jobs WHERE idem_key = ?", (idem_key,)).fetchone()
            if row:
                return row["id"], False
        cur = conn.execute("INSERT INTO jobs (idem_key, year, payload, created_at, updated_at) VALUES (?,?,?,?,?)",
                           (idem_key, year, json.dumps(payload, ensure_ascii=False), now, now))
        return cur.lastrowid, True


def claim(conn, worker: str, lease_s: float = 300) -> dict | None:
    """Take the oldest ready job, or None.  Also returns jobs whose worker vanished (lease expired)."""
    now = time.time()
    with tx(conn):
        conn.execute("UPDATE jobs SET status='queued', worker=NULL WHERE status='running' AND lease_until < ?", (now,))
        row = conn.execute("SELECT * FROM jobs WHERE status='queued' AND run_after <= ? ORDER BY id LIMIT 1",
                           (now,)).fetchone()
        if not row:
            return None
        conn.execute("UPDATE jobs SET status='running', worker=?, lease_until=?, attempts=attempts+1, updated_at=? WHERE id=?",
                     (worker, now + lease_s, now, row["id"]))
        job = dict(row)
        job["attempts"] += 1
        job["payload"] = json.loads(job["payload"])
        return job


def heartbeat(conn, job_id: int, lease_s: float = 300) -> None:
    conn.execute("UPDATE jobs SET lease_until=? WHERE id=? AND status='running'", (time.time() + lease_s, job_id))


def set_pdf(conn, job_id: int, pdf_path: str, pages: int) -> None:
    """Remember the rendered PDF so a retry after an e-mail failure does not render again."""
    conn.execute("UPDATE jobs SET pdf_path=?, pages=?, updated_at=? WHERE id=?", (pdf_path, pages, time.time(), job_id))


def complete(conn, job_id: int) -> None:
    """Delivered: erase the customer's details from the queue."""
    conn.execute("UPDATE jobs SET status='done', payload='{}', pdf_path=NULL, error=NULL, worker=NULL, updated_at=? WHERE id=?",
                 (time.time(), job_id))


def fail(conn, job_id: int, error: str, *, retry: bool = True) -> str:
    """Record a failure.  Returns the new status ('queued' for another try, or 'failed')."""
    now = time.time()
    with tx(conn):
        row = conn.execute("SELECT attempts FROM jobs WHERE id=?", (job_id,)).fetchone()
        n = row["attempts"] if row else MAX_ATTEMPTS
        if retry and n < MAX_ATTEMPTS:
            delay = BACKOFF_S[min(n - 1, len(BACKOFF_S) - 1)]
            conn.execute("UPDATE jobs SET status='queued', worker=NULL, error=?, run_after=?, updated_at=? WHERE id=?",
                         (error[:500], now + delay, now, job_id))
            return QUEUED
        conn.execute("UPDATE jobs SET status='failed', worker=NULL, error=?, updated_at=? WHERE id=?",
                     (error[:500], now, job_id))
        return FAILED


def get(conn, job_id: int) -> dict | None:
    row = conn.execute("SELECT id, status, attempts, pages, error, created_at, updated_at FROM jobs WHERE id=?",
                       (job_id,)).fetchone()
    return dict(row) if row else None


def stats(conn) -> dict:
    out = {QUEUED: 0, RUNNING: 0, DONE: 0, FAILED: 0}
    for r in conn.execute("SELECT status, COUNT(*) n FROM jobs GROUP BY status"):
        out[r["status"]] = r["n"]
    return out


def retry_failed(conn) -> int:
    """Put every failed job back in the queue (after you fixed the cause).  Their attempt counter restarts."""
    with tx(conn):
        cur = conn.execute("UPDATE jobs SET status='queued', attempts=0, run_after=0, error=NULL WHERE status='failed'")
        return cur.rowcount
