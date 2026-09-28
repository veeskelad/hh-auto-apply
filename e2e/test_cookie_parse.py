"""Разбор кук из того, что пользователь копирует из DevTools разных браузеров."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.routes.accounts import _parse_cookies_str  # noqa: E402

C = "hhtoken=AAA111; _xsrf=bbb222; hhuid=ccc%3D%3D; crypted_id=DDD"
WANT = {"hhtoken": "AAA111", "_xsrf": "bbb222", "hhuid": "ccc%3D%3D", "crypted_id": "DDD"}


def parsed(raw):
    cookies, line = _parse_cookies_str(raw)
    return {k: cookies.get(k) for k in WANT} if line else {}


def test_curl_bash_b():
    assert parsed(f"curl 'https://hh.ru/shards/x' \\\n  -H 'accept: */*' \\\n  -b '{C}'") == WANT


def test_curl_bash_cookie_header():
    assert parsed(f"curl 'https://hh.ru/x' -H 'cookie: {C}'") == WANT


def test_curl_cmd_windows():
    esc = C.replace("%", "^%")
    raw = f'curl ^"https://hh.ru/shards/x^" ^\r\n  -H ^"accept: */*^" ^\r\n  -b ^"{esc}^" ^\r\n  -H ^"x-xsrftoken: bbb222^"'
    assert parsed(raw) == WANT


def test_curl_cmd_cookie_header():
    esc = C.replace("%", "^%")
    assert parsed(f'curl ^"https://hh.ru/x^" -H ^"cookie: {esc}^"') == WANT


def test_powershell():
    raw = "$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession\n" + "\n".join(
        f'$session.Cookies.Add((New-Object System.Net.Cookie("{k}", "{v}", "/", ".hh.ru")))' for k, v in WANT.items())
    assert parsed(raw) == WANT


def test_fetch_nodejs_with_cookie():
    raw = f'fetch("https://hh.ru/x", {{\n  "headers": {{\n    "accept": "*/*",\n    "cookie": "{C}"\n  }},\n  "method": "GET"\n}});'
    assert parsed(raw) == WANT


def test_fetch_browser_without_cookie():
    raw = 'fetch("https://hh.ru/x", {\n  "headers": {"accept": "*/*"},\n  "method": "GET",\n  "credentials": "include"\n});'
    assert parsed(raw) == {}


def test_plain_cookie_line():
    assert parsed(C) == WANT
    assert parsed("Cookie: " + C) == WANT
