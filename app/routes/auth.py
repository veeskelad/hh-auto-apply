"""
Авторизация дашборда: вход по паролю (сессия в signed cookie).

Пароль задаётся переменной окружения DASHBOARD_PASSWORD.
Если она пустая — авторизация ОТКЛЮЧЕНА (открытый доступ, поведение по умолчанию).
"""

import os
import secrets

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse


router = APIRouter()

DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "").strip()


def auth_enabled() -> bool:
    return bool(DASHBOARD_PASSWORD)


_LOGIN_PAGE = """<!doctype html>
<html lang="ru"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Вход — HH Bot</title>
<style>
  body{{margin:0;height:100vh;display:flex;align-items:center;justify-content:center;
       background:#0f1115;color:#e6e6e6;font-family:system-ui,sans-serif}}
  form{{background:#1a1d23;border:1px solid #2a2e37;border-radius:12px;padding:28px;
        width:300px;box-shadow:0 8px 30px rgba(0,0,0,.4)}}
  h1{{font-size:18px;margin:0 0 18px;text-align:center}}
  input{{width:100%;box-sizing:border-box;padding:10px 12px;margin-bottom:12px;
         background:#0f1115;border:1px solid #2a2e37;border-radius:8px;color:#e6e6e6;font-size:14px}}
  button{{width:100%;padding:10px;background:#2563eb;color:#fff;border:0;border-radius:8px;
          font-size:14px;cursor:pointer}}
  button:hover{{background:#1d4ed8}}
  .err{{color:#ef4444;font-size:12px;text-align:center;margin-bottom:10px}}
</style></head>
<body>
<form method="post" action="/login">
  <h1>🔐 HH Bot</h1>
  {error}
  <input type="password" name="password" placeholder="Пароль" autofocus autocomplete="current-password">
  <button type="submit">Войти</button>
</form>
</body></html>"""


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: int = 0):
    if not auth_enabled() or request.session.get("auth"):
        return RedirectResponse(url="/", status_code=302)
    err_html = '<div class="err">Неверный пароль</div>' if error else ""
    return HTMLResponse(_LOGIN_PAGE.format(error=err_html))


@router.post("/login")
async def login_submit(request: Request, password: str = Form("")):
    if not auth_enabled():
        return RedirectResponse(url="/", status_code=302)
    if secrets.compare_digest(password, DASHBOARD_PASSWORD):
        request.session["auth"] = True
        return RedirectResponse(url="/", status_code=302)
    return RedirectResponse(url="/login?error=1", status_code=302)


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)
