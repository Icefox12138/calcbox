"""Command line: one expression, JSON (or a short human line) out."""
import argparse
import json
import sys

from .backends import compute as run_compute
from .contract import BackendUnavailable, ComputeError


def main(argv=None):
    ap = argparse.ArgumentParser(prog="calcbox",
                                 description="compute one expression with provenance")
    ap.add_argument("expression")
    ap.add_argument("--op", default="simplify")
    ap.add_argument("--var", default="x")
    ap.add_argument("--point", default="0")
    ap.add_argument("--target", default=None)
    ap.add_argument("--backend", default="auto")
    ap.add_argument("--timeout", type=float, default=8.0)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    try:
        out = run_compute(args.expression, operation=args.op,
                               variable=args.var, point=args.point,
                               target=args.target, timeout=args.timeout,
                               backend=args.backend)
    except BackendUnavailable as e:
        print("backend unavailable: %s" % e, file=sys.stderr)
        return 3
    except ComputeError as e:
        print("bad request: %s" % e, file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print("%s = %s   [%s %s, %.1f ms]" % (
            out["input"], out["result"], out["backend"],
            out["engine_version"] or "?", out["elapsed_ms"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
