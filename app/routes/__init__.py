"""
FastAPI app creation and route registration.
"""

import os
import secrets
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware

# Singleton bot/manager are created in app.instances so every router module
# can import them without pulling in the package __init__ (avoids circular imports).
from app.instances import bot, manager  # re-exported for back-compat

app = FastAPI(title="HH Bot Dashboard")

STATIC_DIR = Path("static")
STATIC_DIR.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")

# ============================================================
# АВТОРИЗАЦИЯ (пароль + сессия)
# ============================================================
# Пароль из env DASHBOARD_PASSWORD. Если пусто — авторизация выключена.
_DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "").strip()
# Секрет подписи сессии: из env (стабильный между рестартами) или случайный.
_SESSION_SECRET = os.environ.get("SESSION_SECRET", "").strip() or secrets.token_hex(32)

# Пути, доступные без авторизации.
_PUBLIC_PATHS = {"/login", "/logout", "/favicon.ico"}


@app.middleware("http")
async def _require_auth(request, call_next):
    if not _DASHBOARD_PASSWORD:
        return await call_next(request)  # авторизация отключена
    path = request.url.path
    if path in _PUBLIC_PATHS or path.startswith("/static"):
        return await call_next(request)
    if request.session.get("auth"):
        return await call_next(request)
    # Не авторизован: API → 401, страницы → редирект на форму входа
    if path.startswith("/api"):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return RedirectResponse(url="/login", status_code=302)


# SessionMiddleware добавляется ПОСЛЕ _require_auth → становится внешним,
# поэтому request.session уже доступен внутри _require_auth.
app.add_middleware(
    SessionMiddleware,
    secret_key=_SESSION_SECRET,
    session_cookie="hh_session",
    same_site="lax",
    max_age=14 * 24 * 3600,
)

# -- Register routers (imported after app is created) --
from app.routes.core import router as core_router          # noqa: E402
from app.routes.accounts import router as accounts_router  # noqa: E402
from app.routes.sessions import router as sessions_router  # noqa: E402
from app.routes.data import router as data_router          # noqa: E402
from app.routes.apply import router as apply_router        # noqa: E402
from app.routes.settings import router as settings_router  # noqa: E402
from app.routes.llm import router as llm_router            # noqa: E402
from app.routes.debug import router as debug_router      # noqa: E402
from app.routes.hh_login import router as hh_login_router  # noqa: E402
from app.routes.auth import router as auth_router          # noqa: E402
from app.routes.campaigns import router as campaigns_router  # noqa: E402

app.include_router(auth_router)
app.include_router(core_router)
app.include_router(accounts_router)
app.include_router(sessions_router)
app.include_router(data_router)
app.include_router(apply_router)
app.include_router(settings_router)
app.include_router(llm_router)
app.include_router(debug_router)
app.include_router(hh_login_router)
app.include_router(campaigns_router)
