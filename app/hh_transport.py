"""Запросы к hh.ru через curl_cffi с TLS-отпечатком Chrome.

hh.ru (DDoS-Guard) отвечает 403 с капчей на TLS-отпечаток python-requests.
install() подменяет requests.Session.request: всё, что идёт на *.hh.ru, уходит
через curl_cffi, остальные хосты (LLM, Telegram) — обычным requests.
Сессия curl_cffi создаётся на каждый запрос, чтобы куки аккаунтов не смешивались.
"""
from urllib.parse import urlsplit

import requests
from curl_cffi import CurlMime
from curl_cffi import requests as cffi

_PASS = ("params", "data", "json", "timeout", "allow_redirects", "proxies", "verify", "auth", "stream")
_DEFAULT_HEADERS = dict(requests.utils.default_headers())


def _is_hh(url: str) -> bool:
    host = urlsplit(url).hostname or ""
    return host == "hh.ru" or host.endswith(".hh.ru")


def _mime(files: dict) -> CurlMime:
    """requests-style files={name: (filename, data[, content_type])} → multipart curl_cffi."""
    mime = CurlMime()
    for name, spec in files.items():
        filename, data, *rest = spec if isinstance(spec, tuple) else (None, spec)
        if hasattr(data, "read"):
            data = data.read()
        if isinstance(data, str):
            data = data.encode()
        mime.addpart(name=name, filename=filename, data=data, content_type=rest[0] if rest else None)
    return mime


def install() -> None:
    orig = requests.Session.request

    def request(self, method, url, **kw):
        if not _is_hh(url):
            return orig(self, method, url, **kw)
        # дефолтные заголовки requests (UA python-requests) выдали бы бота при TLS Chrome;
        # их место займут браузерные заголовки curl_cffi
        base = {k: v for k, v in self.headers.items() if _DEFAULT_HEADERS.get(k) != v}
        headers = {**base, **(kw.get("headers") or {})}
        cookies = {**self.cookies.get_dict(), **(kw.get("cookies") or {})}
        extra = {k: kw[k] for k in _PASS if kw.get(k) is not None}
        files = kw.get("files")
        mime = _mime(files) if files else None
        try:
            resp = cffi.request(method, url, headers=headers, cookies=cookies,
                                multipart=mime, impersonate="chrome", **extra)
        except cffi.RequestsError as e:
            if "timed out" in str(e).lower():
                raise requests.exceptions.Timeout(str(e)) from e
            raise requests.exceptions.ConnectionError(str(e)) from e
        finally:
            if mime:
                mime.close()
        self.cookies.update(dict(resp.cookies))
        return resp

    requests.Session.request = request
