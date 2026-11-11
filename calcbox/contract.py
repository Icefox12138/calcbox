"""calcbox wire contract.

One dict shape is shared by the Python API, the HTTP router, the MCP server and
the CLI. Anything that changes here is a breaking change.

Successful result:
    {
      "ok": true,
      "backend": "sympy",
      "engine_version": "1.13.3",
      "operation": "integrate",
      "input": "x**2",
      "variable": "x",
      "result": "x**3/3",
      "latex": "\\frac{x^{3}}{3}",
      "numeric": null,
      "assumptions": {"variable": "x", "domain": "complex"},
      "verification": {"method": "differentiate-back", "passed": true},
      "disputed": false,
      "sandbox": "audit-only",
      "credentials": {"backend": "sympy", "verification": {...}, "sandbox": "audit-only"},
      "input_sha256": "…",
      "generated_at": "2026-11-11T09:00:00Z",
      "elapsed_ms": 12.4
    }

Failure: ComputeError (client error) or BackendUnavailable (missing dependency
or disabled external backend). Transports map them to 400 / 503.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

OPS_SYMBOLIC = {"simplify", "diff", "integrate", "solve", "limit", "value",
                "latex", "factor", "expand"}
OPS_NUMERIC = {"quad", "minimize", "root"}
OPS_UNITS = {"convert"}
OPS_CONTROL = {"step"}
OPS_EXTERNAL = {"eval", "check"}

BACKENDS = ("sympy", "scipy", "pint", "control", "wolfram", "lean")


class ComputeError(ValueError):
    """The request is invalid (bad expression, unknown operation, bad backend)."""


class BackendUnavailable(ComputeError):
    """The backend exists but cannot serve: dependency missing or not enabled."""


@dataclass
class ComputeRequest:
    expression: str
    operation: str = "simplify"
    variable: str = "x"
    point: str = "0"
    target: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    timeout: float = 8.0
    backend: str = "auto"

    def payload(self) -> Dict[str, Any]:
        return {"backend": self.backend, "expression": self.expression,
                "operation": self.operation, "variable": self.variable,
                "point": self.point, "target": self.target, "data": self.data,
                "timeout": self.timeout}


@dataclass
class ComputeResult:
    ok: bool
    backend: str
    engine_version: Optional[str]
    operation: str
    input: str
    variable: str
    result: Any
    latex: str = ""
    numeric: Any = None
    assumptions: Dict[str, Any] = field(default_factory=dict)
    verification: Dict[str, Any] = field(default_factory=dict)
    disputed: bool = False
    sandbox: str = "audit-only"
    credentials: Dict[str, Any] = field(default_factory=dict)
    input_sha256: str = ""
    generated_at: str = ""
    elapsed_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok, "backend": self.backend,
            "engine_version": self.engine_version, "operation": self.operation,
            "input": self.input, "variable": self.variable,
            "result": self.result, "latex": self.latex,
            "numeric": self.numeric, "assumptions": self.assumptions,
            "verification": self.verification, "disputed": self.disputed,
            "sandbox": self.sandbox, "credentials": self.credentials,
            "input_sha256": self.input_sha256,
            "generated_at": self.generated_at, "elapsed_ms": self.elapsed_ms,
        }


@dataclass
class BackendStatus:
    available: bool
    version: Optional[str] = None
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"available": self.available}
        if self.version:
            out["version"] = self.version
        if self.reason:
            out["reason"] = self.reason
        return out
