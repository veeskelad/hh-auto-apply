"""Очередь откликов «бот готовит — владелец жмёт»: хранилище, подготовка без POST в hh, API, карточки бота.

В hh и к нейросети тесты не ходят: сеть и модель подменяются.
"""
import asyncio
import json
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from app import apply_queue, hh_apply  # noqa: E402

FORM = """<form>
<input type="hidden" name="_xsrf" value="x"/>
<div data-qa="task-body"><div data-qa="task-question">Готовы к офису?</div>
<label><input name="task_2" type="radio" value="21"/>да</label>
<label><input name="task_2" type="radio" value="22"/>нет</label></div>
<div data-qa="task-body"><div data-qa="task-question">Опыт с Vault?</div>
<textarea name="task_3_text"></textarea></div>
</form>"""


@pytest.fixture
def queue(tmp_path, monkeypatch):
    monkeypatch.setattr(apply_queue, "QUEUE_FILE", tmp_path / "apply_queue.json")
    apply_queue.reset_cache()
    yield apply_queue
    apply_queue.reset_cache()


def test_queue_add_find_close(queue):
    a = queue.add("Дима", "101", {"title": "DevOps", "company": "Acme", "letter": "Привет"})
    assert a["id"] == "1" and a["status"] == "open"
    assert a["response_url"] == "https://hh.ru/applicant/vacancy_response?vacancyId=101"
    assert queue.add("Дима", "101", {"title": "другое"})["id"] == "1"  # повтор — та же запись
    assert queue.is_queued("Дима", "101") and not queue.is_queued("Другой", "101")
    queue.add("Дима", "102", {})
    assert [it["vacancy_id"] for it in queue.items("open")] == ["101", "102"]
    assert queue.close("1", "done")["status"] == "done"
    assert queue.close("1", "skipped")["status"] == "done"  # закрытую не переоткрываем
    assert queue.close("99", "done") == {}
    assert queue.is_queued("Дима", "101")  # закрытую бот второй раз не готовит
    queue.reset_cache()
    assert [it["id"] for it in queue.items("open")] == ["2"]  # пережило перечитывание файла
    with pytest.raises(ValueError):
        queue.close("2", "open")


class Resp:
    def __init__(self, text):
        self.text, self.status_code = text, 200


def _no_post(*a, **kw):
    raise AssertionError("в режиме очереди POST в hh запрещён")


def _prepare(monkeypatch, html, llm_result):
    async def letter(acc, vid):
        return "Письмо под вакансию"
    monkeypatch.setattr(hh_apply, "_resolve_letter", letter)
    monkeypatch.setattr(hh_apply.requests, "get", lambda *a, **kw: Resp(html))
    monkeypatch.setattr(hh_apply.requests, "post", _no_post)
    monkeypatch.setattr(hh_apply, "_llm_questionnaire", lambda *a: llm_result)
    acc = {"name": "Дима", "cookies": {"_xsrf": "x"}}
    return asyncio.run(hh_apply.prepare_manual_apply(acc, "201", "SRE", "Acme", "от 300 000", "c1"))


def test_prepare_with_questionnaire(queue, monkeypatch):
    res, item = _prepare(monkeypatch, FORM, ({"task_2": "22", "task_3_text": "Vault HA в проде"}, True, []))
    assert res == "queued"
    assert item["letter"] == "Письмо под вакансию" and item["campaign_id"] == "c1"
    assert item["qa"] == [{"q": "Готовы к офису?", "a": "нет"}, {"q": "Опыт с Vault?", "a": "Vault HA в проде"}]
    assert item["note"] == ""
    assert queue.is_queued("Дима", "201")


def test_prepare_unanswered_left_to_owner(queue, monkeypatch):
    _, item = _prepare(monkeypatch, FORM, ({"task_3_text": "Vault"}, True, ["Готовы к офису?"]))
    assert item["qa"] == [{"q": "Готовы к офису?", "a": "— ответь сам"}, {"q": "Опыт с Vault?", "a": "Vault"}]
    assert "нет ответа по фактам" in item["note"]


def test_prepare_template_answers_hidden(queue, monkeypatch):
    """Нейросеть не ответила: шаблон («да», первый вариант) владельцу не показываем."""
    _, item = _prepare(monkeypatch, FORM, ({"task_2": "21", "task_3_text": "шаблон"}, False, []))
    assert [x["a"] for x in item["qa"]] == ["— ответь сам", "— ответь сам"]
    assert "ответь сам" in item["note"]


