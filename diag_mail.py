import json, os, smtplib, ssl, time
from email.message import EmailMessage
from pathlib import Path
import report, mailer
from report import config
req = json.load(open("fixtures/reference_aquarius.json"))
Path("out").mkdir(exist_ok=True)
t = time.time(); res = report.generate(req, 2027, "out/diag.pdf")
mb = os.path.getsize("out/diag.pdf") / 1_048_576
print(f"1) PDF: {res['pages']} pages, {mb:.1f} MB, {time.time()-t:.0f}s | pymupdf installed:", __import__("importlib").util.find_spec("pymupdf") is not None)
s = config.SMTP
print("2) SMTP:", s["host"], s["port"], s["username"], "| password length:", len(s["password"]))
try:
    with smtplib.SMTP_SSL(s["host"], s["port"], context=ssl.create_default_context(), timeout=60) as c:
        c.login(s["username"], s["password"]); print("   login OK")
        m = EmailMessage(); m["Subject"] = "SMTP small test"; m["From"] = s["from_address"]; m["To"] = s["username"]; m.set_content("ok")
        c.send_message(m); print("   small mail sent")
except Exception as e:
    print("   SMALL MAIL FAILED:", type(e).__name__, e); raise SystemExit
t = time.time()
try:
    mailer.send_report(s["username"], "Diag Test", 2027, "out/diag.pdf")
    print(f"3) BIG MAIL SENT with {mb:.1f} MB attachment in {time.time()-t:.0f}s -> check your inbox")
except Exception as e:
    print(f"3) BIG MAIL FAILED after {time.time()-t:.0f}s:", type(e).__name__, e)
