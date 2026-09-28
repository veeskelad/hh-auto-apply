#!/usr/bin/env python3
"""
Hermes HH Notification Poller.

Checks ~/projects/hh-auto-apply/data/notifications/ for new .json files
and outputs them as a digest for Hermes cron to deliver to Telegram.

Usage: python3 poll_notifications.py
Output: markdown digest of pending notifications

Files are marked as delivered (delivered: true) after reading.
"""

import json
import os
from datetime import datetime
from pathlib import Path

NOTIFY_DIR = Path(os.environ.get("HH_NOTIFY_DIR", 
    os.path.expanduser("~/projects/hh-auto-apply/data/notifications")))


def poll() -> str:
    if not NOTIFY_DIR.exists():
        return "[SILENT]"
    
    files = sorted(NOTIFY_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime)
    if not files:
        return "[SILENT]"
    
    # Group by type
    by_type = {}
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("delivered"):
                continue
            t = data.get("type", "other")
            by_type.setdefault(t, []).append(data)
            data["delivered"] = True
            f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            continue
    
    if not by_type:
        return "[SILENT]"
    
    lines = ["## 📬 HH Auto Apply — уведомления", ""]
    
    for t, items in sorted(by_type.items()):
        if t == "interview":
            lines.append(f"### 🎯 Приглашения ({len(items)})")
        elif t == "response":
            lines.append(f"### 📤 Отклики ({len(items)})")
        elif t == "discard":
            lines.append(f"### ❌ Отказы ({len(items)})")
        elif t == "error":
            lines.append(f"### ⚠️ Ошибки ({len(items)})")
        elif t == "daily_summary":
            lines.append(f"### 📊 Сводка ({len(items)})")
        else:
            lines.append(f"### {t} ({len(items)})")
        
        for item in items:
            lines.append(f"- {item.get('message', '')}")
        lines.append("")
    
    return "\n".join(lines)


if __name__ == "__main__":
    result = poll()
    print(result)
