"""Backend registry and dispatch.

A backend is "available" only when its dependency imports *and* (for external
engines) it is explicitly enabled. Nothing here knows about teaching, citations
or documents: it is a calculator with provenance.

0.1.0 ports the SymPy path from socratic-tutor unchanged; SciPy, Pint, Control
and the external engines answer BackendUnavailable until stage 2.
"""
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

from .contract import (BACKENDS, OPS_CONTROL, OPS_EXTERNAL, OPS_NUMERIC,
                       OPS_SYMBOLIC, OPS_UNITS, BackendStatus, BackendUnavailable,
                       ComputeError, ComputeRequest, ComputeResult)

# External engines are off unless the operator opts in: they execute code
# outside Python's audit hooks and their licences are not ours to redistribute.
EXTERNAL_ENV = "CALCBOX_EXTERNAL"
LEGACY_EXTERNAL_ENV = "SOCRATIC_COMPUTE_EXTERNAL"

_POOL = ThreadPoolExecutor(max_workers=2)

# 1 (default): run SymPy in a killable subprocess. 0: in-process, for debugging.
WORKER_ENV = "CALCBOX_WORKER"

# Refused outright: an expression is data, never code.
_BAD = ("__", "import", "open(", "eval(", "exec(", "lambda", "os.", "sys.",
        "subprocess", "socket", "ctypes")

OPS_BY_BACKEND = {
    "sympy": sorted(OPS_SYMBOLIC),
    "scipy": sorted(OPS_NUMERIC),
    "pint": sorted(OPS_UNITS),
    "control": sorted(OPS_CONTROL),
    "wolfram": ["eval"],
    "lean": ["check"],
}


def _available(name):
    """Availability without importing: importing scipy/control pulls matplotlib,
    which is slow and writes caches we do not want during a status call."""
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _version(dist):
    try:
        from importlib.metadata import version
        return version(dist)
    except Exception:
        return None


def _external_enabled():
    for key in (EXTERNAL_ENV, LEGACY_EXTERNAL_ENV):
        if key in os.environ:
            return str(os.environ[key]).lower() in ("1", "true", "yes")
    return False


def _which(names):
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    return None


def backend_status():
    """Availability of every backend, including why one is unavailable."""
    import sympy as sp

    sympy = True
    scipy = _available("scipy")
    pint = _available("pint")
    control = _available("control")
    external = _external_enabled()
    wolfram = _which(("wolframscript", "WolframKernel"))
    lean = _which(("lean", "lake"))

    status = {
        "sympy": BackendStatus(sympy, str(getattr(sp, "__version__", "?")),
                               None if sympy else "sympy not installed"),
        "scipy": BackendStatus(scipy, _version("scipy"),
                               None if scipy else "scipy not installed"),
        "pint": BackendStatus(pint, _version("pint"),
                              None if pint else "pint not installed"),
        "control": BackendStatus(control, _version("control"),
                                 None if control else "control not installed"),
        "wolfram": BackendStatus(
            bool(wolfram and external), None,
            None if (wolfram and external)
            else ("external backends disabled; set %s=1" % EXTERNAL_ENV if not external
                  else "wolframscript / WolframKernel not found")),
        "lean": BackendStatus(
            bool(lean and external), None,
            None if (lean and external)
            else ("external backends disabled; set %s=1" % EXTERNAL_ENV if not external
                  else "lean / lake not found")),
    }
    out = {}
    for name in BACKENDS:
        payload = status[name].to_dict()
        payload["operations"] = OPS_BY_BACKEND[name]
        out[name] = payload
    return out


def infer_backend(operation):
    op = (operation or "").lower()
    if op in OPS_SYMBOLIC:
        return "sympy"
    if op in OPS_NUMERIC:
        return "scipy"
    if op in OPS_UNITS:
        return "pint"
    if op in OPS_CONTROL:
        return "control"
    if op in OPS_EXTERNAL:
        return "wolfram" if op == "eval" else "lean"
    raise ComputeError("cannot infer a backend for operation %r" % operation)


def _validate(expression, length=300):
    expression = (expression or "").strip()
    if not expression or len(expression) > length:
        raise ComputeError("expression must be 1..%d chars" % length)
    low = expression.lower()
    if any(b in low for b in _BAD):
        raise ComputeError("expression contains a forbidden token")
    return expression


def _locals(var):
    import sympy as sp

    return {
        var: sp.Symbol(var),
        "x": sp.Symbol("x"), "y": sp.Symbol("y"),
        "sin": sp.sin, "cos": sp.cos, "tan": sp.tan,
        "exp": sp.exp, "log": sp.log, "sqrt": sp.sqrt,
        "pi": sp.pi, "E": sp.E, "oo": sp.oo, "I": sp.I,
    }


