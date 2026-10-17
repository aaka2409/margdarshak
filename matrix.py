import argparse, shutil, sys, time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
SIGNS = "Aries Taurus Gemini Cancer Leo Virgo Libra Scorpio Sagittarius Capricorn Aquarius Pisces".split()
LORD = dict(zip(SIGNS, "Mars Venus Mercury Moon Sun Mercury Venus Mars Jupiter Saturn Saturn Jupiter".split()))
ELEM = {s: ["Agni (Fire)", "Prithvi (Earth)", "Vayu (Air)", "Jal (Water)"][i % 4] for i, s in enumerate(SIGNS)}

def one(job):
    import report
    moon, asc, mul = job
    req = {"name": f"Matrix {moon} {asc} M{mul}", "dob": f"{mul:02d}/05/1995", "tob": "10:00", "pob": "Delhi", "sex": "Male",
           "lat": 28.61, "lon": 77.2, "tz": 5.5, "email": "", "user_id": "matrix",
           "chart": {"moon_sign": moon, "sun_sign": "Taurus", "ascendant": asc, "ascendant_lord": LORD[asc],
                     "rasi_lord": LORD[moon], "nakshatra": "Rohini", "nakshatra_lord": "Moon", "tithi": "S.Tritiya",
                     "yoga": "Vyatipata", "karana": "Garaja", "gana": "manushya", "yoni": "snake", "nadi": "Madhya",
                     "varna": "Vaishya", "vasya": "Manava", "paya": "Iron", "tatva": ELEM[moon]}}
    out = Path("out/matrix_tmp") / f"{moon}_{asc}_M{mul}_{time.time_ns()}.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        res = report.generate(req, 2027, out, strict=True)
        probs = res.get("problems", [])
        if probs:
            keep = Path("out/matrix_fail"); keep.mkdir(parents=True, exist_ok=True)
            shutil.copy(out, keep / out.name)
        out.unlink(missing_ok=True)
        return job, res["pages"], probs
    except Exception as exc:
        out.unlink(missing_ok=True)
        return job, 0, [f"{type(exc).__name__}: {exc}"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    jobs = [(SIGNS[mi], SIGNS[(mi * 5 + mul * 7) % 12], mul) for mi in range(12) for mul in range(1, 10)]
    t0 = time.time(); bad = 0; pages = set()
    with ProcessPoolExecutor(a.workers) as ex:
        futs = [ex.submit(one, j) for j in jobs]
        for n, f in enumerate(as_completed(futs), 1):
            job, pg, probs = f.result(); pages.add(pg)
            if probs:
                bad += 1; print(f"FAIL {job}: {probs[:3]}")
            if n % 10 == 0 or n == len(jobs):
                print(f"  {n}/{len(jobs)} done, {bad} failed, {time.time() - t0:.0f}s", flush=True)
    print(f"\nRESULT: {len(jobs) - bad}/{len(jobs)} clean | page counts: {sorted(pages - {0})}")

if __name__ == "__main__":
    main()
