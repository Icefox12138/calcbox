"""Audit-only sandbox.

This is **not** an OS-level jail. It is a set of sys.audit hooks that refuse a
short, explicit list of dangerous operations inside the worker process. It
raises the cost of an accidental shell-out; it does not stop a determined
attacker, and it is not a substitute for a container or a restricted user.

Reported to callers as sandbox="audit-only" so nobody mistakes it for isolation.
"""
import os
import sys

DENIED_PREFIXES = (
    "os.system",
    "os.exec",
    "os.posix_spawn",
    "os.spawn",
    "subprocess.Popen",
    "socket.connect",
    "socket.bind",
    "ctypes.dlopen",
)

TEMP_ENV = "CALCBOX_SANDBOX_TEMP"


class PolicyViolation(RuntimeError):
    """Raised from an audit hook when the policy denies an operation."""


def status():
    return {"available": True, "mode": "audit-only",
            "network": "denied-by-policy",
            "subprocess": "denied-by-policy",
            "filesystem": "temp-only",
            "note": "audit hooks are advisory; run real workloads in a container"}


def _hook(event, args):
    for prefix in DENIED_PREFIXES:
        if event == prefix or event.startswith(prefix):
            raise PolicyViolation("calcbox audit policy denied %s" % event)


def install(temp_dir=None):
    """Install the audit hook; optionally constrain the working directory."""
    if temp_dir:
        os.makedirs(temp_dir, exist_ok=True)
        os.chdir(temp_dir)
        os.environ[TEMP_ENV] = temp_dir
    sys.addaudithook(_hook)
    return status()
