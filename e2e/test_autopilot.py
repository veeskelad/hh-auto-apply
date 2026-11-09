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
