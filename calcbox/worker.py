"""Subprocess worker: one request in, one response out.

Runs in its own process so a timeout can kill it without taking the caller down.
The parent sends JSON on stdin; the worker installs the audit policy, executes,
and prints JSON on stdout.
"""
import json
import sys


def main(argv=None):
    from .backends import _execute_local
    from .sandbox import install

    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except ValueError as e:
        print(json.dumps({"error": "bad payload: %s" % e}))
        return 2
    install(payload.get("temp_dir"))
    try:
        out = _execute_local(**payload)
    except Exception as e:  # surfaced to the caller as a structured error
        print(json.dumps({"error": "%s: %s" % (type(e).__name__, e)}))
        return 1
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
