#!/usr/bin/env python3
"""Load test against a running API.

    python tools/load_test.py --url http://localhost:8080 --n 100 --seconds 60 [--token X]

Sends N distinct orders spread over `seconds` (use --seconds 0 for one instant burst), then a duplicate of each
(must NOT create new jobs), and reports latency and how many were accepted.  Start `python worker.py` separately
to watch them drain:  curl localhost:8080/queue
"""
import argparse, json, statistics, threading, time, urllib.request, urllib.error

ap = argparse.ArgumentParser()
ap.add_argument("--url", default="http://localhost:8080")
ap.add_argument("--n", type=int, default=100)
ap.add_argument("--seconds", type=float, default=60)
ap.add_argument("--token", default="")
ap.add_argument("--prefix", default="lt")
a = ap.parse_args()
lat, codes, ids, lock = [], {}, set(), threading.Lock()


def post(i):
    body = json.dumps({"name": f"Load {i}", "dob": f"{i % 28 + 1:02d}/05/1995", "tob": "10:00", "pob": "Delhi", "sex": "Male",
                       "lat": 28.6, "lon": 77.2, "tz": 5.5, "email": f"load{i}@example.com", "user_id": f"{a.prefix}{i}"}).encode()
    req = urllib.request.Request(a.url + "/generate-2027-report", body, {"Content-Type": "application/json",
                                 **({"X-Api-Token": a.token} if a.token else {})})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            code, data = r.status, json.load(r)
    except urllib.error.HTTPError as e:
        code, data = e.code, {}
    with lock:
        lat.append(time.time() - t0)
        codes[code] = codes.get(code, 0) + 1
        if data.get("job_id"):
            ids.add(data["job_id"])


def run(offset):
    ts = []
    for i in range(a.n):
        t = threading.Thread(target=post, args=(i,))
        t.start(); ts.append(t)
        if a.seconds:
            time.sleep(a.seconds / a.n)
    for t in ts:
        t.join()


t0 = time.time(); run(0); first = time.time() - t0
print(f"{a.n} orders in {first:.1f}s -> status codes {codes}; distinct jobs {len(ids)}")
print(f"latency ms: median {statistics.median(lat)*1000:.0f}, p95 {sorted(lat)[int(len(lat)*.95)-1]*1000:.0f}, max {max(lat)*1000:.0f}")
codes.clear(); lat.clear(); before = len(ids)
run(0)                                       # same user_ids again = double-submit by the order system
print(f"duplicates re-sent: codes {codes}; new distinct jobs created: {len(ids) - before}")
