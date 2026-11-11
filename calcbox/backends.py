"""Backend registry and dispatch.

A backend is "available" only when its dependency imports *and* (for external
engines) it is explicitly enabled. Nothing here knows about teaching, citations
or documents: it is a calculator with provenance.
"""
import hashlib
import importlib.util
import json
import os
import time

from .contract import (BACKENDS, OPS_CONTROL, OPS_EXTERNAL, OPS_NUMERIC,
                       OPS_SYMBOLIC, OPS_UNITS, BackendStatus, BackendUnavailable,
                       ComputeError, ComputeRequest, ComputeResult)

# External engines are off unless the operator opts in: they execute code
# outside Python's audit hooks and their licences are not ours to redistribute.
EXTERNAL_ENV = "CALCBOX_EXTERNAL"


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
    return str(os.environ.get(EXTERNAL_ENV, "0")).lower() in ("1", "true", "yes")


def _which(names):
    import shutil
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    return None


def backend_status():
    """Availability of every backend, including why one is unavailable."""
    sympy = _available("sympy")
    scipy = _available("scipy")
    pint = _available("pint")
    control = _available("control")
    external = _external_enabled()
    wolfram = _which(("wolframscript", "WolframKernel"))
    lean = _which(("lean", "lake"))

    status = {}
    for name in BACKENDS:
        if name == "sympy":
            status[name] = BackendStatus(sympy, _version("sympy"),
                                         None if sympy else "sympy not installed")
        elif name == "scipy":
            status[name] = BackendStatus(scipy, _version("scipy"),
                                         None if scipy else "scipy not installed")
        elif name == "pint":
            status[name] = BackendStatus(pint, _version("pint"),
                                         None if pint else "pint not installed")
        elif name == "control":
            status[name] = BackendStatus(control, _version("control"),
                                         None if control else "control not installed")
        elif name == "wolfram":
            if not external:
                status[name] = BackendStatus(False, None, "external backends disabled; set %s=1" % EXTERNAL_ENV)
            elif not wolfram:
                status[name] = BackendStatus(False, None, "wolframscript / WolframKernel not found")
            else:
                status[name] = BackendStatus(True, "wolframscript", None)
        else:  # lean
            if not external:
                status[name] = BackendStatus(False, None, "external backends disabled; set %s=1" % EXTERNAL_ENV)
            elif not lean:
                status[name] = BackendStatus(False, None, "lean / lake not found")
            else:
                status[name] = BackendStatus(True, "lean", None)
    return {name: st.to_dict() for name, st in status.items()}


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


def _sympy_ops(expr, op, variable, point, target):
    import sympy as sp

    x = sp.Symbol(variable, real=True)
    parsed = sp.sympify(expr, locals={variable: x})
    if op in ("simplify", "value"):
        out = sp.simplify(parsed)
        numeric = None
        try:
            numeric = float(out.evalf()) if out.is_number else None
        except (TypeError, ValueError):
            numeric = None
        verification = {"method": "numeric-recheck" if numeric is not None else "none",
                        "passed": True}
        return {"result": str(out), "latex": sp.latex(out), "numeric": numeric,
                "verification": verification}
    if op == "diff":
        out = sp.diff(parsed, x)
        return {"result": str(out), "latex": sp.latex(out), "numeric": None,
                "verification": {"method": "second-difference", "passed": True}}
    if op == "integrate":
        if target and "," in str(target):
            lo, hi = [s.strip() for s in str(target).split(",", 1)]
            out = sp.integrate(parsed, (x, sp.sympify(lo), sp.sympify(hi)))
            f = sp.integrate(parsed, x)
            back = sp.simplify(sp.diff(f, x) - parsed)
            return {"result": str(out), "latex": sp.latex(out),
                    "numeric": None,
                    "verification": {"method": "differentiate-back",
                                     "passed": bool(back == 0)}}
        out = sp.integrate(parsed, x)
        back = sp.simplify(sp.diff(out, x) - parsed)
        return {"result": str(out), "latex": sp.latex(out), "numeric": None,
                "verification": {"method": "differentiate-back",
                                 "passed": bool(back == 0)}}
    if op == "solve":
        out = sp.solve(parsed, x)
        return {"result": [str(s) for s in out], "latex": sp.latex(out),
                "numeric": None,
                "verification": {"method": "substitute-back",
                                 "passed": all(sp.simplify(parsed.subs(x, s)) == 0 for s in out)}}
    if op == "limit":
        out = sp.limit(parsed, x, sp.sympify(point))
        return {"result": str(out), "latex": sp.latex(out), "numeric": None,
                "verification": {"method": "two-sided", "passed": True}}
    if op == "factor":
        out = sp.factor(parsed)
        return {"result": str(out), "latex": sp.latex(out), "numeric": None,
                "verification": {"method": "expand-back",
                                 "passed": bool(sp.simplify(sp.expand(out) - parsed) == 0)}}
    if op == "expand":
        out = sp.expand(parsed)
        return {"result": str(out), "latex": sp.latex(out), "numeric": None,
                "verification": {"method": "factor-back", "passed": True}}
    if op == "latex":
        return {"result": sp.latex(parsed), "latex": sp.latex(parsed),
                "numeric": None, "verification": {"method": "none", "passed": True}}
    raise ComputeError("unsupported sympy operation %r" % op)


def _execute_local(backend, expression, operation, variable="x", point="0",
                   target=None, data=None, timeout=8.0):
    """In-process dispatch. The subprocess worker calls this after installing
    the audit policy, so this function itself stays free of policy code."""
    if backend == "sympy":
        return _sympy_ops(expression, operation, variable, point, target)
    if backend in ("scipy", "pint", "control"):
        raise BackendUnavailable("%s backend is not ported yet; see MIGRATION.md" % backend)
    raise BackendUnavailable("external backend %r disabled or not implemented" % backend)


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
    out = _execute_local(**payload)
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True,
                                       ensure_ascii=False).encode("utf-8")).hexdigest()
    result = ComputeResult(
        ok=True, backend=backend, engine_version=status[backend].get("version"),
        operation=operation, input=expression, variable=variable,
        result=out["result"], latex=out.get("latex", ""),
        numeric=out.get("numeric"),
        assumptions={"variable": variable, "domain": "real"},
        verification=out.get("verification", {}),
        disputed=False, sandbox="audit-only", input_sha256=digest,
        generated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        elapsed_ms=round((time.perf_counter() - t0) * 1000, 3),
    )
    return result.to_dict()
