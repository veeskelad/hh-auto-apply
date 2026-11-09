#!/usr/bin/env python3
"""
Уведомления hh-автопилота для Hermes: что пришло нового с прошлого запуска.

    python3 scripts/poll_notifications.py          новое → markdown для Telegram, файлы помечаются delivered
    python3 scripts/poll_notifications.py --peek   то же без пометки (проверка)

Каталог — HH_NOTIFY_DIR или data/notifications рядом со скриптом. Нечего сообщить — печатает
[SILENT], и Hermes ничего не шлёт. Отклики идут одной строкой-счётчиком: подробности в вечерней
сводке (scripts/hh_digest.py).
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOTIFY_DIR = Path(os.environ.get("HH_NOTIFY_DIR", ROOT / "data" / "notifications"))


def _chat_block(n: dict) -> list:
    head = "💬 Ответил сам" if n.get("sent") else "✋ Нужен твой ответ"
    lines = [f"**{head}** — {n.get('company', '')}, {n.get('title', '')}",
             f"> {(n.get('employer_msg') or '').strip()[:600]}"]
    if n.get("sent"):
        lines.append(f"Отправлено: {n.get('reply', '')}")
        if n.get("variants"):
            lines.append("Другие варианты (на будущее): " + " | ".join(n["variants"]))
    else:
        opts = [n.get("reply", "")] + list(n.get("variants") or [])
        for i, v in enumerate([o for o in opts if o], 1):
            lines.append(f"{i}. {v}")
        if n.get("reason"):
            lines.append(f"_Почему не ответил сам: {n['reason']}_")
        lines.append(f"Ответ: `hh reply {n.get('draft_id', '')} <номер или свой текст>` · "
                     f"пропустить: `hh skip {n.get('draft_id', '')}`")
    return lines + [""]


def poll(mark: bool = True) -> str:
    if not NOTIFY_DIR.exists():
        return "[SILENT]"
    fresh = []
    for f in sorted(NOTIFY_DIR.glob("*.json"), key=lambda f: f.name):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("delivered"):
            continue
        fresh.append(data)
        if mark:
            data["delivered"] = True
            f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    if not fresh:
        return "[SILENT]"

    by = {}
    for n in fresh:
        by.setdefault(n.get("type", "other"), []).append(n)
    lines = []
    for n in by.pop("interview", []):
        lines.append(f"🎯 **Приглашение**: {n.get('message', '')}")
    if lines:
        lines.append("")
    for n in by.pop("chat", []):
        lines += _chat_block(n)
    auth = [n for n in by.get("error", []) if n.get("subtype") == "auth"]
    if auth:
        cmd = os.environ.get("HH_LOGIN_CMD", "python3 scripts/ego_login.py --target <сервер>")
        lines += ["🔑 **Вход в hh.ru протух.** Войди в hh.ru в ego lite на компьютере и выполни:",
                  f"`{cmd}`", ""]
    errors = [n for n in by.pop("error", []) if n.get("subtype") != "auth"]
    if errors:
        lines.append(f"⚠️ Ошибки откликов: {len(errors)}")
        lines += [f"- {n.get('message', '')}" for n in errors[:3]]
        lines.append("")
    responses = by.pop("response", [])
    if responses:
        names = ", ".join(f"{n.get('title', '')} ({n.get('company', '')})" for n in responses[:5])
        more = f" и ещё {len(responses) - 5}" if len(responses) > 5 else ""
        lines += [f"📤 Отклики: {len(responses)} — {names}{more}", ""]
    for t, items in by.items():
        lines += [f"- {n.get('message', '')}" for n in items]
    text = "\n".join(lines).strip()
    return text or "[SILENT]"


if __name__ == "__main__":
    print(poll(mark="--peek" not in sys.argv))
