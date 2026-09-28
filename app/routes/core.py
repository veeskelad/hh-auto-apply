"""
Core routes: startup, index, websocket, global pause, broadcast loop.
"""

import asyncio
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from app.logging_utils import log_debug
from app.config import CONFIG, _CONFIG_KEYS, save_config, _url_entry
from app.instances import bot, manager


router = APIRouter()


# ============================================================
# STARTUP
# ============================================================

@router.on_event("startup")
async def startup():
    from app.config import load_accounts
    load_accounts()
    bot.start()
    asyncio.create_task(broadcast_loop())


# ============================================================
# INDEX
# ============================================================

@router.get("/")
async def index():
    return FileResponse("static/index.html", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


# ============================================================
# WEBSOCKET
# ============================================================

@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    # Авторизация: если задан DASHBOARD_PASSWORD — требуем сессию
    from app.routes.auth import auth_enabled
    if auth_enabled() and not ws.session.get("auth"):
        await ws.close(code=1008)  # policy violation
        return
    await manager.connect(ws)
    try:
        while True:
            data = await ws.receive_json()
            cmd = data.get("type", "")

            if cmd == "pause_toggle":
                bot.toggle_pause()
            elif cmd == "account_pause":
                try:
                    idx = int(data.get("idx", -1))
                except (ValueError, TypeError):
                    continue
                bot.toggle_account_pause(idx)
            elif cmd == "account_llm":
                try:
                    idx = int(data.get("idx", -1))
                except (ValueError, TypeError):
                    continue
                bot.toggle_account_llm(idx)
            elif cmd == "account_oauth":
                try:
                    idx = int(data.get("idx", -1))
                except (ValueError, TypeError):
                    continue
                bot.toggle_account_oauth(idx)
            elif cmd == "set_config":
                key = data.get("key")
                value = data.get("value")
                if key == "allowed_schedules" and isinstance(value, list):
                    CONFIG.allowed_schedules = [s for s in value if isinstance(s, str)]
                    save_config()
                    bot._add_log("", "", f"⚙️ Формат работы: {CONFIG.allowed_schedules or 'все'}", "info")
                elif key in ("title_blacklist", "title_whitelist") and isinstance(value, list):
                    cleaned = [s.strip() for s in value if isinstance(s, str) and s.strip()]
                    setattr(CONFIG, key, cleaned)
                    save_config()
                    label = "Стоп-слова" if key == "title_blacklist" else "Только заголовки"
                    bot._add_log("", "", f"⚙️ {label}: {cleaned or 'нет'}", "info")
                elif key == "auto_apply_tests":
                    CONFIG.auto_apply_tests = bool(value)
                    save_config()
                    bot._add_log("", "", f"⚙️ Авто-тесты: {'ВКЛ' if CONFIG.auto_apply_tests else 'ВЫКЛ'}", "info")
                elif key and key in _CONFIG_KEYS:
                    old_val = getattr(CONFIG, key)
                    try:
                        setattr(CONFIG, key, type(old_val)(value))
                        save_config()
                        bot._add_log("", "", f"⚙️ {key} = {value}", "info")
                    except Exception as e:
                        log_debug(f"set_config error: {e}")
            elif cmd == "set_questionnaire":
                templates = data.get("templates")
                default = data.get("default_answer")
                if isinstance(templates, list):
                    CONFIG.questionnaire_templates = templates
                if isinstance(default, str):
                    CONFIG.questionnaire_default_answer = default
                save_config()
                bot._add_log("", "", f"\U0001f4dd Шаблоны опроса обновлены ({len(CONFIG.questionnaire_templates)} шт.)", "info")
            elif cmd == "set_letter_templates":
                templates = data.get("templates")
                if isinstance(templates, list):
                    CONFIG.letter_templates = templates
                    save_config()
                    bot._add_log("", "", f"✉️ Шаблоны писем обновлены ({len(templates)} шт.)", "info")
            elif cmd == "set_url_pool":
                pool = data.get("urls")
                if isinstance(pool, list):
                    normalized = []
                    for u in pool:
                        entry = _url_entry(u)
                        if entry["url"]:
                            normalized.append(entry)
                    CONFIG.url_pool = normalized
                    save_config()
                    bot._add_log("", "", f"\U0001f517 Пул URL обновлён ({len(CONFIG.url_pool)} шт.)", "info")
    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception:
        manager.disconnect(ws)


# ============================================================
# GLOBAL PAUSE
# ============================================================

@router.post("/api/pause")
async def api_pause():
    bot.toggle_pause()
    return {"paused": bot.paused}


@router.get("/api/status")
async def api_status():
    """Текущее состояние бота без side effects."""
    return {
        "paused": bot.paused,
        "accounts": len(bot.account_states) + len(bot.temp_states),
        "active_accounts": sum(
            1 for s in bot.account_states + list(bot.temp_states.values())
            if not s.paused and not s.hard_stopped
        ),
        "uptime_seconds": int((datetime.now() - bot._start_time).total_seconds()) if bot._start_time else 0,
    }


# ============================================================
# BROADCAST LOOP
# ============================================================

async def broadcast_loop():
    while True:
        try:
            if manager.active:
                snapshot = bot.get_state_snapshot()
                await manager.broadcast(snapshot)
        except Exception as e:
            log_debug(f"broadcast_loop error: {e}")
        await asyncio.sleep(0.3)
