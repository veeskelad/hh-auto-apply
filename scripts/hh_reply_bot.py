#!/usr/bin/env python3
"""Отдельный Telegram-бот для чатов hh, где нужен ответ владельца.

    python3 scripts/hh_reply_bot.py          работать (long polling), для systemd
    python3 scripts/hh_reply_bot.py --check  проверить токен и доступ к Telegram, ничего не слать

Карточка на каждый черновик: сообщение работодателя, варианты кнопками, «Свой ответ»,
«Пропустить». Вариант или свой текст сначала показываются с вопросом «Отправить?», и только
после «Отправить» уходят работодателю через очередь дашборда (/api/llm/pending/*).
Сюда же идут остальные уведомления hh: сразу — капча, протухший вход, приглашения, ответы,
отправленные ботом сам; отклики и ошибки по вакансиям — в итоге дня (20:30 по HH_DIGEST_TZ).
Пока бот жив (heartbeat в data/reply_bot_state.json), Hermes по hh молчит; бот упал — Hermes
снова присылает всё сам.

.env: HH_REPLY_BOT_TOKEN — токен бота, HH_REPLY_CHAT_ID — id владельца (команды принимаются
только от него). Токен никуда не печатается.
"""
import html
import json
import os
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("HH_DATA_DIR", ROOT / "data"))
NOTIFY_DIR = DATA / "notifications"
STATE_FILE = DATA / "reply_bot_state.json"
API_BASE = os.environ.get("HH_API_BASE", "http://127.0.0.1:8000")
HEARTBEAT_TTL = 300  # сек: дольше бот молчит — черновики снова уходят через Hermes
QUEUE_OPEN = int(os.environ.get("HH_QUEUE_OPEN", "5"))  # открытых карточек очереди откликов сразу


def load_env() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def alive() -> bool:
    """Жив ли бот (для poll_notifications.py): свежий heartbeat в файле состояния."""
    try:
        st = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return time.time() - float(st.get("alive_at", 0)) < HEARTBEAT_TTL
    except Exception:
        return False


# ── состояние ────────────────────────────────────────────────────────────────

def load_state() -> dict:
    try:
        st = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        st = {}
    st.setdefault("offset", 0)
    st.setdefault("next_id", 1)
    st.setdefault("cards", {})    # id карточки → {draft_id, file, message_id, options, status}
    st.setdefault("seen", [])     # файлы уведомлений, по которым карточка уже есть
    st.setdefault("custom", {})   # message_id приглашения «напиши ответ» → id карточки
    st.setdefault("queue", {})    # id записи очереди откликов → {message_id, extra: [message_id…]}
    return st


def save_state(st: dict) -> None:
    st["alive_at"] = time.time()
    st["seen"] = st["seen"][-2000:]
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(STATE_FILE)


# ── Telegram и дашборд ───────────────────────────────────────────────────────

class TG:
    def __init__(self, token: str):
        self.base = f"https://api.telegram.org/bot{token}/"

    def call(self, method: str, **params):
        r = requests.post(self.base + method, json=params, timeout=70)
        d = r.json()
        if not d.get("ok"):
            # «message is not modified» не ошибка: карточка уже в нужном виде
            if "not modified" in str(d.get("description", "")):
                return None
            raise RuntimeError(f"Telegram {method}: {d.get('description')}")
        return d.get("result")


def api(method: str, path: str, body: dict = None) -> dict:
    try:
        if method == "GET":
            r = requests.get(API_BASE + path, timeout=15)
        else:
            r = requests.post(API_BASE + path, json=body or {}, timeout=90)
        return r.json() or {}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def pending_ids() -> set:
    return {d.get("draft_id") for d in (api("GET", "/api/llm/pending").get("pending") or [])}


# ── карточки ─────────────────────────────────────────────────────────────────

def card_text(n: dict, footer: str = "") -> str:
    e = html.escape
    lines = [f"✋ <b>{e(n.get('company', ''))}</b> · {e(n.get('title', ''))}",
             f"<blockquote expandable>{e((n.get('employer_msg') or '').strip()[:3000])}</blockquote>"]
    opts = card_options(n)
    if opts:
        lines.append("<b>Варианты</b>")
        lines += [f"<b>{i}.</b> {e(v)}" for i, v in enumerate(opts, 1)]
    if n.get("reason"):
        lines.append(f"<i>💭 {e(n['reason'])}</i>")
    if footer:
        lines += ["", footer]
    return "\n".join(lines)


