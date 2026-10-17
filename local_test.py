#!/usr/bin/env python3
"""One command, whole flow on this computer: start the API + worker, place an order, wait, report, stop.

    python local_test.py you@gmail.com            # e-mails the PDF to you@gmail.com
    python local_test.py --keep                   # no e-mail; PDF is kept in generated_reports/
"""
import argparse, json, os, socket, subprocess, sys, time, urllib.error, urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("email", nargs="?", default="")
ap.add_argument("--keep", action="store_true", help="do not e-mail; keep the PDF in generated_reports/")
ap.add_argument("--name", default="Aakash Kumar")
ap.add_argument("--dob", default="24/09/2002")
ap.add_argument("--tob", default="19:15")
ap.add_argument("--pob", default="Delhi")
ap.add_argument("--lat", type=float, default=28.6139)
ap.add_argument("--lon", type=float, default=77.2090)
ap.add_argument("--port", type=int, default=8765)
a = ap.parse_args()
if not a.keep and "@" not in a.email:
    sys.exit("give an e-mail:  python local_test.py you@gmail.com     (or --keep to just save the PDF)")

env = dict(os.environ, EMBEDDED_WORKERS="1", PORT=str(a.port), DB_HOST="", QUEUE_DB="local_test_queue.db",
           WORKER_KEEP_PDF="1" if a.keep else "0")
for f in ("local_test_queue.db", "local_test_queue.db-wal", "local_test_queue.db-shm"):
    if os.path.exists(f):
        os.remove(f)
sys.path.insert(0, ".")
from report import config
token = config.API_TOKEN
SAMPLE_CHART = {"moon_sign": "Aquarius", "sun_sign": "Virgo", "ascendant": "Pisces", "ascendant_lord": "Jupiter", "rasi_lord": "Saturn",
                "nakshatra": "Dhanista", "nakshatra_lord": "Mars", "tithi": "S.Tritiya", "yoga": "Vyatipata", "karana": "Garaja",
                "gana": "rakshas", "yoni": "lion", "nadi": "Madhya", "varna": "Shudra", "vasya": "Manava", "paya": "Iron", "tatva": "Vayu (Air)"}
order = {"name": a.name, "dob": a.dob, "tob": a.tob, "pob": a.pob, "sex": "Male", "lat": a.lat, "lon": a.lon, "tz": 5.5,
         "email": a.email, "user_id": f"local{int(time.time())}"}
if not config.VEDIC_ASTRO_API_KEY:
    order["chart"] = SAMPLE_CHART
    print("NOTE: no VEDIC_ASTRO_API_KEY in .env -> using a fixed sample chart")
if a.keep and not order["email"]:
    order["email"] = "keep@example.com"

base = f"http://127.0.0.1:{a.port}"
hdr = {"Content-Type": "application/json", **({"X-Api-Token": token} if token else {})}

def call(path, body=None):
    req = urllib.request.Request(base + path, json.dumps(body).encode() if body is not None else None, hdr)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")

server = subprocess.Popen([sys.executable, "app.py"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
try:
    for _ in range(60):
        try:
            socket.create_connection(("127.0.0.1", a.port), 1).close(); break
        except OSError:
            if server.poll() is not None:
                sys.exit("server did not start:\n" + server.stderr.read().decode()[-1500:])
            time.sleep(0.5)
    code, res = call("/generate-2027-report", order)
    print(f"order -> HTTP {code} {res}")
    if code not in (200, 202):
        sys.exit("order rejected")
    jid, t0, last = res["job_id"], time.time(), ""
    while time.time() - t0 < 600:
        _, j = call(f"/jobs/{jid}")
        job = j.get("job", {})
        if job.get("status") != last:
            last = job.get("status"); print(f"  {time.time() - t0:4.0f}s  job {jid}: {last}" + (f"  error: {job['error']}" if job.get("error") else ""))
        if last in ("done", "failed"):
            break
        time.sleep(3)
    if last == "done":
        print(f"\nDONE: {job.get('pages')} pages in {time.time() - t0:.0f}s.", "PDF kept in generated_reports/" if a.keep else f"E-mailed to {a.email}  (check inbox + spam)")
    else:
        print(f"\nNOT DONE (status {last}). Last error: {job.get('error')}")
finally:
    server.terminate()
    try:
        server.wait(10)
    except subprocess.TimeoutExpired:
        server.kill()
