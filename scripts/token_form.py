#!/usr/bin/env python3
"""Одноразовая веб-форма для токена Telegram-бота: значение сразу ложится в .env и нигде не печатается.

    python3 scripts/token_form.py --path SECRET [--port 8791] [--bot ninjiu_bot] [--minutes 30]

Слушает только 127.0.0.1, наружу её отдаёт reverse proxy с HTTPS. Отвечает только на /SECRET/,
остальное — 404. Перед записью спрашивает у Telegram getMe и сохраняет токен, только если он от
бота --bot (чтобы по ошибке не взять токен боевого бота). После сохранения или по таймеру выходит.
Логов запросов нет. Тело POST никуда не пишется, кроме строки HH_REPLY_BOT_TOKEN= в .env.
"""
import argparse
import html
import json
import os
import re
import threading
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ENV = Path(__file__).resolve().parent.parent / ".env"
KEY = "HH_REPLY_BOT_TOKEN"
TOKEN_RE = re.compile(r"^\d{6,12}:[A-Za-z0-9_-]{30,}$")

PAGE = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>Токен бота</title><style>
body{{font:17px -apple-system,system-ui,sans-serif;margin:0;padding:24px 16px;background:#0f1115;color:#e8e8ea}}
main{{max-width:440px;margin:auto}}h1{{font-size:21px}}p{{color:#a9adb5;line-height:1.45}}
input{{width:100%;box-sizing:border-box;font:16px ui-monospace,monospace;padding:14px;border-radius:10px;
border:1px solid #333;background:#1a1d23;color:#fff}}
button{{width:100%;margin-top:14px;padding:14px;font:600 17px system-ui;border:0;border-radius:10px;background:#2f7cf6;color:#fff}}
.msg{{padding:12px;border-radius:10px;margin:14px 0}}.ok{{background:#173d24}}.err{{background:#4a1d1d}}
</style></head><body><main><h1>Токен @{bot}</h1>{msg}{form}</main></body></html>"""

FORM = """<p>@BotFather → /mybots → @{bot} → API Token. Вставь токен сюда: он сразу запишется
на сервер, в чат и логи не попадёт. Форма одноразовая.</p>
<form method="post" autocomplete="off"><input name="token" type="password" placeholder="123456789:AA…"
autocapitalize="off" autocorrect="off" spellcheck="false" required><button>Сохранить</button></form>"""


def bot_username(token: str) -> str:
    with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/getMe", timeout=15) as r:
        d = json.loads(r.read().decode())
    return (d.get("result") or {}).get("username", "") if d.get("ok") else ""


def save(token: str) -> None:
    lines = ENV.read_text(encoding="utf-8").splitlines() if ENV.exists() else []
    lines = [ln for ln in lines if not ln.startswith(KEY + "=")] + [f"{KEY}={token}"]
    tmp = ENV.with_suffix(".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(ENV)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True)
    ap.add_argument("--port", type=int, default=8791)
    ap.add_argument("--bot", default="ninjiu_bot")
    ap.add_argument("--minutes", type=int, default=30)
    a = ap.parse_args()
    prefix = "/" + a.path.strip("/") + "/"
    done = threading.Event()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *args):  # без журнала запросов
            pass

        def _page(self, code: int, msg: str = "", form: bool = True):
            body = PAGE.format(bot=a.bot, msg=msg, form=FORM.format(bot=a.bot) if form else "").encode()
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self.path.startswith(prefix):
                self.send_error(404)
                return
            self._page(200)

        def do_POST(self):
            if not self.path.startswith(prefix) or done.is_set():
                self.send_error(404)
                return
            n = min(int(self.headers.get("Content-Length") or 0), 4096)
            token = (urllib.parse.parse_qs(self.rfile.read(n).decode("utf-8", "replace")).get("token") or [""])[0]
            token = re.sub(r"\s+", "", token)
            if not TOKEN_RE.match(token):
                self._page(400, '<div class="msg err">Это не похоже на токен бота (вид 123456789:AA…).</div>')
                return
            try:
                name = bot_username(token)
            except Exception:
                name = ""
            if not name:
                self._page(400, '<div class="msg err">Telegram не принял этот токен.</div>')
                return
            if name.lower() != a.bot.lower():
                self._page(400, f'<div class="msg err">Это токен @{html.escape(name)}, а нужен @{a.bot}. '
                                'Ничего не сохранено.</div>')
                return
            save(token)
            done.set()
            self._page(200, f'<div class="msg ok">Сохранено: токен @{html.escape(name)} на сервере. '
                            'Страницу можно закрыть.</div>', form=False)
            print(f"saved: @{name}", flush=True)

    srv = ThreadingHTTPServer(("127.0.0.1", a.port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    if not done.wait(a.minutes * 60):
        print("timeout: токен не введён", flush=True)
    srv.shutdown()
    return 0 if done.is_set() else 1


if __name__ == "__main__":
    raise SystemExit(main())
