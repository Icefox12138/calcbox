# Changelog

## 0.3.1 — 2026-11-12

- `backend_status()` no longer imports SymPy. A bare `pip install calcbox` (no
  extras) can now report every backend as unavailable instead of raising
  `ImportError`; the new `bare install` CI job keeps it that way.
- CI runs on every push and pull request: tests on Python 3.10/3.11/3.12, a bare
  install, and a build + `twine check`.
- Documentation only otherwise: no behaviour change on any backend.

## 0.3.0 — 2026-11-11

- Wolfram and Lean backends (disabled unless `CALCBOX_EXTERNAL=1`; a missing
  binary is reported, never silently ignored).
- First PyPI release through Trusted Publishing.

## 0.2.0

- SciPy (`quad` with a symbolic cross-check, `minimize`, `root`), Pint
  (`convert`), Control (`step`).

## 0.1.0

- SymPy backend: simplify, diff, integrate, solve, limit, value, latex, factor,
  expand; killable subprocess worker; audit-only sandbox.

## 0.0.1

- Skeleton: contract, backend registry, CLI, HTTP router, MCP server.