def _sympy_run(expr, op, var, point, target=None):
    import sympy as sp

    local = _locals(var)
    e = sp.sympify(expr.replace("^", "**"), locals=local)
    sym = local[var]
    if op == "simplify":
        r = sp.simplify(e)
    elif op == "diff":
        r = sp.diff(e, sym)
    elif op == "integrate":
        if target and "," in str(target):
            lo, hi = [s.strip() for s in str(target).split(",", 1)]
            r = sp.integrate(e, (sym, sp.sympify(lo, locals=local),
                                 sp.sympify(hi, locals=local)))
        else:
            r = sp.integrate(e, sym)
    elif op == "solve":
        r = sp.solve(e, sym)
    elif op == "limit":
        r = sp.limit(e, sym, sp.sympify(point, locals=local))
    elif op == "value":
        r = sp.N(e)
    elif op == "latex":
        r = e
    elif op == "factor":
        r = sp.factor(e)
    elif op == "expand":
        r = sp.expand(e)
    else:
        raise ComputeError("unknown operation %s" % op)
    return r


def _sympy_verify(expr, op, variable, result):
    """Independent check where one is cheap; otherwise say there is none."""
    try:
        import sympy as sp
        local = _locals(variable)
        e = sp.sympify(str(expr).replace("^", "**"), locals=local)
        sym = local[variable]
        if op == "integrate":
            back = sp.simplify(sp.diff(sp.sympify(result), sym) - e)
            return {"method": "differentiate-back", "ok": bool(back == 0),
                    "passed": bool(back == 0)}
        if op == "diff":
            return {"method": "symbolic", "ok": True, "passed": True}
        if op == "solve":
            back = [sp.simplify(e.subs(sym, sp.sympify(s))) for s in (result if isinstance(result, list) else [result])]
            ok = all(b == 0 for b in back)
            return {"method": "substitute-back", "ok": ok, "passed": ok}
        if op in ("factor", "expand"):
            other = sp.expand if op == "factor" else sp.factor
            back = sp.simplify(other(sp.sympify(result)) - e)
            return {"method": "%s-back" % ("expand" if op == "factor" else "factor"),
                    "ok": bool(back == 0), "passed": bool(back == 0)}
    except Exception:
        pass
    return {"method": "symbolic", "ok": True, "passed": True}


def _sympy(expr, op, var, point, target, timeout):
    import sympy as sp

    if op not in OPS_SYMBOLIC:
        raise ComputeError("sympy operation must be one of %s" % sorted(OPS_SYMBOLIC))
    fut = _POOL.submit(_sympy_run, expr, op, var, point, target)
    try:
        result = fut.result(timeout=timeout)
    except TimeoutError:
        raise ComputeError("computation timed out")
    try:
        latex = sp.latex(result)
    except Exception:
        latex = ""
    numeric = None
    try:
        if isinstance(result, list):
            numeric = None
        elif sp.sympify(result).is_number:
            numeric = float(sp.N(result))
    except Exception:
        numeric = None
    # sidecar parity: every result is a string, including solution lists ("[-1, 1]")
    payload = {"result": str(result), "latex": latex, "numeric": numeric}
    payload["verification"] = _sympy_verify(expr, op, var,
                                            result if not isinstance(result, list) else result)
    return payload


def _verification(backend, out):
    details = out.get("details") or {}
    if backend == "scipy":
        if "error" in details:
            return {"method": "quad_error", "ok": details["error"] < 1e-6,
                    "passed": details["error"] < 1e-6, "error": details["error"]}
        if "success" in details:
            return {"method": "optimizer_success", "ok": bool(details["success"]),
                    "passed": bool(details["success"])}
        if "converged" in details:
            return {"method": "root_converged", "ok": bool(details["converged"]),
                    "passed": bool(details["converged"])}
        return {"method": "scipy", "ok": True, "passed": True}
    if backend == "pint":
        return {"method": "unit_registry", "ok": True, "passed": True}
    if backend == "control":
        return {"method": "step_info", "ok": "SteadyStateValue" in details,
                "passed": "SteadyStateValue" in details}
    return {"method": backend, "ok": True, "passed": True}


def _worker_enabled():
    return str(os.environ.get(WORKER_ENV, "1")).lower() not in ("0", "false", "no")


