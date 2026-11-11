#!/usr/bin/env python3
"""Вечерняя сводка hh-автопилота за день — для Hermes cron.

    python3 scripts/hh_digest.py            за сегодня
    python3 scripts/hh_digest.py 2026-11-09 за дату

Источники: data/notifications (отклики, чаты, приглашения, ошибки), data/questionnaire_log.jsonl
(ответы на анкеты) и очередь черновиков дашборда. День без событий — [SILENT].
"""
import json
import os
import sys
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("HH_DATA_DIR", ROOT / "data"))
API_BASE = os.environ.get("HH_API_BASE", "http://127.0.0.1:8000")


def _pending() -> list:
    try:
        with urllib.request.urlopen(API_BASE + "/api/llm/pending", timeout=5) as r:
            return json.loads(r.read().decode()).get("pending") or []
    except Exception:
        return []


def digest(day: str) -> str:
    notes = []
    for f in sorted((DATA / "notifications").glob(f"{day.replace('-', '')}_*.json")):
        try:
            notes.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            continue
    by = {}
    for n in notes:
        by.setdefault(n.get("type"), []).append(n)

    qlog = []
    qf = DATA / "questionnaire_log.jsonl"
    if qf.exists():
        for line in qf.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("at", "").startswith(day):
                qlog.append(rec)

    responses, chats, interviews = by.get("response", []), by.get("chat", []), by.get("interview", [])
    errors = by.get("error", [])
    pending = _pending()
    if not (responses or chats or interviews or errors or qlog or pending):
        return "[SILENT]"

    out = [f"## 📊 hh за {day}", ""]
    out.append(f"📤 Откликов: {len(responses)}")
    for n in responses[:15]:
        out.append(f"- {n.get('title', '')} — {n.get('company', '')}")
    if len(responses) > 15:
        out.append(f"- …и ещё {len(responses) - 15}")
    out.append("")

    if qlog:
        sent = sum(r.get("result") == "sent" for r in qlog)
        out.append(f"📝 Анкет: {len(qlog)}, приняты {sent}, нейросетью {sum(bool(r.get('by_llm')) for r in qlog)}")
        for r in qlog[:3]:
            out.append(f"**{r.get('title') or r.get('vacancy_id')}** — {r.get('company', '')} ({r.get('result')})")
            for qa in r.get("qa", [])[:4]:
                out.append(f"- В: {qa.get('q', '')[:150]}\n  О: {qa.get('a', '')[:300]}")
        if len(qlog) > 3:
            out.append(f"…все ответы: {qf}")
        out.append("")

    auto = [c for c in chats if c.get("sent")]
    if chats:
        out.append(f"💬 Чаты: ответил сам {len(auto)}, ждут тебя {len(pending)}")
        for c in auto[:10]:
            out.append(f"- {c.get('company', '')}: «{(c.get('employer_msg') or '')[:80]}» → {c.get('reply', '')[:200]}")
        out.append("")
    if pending:
        out.append("✋ Ждут ответа:")
        for d in pending[:10]:
            out.append(f"- `{d.get('draft_id')}` {d.get('employer', '')}: «{(d.get('employer_msg') or '')[:100]}»")
        out.append("")
    if interviews:
        out.append(f"🎯 Приглашений: {len(interviews)}")
        out += [f"- {n.get('message', '')}" for n in interviews]
        out.append("")
    if errors:
        out.append(f"⚠️ Ошибок: {len(errors)}")
        out += [f"- {n.get('message', '')}" for n in errors[:5]]
    return "\n".join(out).strip()


def _reply_bot_alive() -> bool:
    try:
        import time
        st = json.loads((DATA / "reply_bot_state.json").read_text(encoding="utf-8"))
        return time.time() - float(st.get("alive_at", 0)) < 300
    except Exception:
        return False


if __name__ == "__main__":
    # Итог дня шлёт @ninjiu_bot (hh_reply_bot.py); Hermes — только если бот лежит
    if _reply_bot_alive() and "--force" not in sys.argv[1:]:
        print("[SILENT]")
    else:
        print(digest(next((x for x in sys.argv[1:] if not x.startswith("--")), date.today().isoformat())))