def test_prepare_without_questionnaire(queue, monkeypatch):
    _, item = _prepare(monkeypatch, "<form><textarea name='letter'></textarea></form>", None)
    assert item["qa"] == [] and item["note"] == ""


def test_prepare_captcha_or_login_not_queued(queue, monkeypatch):
    res, info = _prepare(monkeypatch, '{"hhcaptcha":{"isBot":true}}', None)
    assert res == "captcha" and info["captcha_url"].endswith("vacancyId=201")
    monkeypatch.setattr(hh_apply, "_is_login_page", lambda html: True)
    res, _ = _prepare(monkeypatch, "<html>вход</html>", None)
    assert res == "auth_error"
    assert queue.items() == []


def _manager(monkeypatch, results):
    from app import manager
    seen = []

    async def prep(acc, vid, title, company, salary, cid, meta):
        seen.append((vid, title, salary, cid))
        return results.pop(0)
    monkeypatch.setattr(manager, "prepare_manual_apply", prep)
    monkeypatch.setattr(manager.random, "uniform", lambda a, b: 0)
    logs, flags = [], []
    fake = SimpleNamespace(_stop_event=threading.Event(), _add_log=lambda *a: logs.append(a[2]),
                           _add_acc_event=lambda *a: None, _mark_cookies_expired=lambda st: flags.append("expired"))
    state = SimpleNamespace(paused=False, active_campaign_id="c1", armed=True, vacancy_meta={
        "1": {"title": "DevOps", "company": "Acme"}}, daily_date="", daily_sent=0, hard_stopped=False,
        campaign_sent=0, errors=0, action_history=[], short="Д", color="", status="", status_detail="",
        current_vacancy_id="", current_vacancy_title="", current_vacancy_company="")
    return manager, fake, state, seen, logs, flags


def test_manager_queue_manual_counts(queue, monkeypatch):
    manager, fake, state, seen, logs, _ = _manager(monkeypatch, [("queued", {"qa": [{"q": "q", "a": "a"}]}),
                                                                ("queued", {"qa": []})])
    stop = manager.BotManager._queue_manual(fake, state, {"name": "Дима"}, ["1", "2"], {"1": 300000})
    assert stop is False
    assert seen == [("1", "DevOps", "от 300 000", "c1"), ("2", "", "", "c1")]
    assert state.daily_sent == 2 and state.campaign_sent == 2 and state.queued == 2
    assert logs[0].startswith("📝 В очередь: DevOps @ Acme (анкета 1)")


def test_manager_queue_manual_stops(queue, monkeypatch):
    from app import manager
    notified = []
    monkeypatch.setattr(manager, "notify_captcha", lambda acc, url: notified.append(url))
    manager_, fake, state, seen, _, _ = _manager(monkeypatch, [("captcha", {"captcha_url": "u"})])
    assert manager.BotManager._queue_manual(fake, state, {"name": "Дима"}, ["1", "2"], {}) is True
    assert state.status == "captcha" and state.paused and notified == ["u"] and state.daily_sent == 0
    assert len(seen) == 1

    _, fake, state, seen, _, flags = _manager(monkeypatch, [("auth_error", {})])
    assert manager.BotManager._queue_manual(fake, state, {"name": "Дима"}, ["1"], {}) is True
    assert flags == ["expired"] and state.paused and state.daily_sent == 0

    monkeypatch.setattr(manager.CONFIG, "manual_queue_max", 2)
    queue.add("Дима", "a", {})
    queue.add("Дима", "b", {})
    _, fake, state, seen, logs, _ = _manager(monkeypatch, [])
    assert manager.BotManager._queue_manual(fake, state, {"name": "Дима"}, ["1"], {}) is True
    assert seen == [] and state.status == "limit" and state.paused and "Очередь полна: 2" in state.status_detail


class Req:
    def __init__(self, body):
        self.body = body

    async def json(self):
        return self.body


