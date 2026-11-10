"""Автопилот: факты и плейбук в промптах, разбор плана ответа в чате, журнал анкет, уведомления.

Нейросеть подменяется: тесты не ходят ни в hh, ни к модели.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import hh_apply, llm, notify  # noqa: E402


@pytest.fixture
def files(tmp_path, monkeypatch):
    facts = tmp_path / "profile_facts.md"
    playbook = tmp_path / "chat_playbook.md"
    facts.write_text("<!-- ПРОВЕРЬ: служебное -->\nDevOps в Acme, Vault HA", encoding="utf-8")
    playbook.write_text("### thanks\nкоротко", encoding="utf-8")
    monkeypatch.setattr(llm, "PROFILE_FACTS_FILE", facts)
    monkeypatch.setattr(llm, "CHAT_PLAYBOOK_FILE", playbook)
    llm._file_cache.clear()
    return facts, playbook


def fake_llm(monkeypatch, answer):
    seen = {}

    def _chat(messages, **kw):
        seen["messages"] = messages
        return answer
    monkeypatch.setattr(llm, "_llm_chat", _chat)
    return seen


def test_facts_without_comments(files):
    assert llm.profile_facts() == "DevOps в Acme, Vault HA"
    assert "ПРОВЕРЬ" not in llm._facts_block()


def test_facts_reread_on_change(files):
    facts, _ = files
    assert "Vault" in llm.profile_facts()
    facts.write_text("новые факты", encoding="utf-8")
    import os
    os.utime(facts, (facts.stat().st_atime, facts.stat().st_mtime + 5))
    assert llm.profile_facts() == "новые факты"


def test_cover_letter_gets_facts(files, monkeypatch):
    seen = fake_llm(monkeypatch, "письмо")
    assert llm.generate_cover_letter("DevOps", "описание", "Acme", "резюме") == "письмо"
    assert "Vault HA" in seen["messages"][0]["content"]


def test_plan_auto_category(files, monkeypatch):
    seen = fake_llm(monkeypatch, json.dumps({
        "category": "experience", "confidence": 0.9, "reply": "Да — работал с Vault",
        "variants": ["Вариант 2", "Вариант 3"], "reason": "вопрос про опыт"}, ensure_ascii=False))
    plan = llm.generate_llm_reply_plan([{"sender": "employer", "text": "Был опыт с Vault?"}], "Acme")
    assert plan["auto"] is True and plan["category"] == "experience"
    assert "—" not in plan["reply"]
    assert plan["variants"] == ["Вариант 2", "Вариант 3"]
    system = seen["messages"][0]["content"]
    assert "Плейбук" in system and "Vault HA" in system
    assert "Работодатель: Был опыт с Vault?" in seen["messages"][1]["content"]


@pytest.mark.parametrize("payload, auto", [
    ({"category": "offer", "confidence": 0.99, "reply": "Спасибо"}, False),          # оффер — только владельцу
    ({"category": "thanks", "confidence": 0.4, "reply": "Спасибо"}, False),          # неуверенно
    ({"category": "something", "confidence": 1, "reply": "x"}, False),               # чужая категория → unknown
    ({"category": "interview_invite", "confidence": 0.8, "reply": ""}, False),      # пустой ответ
])
def test_plan_not_auto(files, monkeypatch, payload, auto):
    fake_llm(monkeypatch, json.dumps(payload))
    plan = llm.generate_llm_reply_plan([{"sender": "employer", "text": "?"}])
    assert plan["auto"] is auto
    if payload["category"] == "something":
        assert plan["category"] == "unknown"


def test_plan_plain_text_is_draft(files, monkeypatch):
    fake_llm(monkeypatch, "Просто текст без JSON")
    plan = llm.generate_llm_reply_plan([{"sender": "employer", "text": "?"}])
    assert plan["category"] == "unknown" and plan["auto"] is False and plan["reply"] == "Просто текст без JSON"


def test_plan_no_reply(files, monkeypatch):
    fake_llm(monkeypatch, "[NO_REPLY]")
    assert llm.generate_llm_reply_plan([{"sender": "employer", "text": "Отклик получен"}])["category"] == "no_reply"


def test_plan_llm_down(files, monkeypatch):
    fake_llm(monkeypatch, "")
    assert llm.generate_llm_reply_plan([{"sender": "employer", "text": "?"}]) == {}


def test_questionnaire_prompt_has_facts(files, monkeypatch):
    seen = {}

    class Resp:
        def __init__(self, text):
            self.choices = [type("C", (), {"message": type("M", (), {"content": text})()})()]

    class Client:
        class chat:
            class completions:
                @staticmethod
                def create(**kw):
                    seen.update(kw)
                    return Resp('{"task_1": "Kubernetes 3 года", "task_2": "2"}')

    monkeypatch.setattr(llm, "_client_for", lambda p: Client())
    monkeypatch.setattr(llm.CONFIG, "llm_profiles", [{"name": "t", "api_key": "x", "base_url": "claude-cli"}])
    qs = [{"field": "task_1", "type": "textarea", "text": "Опыт с k8s?"},
          {"field": "task_2", "type": "radio", "text": "Уровень", "options": [{"value": "1", "label": "нет"},
                                                                             {"value": "2", "label": "да"}]}]
    ans = llm.generate_llm_questionnaire_answers(qs, "DevOps", "Acme", resume_text="R" * 7000)
    assert ans == {"task_1": "Kubernetes 3 года", "task_2": "2"}
    system = seen["messages"][0]["content"]
    assert "Vault HA" in system and "вопрос на знания" in system.lower()
    assert "R" * 6000 in system and "R" * 6001 not in system


def test_questionnaire_log(tmp_path, monkeypatch):
    log = tmp_path / "q.jsonl"
    monkeypatch.setattr(hh_apply, "QUESTIONNAIRE_LOG", log)
    qs = [{"field": "t1", "text": "Опыт?", "options": []},
          {"field": "t2", "text": "Удалёнка?", "options": [{"value": "7", "label": "Да"}]}]
    hh_apply.log_questionnaire("123", "DevOps", "Acme", qs, {"t1": "5 лет", "t2": "7"}, "sent", by_llm=True)
    rec = json.loads(log.read_text(encoding="utf-8"))
    assert rec["result"] == "sent" and rec["by_llm"] is True
    assert rec["qa"] == [{"q": "Опыт?", "a": "5 лет"}, {"q": "Удалёнка?", "a": "Да"}]


def test_notify_chat(tmp_path, monkeypatch):
    monkeypatch.setattr(notify, "NOTIFY_DIR", tmp_path)
    plan = {"category": "unknown", "reply": "черновик", "variants": ["a", "b"], "reason": "нет факта"}
    notify.notify_chat("Acme", "DevOps", "Пришлите NDA", plan, sent=False, draft_id="acc:1", neg_id="1")
    data = json.loads(next(tmp_path.glob("*_chat.json")).read_text(encoding="utf-8"))
    assert data["type"] == "chat" and data["sent"] is False and data["draft_id"] == "acc:1"
    assert data["variants"] == ["a", "b"] and data["delivered"] is False


def _scripts():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import hh_digest
    import poll_notifications
    return poll_notifications, hh_digest


def test_poll_groups_and_marks(tmp_path, monkeypatch):
    poll_notifications, _ = _scripts()
    monkeypatch.setattr(notify, "NOTIFY_DIR", tmp_path)
    monkeypatch.setattr(poll_notifications, "NOTIFY_DIR", tmp_path)
    for i in range(7):
        notify.notify_response(f"DevOps {i}", "Acme")
    notify.notify_chat("Acme", "SRE", "Когда удобно созвониться?",
                       {"category": "unknown", "reply": "Завтра в 12", "variants": ["Чт в 15"]},
                       sent=False, draft_id="acc:9")
    notify.notify_auth_expired("acc")
    text = poll_notifications.poll()
    assert "📤 Отклики: 7" in text and "и ещё 2" in text
    assert "1. Завтра в 12" in text and "2. Чт в 15" in text and "hh reply acc:9" in text
    assert "ego_login.py --target" in text
    assert poll_notifications.poll() == "[SILENT]"


def test_digest(tmp_path, monkeypatch):
    _, hh_digest = _scripts()
    (tmp_path / "notifications").mkdir()
    monkeypatch.setattr(notify, "NOTIFY_DIR", tmp_path / "notifications")
    monkeypatch.setattr(hh_digest, "DATA", tmp_path)
    monkeypatch.setattr(hh_digest, "_pending", lambda: [])
    from datetime import date
    assert hh_digest.digest(date.today().isoformat()) == "[SILENT]"
    notify.notify_response("DevOps", "Acme")
    monkeypatch.setattr(hh_apply, "QUESTIONNAIRE_LOG", tmp_path / "questionnaire_log.jsonl")
    hh_apply.log_questionnaire("1", "SRE", "Beta", [{"field": "f", "text": "Опыт с Vault?"}],
                               {"f": "Да, HA на Raft"}, "sent", by_llm=True)
    text = hh_digest.digest(date.today().isoformat())
    assert "Откликов: 1" in text and "Анкет: 1, приняты 1, нейросетью 1" in text and "HA на Raft" in text


FORM_OPEN = """<form>
<div data-qa="task-body"><div data-qa="task-question">Формат работы на двух последних местах?</div>
<label><input name="task_1" type="radio" value="11"/><span>трудовой договор;</span></label>
<label><input name="task_1" type="radio" value="12"/><span>ГПХ, ИП или самозанятый;</span></label>
<label><input name="task_1" type="radio" value="open"/><span>Own variant</span></label>
<textarea name="task_1_text"></textarea></div>
<div data-qa="task-body"><div data-qa="task-question">Готовы к офису?</div>
<label><input name="task_2" type="radio" value="21"/>да</label>
<label><input name="task_2" type="radio" value="22"/>нет</label></div>
<div data-qa="task-body"><div data-qa="task-question">Опыт с Vault?</div>
<textarea name="task_3_text"></textarea></div>
</form>"""


def test_parse_open_variant_is_one_question():
    from app.questionnaire import _parse_questionnaire_rich, _parse_questionnaire_fields
    qs = _parse_questionnaire_rich(FORM_OPEN)
    assert [q["type"] for q in qs] == ["radio", "radio", "textarea"]
    first = qs[0]
    assert first["text"] == "Формат работы на двух последних местах?"
    assert first["text_field"] == "task_1_text"
    assert [o["label"] for o in first["options"]][:2] == ["трудовой договор;", "ГПХ, ИП или самозанятый;"]
    assert first["options"][-1]["value"] == "open"
    assert qs[1]["text"] == "Готовы к офису?" and "text_field" not in qs[1]
    questions, fa = _parse_questionnaire_fields(FORM_OPEN)
    assert len(questions) == 3
    assert fa["task_1"] in ("11", "12") and fa["task_1_text"] == ""
    assert fa["task_2"] in ("21", "22") and "task_3_text" in fa


def test_answer_text_open_variant():
    from app.questionnaire import _parse_questionnaire_rich, answer_text
    q = _parse_questionnaire_rich(FORM_OPEN)[0]
    assert answer_text(q, {"task_1": "open", "task_1_text": "Штат и самозанятость"}) == "Штат и самозанятость"
    assert answer_text(q, {"task_1": "11", "task_1_text": ""}) == "трудовой договор;"


def test_questionnaire_prompt_open_variant(files, monkeypatch):
    from app.questionnaire import _parse_questionnaire_rich
    seen = {}

    class Resp:
        def __init__(self, text):
            self.choices = [type("C", (), {"message": type("M", (), {"content": text})()})()]

    class Client:
        class chat:
            class completions:
                @staticmethod
                def create(**kw):
                    seen.update(kw)
                    return Resp('{"task_1": "open", "task_1_text": "Штат, затем самозанятость"}')

    monkeypatch.setattr(llm, "_client_for", lambda p: Client())
    monkeypatch.setattr(llm.CONFIG, "llm_profiles", [{"name": "t", "api_key": "x", "base_url": "claude-cli"}])
    ans = llm.generate_llm_questionnaire_answers(_parse_questionnaire_rich(FORM_OPEN)[:1], "SRE", "Acme")
    assert ans == {"task_1": "open", "task_1_text": "Штат, затем самозанятость"}
    user = seen["messages"][1]["content"]
    assert 'value=open, а текст в поле "task_1_text"' in user and '"task_1_text": ""' in user


def test_rebind_campaigns_on_new_browser(monkeypatch):
    from app.routes import sessions
    camps = [{"id": "a", "session_key": "old-uid"}, {"id": "b", "session_key": "other"}]
    saved = []
    monkeypatch.setattr(sessions, "list_campaigns", lambda: camps)
    monkeypatch.setattr(sessions, "upsert_campaign", lambda c: saved.append(c) or c)
    n = sessions._rebind_campaigns({"hhuid": "old-uid"}, {"hhuid": "new-uid", "hhtoken": "t"})
    assert n == 1 and saved == [{"id": "a", "session_key": "new-uid"}]
    assert sessions._rebind_campaigns({"hhuid": "new-uid"}, {"hhuid": "new-uid"}) == 0


@pytest.mark.parametrize("text, skip", [
    ("Дмитрий, здравствуйте! Большое спасибо за интерес к нашей компании! К сожалению, сейчас мы не готовы "
     "пригласить вас на следующий этап. Ценим ваше внимание и будем рады взаимодействию в будущем.", True),
    ("Спасибо за интерес к компании! Мы ценим ваше желание работать с нами, но уже закрыли позицию. "
     "Возможно, скоро снова появится подходящая для вас позиция. Успехов!", True),
    ("Спасибо за отклик! Мы с вами свяжемся.", True),
    ("Спасибо за отклик! Готовы ли вы выйти в офис?", False),
    ("Когда вам удобно созвониться?", False),
])
def test_no_reply_filter(text, skip):
    from app.manager import BotManager
    assert BotManager._msg_needs_no_reply(None, text) is skip


def test_poll_captcha(tmp_path, monkeypatch):
    poll_notifications, _ = _scripts()
    monkeypatch.setattr(notify, "NOTIFY_DIR", tmp_path)
    monkeypatch.setattr(poll_notifications, "NOTIFY_DIR", tmp_path)
    notify.notify_captcha("acc", "https://hh.ru/account/captcha?state=x&backurl=https%3A%2F%2Fhh.ru%2F")
    text = poll_notifications.poll()
    assert "капчу" in text and "account/captcha?state=x" in text
    assert "Ошибки откликов" not in text


@pytest.mark.parametrize("status, body, want", [
    (200, '{"success": "true", "response_label": "req-letter-no-test", "responseStatus": '
          '{"alreadyApplied": false, "shortVacancy": {"name": "SRE", "company": {"name": "Acme"}}}}', "sent"),
    (200, '{"success": "false", "error": "test-required"}', "test"),
    (200, '{"responseStatus": {"alreadyApplied": true}}', "already"),
    (200, '{"error": "negotiations-limit-exceeded"}', "limit"),
    (403, '{"errors": [{"value": "captcha_required"}]}', "captcha"),
    (200, '<html>что-то другое</html>', "error"),
])
def test_web_apply_result(monkeypatch, status, body, want):
    import asyncio
    class R:
        status_code, text = status, body
    monkeypatch.setattr(hh_apply.requests, "post", lambda *a, **kw: R())

    async def _letter(acc, vid):
        return "письмо"
    monkeypatch.setattr(hh_apply, "_resolve_letter", _letter)
    acc = {"name": "t", "resume_hash": "r", "cookies": {"_xsrf": "x"}}
    res, info = asyncio.run(hh_apply.send_response_async(acc, "1"))
    assert res == want
    if want == "sent":
        assert info["title"] == "SRE" and info["company"] == "Acme"


def test_poll_skips_drafts_when_reply_bot_alive(tmp_path, monkeypatch):
    import time
    poll_notifications, _ = _scripts()
    nd = tmp_path / "notifications"
    nd.mkdir()
    monkeypatch.setattr(notify, "NOTIFY_DIR", nd)
    monkeypatch.setattr(poll_notifications, "NOTIFY_DIR", nd)
    notify.notify_chat("Acme", "SRE", "Когда созвонимся?", {"category": "unknown", "reply": "Завтра"},
                       sent=False, draft_id="acc:1")
    notify.notify_chat("Beta", "DevOps", "Спасибо!", {"category": "thanks", "reply": "И вам"}, sent=True)
    (tmp_path / "reply_bot_state.json").write_text(json.dumps({"alive_at": time.time()}))
    text = poll_notifications.poll()
    assert "Acme" not in text and "Beta" in text


def test_reply_bot_card():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import hh_reply_bot as b
    n = {"company": "A&B", "title": "SRE", "employer_msg": "Когда <удобно>?", "reply": "Завтра",
         "variants": ["Чт"], "reason": "нет окон"}
    t = b.card_text(n)
    assert "A&amp;B" in t and "&lt;удобно&gt;" in t and "<b>1.</b> Завтра" in t and "<b>2.</b> Чт" in t
    kb = b.card_keyboard("7", 2)["inline_keyboard"]
    assert [x["callback_data"] for x in kb[0]] == ["pick:7:1", "pick:7:2"]
    assert kb[1][0]["callback_data"] == "own:7" and kb[1][1]["callback_data"] == "skip:7"


def test_reply_bot_flow(tmp_path, monkeypatch):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import hh_reply_bot as b
    nd = tmp_path / "notifications"
    nd.mkdir()
    monkeypatch.setattr(b, "NOTIFY_DIR", nd)
    monkeypatch.setattr(b, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(notify, "NOTIFY_DIR", nd)
    notify.notify_chat("Acme", "SRE", "Когда созвонимся?", {"category": "unknown", "reply": "Завтра в 12",
                       "variants": ["Чт после 15"]}, sent=False, draft_id="acc:1")
    calls, sent = [], []

    class FakeTG:
        def call(self, method, **p):
            calls.append((method, p))
            return {"message_id": 100 + len(calls)}

    def fake_api(method, path, body=None):
        if path == "/api/llm/pending":
            return {"pending": [{"draft_id": "acc:1"}]}
        if path.endswith("/edit"):
            sent.append(body["text"])
            return {"ok": True}
        if path.endswith("/send"):
            return {"sent": 1}
        return {"removed": 1}
    monkeypatch.setattr(b, "api", fake_api)
    tg, st = FakeTG(), b.load_state()
    b.new_cards(tg, 1, st)
    assert calls[0][0] == "sendMessage" and "Завтра в 12" in calls[0][1]["text"]
    b.new_cards(tg, 1, st)
    assert len([c for c in calls if c[0] == "sendMessage"]) == 1  # повторно не шлёт
    b.on_callback(tg, 1, st, {"id": "q", "data": "pick:1:2"})
    assert "Отправить вариант 2?" in calls[-2][1]["text"] and sent == []
    b.on_callback(tg, 1, st, {"id": "q", "data": "send:1"})
    assert sent == ["Чт после 15"] and st["cards"]["1"]["status"] == "sent"
    b.on_callback(tg, 1, st, {"id": "q", "data": "send:1"})
    assert sent == ["Чт после 15"]  # закрытую карточку второй раз не отправить


def test_hh_proxy_routing(monkeypatch):
    from app import hh_transport as t
    monkeypatch.delenv("HH_PROXY", raising=False)
    assert t.proxy_alive() is True
    monkeypatch.setenv("HH_PROXY", "socks5h://127.0.0.1:9")  # порт 9 никто не слушает
    assert t.proxy_alive(timeout=0.5) is False
    seen = {}

    class Resp:
        cookies = {}
    monkeypatch.setattr(t.cffi, "request", lambda m, u, **kw: seen.update(kw) or Resp())
    orig = t.requests.Session.request
    try:
        t.install()
        t.requests.get("https://hh.ru/search/vacancy")
        assert seen["proxies"] == {"http": "socks5h://127.0.0.1:9", "https": "socks5h://127.0.0.1:9"}
    finally:
        t.requests.Session.request = orig


def test_keep_antibot_cookies():
    from app.routes.accounts import _keep_cookie
    for name in ("hhtoken", "_xsrf", "__ddg1_", "__ddg10_", "gsscgib-w-hh", "cfidsgib-w-hh", "__zzatgib-w-hh"):
        assert _keep_cookie(name), name
    for name in ("_ym_uid", "tmr_lvid", "filters77161675", "device_breakpoint"):
        assert not _keep_cookie(name), name
