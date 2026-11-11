# Security policy

## What this package executes

`calcbox` evaluates mathematical expressions with SymPy and, when enabled, runs
external engines (`wolframscript`, `lean`) as subprocesses. `operation="eval"` and
`operation="check"` are the sharp edges.

## The sandbox is audit-only

`calcbox.sandbox` installs `sys.audit` hooks that refuse a short list of events
(`os.system`, `subprocess.Popen`, `socket.connect`, `ctypes.dlopen`, …).

That is a guard against accidents, **not** a security boundary:

- it runs inside the same Python process as the expression;
- it can be bypassed by code that never triggers an audited event;
- it does not limit CPU, memory or disk.

For untrusted input, run `calcbox` inside a container, a restricted user, or a
dedicated sandbox service — and treat `eval`/`check` as disabled unless you did.

## Reporting

Open a private security advisory on the repository, or email the maintainer listed in
`pyproject.toml`. Please do not file a public issue for a bypass.
