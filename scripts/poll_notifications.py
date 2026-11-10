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
import re
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOTIFY_DIR = Path(os.environ.get("HH_NOTIFY_DIR", ROOT / "data" / "notifications"))


_GREETING = re.compile(r"^\s*([А-ЯЁA-Z][\w-]+,\s*)?(добрый\s+(день|вечер)|здравствуйте|привет)\w*[!,.]?\s*", re.I)


def _quote(text: str, limit: int = 400) -> str:
    """Сообщение работодателя одной строкой цитаты: Telegram цитирует строку с «>», а переносы рвут цитату."""
    one = re.sub(r"\s+", " ", (text or "")).strip()
    one = _GREETING.sub("", one) or one
    return "> " + (one[:limit] + "…" if len(one) > limit else one)


def _reply_bot_alive() -> bool:
    """Отдельный бот для ответов жив — черновики идут туда, а не в Hermes."""
    try:
        import time
        st = json.loads((NOTIFY_DIR.parent / "reply_bot_state.json").read_text(encoding="utf-8"))
        return time.time() - float(st.get("alive_at", 0)) < 300
    except Exception:
        return False


def _chat_block(n: dict) -> list:
    draft = n.get("draft_id", "")
    head = "💬 Ответил сам" if n.get("sent") else "✋ Нужен твой ответ"
    lines = [f"**{head}** — {n.get('company', '')}, {n.get('title', '')}", _quote(n.get("employer_msg"))]
    if n.get("sent"):
        lines.append(f"**Отправил:** {n.get('reply', '')}")
        return lines + [""]
    opts = [o for o in [n.get("reply", "")] + list(n.get("variants") or []) if o]
    if opts:
        lines.append("**Варианты:**")
        lines += [f"{i}. {v}" for i, v in enumerate(opts, 1)]
    if n.get("reason"):
        lines.append(f"💭 {n['reason']}")
    lines += [f"`hh reply {draft} 1` — отправить вариант 1 (вместо номера можно свой текст)",
              f"`hh skip {draft}` — не отвечать", ""]
    return lines


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
    bot_alive = _reply_bot_alive()
    for n in by.pop("chat", []):
        if bot_alive and not n.get("sent"):
            continue  # черновик ушёл карточкой в отдельный бот (hh_reply_bot.py)
        lines += _chat_block(n)
    auth = [n for n in by.get("error", []) if n.get("subtype") == "auth"]
    if auth:
        cmd = os.environ.get("HH_LOGIN_CMD", "python3 scripts/ego_login.py --target <сервер>")
        lines += ["🔑 **Вход в hh.ru протух.** Войди в hh.ru в ego lite на компьютере и выполни:",
                  f"`{cmd}`", ""]
    captcha = [n for n in by.get("error", []) if n.get("subtype") == "captcha"]
    if captcha:
        url = captcha[-1].get("captcha_url", "")
        lines += ["🧩 **hh просит капчу на отклики, бот стоит.** Открой ссылку в браузере, где вошёл в hh, "
                  "реши капчу. Кампании продолжат при следующем запуске по расписанию.",
                  url or "(ссылки нет, открой hh.ru)", ""]
    errors = [n for n in by.pop("error", []) if n.get("subtype") not in ("auth", "captcha")]
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
