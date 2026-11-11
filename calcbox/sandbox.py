"""Audit-only sandbox for the compute worker.

Blocks, at the Python level: network sockets, process creation, and any
filesystem write outside the per-run temp directory. There is no namespace, no
seccomp, no read-only mount — a determined expression can still consume CPU or
memory. Reported as sandbox="audit-only" so nobody mistakes it for isolation.

Ported from socratic-tutor's sandbox_policy.py; the only change is the
environment variable name (CALCBOX_SANDBOX_TEMP).
"""
import os
import sys

TEMP_ENV = "CALCBOX_SANDBOX_TEMP"

_NETWORK = ("socket.__new__", "socket.connect", "socket.bind",
            "socket.getaddrinfo", "socket.gethostbyname", "socket.sendto")
_PROCESS = ("subprocess.Popen", "os.system", "os.exec", "os.spawn",
            "os.posix_spawn", "os.fork")
_WRITE_EVENTS = ("os.remove", "os.unlink", "os.mkdir", "os.rmdir", "os.chmod",
                 "os.utime", "os.truncate")
_RENAME_EVENTS = ("os.rename", "os.replace")


class PolicyViolation(PermissionError):
    """Raised from the audit hook when the policy denies an operation."""


def status():
    return {"available": True, "mode": "audit-only",
            "network": "denied-by-policy",
            "subprocess": "denied-by-policy",
            "filesystem": "temp-only",
            "note": "audit hooks are advisory; run real workloads in a container"}


def install(temp):
    temp = os.path.realpath(temp or "")
    if not temp:
        raise RuntimeError("sandbox temp is required")

    def inside(path):
        if path is None or isinstance(path, int):
            return False
        try:
            p = os.path.realpath(str(path))
        except Exception:
            return False
        return p == temp or p.startswith(temp + os.sep)

    def hook(event, args):
        if event in _NETWORK:
            raise PermissionError("network disabled by compute sandbox")
        if event in _PROCESS:
            raise PermissionError("process creation disabled by compute sandbox")
        if event == "open":
            path = args[0] if args else None
            mode = args[1] if len(args) > 1 else "r"
            flags = args[2] if len(args) > 2 else 0
            writing = False
            if isinstance(mode, str):
                writing = any(c in mode for c in "wax+")
            elif isinstance(flags, int):
                writing = bool(flags & (os.O_WRONLY | os.O_RDWR |
                                        os.O_CREAT | os.O_APPEND))
            if writing and not inside(path):
                raise PermissionError("read-only filesystem: %s" % (path,))
        if event in _WRITE_EVENTS:
            path = args[0] if args else None
            if path is not None and not inside(path):
                raise PermissionError("read-only filesystem: %s" % (path,))
        if event in _RENAME_EVENTS:
            for path in args[:2]:
                if path is not None and not inside(path):
                    raise PermissionError("read-only filesystem: %s" % (path,))

    sys.addaudithook(hook)
    return status()