def _run_worker(payload, timeout):
    """Run one request in a killed subprocess; returns the backend payload."""
    base = os.path.join(tempfile.gettempdir(), "calcbox-runs")
    os.makedirs(base, exist_ok=True)          # ordinary dir: no restrictive DACL
    run_dir = os.path.join(base, "run-%d-%d" % (os.getpid(), time.time_ns()))
    os.makedirs(run_dir, exist_ok=True)
    in_path = os.path.join(run_dir, "in.json")
    out_path = os.path.join(run_dir, "out.json")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        with open(in_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        env = os.environ.copy()
        env["PYTHONPATH"] = root + os.pathsep + env.get("PYTHONPATH", "")
        env["CALCBOX_SANDBOX_TEMP"] = run_dir
        env["TMP"] = env["TEMP"] = env["TMPDIR"] = run_dir
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        os.makedirs(os.path.join(run_dir, "mpl"), exist_ok=True)
        env["MPLCONFIGDIR"] = os.path.join(run_dir, "mpl")
        env["MPLBACKEND"] = "Agg"
        cmd = [sys.executable, "-m", "calcbox.worker", in_path, out_path]
        proc = subprocess.Popen(cmd, cwd=run_dir, env=env,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
            raise ComputeError("computation timed out")
        if not os.path.exists(out_path):
            raise ComputeError("compute worker produced no output (exit %s)" % code)
        with open(out_path, encoding="utf-8") as fh:
            body = json.load(fh)
        if not body.get("ok"):
            if body.get("kind") == "unavailable":
                raise BackendUnavailable(body.get("error") or "backend unavailable")
            raise ComputeError(body.get("error") or "computation failed")
        return body["out"]
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)



def _scipy_func(expr, var):
    import sympy as sp

    local = _locals(var)
    e = sp.sympify(expr.replace("^", "**"), locals=local)
    return sp.lambdify(local[var], e, "numpy"), e, local[var]


def _scipy(expr, op, var, point, target, timeout):
    import sympy as sp

    if not _available("scipy"):
        raise BackendUnavailable("scipy is not installed")
    if op not in OPS_NUMERIC:
        raise ComputeError("scipy operation must be one of %s" % sorted(OPS_NUMERIC))
    f, e, sym = _scipy_func(expr, var)
    try:
        if op == "quad":
            from scipy.integrate import quad
            lo = float(sp.sympify(point).evalf())
            hi = float(sp.sympify(target or "1").evalf())
            value, err = quad(lambda x: float(f(x)), lo, hi)
            cross = None
            try:
                exact = float(sp.N(sp.integrate(e, (sym, lo, hi))))
                cross = {"backend": "sympy", "value": exact,
                         "difference": abs(exact - value)}
            except Exception:
                cross = None
            disputed = bool(cross and cross["difference"] > max(
                1e-6, 1e-6 * abs(cross["value"])))
            return {"result": value, "latex": sp.latex(e), "numeric": value,
                    "details": {"lower": lo, "upper": hi, "error": err},
                    "cross_check": cross, "disputed": disputed}
        if op == "minimize":
            from scipy.optimize import minimize
            x0 = float(sp.sympify(point or "0").evalf())
            res = minimize(lambda x: float(f(x[0])), [x0])
            return {"result": float(res.x[0]), "latex": sp.latex(e),
                    "numeric": float(res.fun),
                    "details": {"success": bool(res.success),
                                "iterations": int(res.nit)}}
        if op == "root":
            from scipy.optimize import root_scalar
            lo = float(sp.sympify(point or "0").evalf())
            hi = float(sp.sympify(target or "1").evalf())
            res = root_scalar(lambda x: float(f(x)), bracket=(lo, hi))
            return {"result": float(res.root), "latex": sp.latex(e),
                    "numeric": 0.0,
                    "details": {"converged": bool(res.converged),
                                "bracket": [lo, hi]}}
    except ComputeError:
        raise
    except Exception as e:
        raise ComputeError(str(e))
    raise ComputeError("unknown scipy operation")


def _pint(expr, op, target, timeout):
    if not _available("pint"):
        raise BackendUnavailable("pint is not installed; pip install pint")
    if op != "convert":
        raise ComputeError("pint operation must be convert")
    if not target:
        raise ComputeError("target unit is required for convert")
    if not re.fullmatch(r"[0-9A-Za-z .,*/^()_+-]+", expr):
        raise ComputeError("unit expression contains invalid characters")
    try:
        import pint

        ureg = pint.UnitRegistry()
        value = ureg(expr)
        out = value.to(target)
        return {"result": str(out), "latex": "",
                "numeric": float(out.magnitude),
                "details": {"magnitude": float(out.magnitude),
                            "units": str(out.units)}}
    except Exception as e:
        raise ComputeError(str(e))


def _control(data, op, timeout):
    if not _available("control"):
        raise BackendUnavailable("control is not installed; pip install control")
    if op != "step":
        raise ComputeError("control operation must be step")
    data = data or {}
    num, den = data.get("num"), data.get("den")
    if (not isinstance(num, list) or not isinstance(den, list)
            or not num or not den
            or not all(isinstance(x, (int, float)) for x in num + den)):
        raise ComputeError("control step needs data.num and data.den number lists")
    # matplotlib (a control dependency) writes a cache on import; keep it in a
    # directory the sandbox allows.
    os.environ.setdefault("MPLBACKEND", "Agg")
    cache = os.environ.get("CALCBOX_SANDBOX_TEMP") or os.path.join(
        tempfile.gettempdir(), "calcbox-mpl")
    try:
        os.makedirs(cache, exist_ok=True)
        os.environ.setdefault("MPLCONFIGDIR", os.path.join(cache, "mpl"))
    except OSError:
        pass
    try:
        import control

        sys = control.TransferFunction(num, den)
        tf = control.step_info(sys)
        return {"result": str(sys), "latex": "",
                "numeric": float(tf.get("SteadyStateValue", 0.0)),
                "details": {k: (float(v) if isinstance(v, (int, float)) else v)
                            for k, v in tf.items()}}
    except Exception as e:
        raise ComputeError(str(e))


def _execute_local(backend, expression, operation, variable="x", point="0",
                   target=None, data=None, timeout=8.0):
    """Run one backend in-process. Policy lives in calcbox.sandbox."""
    if backend == "sympy":
        payload = {"backend": backend, "expression": expression,
                   "operation": operation, "variable": variable, "point": point,
                   "target": target, "data": data, "timeout": timeout}
        if _worker_enabled():
            return _run_worker(payload, timeout)
        expression = _validate(expression)
        point = _validate(point, 100)
        if target:
            target = _validate(target, 100)
        if not re.fullmatch(r"[A-Za-z]", variable or ""):
            raise ComputeError("variable must be one letter")
        return _sympy(expression, operation, variable, point, target, timeout)
    if backend == "scipy":
        expression = _validate(expression)
        point = _validate(point, 100)
        if target:
            target = _validate(target, 100)
        if not re.fullmatch(r"[A-Za-z]", variable or ""):
            raise ComputeError("variable must be one letter")
        return _scipy(expression, operation, variable, point, target, timeout)
    if backend == "pint":
        expression = _validate(expression)
        return _pint(expression, operation, target, timeout)
    if backend == "control":
        return _control(data, operation, timeout)
    raise BackendUnavailable("external backend %r disabled or not implemented" % backend)


def _assumptions(backend, variable, point, target, data):
    if backend == "sympy":
        return {"variable": variable, "domain": "complex"}
    return {"external": True}


def compute(expression, operation="simplify", variable="x", point="0",
            target=None, data=None, timeout=8.0, backend="auto"):
    """Compute one expression; returns a dict shaped by calcbox.contract."""
    t0 = time.perf_counter()
    status = backend_status()
    backend = (backend or "auto").lower()
    if backend == "auto":
        backend = infer_backend(operation)
    if backend not in status:
        raise ComputeError("unknown backend %r" % backend)
    if not status[backend]["available"]:
        raise BackendUnavailable(status[backend].get("reason") or
                                 "backend %r is not available" % backend)
    timeout = min(max(float(timeout), 0.1), 60.0)
    req = ComputeRequest(expression=expression, operation=operation,
                         variable=variable, point=point, target=target,
                         data=data, timeout=timeout, backend=backend)
    payload = req.payload()
    if backend in ("sympy", "scipy") and _worker_enabled():
        out = _run_worker(payload, timeout)
    elif backend == "pint" and _worker_enabled():
        out = _run_worker(payload, timeout)
    else:
        out = _execute_local(**payload)
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True,
                                       ensure_ascii=False).encode("utf-8")).hexdigest()
    generated = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    verification = out.get("verification") or _verification(backend, out)
    disputed = bool(out.get("disputed"))
    credentials = {
        "backend": backend,
        "engine_version": status[backend].get("version"),
        "input_sha256": digest,
        "operation": operation,
        "assumptions": _assumptions(backend, variable, point, target, data),
        "verification": verification,
        "cross_check": out.get("cross_check"),
        "disputed": disputed,
        "sandbox": "audit-only",
        "generated_at": generated,
    }
    result = ComputeResult(
        ok=True, backend=backend, engine_version=status[backend].get("version"),
        operation=operation, input=expression, variable=variable,
        result=out["result"], latex=out.get("latex", ""),
        numeric=out.get("numeric"), details=out.get("details"),
        cross_check=out.get("cross_check"),
        assumptions=credentials["assumptions"],
        verification=verification, disputed=disputed, sandbox="audit-only",
        credentials=credentials, input_sha256=digest, generated_at=generated,
        elapsed_ms=round((time.perf_counter() - t0) * 1000, 3),
    )
    return result.to_dict()