def card_options(n: dict) -> list:
    return [o for o in [n.get("reply", "")] + list(n.get("variants") or []) if o][:5]


def card_keyboard(cid: str, n_opts: int) -> dict:
    row = [{"text": str(i), "callback_data": f"pick:{cid}:{i}"} for i in range(1, n_opts + 1)]
    rows = [row] if row else []
    rows.append([{"text": "✏️ Свой ответ", "callback_data": f"own:{cid}"},
                 {"text": "Пропустить", "callback_data": f"skip:{cid}"}])
    return {"inline_keyboard": rows}


def confirm_keyboard(cid: str) -> dict:
    return {"inline_keyboard": [[{"text": "✅ Отправить", "callback_data": f"send:{cid}"},
                                 {"text": "↩️ Назад", "callback_data": f"back:{cid}"}]]}


def new_cards(tg: TG, chat_id: int, st: dict) -> None:
    """Черновики из уведомлений (sent=False), по которым ещё нет карточки."""
    if not NOTIFY_DIR.exists():
        return
    live = None
    for f in sorted(NOTIFY_DIR.glob("*_chat.json"), key=lambda p: p.name):
        if f.name in st["seen"]:
            continue
        try:
            n = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        st["seen"].append(f.name)
        if n.get("sent") or not n.get("draft_id"):
            continue
        live = pending_ids() if live is None else live
        if not n.get("demo") and n["draft_id"] not in live:  # черновик уже отправлен или убран в дашборде
            continue
        cid = str(st["next_id"])
        st["next_id"] += 1
        opts = card_options(n)
        msg = tg.call("sendMessage", chat_id=chat_id, text=card_text(n), parse_mode="HTML",
                      reply_markup=card_keyboard(cid, len(opts)), disable_web_page_preview=True)
        st["cards"][cid] = {"draft_id": n["draft_id"], "file": f.name, "message_id": msg["message_id"],
                            "options": opts, "status": "open", "choice": "", "demo": bool(n.get("demo"))}
        save_state(st)


def _notification(card: dict) -> dict:
    try:
        return json.loads((NOTIFY_DIR / card["file"]).read_text(encoding="utf-8"))
    except Exception:
        return {"employer_msg": "", "company": "", "title": ""}


def show_card(tg: TG, chat_id: int, card: dict, cid: str, footer: str = "", keyboard=None) -> None:
    n = _notification(card)
    tg.call("editMessageText", chat_id=chat_id, message_id=card["message_id"], text=card_text(n, footer),
            parse_mode="HTML", disable_web_page_preview=True,
            reply_markup=keyboard if keyboard is not None else {"inline_keyboard": []})


def send_choice(card: dict) -> str:
    """Отправить работодателю выбранный текст. '' — успех, иначе причина."""
    did = card["draft_id"]
    if did not in pending_ids():
        return "черновика уже нет в очереди: ответ ушёл или дашборд перезапускался"
    r = api("POST", "/api/llm/pending/edit", {"id": did, "text": card["choice"]})
    if not r.get("ok"):
        return f"не удалось поправить черновик: {r.get('error')}"
    r = api("POST", "/api/llm/pending/send", {"ids": [did]})
    return "" if r.get("sent") else f"hh не принял ответ: {str(r)[:200]}"


# ── очередь откликов: бот готовит, владелец жмёт на hh (app/apply_queue.py) ─────

def queue_text(it: dict) -> tuple:
    """(карточка, [сообщения с анкетой, если в карточку не влезла])."""
    e = html.escape
    head = [f"📝 <b>{e(it.get('company') or '—')}</b> · {e(it.get('title') or it['vacancy_id'])}"]
    if it.get("salary"):
        head.append(f"💰 {e(it['salary'])}")
    head.append(f'<a href="{e(it["url"])}">Вакансия</a>')
    if it.get("note"):
        head.append(f"⚠️ {e(it['note'])}")
    letter = (it.get("letter") or "").strip()
    head += ["", "<b>Письмо</b> (нажми, чтобы скопировать)", f"<pre>{e(letter[:3300])}</pre>"]
    qa = [f"<b>{i}. {e(x.get('q', '')[:400])}</b>\n<code>{e(x.get('a', '')[:900])}</code>"
          for i, x in enumerate(it.get("qa") or [], 1)]
    card = "\n".join(head)
    if not qa:
        return card, []
    block = "<b>Анкета</b>\n" + "\n\n".join(qa)
    if len(card) + len(block) < 3900:
        return card + "\n\n" + block, []
    parts, part = [], "<b>Анкета</b>"
    for q in qa:
        if len(part) + len(q) > 3800:
            parts.append(part)
            part = ""
        part = f"{part}\n\n{q}" if part else q
    parts.append(part)
    return card + "\n\n<i>Анкета — следующим сообщением</i>", parts


