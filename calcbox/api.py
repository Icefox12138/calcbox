"""Optional HTTP surface.

    from fastapi import FastAPI
    from calcbox.api import create_router

    app = FastAPI()
    app.include_router(create_router())

The routes mirror the contract exactly; they carry no authentication, because
that is the host's job (calcbox has no notion of users).
"""
from typing import Any, Dict, Optional

from . import backends as _backends
from .contract import BackendUnavailable, ComputeError


def create_router():
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel

    router = APIRouter()

    class ComputeIn(BaseModel):
        expression: str
        operation: str = "simplify"
        variable: str = "x"
        point: str = "0"
        target: Optional[str] = None
        data: Optional[Dict[str, Any]] = None
        timeout: float = 8.0
        backend: str = "auto"

    @router.get("/v1/compute/backends")
    def get_backends():
        return {"backends": _backends.backend_status()}

    @router.post("/v1/compute")
    def post_compute(body: ComputeIn):
        try:
            return _backends.compute(body.expression, operation=body.operation,
                                     variable=body.variable, point=body.point,
                                     target=body.target, data=body.data,
                                     timeout=body.timeout, backend=body.backend)
        except BackendUnavailable as e:
            raise HTTPException(status_code=503, detail={"code": "backend_unavailable",
                                                         "detail": str(e)})
        except ComputeError as e:
            raise HTTPException(status_code=400, detail={"code": "bad_request",
                                                         "detail": str(e)})

    return router
