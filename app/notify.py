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


def _write_notification(n_type: str, title: str, company: str, message: str, account: str = ""):
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
