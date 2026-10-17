#!/usr/bin/env python3
"""Worker: takes orders from the queue, builds the PDF, e-mails it.

    python worker.py --concurrency 2              # 2 reports at a time (each uses one Chromium, ~0.5 GB RAM)
    python worker.py --concurrency 4 --once       # stop when the queue is empty (handy for a batch run)
    python worker.py --no-mail                    # build PDFs into generated_reports/ and keep them (testing)
    python worker.py --dry-run                    # fake render + fake mail, to test the queue itself

Run as many as the machine can carry; they never take the same job.  Ctrl+C / SIGTERM finishes the current job first.
"""
from __future__ import annotations

import argparse
import logging
import multiprocessing as mp
import os
import signal
import socket
import time
import threading
import traceback
from pathlib import Path

import db
import jobqueue as jq
import mailer
import report
from report import config

log = logging.getLogger("margdarshak.worker")

# Wrong order data or broken content will fail the same way every time, so do not retry those.
NO_RETRY = (ValueError, report.ContentError, report.RenderError)


def _real_render(payload: dict, year: int, pdf: Path) -> int:
    return report.generate(payload, year, pdf, chart_provider=config.chart_provider(),
                           allow_sample=config.ALLOW_SAMPLE_CONTENT)["pages"]


def _real_send(payload: dict, year: int, pdf: Path) -> None:
    mailer.send_report(payload["email"], payload.get("name", "User"), year, pdf)


def _fake_render(payload: dict, year: int, pdf: Path) -> int:
    time.sleep(float(os.environ.get("FAKE_RENDER_S", "0.2")))
    pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.write_bytes(b"%PDF-1.4 fake\n")
    return 1


def _fake_send(payload: dict, year: int, pdf: Path) -> None:
    time.sleep(0.02)


def process(conn, job: dict, *, render, send, keep_pdf: bool = False, out_dir: Path | None = None) -> str:
    """Do one claimed job.  Returns the final status of this attempt: done / queued (will retry) / failed."""
    out_dir = out_dir or config.OUTPUT_DIR
    payload, year, jid = job["payload"], job["year"], job["id"]
    safe = mailer._safe(str(payload.get("name") or "Report"))
    pdf = Path(job["pdf_path"]) if job.get("pdf_path") else out_dir / f"{safe}_Margdarshak_{year}_{jid}.pdf"
    db_id = payload.get("_db_job")
    try:
        if not pdf.exists():                                   # a retry after a mail failure reuses the PDF
            out_dir.mkdir(parents=True, exist_ok=True)
            pages = render(payload, year, pdf)
            jq.set_pdf(conn, jid, str(pdf), pages)
        if not keep_pdf:
            send(payload, year, pdf)
            pdf.unlink(missing_ok=True)                        # delivered: keep no copy of the customer's report
        jq.complete(conn, jid)
        db.finish_job(db_id, 1)
        db.mark_order(payload.get("user_id"), 1)
        return jq.DONE
    except Exception as exc:                                   # noqa: BLE001 - a worker must never die on one job
        retry = not isinstance(exc, NO_RETRY)
        status = jq.fail(conn, jid, f"{type(exc).__name__}: {exc}", retry=retry)
        if status == jq.FAILED:
            pdf.unlink(missing_ok=True)
            db.finish_job(db_id, -1)
            log.error("job %s FAILED for good: %s", jid, exc)
        else:
            log.warning("job %s failed (attempt %s), will retry: %s", jid, job["attempts"], exc)
        if os.environ.get("WORKER_TRACE"):
            traceback.print_exc()
        return status


def run_loop(name: str, render, send, keep_pdf: bool, once: bool, stop) -> None:
    conn = jq.connect()
    idle = 0
    while not stop.is_set():
        job = jq.claim(conn, name)
        if job is None:
            st = jq.stats(conn)
            if once and not st[jq.RUNNING] and not st[jq.QUEUED] and idle > 2:
                return
            idle += 1
            stop.wait(1.0)
            continue
        idle = 0
        t0 = time.time()
        status = process(conn, job, render=render, send=send, keep_pdf=keep_pdf)
        log.info("%s job %s -> %s (%.1fs)", name, job["id"], status, time.time() - t0)


def _child(idx: int, dry: bool, keep_pdf: bool, once: bool) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    name = f"{socket.gethostname()}:{os.getpid()}#{idx}"
    render, send = (_fake_render, _fake_send) if dry else (_real_render, _real_send)
    run_loop(name, render, send, keep_pdf, once, stop)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--concurrency", type=int, default=int(os.environ.get("WORKER_CONCURRENCY", "2")))
    ap.add_argument("--once", action="store_true", help="exit when the queue is empty")
    ap.add_argument("--no-mail", action="store_true", help="keep the PDFs in generated_reports/ instead of e-mailing")
    ap.add_argument("--dry-run", action="store_true", help="fake render and fake mail (tests the queue only)")
    a = ap.parse_args()
    jq.connect().close()                                       # create the file/schema once, before the children start
    procs = [mp.Process(target=_child, args=(i, a.dry_run, a.no_mail, a.once)) for i in range(a.concurrency)]
    for p in procs:
        p.start()
    try:
        for p in procs:
            p.join()
    except KeyboardInterrupt:
        for p in procs:
            p.join()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
