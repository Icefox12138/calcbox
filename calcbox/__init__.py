"""calcbox — backend-agnostic compute kernel.

    from calcbox import compute, backends
    compute("x**2", "integrate")          # -> dict, see calcbox.contract
    backend_status()                      # -> {"sympy": {"available": True, ...}}

Every answer carries provenance: backend, engine version, assumptions,
verification and an input hash. The sandbox is audit-only; see README.
"""
from .backends import backend_status, compute
from .contract import (BackendStatus, BackendUnavailable, ComputeError,
                       ComputeRequest, ComputeResult)

__version__ = "0.3.0"
__all__ = ["compute", "backend_status", "ComputeError", "BackendUnavailable",
           "ComputeRequest", "ComputeResult", "BackendStatus", "__version__"]
