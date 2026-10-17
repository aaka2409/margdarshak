"""HTTP service: the order system posts a customer, gets the report e-mailed.

    python app.py                       # development server on http://localhost:8080
    waitress-serve --port=8080 app:app  # production

POST /generate-2027-report   (also /generate-<year>-report)
    JSON: name, dob (DD/MM/YYYY), tob (HH:MM), pob, lat, lon, tz, email, sex, user_id
    Normal use: the order is QUEUED and the API answers 202 {job_id} at once; `python worker.py` builds the PDF
    and e-mails it.  The same user_id posted twice is queued once.
    ?email=0 -> old behaviour for testing: build the PDF in this request and return it (slow, 2 at a time).
GET  /jobs/<id>              status: queued / running / done / failed
GET  /queue                  counts per status
If API_TOKEN is set, callers must send it in the X-Api-Token header.

"""
from __future__ import annotations

import hmac
import logging
import os
import re
import tempfile
import threading
from pathlib import Path

from flask import Flask, jsonify, request, send_file

import db
import jobqueue as jq
import mailer
import report
from report import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("margdarshak")
app = Flask(__name__)

# Chromium is heavy: render this many reports at once, make the rest wait.
_slots = threading.BoundedSemaphore(int(os.environ.get("MAX_PARALLEL_REPORTS", "2")))
MAX_QUEUE = int(os.environ.get("MAX_QUEUE", "20000"))      # refuse (503) beyond this many waiting orders
config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _authorised() -> bool:
    if not config.API_TOKEN:
        return True
    return hmac.compare_digest(request.headers.get("X-Api-Token", ""), config.API_TOKEN)


@app.get("/")
def home():
    return f"Margdarshak report API is running (default year {config.REPORT_YEAR})."


@app.post("/chart")
def chart_only():
    """Live test of the chart lookup (VedicAstroAPI) without needing any report text."""
    if not _authorised():
        return jsonify(status="error", message="unauthorised"), 401
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(status="error", message="send a JSON object"), 400
    data = {k: v for k, v in data.items() if k != "chart"}
    provider = config.chart_provider()
    if provider is None:
        return jsonify(status="error", message="VEDIC_ASTRO_API_KEY is not set in .env"), 500
    try:
        chart = provider.get_chart(report.Person.from_request(data))
        from report.astro import mulank
        return jsonify(status="success", mulank=mulank(data["dob"]),
                       chart=chart if isinstance(chart, dict) else chart.__dict__)
    except (ValueError, report.ChartError) as exc:
        return jsonify(status="error", message=str(exc)), 422


def _enqueue(data: dict, year: int):
    """Validate the order cheaply (no chart lookup, no rendering) and put it in the queue."""
    try:
        report.Person.from_request(data)
    except ValueError as exc:
        return jsonify(status="error", message=str(exc)), 422
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", str(data.get("email", ""))):
        return jsonify(status="error", message="'email' is not a valid address"), 422
    conn = jq.connect()
    try:
        if jq.stats(conn)[jq.QUEUED] >= MAX_QUEUE:
            resp = jsonify(status="error", message="too many orders waiting, try again shortly")
            resp.headers["Retry-After"] = "60"
            return resp, 503
        data = {k: v for k, v in data.items() if k != "_db_job"}
        uid = data.get("user_id")
        key = f"{year}:{uid}" if uid not in (None, "") else None
        if key and conn.execute("SELECT 1 FROM jobs WHERE idem_key = ?", (key,)).fetchone() is None:
            data["_db_job"] = db.start_job(data)
        elif not key:
            data["_db_job"] = db.start_job(data)
        job_id, created = jq.enqueue(conn, data, year, key)
        return jsonify(status="queued", job_id=job_id, duplicate=not created), 202 if created else 200
    finally:
        conn.close()


@app.get("/jobs/<int:job_id>")
def job_status(job_id: int):
    if not _authorised():
        return jsonify(status="error", message="unauthorised"), 401
    conn = jq.connect()
    try:
        job = jq.get(conn, job_id)
    finally:
        conn.close()
    if not job:
        return jsonify(status="error", message="no such job"), 404
    return jsonify(status="success", job=job)


@app.get("/queue")
def queue_stats():
    if not _authorised():
        return jsonify(status="error", message="unauthorised"), 401
    conn = jq.connect()
    try:
        return jsonify(status="success", **jq.stats(conn))
    finally:
        conn.close()


@app.post("/generate-<int:year>-report")
def generate_report(year: int):
    if not _authorised():
        return jsonify(status="error", message="unauthorised"), 401
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(status="error", message="send a JSON object"), 400
    send_mail = request.args.get("email", "1") != "0"
    if send_mail and not data.get("email"):
        return jsonify(status="error", message="'email' is required"), 400
    if send_mail:
        return _enqueue(data, year)

    job_id = db.start_job(data)
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", str(data.get("user_id") or data.get("name") or "report"))
    pdf = config.OUTPUT_DIR / f"{year}_report_{safe}.pdf"
    try:
        with _slots:
            result = report.generate(data, year, pdf, chart_provider=config.chart_provider(),
                                      allow_sample=config.ALLOW_SAMPLE_CONTENT)
        if send_mail:
            mailer.send_report(data["email"], data.get("name", "User"), year, pdf)
    except (ValueError, report.ChartError) as exc:            # bad order data or chart lookup failed
        db.finish_job(job_id, -1)
        log.warning("rejected %s: %s", safe, exc)
        return jsonify(status="error", message=str(exc)), 422
    except (report.ContentError, report.RenderError, mailer.MailError) as exc:
        db.finish_job(job_id, -1)
        log.error("failed %s: %s", safe, exc)
        return jsonify(status="error", message=str(exc)), 500
    except Exception as exc:                                    # noqa: BLE001
        db.finish_job(job_id, -1)
        log.exception("unexpected failure for %s", safe)
        return jsonify(status="error", message=f"unexpected error: {exc}"), 500

    db.finish_job(job_id, 1)
    db.mark_order(data.get("user_id"), 1)
    if not send_mail:
        return send_file(pdf, mimetype="application/pdf", as_attachment=True, download_name=pdf.name)
    pdf.unlink(missing_ok=True)                                 # delivered by e-mail; keep no copy of the customer's report
    return jsonify(status="success", message=f"{year} report generated and e-mailed.", pages=result["pages"])


if __name__ == "__main__":
    # One command runs everything: the API plus the workers that build and e-mail the PDFs.
    # EMBEDDED_WORKERS=0 -> API only (run `python worker.py` yourself, e.g. on other machines).
    import multiprocessing as mp
    import worker as _worker
    _n = int(os.environ.get("EMBEDDED_WORKERS", "2"))
    _keep = os.environ.get("WORKER_KEEP_PDF") == "1"          # testing: keep PDFs in generated_reports/ instead of e-mailing
    for _i in range(_n):
        mp.Process(target=_worker._child, args=(_i, False, _keep, False), daemon=True).start()
    log.info("API on port %s with %s embedded worker(s)", os.environ.get("PORT", 8080), _n)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
