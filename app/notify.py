"""
Telegram notification bridge for HH Bot Dashboard.

Writes notification JSON files to data/notifications/ directory.
Hermes cron job reads them and delivers to Telegram DM.

Format:
{
  "type": "interview|response|discard|error|daily_summary",
  "title": "Senior Python Developer",
  "company": "Yandex",
  "message": "Приглашение на собеседование!",
  "account": "Основной",
  "timestamp": "2026-05-30T14:30:00",
  "delivered": false
}
"""

import json
import os
from datetime import datetime
from pathlib import Path

NOTIFY_DIR = Path("data/notifications")
NOTIFY_DIR.mkdir(exist_ok=True, parents=True)


def _write_notification(n_type: str, title: str, company: str, message: str, account: str = "",
                        extra: dict = None):
    """Write a notification file. Hermes will pick it up and deliver to Telegram."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"{ts}_{n_type}.json"
    data = {
        "type": n_type,
        "title": title,
        "company": company,
        "message": message,
        "account": account,
        "timestamp": datetime.now().isoformat(),
        "delivered": False,
    }
    if extra:
        data.update(extra)
    try:
        with open(NOTIFY_DIR / filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"notify error: {e}")
        return False


def notify_interview(title: str, company: str, account: str = ""):
    """Приглашение на собеседование"""
    _write_notification("interview", title, company,
                        f"🎯 Приглашение на собеседование! {title} — {company}", account)


def notify_response(title: str, company: str, account: str = ""):
    """Отклик отправлен"""
    _write_notification("response", title, company,
                        f"📤 Откликнулся: {title} — {company}", account)


def notify_discard(title: str, company: str, reason: str, account: str = ""):
    """Отказ"""
    _write_notification("discard", title, company,
                        f"❌ Отказ: {title} — {company} ({reason})", account)


def notify_error(title: str, company: str, error: str, account: str = ""):
    """Ошибка при отклике"""
    _write_notification("error", title, company,
                        f"⚠️ Ошибка: {title} — {company}: {error}", account)


def notify_daily_summary(sent: int, errors: int, interviews: int, account: str = ""):
    """Ежедневная сводка"""
    _write_notification("daily_summary", "", "",
                        f"📊 Дневная сводка: {sent} откликов, {errors} ошибок, {interviews} приглашений",
                        account)


def notify_chat(employer: str, vacancy_title: str, employer_msg: str, plan: dict, sent: bool,
                draft_id: str = "", neg_id: str = "", account: str = ""):
    """Сообщение работодателя: что бот ответил сам или какие варианты ждут владельца.

    draft_id — ключ черновика в очереди дашборда: владелец выбирает вариант, Hermes
    кладёт текст через /api/llm/pending/edit и отправляет через /api/llm/pending/send.
    """
    head = "💬 Ответил сам" if sent else "✋ Нужен твой ответ"
    _write_notification("chat", vacancy_title, employer,
                        f"{head}: {employer} — {vacancy_title}", account,
                        extra={"employer_msg": employer_msg[:1500], "sent": sent,
                               "category": plan.get("category", ""), "reason": plan.get("reason", ""),
                               "reply": plan.get("reply", ""), "variants": plan.get("variants", []),
                               "draft_id": draft_id, "neg_id": neg_id})


def notify_check(title: str, company: str, vid: str, snippet: str, account: str = ""):
    """В тексте вакансии указание для ИИ/ботов: бот не откликнулся, владелец смотрит сам."""
    _write_notification("check", title, company, snippet[:300], account,
                        extra={"url": f"https://hh.ru/vacancy/{vid}", "vacancy_id": str(vid)})


def notify_captcha(account: str = "", url: str = ""):
    """hh требует капчу на отклики через API: владелец решает её по ссылке в браузере, где вошёл в hh."""
    _write_notification("error", "", "", "🧩 hh просит капчу, отклики стоят", account,
                        extra={"subtype": "captcha", "captcha_url": url})


def notify_auth_expired(account: str = ""):
    """Куки hh протухли: владельцу нужно войти в ego и передать куки заново."""
    _write_notification("error", "", "", "🔑 Вход в hh.ru протух, отклики стоят", account,
                        extra={"subtype": "auth"})
