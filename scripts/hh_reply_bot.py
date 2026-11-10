#!/usr/bin/env python3
"""Отдельный Telegram-бот для чатов hh, где нужен ответ владельца.

    python3 scripts/hh_reply_bot.py          работать (long polling), для systemd
    python3 scripts/hh_reply_bot.py --check  проверить токен и доступ к Telegram, ничего не слать

Карточка на каждый черновик: сообщение работодателя, варианты кнопками, «Свой ответ»,
«Пропустить». Вариант или свой текст сначала показываются с вопросом «Отправить?», и только
после «Отправить» уходят работодателю через очередь дашборда (/api/llm/pending/*).
Остальное (отклики, сводка, капча, вход) по-прежнему идёт через Hermes: poll_notifications.py
пропускает черновики, пока этот бот жив (heartbeat в data/reply_bot_state.json).

.env: HH_REPLY_BOT_TOKEN — токен бота, HH_REPLY_CHAT_ID — id владельца (команды принимаются
только от него). Токен никуда не печатается.
"""
import html
import json
import os
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("HH_DATA_DIR", ROOT / "data"))
NOTIFY_DIR = DATA / "notifications"
STATE_FILE = DATA / "reply_bot_state.json"
API_BASE = os.environ.get("HH_API_BASE", "http://127.0.0.1:8000")
HEARTBEAT_TTL = 300  # сек: дольше бот молчит — черновики снова уходят через Hermes


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
        if n["draft_id"] not in live:  # черновик уже отправлен или убран в дашборде
            continue
        cid = str(st["next_id"])
        st["next_id"] += 1
        opts = card_options(n)
        msg = tg.call("sendMessage", chat_id=chat_id, text=card_text(n), parse_mode="HTML",
                      reply_markup=card_keyboard(cid, len(opts)), disable_web_page_preview=True)
        st["cards"][cid] = {"draft_id": n["draft_id"], "file": f.name, "message_id": msg["message_id"],
                            "options": opts, "status": "open", "choice": ""}
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


def on_callback(tg: TG, chat_id: int, st: dict, cb: dict) -> None:
    action, _, rest = (cb.get("data") or "").partition(":")
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
        api("POST", "/api/llm/pending/discard", {"ids": [card["draft_id"]]})
        card["status"] = "skipped"
        show_card(tg, chat_id, card, cid, "⏭ <i>Пропущено, работодателю ничего не ушло</i>")
    elif action == "send" and card.get("choice"):
        why = send_choice(card)
        if why:
            note = "Не отправилось"
            show_card(tg, chat_id, card, cid, f"❌ {e(why)}", card_keyboard(cid, len(card["options"])))
        else:
            card["status"] = "sent"
            show_card(tg, chat_id, card, cid, f"✅ <b>Отправлено:</b> {e(card['choice'])}")
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
            "Сюда приходят чаты hh, где нужен твой ответ. Нажми вариант или «Свой ответ», "
            "потом «Отправить». Остальное (отклики, сводка) приходит в aisy."))
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