def test_api_done_records_applied(queue, monkeypatch):
    from app.routes import apply_queue as routes
    applied = []
    monkeypatch.setattr(routes, "add_applied", lambda acc, vid, info: applied.append((acc, vid, info)))
    queue.add("Дима", "301", {"title": "SRE", "company": "Acme", "campaign_id": "c1",
                              "meta": {"source_query": "sre", "source_url": None}})
    queue.add("Дима", "302", {"title": "ML"})
    assert asyncio.run(routes.queue_list("open"))["count"] == 2
    r = asyncio.run(routes.queue_done(Req({"id": "1"})))
    assert r["ok"] and r["item"]["status"] == "done"
    assert applied == [("Дима", "301", {"title": "SRE", "company": "Acme", "campaign_id": "c1",
                                        "source_query": "sre"})]
    assert asyncio.run(routes.queue_skip(Req({"id": "2"})))["item"]["status"] == "skipped"
    assert asyncio.run(routes.queue_done(Req({"id": "1"})))["ok"]  # повтор не пишет второй раз
    assert len(applied) == 1
    assert asyncio.run(routes.queue_done(Req({"id": "9"})))["ok"] is False
    assert asyncio.run(routes.queue_list("bad"))["ok"] is False


# ── @ninjiu_bot ──────────────────────────────────────────────────────────────

class FakeTG:
    def __init__(self):
        self.calls, self.n = [], 100

    def call(self, method, **p):
        self.calls.append((method, p))
        self.n += 1
        return {"message_id": self.n}


def _item(iid, qa=None, letter="Здравствуйте! <опыт> 5 лет"):
    return {"id": iid, "vacancy_id": f"v{iid}", "title": "DevOps", "company": "Acme & Co", "salary": "от 300 000",
            "url": f"https://hh.ru/vacancy/v{iid}", "note": "",
            "response_url": f"https://hh.ru/applicant/vacancy_response?vacancyId=v{iid}",
            "letter": letter, "qa": qa or []}


@pytest.fixture
def bot(tmp_path, monkeypatch):
    import hh_reply_bot
    monkeypatch.setattr(hh_reply_bot, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(hh_reply_bot, "QUEUE_OPEN", 2)
    return hh_reply_bot


def test_queue_text_escapes_and_fits(bot):
    text, extra = bot.queue_text(_item("1", [{"q": "Опыт с Vault?", "a": "Vault HA"}]))
    assert "Acme &amp; Co" in text and "&lt;опыт&gt;" in text and "<pre>" in text
    assert "<code>Vault HA</code>" in text and extra == []
    long_qa = [{"q": f"Вопрос {i}", "a": "ответ " * 120} for i in range(8)]
    text, extra = bot.queue_text(_item("2", long_qa, letter="п" * 2500))
    assert "следующим сообщением" in text and extra
    assert all(len(p) < 4096 for p in [text] + extra)
    assert sum(p.count("<b>") for p in extra) == 8 + 1  # все вопросы и заголовок «Анкета»


def test_queue_cards_limit_and_close(bot, monkeypatch):
    open_items = [_item("1"), _item("2"), _item("3")]
    posted = []

    def api(method, path, body=None):
        if method == "GET":
            return {"ok": True, "items": [it for it in open_items], "count": len(open_items)}
        posted.append((path, body))
        it = next(i for i in open_items if i["id"] == body["id"])
        open_items.remove(it)
        return {"ok": True, "item": {**it, "status": "done" if path.endswith("done") else "skipped"}}
    monkeypatch.setattr(bot, "api", api)
    tg, st = FakeTG(), bot.load_state()
    bot.queue_cards(tg, 1, st)
    sent = [p for m, p in tg.calls if m == "sendMessage"]
    assert len(sent) == 2  # не больше QUEUE_OPEN
    kb = sent[0]["reply_markup"]["inline_keyboard"]
    assert kb[0][0]["url"].endswith("vacancyId=v1") and kb[1][0]["callback_data"] == "q:done:1"
    bot.queue_cards(tg, 1, st)
    assert len([1 for m, _ in tg.calls if m == "sendMessage"]) == 2  # повторно те же не шлём

    bot.on_callback(tg, 1, st, {"id": "cb", "data": "q:done:1", "message": {"message_id": 101}})
    assert posted == [("/api/apply_queue/done", {"id": "1"})]
    edit = [p for m, p in tg.calls if m == "editMessageText"][-1]
    assert edit["text"].startswith("✅ Отправил") and "reply_markup" not in edit
    bot.queue_cards(tg, 1, st)
    sent = [p for m, p in tg.calls if m == "sendMessage"]
    assert len(sent) == 3 and "v3" in json.dumps(sent[-1]["reply_markup"])  # место освободилось