def queue_keyboard(it: dict) -> dict:
    return {"inline_keyboard": [
        [{"text": "🔗 Откликнуться на hh", "url": it["response_url"]}],
        [{"text": "✅ Отправил", "callback_data": f"q:done:{it['id']}"},
         {"text": "⏭ Пропустить", "callback_data": f"q:skip:{it['id']}"}]]}


def queue_cards(tg: TG, chat_id: int, st: dict) -> None:
    """Новые записи очереди → карточки, не больше QUEUE_OPEN открытых сразу (закрыл одну — пришла следующая)."""
    res = api("GET", "/api/apply_queue?status=open")
    if not res.get("ok"):
        return
    items = res.get("items") or []
    shown = sum(1 for it in items if it["id"] in st["queue"])
    for it in items:
        if shown >= QUEUE_OPEN:
            break
        if it["id"] in st["queue"]:
            continue
        text, extra = queue_text(it)
        msg = tg.call("sendMessage", chat_id=chat_id, text=text, parse_mode="HTML",
                      reply_markup=queue_keyboard(it), disable_web_page_preview=True)
        ids = []
        for part in extra:
            m = tg.call("sendMessage", chat_id=chat_id, text=part, parse_mode="HTML",
                        reply_to_message_id=msg["message_id"], disable_web_page_preview=True)
            ids.append(m["message_id"])
        st["queue"][it["id"]] = {"message_id": msg["message_id"], "extra": ids}
        shown += 1
        save_state(st)


def on_queue(tg: TG, chat_id: int, st: dict, cb: dict, rest: str) -> None:
    what, _, iid = rest.partition(":")
    card = st["queue"].get(iid) or {}
    r = api("POST", f"/api/apply_queue/{'done' if what == 'done' else 'skip'}", {"id": iid})
    note = ""
    it = r.get("item") or {}
    if not r.get("ok"):
        note = f"Не вышло: {r.get('error', '')}"[:190]
    else:
        e = html.escape
        mark = "✅ Отправил" if it.get("status") == "done" else "⏭ Пропущено"
        msg_id = card.get("message_id") or (cb.get("message") or {}).get("message_id")
        tg.call("editMessageText", chat_id=chat_id, message_id=msg_id, parse_mode="HTML",
                disable_web_page_preview=True,
                text=f"{mark}: <b>{e(it.get('company') or '—')}</b> · {e(it.get('title') or it.get('vacancy_id', ''))}")
        for mid in card.get("extra") or []:
            try:
                tg.call("deleteMessage", chat_id=chat_id, message_id=mid)
            except Exception:
                pass
        if iid in st["queue"]:
            st["queue"][iid]["closed"] = True
    save_state(st)
    tg.call("answerCallbackQuery", callback_query_id=cb["id"], text=note)


