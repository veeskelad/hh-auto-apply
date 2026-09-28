#!/usr/bin/env python3
"""
HH Telegram Bridge — управление HH Auto Apply через Hermes.

Использование (через Hermes):
  /hh-status     — статус бота и статистика
  /hh-start      — запустить/возобновить
  /hh-pause      — поставить на паузу
  /hh-llm        — включить/выключить AI ответы
  /hh-stats      — подробная статистика
  /hh-log        — последние события в логе

API: вызывает REST эндпоинты HH дашборда (localhost:8000)
"""

import json
import sys
import urllib.request
import urllib.error
from datetime import datetime

API_BASE = "http://localhost:8000"


def _api_get(path: str) -> dict:
    """GET запрос к HH dashboard API."""
    try:
        req = urllib.request.Request(f"{API_BASE}{path}")
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"error": str(e)}


def _api_post(path: str, data: dict = None) -> dict:
    """POST запрос к HH dashboard API."""
    try:
        body = json.dumps(data or {}).encode()
        req = urllib.request.Request(f"{API_BASE}{path}", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"error": str(e)}


def cmd_status() -> str:
    """Общий статус: работает/пауза, счётчики."""
    # Статус через /api/status (без side effects)
    status = _api_get("/api/status")
    config = _api_get("/api/raw/config")
    
    if "error" in status:
        return f"⚠️ Дашборд HH не отвечает: {status['error']}"
    
    # Читаем отклики из файлов
    applied = 0
    try:
        with open("data/applied_vacancies.json", encoding="utf-8") as f:
            app_data = json.load(f)
            for acc_name, vacancies in app_data.items():
                if isinstance(vacancies, dict):
                    applied += len(vacancies)
    except:
        pass
    
    interviews = 0
    try:
        with open("data/interviews.json", encoding="utf-8") as f:
            int_data = json.load(f)
            interviews = len(int_data) if isinstance(int_data, list) else 0
    except:
        pass
    
    paused = status.get("paused", True)
    active = status.get("active_accounts", 0)
    uptime = status.get("uptime_seconds", 0)
    uptime_str = f"{uptime // 3600}ч {(uptime % 3600) // 60}м" if uptime else "—"
    
    lines = [
        f"{'⏸️' if paused else '▶️'} **HH Auto Apply**",
        f" uptime: {uptime_str}",
        "",
        f"📊 Всего откликов: **{applied}**",
        f"🎯 Приглашений: **{interviews}**",
        f"👤 Аккаунтов активно: **{active}/{status.get('accounts', 0)}**",
        f"⚙️ Лимит в день: **{config.get('daily_apply_limit', 20)}**",
        f"🔍 Фильтр ЗП: **от {config.get('min_salary', 0)}₽**",
        f"📅 Поиск за: **{config.get('search_period_days', 3)} дня**",
        f"🏢 Без агентств: **{'да' if config.get('filter_agencies') else 'нет'}**",
    ]
    
    return "\n".join(lines)


def cmd_toggle_pause() -> str:
    """Вкл/выкл паузу."""
    result = _api_post("/api/pause")
    if "error" in result:
        return f"⚠️ Ошибка: {result['error']}"
    paused = result.get("paused", False)
    return f"{'⏸️' if paused else '▶️'} Бот {'на паузе' if paused else 'запущен'}"


def cmd_log(limit: int = 10) -> str:
    """Последние события из лога бота."""
    try:
        with open("data/config.json", encoding="utf-8") as f:
            config = json.load(f)
    except:
        config = {}
    
    applied = {}
    try:
        with open("data/applied_vacancies.json", encoding="utf-8") as f:
            applied = json.load(f)
    except:
        pass
    
    lines = ["📋 **Последние отклики:**", ""]
    count = 0
    # Берём последние отклики из всех аккаунтов
    all_items = []
    for acc_name, vacancies in applied.items():
        if isinstance(vacancies, dict):
            for vid, info in vacancies.items():
                if isinstance(info, dict):
                    all_items.append({
                        "title": info.get("title", vid),
                        "company": info.get("company", ""),
                        "time": (info.get("at", "") or "")[:16].replace("T", " "),
                        "acc": acc_name,
                    })
    
    all_items.sort(key=lambda x: x.get("time", ""), reverse=True)
    
    for item in all_items[:limit]:
        lines.append(f"  {item['time']} — **{item['title']}** @ {item['company']}")
        count += 1
    
    if not count:
        lines.append("  (нет откликов)")
    
    return "\n".join(lines)


def cmd_help() -> str:
    return """🤖 **HH Telegram Pульт**

**Команды:**
`/hh-status` — общий статус и статистика
`/hh-start`  — запустить / снять с паузы
`/hh-pause`  — поставить на паузу
`/hh-log`    — последние 10 откликов
`/hh-stats`  — полная статистика (просмотры, приглашения)
`/hh-help`   — эта справка

**Пример:** `/hh-status`"""


def main():
    if len(sys.argv) < 2:
        print(cmd_help())
        return
    
    command = sys.argv[1]
    
    handlers = {
        "status": cmd_status,
        "start": cmd_toggle_pause,
        "pause": cmd_toggle_pause,
        "log": cmd_log,
        "stats": cmd_status,
        "help": cmd_help,
    }
    
    handler = handlers.get(command)
    if handler:
        print(handler())
    else:
        print(f"❌ Неизвестная команда: {command}\n{cmd_help()}")


if __name__ == "__main__":
    main()
