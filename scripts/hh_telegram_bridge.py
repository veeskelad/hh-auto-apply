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
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

API_BASE = os.environ.get("HH_API_BASE", "http://127.0.0.1:8000")
NOTIFY_DIR = Path(os.environ.get("HH_NOTIFY_DIR", Path(__file__).resolve().parent.parent / "data" / "notifications"))


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
        with urllib.request.urlopen(req, timeout=60) as r:
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


def _chat_notification(draft_id: str) -> dict:
    """Последнее уведомление о чате с этим черновиком (там лежат варианты ответа)."""
    for f in sorted(NOTIFY_DIR.glob("*_chat.json"), key=lambda f: f.name, reverse=True):
        try:
            n = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if n.get("draft_id") == draft_id:
            return n
    return {}


def cmd_reply(draft_id: str = "", *choice) -> str:
    """Отправить работодателю вариант N из уведомления или свой текст."""
    text = " ".join(choice).strip()
    if not draft_id or not text:
        return "Формат: hh reply <draft_id> <номер варианта или свой текст>"
    if text.isdigit():
        n = _chat_notification(draft_id)
        opts = [o for o in [n.get("reply", "")] + list(n.get("variants") or []) if o]
        k = int(text)
        if not 1 <= k <= len(opts):
            return f"❌ Нет варианта {k} для {draft_id} (есть {len(opts)})"
        text = opts[k - 1]
    pending = {d.get("draft_id") for d in (_api_get("/api/llm/pending").get("pending") or [])}
    if draft_id not in pending:
        return f"❌ Черновика {draft_id} нет в очереди (дашборд перезапускался или ответ уже ушёл)"
    r = _api_post("/api/llm/pending/edit", {"id": draft_id, "text": text})
    if not r.get("ok"):
        return f"❌ Не удалось поправить черновик: {r.get('error')}"
    r = _api_post("/api/llm/pending/send", {"ids": [draft_id]})
    return f"✅ Отправлено: {text}" if r.get("sent") else f"❌ Не отправилось: {r}"


def cmd_skip(draft_id: str = "") -> str:
    r = _api_post("/api/llm/pending/discard", {"ids": [draft_id]})
    return "🗑 Пропущено" if r.get("removed") else f"❌ Черновика {draft_id} нет в очереди"


def cmd_help() -> str:
    return """🤖 **HH Telegram Pульт**

**Команды:**
`/hh-status` — общий статус и статистика
`/hh-start`  — запустить / снять с паузы
`/hh-pause`  — поставить на паузу
`/hh-log`    — последние 10 откликов
`/hh-stats`  — полная статистика (просмотры, приглашения)
`/hh-help`   — эта справка
`reply <draft_id> <N|текст>` — ответить работодателю вариантом N или своим текстом
`skip <draft_id>` — не отвечать

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
        "reply": cmd_reply,
        "skip": cmd_skip,
    }

    handler = handlers.get(command)
    if handler:
        print(handler(*sys.argv[2:]) if command in ("reply", "skip") else handler())
    else:
        print(f"❌ Неизвестная команда: {command}\n{cmd_help()}")


if __name__ == "__main__":
    main()