def on_callback(tg: TG, chat_id: int, st: dict, cb: dict) -> None:
    action, _, rest = (cb.get("data") or "").partition(":")
    if action == "captcha":
        on_captcha(tg, chat_id, st, cb, rest)
        return
    if action == "q":
        on_queue(tg, chat_id, st, cb, rest)
        return
    cid, _, arg = rest.partition(":")
    card = st["cards"].get(cid)
    note = ""
    e = html.escape
    if not card or card["status"] in ("sent", "skipped"):
        note = "Карточка уже закрыта"
    elif action == "pick":
        k = int(arg or 0)
        if 1 <= k <= len(card["options"]):
            card["choice"] = card["options"][k - 1]
            show_card(tg, chat_id, card, cid, f"<b>Отправить вариант {k}?</b>\n{e(card['choice'])}",
                      confirm_keyboard(cid))
    elif action == "own":
        prompt = tg.call("sendMessage", chat_id=chat_id, text="Напиши ответ работодателю ответом на это сообщение.",
                         reply_to_message_id=card["message_id"],
                         reply_markup={"force_reply": True, "input_field_placeholder": "Свой ответ"})
        st["custom"][str(prompt["message_id"])] = cid
    elif action == "back":
        card["choice"] = ""
        show_card(tg, chat_id, card, cid, keyboard=card_keyboard(cid, len(card["options"])))
    elif action == "skip":
        if not card.get("demo"):
            api("POST", "/api/llm/pending/discard", {"ids": [card["draft_id"]]})
        card["status"] = "skipped"
        show_card(tg, chat_id, card, cid, "⏭ <i>Пропущено, работодателю ничего не ушло</i>")
    elif action == "send" and card.get("choice"):
        why = "" if card.get("demo") else send_choice(card)
        if why:
            note = "Не отправилось"
            show_card(tg, chat_id, card, cid, f"❌ {e(why)}", card_keyboard(cid, len(card["options"])))
        else:
            card["status"] = "sent"
            done = "✅ <b>Демо, работодателю не ушло:</b> " if card.get("demo") else "✅ <b>Отправлено:</b> "
            show_card(tg, chat_id, card, cid, done + e(card["choice"]))
    save_state(st)
    tg.call("answerCallbackQuery", callback_query_id=cb["id"], text=note)


def on_message(tg: TG, chat_id: int, st: dict, msg: dict) -> None:
    text = (msg.get("text") or "").strip()
    reply_to = msg.get("reply_to_message") or {}
    rid = str(reply_to.get("message_id", ""))
    cid = st["custom"].get(rid) or next(
        (k for k, c in st["cards"].items() if str(c["message_id"]) == rid), None)
    if text in ("/start", "/help"):
        tg.call("sendMessage", chat_id=chat_id, text=(
            "Сюда приходят чаты hh, где нужен твой ответ: нажми вариант или «Свой ответ», потом «Отправить».\n"
            f"И очередь откликов (по {QUEUE_OPEN} за раз): «Откликнуться на hh», вставь письмо и ответы, "
            "отправь на hh, потом «Отправил». /queue — сколько ждёт."))
        return
    if text == "/queue":
        n = api("GET", "/api/apply_queue?status=open").get("count", "?")
        tg.call("sendMessage", chat_id=chat_id, text=f"📝 В очереди откликов: {n}")
        return
    if not cid or not text or st["cards"].get(cid, {}).get("status") in ("sent", "skipped"):
        if text:
            tg.call("sendMessage", chat_id=chat_id,
                    text="Свой ответ пиши ответом (reply) на карточку или на сообщение «Напиши ответ…».")
        return
    card = st["cards"][cid]
    card["choice"] = text
    st["custom"].pop(rid, None)
    show_card(tg, chat_id, card, cid, f"<b>Отправить свой ответ?</b>\n{html.escape(text)}", confirm_keyboard(cid))
    save_state(st)


def md_to_html(text: str) -> str:
    """Markdown уведомлений (как для Hermes) → HTML Telegram: **жирный**, `код`, [текст](url),
    > цитата (длиннее двух строк — сворачивается), ## заголовок."""
    out, quote = [], []

    def inline(line: str) -> str:
        line = html.escape(line, quote=False)
        line = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', line)
        line = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", line)
        return re.sub(r"`([^`]+)`", r"<code>\1</code>", line)

    def flush():
        if quote:
            tag = "<blockquote expandable>" if len(quote) > 2 else "<blockquote>"
            out.append(tag + "\n".join(quote) + "</blockquote>")
            quote.clear()
    for line in text.splitlines():
        if line.startswith("> "):
            quote.append(inline(line[2:]))
            continue
        flush()
        out.append(f"<b>{inline(line.lstrip('#').strip())}</b>" if line.startswith("#") else inline(line))
    flush()
    return "\n".join(out)


def send_long(tg: "TG", chat_id: int, text: str) -> None:
    """HTML-сообщение частями по абзацам (лимит Telegram 4096)."""
    part = ""
    for block in md_to_html(text).split("\n\n"):
        if part and len(part) + len(block) > 3800:
            tg.call("sendMessage", chat_id=chat_id, text=part, parse_mode="HTML", disable_web_page_preview=True)
            part = ""
        part = f"{part}\n\n{block}" if part else block
    if part.strip():
        tg.call("sendMessage", chat_id=chat_id, text=part, parse_mode="HTML", disable_web_page_preview=True)


