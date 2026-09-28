"""Изоляция e2e-стенда от внешнего мира: ни одного запроса к hh.ru и нейросетям.

Подгружается интерпретатором сам (через PYTHONPATH) до кода приложения.
Любая попытка сходить наружу даёт ConnectionError, а в BLOCK_LOG пишется, куда пытались.
"""
import os
import socket

_BLOCK_LOG = os.environ.get("E2E_BLOCK_LOG", "")
_ALLOWED = {"127.0.0.1", "localhost", "::1", "0.0.0.0"}


def _note(what: str) -> None:
    if _BLOCK_LOG:
        with open(_BLOCK_LOG, "a", encoding="utf-8") as f:
            f.write(what + "\n")


_orig_getaddrinfo = socket.getaddrinfo


def _getaddrinfo(host, *a, **kw):
    h = host.decode() if isinstance(host, bytes) else str(host)
    if h not in _ALLOWED:
        _note(f"dns {h}")
        raise socket.gaierror(socket.EAI_NONAME, f"e2e offline: {h}")
    return _orig_getaddrinfo(host, *a, **kw)


socket.getaddrinfo = _getaddrinfo

# curl_cffi резолвит имена сам, в обход socket: закрываем его отдельно
try:
    from curl_cffi import requests as _cffi

    def _cffi_blocked(method, url, *a, **kw):
        _note(f"curl_cffi {method} {url}")
        raise _cffi.RequestsError(f"e2e offline: {url}")

    _cffi.request = _cffi_blocked
    _cffi.Session.request = lambda self, method, url, *a, **kw: _cffi_blocked(method, url)
except ImportError:
    pass

# CLI нейросетей: подписка не тратится
import subprocess

_orig_run = subprocess.run


def _run(cmd, *a, **kw):
    exe = os.path.basename(str(cmd[0] if isinstance(cmd, (list, tuple)) else cmd).split()[0]).lower()
    if exe.startswith(("claude", "codex")):
        _note(f"cli {exe}")
        raise FileNotFoundError(f"e2e offline: {exe}")
    return _orig_run(cmd, *a, **kw)


subprocess.run = _run
