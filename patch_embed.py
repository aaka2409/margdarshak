from pathlib import Path
p = Path("app.py"); s = p.read_text(encoding="utf-8")
if "EMBEDDED_WORKERS" in s:
    print("already patched"); raise SystemExit
old = '''if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))'''
new = '''if __name__ == "__main__":
    # One command runs everything: the API plus the workers that build and e-mail the PDFs.
    # EMBEDDED_WORKERS=0 -> API only (run `python worker.py` yourself, e.g. on other machines).
    import multiprocessing as mp
    import worker as _worker
    _n = int(os.environ.get("EMBEDDED_WORKERS", "2"))
    _keep = os.environ.get("WORKER_KEEP_PDF") == "1"          # testing: keep PDFs in generated_reports/ instead of e-mailing
    for _i in range(_n):
        mp.Process(target=_worker._child, args=(_i, False, _keep, False), daemon=True).start()
    log.info("API on port %s with %s embedded worker(s)", os.environ.get("PORT", 8080), _n)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))'''
if s.count(old) != 1:
    raise SystemExit("STOP: end of app.py is different, send me your app.py")
Path("app.py.bak2").write_text(s, encoding="utf-8")
p.write_text(s.replace(old, new), encoding="utf-8"); print("patched")