def _now() -> datetime:
    return datetime.now(ZoneInfo(os.environ.get("HH_DIGEST_TZ", "Asia/Ho_Chi_Minh")))


def _captchas_after(ts: str) -> list:
    """Уведомления о капче новее ts (ISO), по времени."""
    out = []
    for f in sorted(NOTIFY_DIR.glob("*_error.json")) if NOTIFY_DIR.exists() else []:
        try:
            n = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if n.get("subtype") == "captcha" and n.get("timestamp", "") > ts:
            out.append(n)
    return out


def _responses_between(a: str, b: str) -> int:
    n = 0
    for f in NOTIFY_DIR.glob("*_response.json") if NOTIFY_DIR.exists() else []:
        try:
            ts = json.loads(f.read_text(encoding="utf-8")).get("timestamp", "")
        except Exception:
            continue
        n += a < ts <= b
    return n


def captcha_prompt(tg: "TG", chat_id: int, st: dict) -> None:
    """Капча hh → владельцу ссылка и кнопка «Решил», но не чаще раза в день (решение владельца
    11.11: «с телефона могу решать, главное чтобы не постоянно»). Капча после перезапуска —
    стоп до утра без вопроса: по 10–11.11 после ~12 откликов hh ставит её на каждый отклик."""
    first = "captcha_last_ts" not in st  # первый запуск: о старых капчах не спрашивать
    fresh = _captchas_after(st.get("captcha_last_ts", ""))
    if not fresh:
        st.setdefault("captcha_last_ts", "")
        return
    n = fresh[-1]
    st["captcha_last_ts"] = n.get("timestamp", "")
    today = _now().date().isoformat()
    if first:
        pass
    elif st.get("captcha_resumed_date") == today:
        if st.get("captcha_fail_date") != today:
            st["captcha_fail_date"] = today
            passed = _responses_between(st.get("captcha_resumed_ts", ""), n.get("timestamp", ""))
            tg.call("sendMessage", chat_id=chat_id, parse_mode="HTML", text=(
                f"🧩 <b>hh снова просит капчу.</b> После твоей прошло откликов: {passed}. "
                "Сегодня больше не спрошу, кампании продолжат утром."))
    elif st.get("captcha_ask_date") != today and _resume_allowed():
        st["captcha_ask_date"] = today
        url = n.get("captcha_url") or "https://hh.ru/applicant/negotiations"
        msg = tg.call("sendMessage", chat_id=chat_id, parse_mode="HTML", text=(
            "🧩 <b>hh просит капчу, отклики стоят.</b>\n"
            "1. Открой ссылку (это вакансия, на которой бот остановился)\n"
            "2. Откликнись и реши капчу\n"
            "3. Нажми «Решил» — бот продолжит кампании\n\n"
            "Не хочешь — «До завтра», бот продолжит утром сам. Спрашиваю не чаще раза в день."),
            reply_markup={"inline_keyboard": [
                [{"text": "🧩 Открыть капчу", "url": url}],
                [{"text": "✅ Решил", "callback_data": f"captcha:solved:{today}"},
                 {"text": "До завтра", "callback_data": f"captcha:skip:{today}"}]]})
        st["captcha_msg_id"] = (msg or {}).get("message_id")
    save_state(st)


def _resume_allowed() -> bool:
    """Перезапуск после капчи — только до HH_CAPTCHA_RESUME_UNTIL (время сервера, по умолч. 12:00).
    Новая капча включает в hh_cron паузу 20 ч: позже полудня она сорвала бы утренний старт
    кампаний (Hermes «hh: кампании» в 09:00 МСК). Часы здесь серверные (МСК), а дата
    captcha_ask_date — по HH_DIGEST_TZ (+07); расходятся только 20:00–24:00 МСК, вне окна вопроса."""
    hh, _, mm = os.environ.get("HH_CAPTCHA_RESUME_UNTIL", "12:00").partition(":")
    now = datetime.now()
    return (now.hour, now.minute) < (int(hh), int(mm or 0))


def _resume_campaigns() -> str:
    """hh_cron в фоне, без паузы 20 ч. '' — запущен, иначе почему нет."""
    import subprocess
    if subprocess.run(["pgrep", "-f", "scripts/hh_cron.py"], capture_output=True).returncode == 0:
        return "кампании уже идут"
    names = os.environ.get("HH_CRON_CAMPAIGNS", "Ai-engineer devops").split()
    with open(DATA / "hh_cron.log", "a", encoding="utf-8") as log:
        subprocess.Popen([sys.executable, str(ROOT / "scripts" / "hh_cron.py"), "--notify", "--after-captcha", *names],
                         cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                         start_new_session=True)
    return ""


