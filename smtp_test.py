import smtplib, ssl, socket
from report import config
s = config.SMTP; u, pw = s["username"], s["password"].replace(" ", "")
print("user:", u, "| password length (spaces hata ke):", len(pw))
for label, port, mode in (("465 SSL", 465, "ssl"), ("587 STARTTLS", 587, "tls")):
    step = "start"
    try:
        socket.create_connection(("smtp.gmail.com", port), timeout=10).close(); step = "connect ok"
        if mode == "ssl":
            c = smtplib.SMTP_SSL("smtp.gmail.com", port, context=ssl.create_default_context(), timeout=30)
        else:
            c = smtplib.SMTP("smtp.gmail.com", port, timeout=30); c.ehlo(); c.starttls(context=ssl.create_default_context()); c.ehlo()
        step = "handshake ok"; c.login(u, pw); step = "login ok"; c.quit()
        print(f"{label}: LOGIN OK")
    except Exception as e:
        print(f"{label}: FAIL after '{step}' ->", type(e).__name__, e)
