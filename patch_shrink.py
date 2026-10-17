from pathlib import Path
p = Path("report/render.py"); s = p.read_text(encoding="utf-8")
if "def _shrink(" in s:
    print("already patched"); raise SystemExit
a = "        shutil.move(str(tmp_pdf), str(output))"
b = "\n\ndef html_to_pdf("
if s.count(a) != 1 or s.count(b) != 1:
    raise SystemExit("STOP: render.py is different, send me your report/render.py")
helper = '\n\ndef _shrink(pdf: Path) -> None:\n    """Lossless clean-up (shared objects, deflate): ~20% smaller, pixel-identical.  Skipped if PyMuPDF is missing."""\n    try:\n        import pymupdf\n    except ImportError:\n        return\n    small = pdf.with_suffix(".small.pdf")\n    try:\n        doc = pymupdf.open(str(pdf))\n        doc.save(str(small), garbage=4, deflate=True, deflate_images=True, deflate_fonts=True, use_objstms=1)\n        doc.close()\n        if 0 < small.stat().st_size < pdf.stat().st_size:\n            small.replace(pdf)\n    except Exception:                      # noqa: BLE001 - the unshrunk PDF is still perfectly good\n        pass\n    finally:\n        small.unlink(missing_ok=True)\n'
s = s.replace(a, "        _shrink(tmp_pdf)\n" + a).replace(b, helper + b)
Path("report/render.py.bak").write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
p.write_text(s, encoding="utf-8"); print("patched")
