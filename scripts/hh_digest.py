#!/usr/bin/env python3
"""Вечерняя сводка hh-автопилота за день — для @ninjiu_bot (запасной канал — Hermes cron).

    python3 scripts/hh_digest.py            за сегодня
    python3 scripts/hh_digest.py 2026-11-09 за дату

Источники: data/notifications (отклики, чаты, приглашения, ошибки), data/questionnaire_log.jsonl
(ответы на анкеты), data/applied_vacancies.json (названия, которых нет в уведомлении)
и очередь черновиков дашборда. День без событий — [SILENT].

Формат — Markdown, который hh_reply_bot.md_to_html переводит в HTML Telegram: **жирный**,
[ссылка](url), `код`, «> » цитата (длинная сворачивается). Блоки разделены пустой строкой:
по ним бот режет сообщение под лимит Telegram, поэтому внутри блока пустых строк нет.
"""
import json
import os
import sys
import urllib.request
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("HH_DATA_DIR", ROOT / "data"))
API_BASE = os.environ.get("HH_API_BASE", "http://127.0.0.1:8000")

MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа",
          "сентября", "октября", "ноября", "декабря"]

# Итог анкеты: значок и что это значит для владельца
Q_RESULT = {
    "sent": ("✅", ""),
    "test": ("⚠️", "hh не принял ответы, отклика нет"),
    "skipped_no_facts": ("⏸", "не отправлена: нет фактов для ответа"),
    "limit": ("🚫", "не отправлена: лимит откликов"),
    "error": ("❌", "ошибка отправки"),
}


def _pending() -> list:
    try:
        with urllib.request.urlopen(API_BASE + "/api/llm/pending", timeout=5) as r:
            return json.loads(r.read().decode()).get("pending") or []
    except Exception:
        return []


def _applied() -> dict:
    """vacancy_id → {title, company} по всем аккаунтам."""
    try:
        raw = json.loads((DATA / "applied_vacancies.json").read_text(encoding="utf-8"))
    except Exception:
        return {}
    out = {}
    for acc in raw.values():
        if isinstance(acc, dict):
            for vid, info in acc.items():
                if isinstance(info, dict):
                    out[str(vid)] = info
    return out


def _cut(text: str, limit: int) -> str:
    """Обрезать по границе слова, а не посреди него."""
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(",.;:—-")
    return cut + "…"


def _link(title: str, url: str) -> str:
    title = (title or "").replace("[", "(").replace("]", ")")
    return f"[{title}]({url})" if url else title


def _day_ru(day: str) -> str:
    try:
        d = date.fromisoformat(day)
        return f"{d.day} {MONTHS[d.month - 1]}"
    except ValueError:
        return day


