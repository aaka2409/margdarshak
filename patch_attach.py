from pathlib import Path
w = Path("worker.py"); s = w.read_text(encoding="utf-8")
if "ATTACH_LIMIT_MB" not in s or 'LINK_FALLBACK") == ' in s:
    print("worker.py: already attaches the PDF, nothing to change")
else:
    a = 'ATTACH_LIMIT_MB = float(os.environ.get("ATTACH_LIMIT_MB", "8"))     # bigger than this -> send a download link instead\nLINK_FALLBACK_MB = 3.0                                              # if even a smaller attachment is refused, fall back to a link\n'
    b = 'ATTACH_LIMIT_MB = float(os.environ.get("ATTACH_LIMIT_MB", "0"))     # 0 = always attach the PDF (default)\nLINK_FALLBACK = os.environ.get("LINK_FALLBACK") == "1"\nLINK_FALLBACK_MB = 3.0\n'
    assert s.count(a) == 1, "worker.py differs"
    s = s.replace(a, b)
    for x, y in (('    if size_mb <= ATTACH_LIMIT_MB:\n', '    if not ATTACH_LIMIT_MB or size_mb <= ATTACH_LIMIT_MB:\n'),
                 ('            if size_mb < LINK_FALLBACK_MB:\n                raise\n', '            if not LINK_FALLBACK or size_mb < LINK_FALLBACK_MB:\n                raise\n')):
        assert s.count(x) == 1; s = s.replace(x, y)
    w.write_text(s, encoding="utf-8"); print("worker.py: PDF is attached (links off)")
m = Path("mailer.py"); m.write_text(m.read_text(encoding="utf-8").replace("timeout=60", "timeout=300"), encoding="utf-8"); print("mailer.py: SMTP timeout 300s")
c = Path("report/config.py"); u = c.read_text(encoding="utf-8")
if '_get("MAX_ATTACHMENT_MB", "17")' in u:
    c.write_text(u.replace('_get("MAX_ATTACHMENT_MB", "17")', '_get("MAX_ATTACHMENT_MB", "18")'), encoding="utf-8"); print("config.py: limit 18 MB")
