"""Queue tests: python -m pytest -q tests/test_queue.py   (a few seconds, no browser, no network)"""
import multiprocessing as mp
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import jobqueue as jq  # noqa: E402
import worker  # noqa: E402


@pytest.fixture()
def conn(tmp_path):
    c = jq.connect(tmp_path / "q.db")
    yield c
    c.close()


def _order(i):
    return {"name": f"N{i}", "dob": "16/01/2002", "email": f"n{i}@example.com", "user_id": i}


def test_same_order_is_queued_once(conn):
    a, created_a = jq.enqueue(conn, _order(1), 2027, "2027:1")
    b, created_b = jq.enqueue(conn, _order(1), 2027, "2027:1")
    assert a == b and created_a and not created_b
    assert jq.stats(conn)["queued"] == 1


def _grab(args):
    path, n = args
    c = jq.connect(path)
    got = []
    while True:
        j = jq.claim(c, f"w{mp.current_process().pid}")
        if j is None:
            return got
        got.append(j["id"])
        jq.complete(c, j["id"])


def test_every_job_is_claimed_exactly_once_by_many_processes(tmp_path):
    path = tmp_path / "q.db"
    c = jq.connect(path)
    for i in range(300):
        jq.enqueue(c, _order(i), 2027, f"2027:{i}")
    with mp.Pool(6) as pool:
        lists = pool.map(_grab, [(path, 0)] * 6)
    ids = [x for l in lists for x in l]
    assert len(ids) == 300 and len(set(ids)) == 300          # none twice, none missed
    assert sum(1 for l in lists if l) >= 2                   # really shared between workers
    assert jq.stats(c)["done"] == 300


def test_dead_worker_job_comes_back(conn):
    jq.enqueue(conn, _order(1), 2027, "k1")
    j = jq.claim(conn, "w1", lease_s=0.2)
    assert j and jq.claim(conn, "w2") is None                 # still leased
    time.sleep(0.4)                                           # w1 "died"
    j2 = jq.claim(conn, "w2")
    assert j2 and j2["id"] == j["id"] and j2["attempts"] == 2


def test_failure_retries_then_fails_for_good(conn, monkeypatch):
    monkeypatch.setattr(jq, "BACKOFF_S", (0, 0, 0))
    monkeypatch.setattr(jq, "MAX_ATTEMPTS", 3)
    jq.enqueue(conn, _order(1), 2027, "k1")
    seen = []
    for _ in range(5):
        j = jq.claim(conn, "w")
        if not j:
            break
        seen.append(jq.fail(conn, j["id"], "boom"))
    assert seen == ["queued", "queued", "failed"]
    assert jq.stats(conn)["failed"] == 1
    assert jq.retry_failed(conn) == 1 and jq.stats(conn)["queued"] == 1


def test_bad_data_is_not_retried(conn, tmp_path):
    jq.enqueue(conn, _order(1), 2027, "k1")
    j = jq.claim(conn, "w")

    def render(p, y, pdf):
        raise ValueError("bad dob")
    st = worker.process(conn, j, render=render, send=lambda *a: None, out_dir=tmp_path)
    assert st == "failed" and jq.stats(conn)["failed"] == 1


def test_mail_failure_retries_without_rendering_again(conn, tmp_path, monkeypatch):
    monkeypatch.setattr(jq, "BACKOFF_S", (0, 0, 0))
    jq.enqueue(conn, _order(1), 2027, "k1")
    renders, sends = [], []

    def render(p, y, pdf):
        renders.append(1)
        pdf.write_bytes(b"%PDF")
        return 3

    def send(p, y, pdf):
        sends.append(1)
        if len(sends) == 1:
            raise OSError("smtp down")
    j = jq.claim(conn, "w")
    assert worker.process(conn, j, render=render, send=send, out_dir=tmp_path) == "queued"
    j = jq.claim(conn, "w")
    assert j["pdf_path"]
    assert worker.process(conn, j, render=render, send=send, out_dir=tmp_path) == "done"
    assert len(renders) == 1 and len(sends) == 2              # rendered once, mailed twice
    row = conn.execute("SELECT payload, pdf_path FROM jobs").fetchone()
    assert row["payload"] == "{}" and row["pdf_path"] is None   # customer data erased after delivery
    assert not list(tmp_path.glob("*.pdf"))                   # and the PDF deleted
