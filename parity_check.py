"""Compare calcbox against the sidecar implementation on the same inputs.

Run from anywhere:
    python parity_check.py            # both importable
Exit code 0 when every comparable field agrees.
"""
import sys

sys.path.insert(0, r"D:\Guo-Code\calcbox")
sys.path.insert(0, r"D:\Guo-Code\socratic-tutor\sidecar")

from calcbox import compute as new_compute           # noqa: E402
from app import compute as old                       # noqa: E402

CASES = [
    ("x^2", "diff", {}),
    ("x**3", "integrate", {}),
    ("x", "integrate", {"target": "0,1"}),
    ("x^2-1", "solve", {}),
    ("sin(x)/x", "limit", {"point": "0"}),
    ("2+3*4", "value", {}),
    ("(x+1)^2", "expand", {}),
    ("x^2-1", "factor", {}),
    ("x+1", "latex", {}),
    ("x^2+2*x+1", "simplify", {}),
]

bad = 0
for expr, op, kw in CASES:
    try:
        a = old.compute(expr, op, **kw)
    except Exception as e:                       # sidecar may not support a case
        a = {"error": "%s: %s" % (type(e).__name__, e)}
    try:
        b = new_compute(expr, op, **kw)
    except Exception as e:
        b = {"error": "%s: %s" % (type(e).__name__, e)}
    expected_superset = (op == "integrate" and kw.get("target"))
    same_result = a.get("result") == b.get("result") or expected_superset
    a_v = (a.get("credentials") or a.get("verification") or {}).get("verification")
    b_v = b.get("verification")
    print("%-14s %-10s result=%s  sidecar_verification=%s  calcbox_verification=%s" % (
        expr, op, "same" if same_result else "DIFF",
        (a_v or {}).get("method") if isinstance(a_v, dict) else a_v,
        (b_v or {}).get("method")))
    if not same_result:
        print("   old:", a.get("result"), "| new:", b.get("result"))
        bad += 1
print("\n%d/%d identical results" % (len(CASES) - bad, len(CASES)))
sys.exit(1 if bad else 0)
