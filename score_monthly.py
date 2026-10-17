"""Fill missing monthly scores (0-100) from the tone of the written forecast.

NOT an independent astrological calculation: the score only mirrors how supportive vs.
cautionary the text written for that month/area is. Only null scores are filled, so any
score entered by hand (or from a spreadsheet) is never overwritten.
Usage: python score_monthly.py [year]      (default 2027)
"""
import json, re, sys, statistics
from pathlib import Path

YEAR = sys.argv[1] if len(sys.argv) > 1 else "2027"
POS = r"""support\w*|favour\w*|productive|gains?|growth|improv\w+|opportunit\w+|progress\w*|confiden\w+|harmony|
warm\w*|clarity|clearer|stabil\w+|stronger|strengthen\w*|reward\w*|positive\w*|beneficial|useful|meaningful|
cooperat\w+|success\w*|relief|refresh\w*|lighter|optimistic|inspir\w+|momentum|encouraging|secur\w+|helpful|
valuable|promising|comfortabl\w+|easier|ease|recognition|settled|grounded|resilien\w+|mature\w*|constructive"""
NEG = r"""avoid\w*|careful\w*|caution\w*|tension|pressure|friction|misunderstanding\w*|delay\w*|expenses?|fatigue|
drain\w*|conflict\w*|difficult\w*|risk\w*|unresolved|overthink\w*|stress\w*|exhaust\w*|demanding|tests?|tested|
restless\w*|unnecessary|impuls\w+|rush\w*|disagreement\w*|hidden|withdraw\w*|distance|uncertain\w*|confus\w+|
struggle\w*|competition|obligations?|repayments?|burden\w*|challeng\w+|mixed|overwhelm\w*|tired\w*|irregular"""
POS_RE = re.compile(r"\b(?:%s)\b" % "|".join(x.strip() for x in POS.split("\n")), re.I)
NEG_RE = re.compile(r"\b(?:%s)\b" % "|".join(x.strip() for x in NEG.split("\n")), re.I)
CENTER, SPREAD, LO, HI = 76.0, 24.0, 58, 94

def raw(text):
    w = max(len(text.split()), 1)
    return 100.0 * (len(POS_RE.findall(text)) - len(NEG_RE.findall(text))) / w

def main():
    base = Path("content") / YEAR / "monthly"
    files = sorted(base.glob("*.json"))
    docs, vals = {}, []
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8")); docs[f] = d
        for m, areas in d["months"].items():
            for a, ps in areas.items():
                t = " ".join(ps)
                if t and "TODO" not in t: vals.append(raw(t))
    mu = statistics.mean(vals); sd = statistics.pstdev(vals) or 1.0
    filled = 0
    for f, d in docs.items():
        for m, areas in d["months"].items():
            for a, ps in areas.items():
                t = " ".join(ps)
                if not t or "TODO" in t or d["scores"][m].get(a) is not None: continue
                z = (raw(t) - mu) / sd
                d["scores"][m][a] = int(max(LO, min(HI, round(CENTER + z * SPREAD / 3))))
                filled += 1
        f.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"filled {filled} scores in {len(files)} files (mean raw {mu:.2f}, sd {sd:.2f})")
main()