def _plural(n: int, one: str, few: str, many: str) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def _near(ts_a: str, ts_b: str, sec: int = 10) -> bool:
    try:
        return abs((datetime.fromisoformat(ts_a) - datetime.fromisoformat(ts_b)).total_seconds()) <= sec
    except ValueError:
        return False


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

    applied = _applied()
    by_name = {(i.get("title"), i.get("company")): vid for vid, i in applied.items() if i.get("title")}

    def named(vid: str, title: str, company: str) -> tuple:
        info = applied.get(str(vid), {}) if vid else {}
        return title or info.get("title") or (f"вакансия {vid}" if vid else "без названия"), \
            company or info.get("company", "")

    # Отклик с анкетой до правки manager.py пришёл без названия и vacancy_id: находим анкету,
    # записанную в ту же секунду (уведомление пишется сразу после анкеты)
    for n in responses:
        if not n.get("vacancy_id") and not n.get("title"):
            q = next((r for r in qlog if _near(n.get("timestamp", ""), r.get("at", ""))), None)
            if q:
                n["vacancy_id"], n["url"] = q.get("vacancy_id"), q.get("url")
        elif not n.get("vacancy_id"):  # старые уведомления без ссылки: ищем вакансию по названию
            n["vacancy_id"] = by_name.get((n.get("title"), n.get("company")), "")
    sent_q = {str(r.get("vacancy_id")) for r in qlog if r.get("result") == "sent"}

    auto = [c for c in chats if c.get("sent")]
    top = [f"📤 {len(responses)} {_plural(len(responses), 'отклик', 'отклика', 'откликов')}"]
    if qlog:
        top.append(f"📝 {len(qlog)} {_plural(len(qlog), 'анкета', 'анкеты', 'анкет')}")
    if chats:
        top.append(f"💬 ответил сам {len(auto)}")
    if pending:
        top.append(f"✋ ждут тебя {len(pending)}")
    if interviews:
        top.append(f"🎯 приглашений {len(interviews)}")
    blocks = [f"## 📊 hh за {_day_ru(day)}\n" + " · ".join(top)]

    if interviews:
        blocks.append("**🎯 Приглашения**\n" + "\n".join(
            f"- {_link(n['title'], n.get('url', ''))}" + (f" — {n['company']}" if n.get("company") else "")
            if n.get("title") else f"- {_cut(n.get('message', ''), 200)}" for n in interviews))

    if pending:
        lines = ["**✋ Ждут твоего ответа**"]
        for d in pending[:10]:
            lines.append(f"- **{d.get('employer', '')}**: «{_cut(d.get('employer_msg'), 120)}» `{d.get('draft_id')}`")
        blocks.append("\n".join(lines))

    if responses:
        lines = [f"**📤 Отклики ({len(responses)})**"]
        for i, n in enumerate(responses[:20], 1):
            vid = str(n.get("vacancy_id") or "")
            title, company = named(vid, n.get("title", ""), n.get("company", ""))
            url = n.get("url") or (f"https://hh.ru/vacancy/{vid}" if vid else "")
            mark = " 📝" if vid in sent_q else ""
            lines.append(f"{i}. {_link(title, url)}" + (f" — {company}" if company else "") + mark)
        if len(responses) > 20:
            lines.append(f"…и ещё {len(responses) - 20}")
        if sent_q:
            lines.append("📝 — с анкетой, ответы ниже")
        blocks.append("\n".join(lines))

    if qlog:
        ok = sum(r.get("result") == "sent" for r in qlog)
        llm = sum(bool(r.get("by_llm")) for r in qlog)
        head = f"**📝 Анкеты: отправлено {ok} из {len(qlog)}**"
        head += "\nОтветы писала нейросеть" if llm == len(qlog) else f"\nНейросеть заполнила {llm} из {len(qlog)}"
        blocks.append(head + ". Длинные ответы свёрнуты: нажми на цитату.")
        # Сначала то, что не ушло: на это стоит посмотреть
        for r in sorted(qlog[:10], key=lambda r: r.get("result") == "sent"):
            icon, note = Q_RESULT.get(r.get("result"), ("❓", str(r.get("result"))))
            title, company = named(r.get("vacancy_id"), r.get("title", ""), r.get("company", ""))
            qa = r.get("qa", [])
            line = f"{icon} **{_link(title, r.get('url', ''))}**" + (f" — {company}" if company else "")
            line += f"\n{note}" if note else ""
            lines = [line]
            for qa_i in qa[:6]:
                lines.append(f"> **В:** {_cut(qa_i.get('q'), 160)}")
                lines.append(f"> **О:** {_cut(qa_i.get('a'), 350) or '⚠️ без ответа'}")
            if len(qa) > 6:
                lines.append(f"> …ещё {len(qa) - 6} вопр.")
            blocks.append("\n".join(lines))
        if len(qlog) > 10:
            blocks.append(f"…ещё {len(qlog) - 10} анкет — на дашборде")

    if auto:
        lines = [f"**💬 Ответил сам ({len(auto)})**"]
        for c in auto[:10]:
            lines.append(f"**{c.get('company', '')}**")
            lines.append(f"> 👤 {_cut(c.get('employer_msg'), 120)}")
            lines.append(f"> 🤖 {_cut(c.get('reply'), 250)}")
        blocks.append("\n".join(lines))

    if errors:
        # Одинаковые ошибки — одной строкой со счётчиком, капча от двух источников — одна
        seen = {}
        for n in errors:
            msg = n.get("message", "")
            if n.get("subtype") == "captcha" or "капч" in msg:
                msg = "🧩 hh включил капчу, отклики стоят до завтра"
            elif not n.get("title") and "ошибка отправки" in msg:
                msg = "ошибка отправки отклика (вакансия не определена)"
            seen[msg] = seen.get(msg, 0) + 1
        blocks.append(f"**⚠️ Ошибки ({len(errors)})**\n" + "\n".join(
            f"- {_cut(m, 200)}" + (f" ×{k}" if k > 1 else "") for m, k in list(seen.items())[:5]))
    return "\n\n".join(blocks).strip()


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