def on_captcha(tg: "TG", chat_id: int, st: dict, cb: dict, rest: str) -> None:
    what, _, day = rest.partition(":")
    msg = cb.get("message") or {}
    today = _now().date().isoformat()
    note, footer = "", ""
    if day != today or st.get("captcha_resumed_date") == today:
        note = "Уже неактуально"
    elif what == "solved" and not _resume_allowed():
        st["captcha_resumed_date"] = st["captcha_fail_date"] = today
        footer = "⏸ Уже после полудня: перезапуск сдвинул бы завтрашний старт. Продолжу утром сам."
    elif what == "solved":
        why = _resume_campaigns()
        if why:
            note = why
        else:
            st["captcha_resumed_date"], st["captcha_resumed_ts"] = today, datetime.now().isoformat()
            footer = "▶️ <b>Продолжаю кампании.</b> Если капча вернётся — стоп до утра, больше не спрошу."
    elif what == "skip":
        st["captcha_resumed_date"] = st["captcha_fail_date"] = today  # сегодня больше не спрашивать
        footer = "⏸ Ок, продолжу утром сам."
    if footer and msg.get("message_id"):
        tg.call("editMessageText", chat_id=chat_id, message_id=msg["message_id"], parse_mode="HTML",
                text=html.escape(msg.get("text", "")) + "\n\n" + footer)
    save_state(st)
    tg.call("answerCallbackQuery", callback_query_id=cb["id"], text=note)


def relay(tg: "TG", chat_id: int, st: dict) -> None:
    """Уведомления hh (кроме черновиков: они карточками) — сюда, а не в Hermes."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import poll_notifications as pn
    text = pn.poll(mark=True, quiet=True, captcha=False)
    if text and text != "[SILENT]":
        send_long(tg, chat_id, text)
    captcha_prompt(tg, chat_id, st)
    # Итог дня
    now = _now()
    if (now.hour, now.minute) >= (20, 30) and st.get("digest_date") != now.date().isoformat():
        import hh_digest
        st["digest_date"] = now.date().isoformat()
        save_state(st)
        d = hh_digest.digest(date.today().isoformat())
        if d and d != "[SILENT]":
            send_long(tg, chat_id, d)


def run() -> int:
    load_env()
    token, chat = os.environ.get("HH_REPLY_BOT_TOKEN", ""), os.environ.get("HH_REPLY_CHAT_ID", "")
    if not token or not chat:
        print("✗ В .env нужны HH_REPLY_BOT_TOKEN и HH_REPLY_CHAT_ID")
        return 2
    chat_id = int(chat)
    tg = TG(token)
    me = tg.call("getMe")
    if "--check" in sys.argv:
        print(f"✓ бот @{me.get('username')} отвечает")
        return 0
    st = load_state()
    if not st["seen"] and NOTIFY_DIR.exists():
        # первый запуск: старые уведомления не превращаем в карточки, только новые
        st["seen"] = [f.name for f in NOTIFY_DIR.glob("*_chat.json")]
    save_state(st)
    print(f"hh_reply_bot: @{me.get('username')} работает", flush=True)
    while True:
        try:
            new_cards(tg, chat_id, st)
            queue_cards(tg, chat_id, st)
            relay(tg, chat_id, st)
            ups = tg.call("getUpdates", offset=st["offset"], timeout=25,
                          allowed_updates=["message", "callback_query"]) or []
            for u in ups:
                st["offset"] = u["update_id"] + 1
                if "callback_query" in u:
                    cb = u["callback_query"]
                    if (cb.get("from") or {}).get("id") == chat_id:
                        on_callback(tg, chat_id, st, cb)
                elif "message" in u:
                    m = u["message"]
                    if (m.get("chat") or {}).get("id") == chat_id:
                        on_message(tg, chat_id, st, m)
            save_state(st)
        except Exception as ex:  # сеть, Telegram, дашборд: подождать и продолжить
            print(f"hh_reply_bot: {str(ex)[:300]}", flush=True)
            save_state(st)
            time.sleep(10)


if __name__ == "__main__":
    sys.exit(run())
