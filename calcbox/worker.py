"""Subprocess worker: one request in, one response out.

Runs in its own process so a timeout can kill it without taking the caller down
(an in-process thread cannot be cancelled, and a stuck SymPy integral would keep
the interpreter alive at exit). The parent writes JSON to a file, spawns us with
that path and a result path, and reads the reply back.
"""
import json
import os
import sys


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2:
        return 2
    in_path, out_path = argv
    with open(in_path, encoding="utf-8") as fh:
        payload = json.load(fh)

    try:
        from .sandbox import install
        install(os.environ.get("CALCBOX_SANDBOX_TEMP") or os.path.dirname(in_path))
    except Exception as e:  # policy problems must not look like compute errors
        body = {"ok": False, "kind": "internal",
                "error": "sandbox install failed: %s" % e}
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(body, fh)
        return 1

    # Inside the worker we are already the sandboxed process: never re-spawn.
    os.environ["CALCBOX_WORKER"] = "0"
    from .backends import BackendUnavailable, ComputeError, _execute_local
    try:
        out = _execute_local(**payload)
        body = {"ok": True, "out": out}
    except BackendUnavailable as e:
        body = {"ok": False, "kind": "unavailable", "error": str(e)}
    except ComputeError as e:
        body = {"ok": False, "kind": "compute", "error": str(e)}
    except Exception as e:
        body = {"ok": False, "kind": "internal", "error": str(e)[:300]}
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(body, fh, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
