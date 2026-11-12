# calcbox

Backend-agnostic math compute kernel: **symbolic, numeric, units, control** — and every
answer carries provenance (backend, engine version, assumptions, verification, input hash).

It knows nothing about teaching, documents or users. It is a calculator that can prove
what it did.

```python
from calcbox import compute

out = compute("x**2", "integrate")
# {'result': 'x**3/3', 'backend': 'sympy', 'engine_version': '1.13.1',
#  'verification': {'method': 'differentiate-back', 'passed': True}, ...}
```

## Why another math tool

There are MCP servers that evaluate arithmetic and matrix operations. What they do not
report is **how the answer was produced**: which backend, which engine version, which
assumptions, and whether a second method agreed. For tutoring, for reproducible
research notes, and for anything a human will quote, that provenance is the point.

```json
{
  "result": "x**3/3",
  "latex": "\\frac{x^{3}}{3}",
  "backend": "sympy",
  "engine_version": "1.13.1",
  "assumptions": {"variable": "x", "domain": "real"},
  "verification": {"method": "differentiate-back", "passed": true},
  "disputed": false,
  "sandbox": "audit-only",
  "input_sha256": "9f2c…",
  "elapsed_ms": 12.4
}
```

## Install

```bash
pip install calcbox              # core, no backends
pip install "calcbox[symbolic]"  # sympy  (calculus, algebra, exact values)
pip install "calcbox[full]"      # sympy + scipy + pint + control
pip install "calcbox[mcp]"       # MCP server (stdio)
pip install "calcbox[api]"       # FastAPI router
```

Nothing is a hard dependency. A missing backend is reported as unavailable **with a
reason**, never as a crash.

## Use it

**Python**

```python
compute("x**2", "integrate")            # indefinite
compute("x", "integrate", target="0,1") # definite
compute("x**3", "diff")
compute("2+3*4", "value")
compute("x**2-1", "solve")
compute("sin(x)/x", "limit", point="0")
compute("x**2", "simplify", backend="sympy")
```

**CLI**

```bash
calcbox "x**2" --op integrate
calcbox "sin(x)/x" --op limit --point 0 --json
```

**HTTP** (optional; no auth by design — that belongs to the host)

```python
from fastapi import FastAPI
from calcbox.api import create_router

app = FastAPI()
app.include_router(create_router())
# GET  /v1/compute/backends
# POST /v1/compute {"expression": "x**2", "operation": "integrate"}
```

**MCP**

```json
{
  "mcpServers": {
    "calcbox": {"command": "calcbox-mcp", "args": []}
  }
}
```

Tools: `compute`, `backends`.

## Contract

| Field | Meaning |
|---|---|
| `operation` | `simplify`, `diff`, `integrate`, `solve`, `limit`, `value`, `latex`, `factor`, `expand`, `quad`, `minimize`, `root`, `convert`, `step`, `eval`, `check` |
| `backend` | `auto` infers from the operation; otherwise one of `sympy`/`scipy`/`pint`/`control`/`wolfram`/`lean` |
| `verification` | method + `passed`; e.g. differentiate-back for integrals, substitute-back for solutions |
| `disputed` | two backends disagreed (only when a cross-check runs) |
| `sandbox` | always `audit-only` for in-process backends |

Errors: `ComputeError` (bad request → 400) and `BackendUnavailable` (missing dependency
or disabled external engine → 503).

## Security

**The sandbox is audit-only.** It is a set of `sys.audit` hooks, not an OS jail. Read
[SECURITY.md](SECURITY.md) before exposing this to untrusted input. External engines
(Wolfram, Lean) are disabled unless `CALCBOX_EXTERNAL=1`.

## Status

0.3.1 — all six backends wired: SymPy, SciPy, Pint, Control, and the external
engines Wolfram and Lean (disabled unless CALCBOX_EXTERNAL=1; both fail with a
reason when the binary is absent, never silently).

15/15 parity with the implementation this was ported from, 36 tests.

Every local call runs in a killable subprocess worker (~0.2-1.2 s overhead);
CALCBOX_WORKER=0 runs in-process for debugging. External engines run in-process
because they are already separate processes.

## Releasing

See [RELEASING.md](RELEASING.md): PyPI Trusted Publishing, no tokens.

## License

MIT.
