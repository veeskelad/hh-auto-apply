"""e2e по HTTP API и WebSocket дашборда на изолированном стенде (без hh.ru и нейросетей)."""
import time


def test_index_served(api):
    html = api.get("/")
    assert "<html" in html and "/static/js/" in html


def test_snapshot_has_account(api):
    snap = api.snapshot()
    names = [a.get("name") for a in snap.get("accounts", [])]
    assert "Тест Тестов" in names


def test_history_endpoints(api):
    applied = api.get("/api/applied")
    assert len(applied) == 12
    assert {"title", "company"} <= set(applied[0])
    tests = api.get("/api/tests")
    assert any("Python Developer" in str(t) for t in (tests if isinstance(tests, list) else tests.values()))
    assert api.get("/api/interviews?limit=2000") is not None
    assert api.get("/api/vacancies") is not None


def test_campaign_crud(api):
    before = {c["id"] for c in api.get("/api/campaigns")["campaigns"]}
    created = api.post("/api/campaigns", {"name": "e2e-new", "account_idx": 0,
                                         "search_query": "Go Developer", "daily_limit": 5})
    assert created["ok"]
    cid = created["campaign"]["id"]
    assert cid not in before

    api.post(f"/api/campaigns/{cid}", {"name": "e2e-renamed", "daily_limit": 7})
    camp = next(c for c in api.get("/api/campaigns")["campaigns"] if c["id"] == cid)
    assert camp["name"] == "e2e-renamed" and camp["daily_limit"] == 7

    assert api.delete(f"/api/campaigns/{cid}")["ok"]
    assert cid not in {c["id"] for c in api.get("/api/campaigns")["campaigns"]}


def test_campaign_applications(api):
    apps = api.get("/api/campaigns/e2ecamp1/applications")["applications"]
    assert len(apps) == 12


def test_settings_roundtrip(api):
    assert api.post("/api/settings", {"key": "response_delay", "value": 3})["ok"]
    assert api.get("/api/raw/config")["response_delay"] == 3
    # флаги нейросети живут не в /api/settings, а в /api/llm_config
    assert not api.post("/api/settings", {"key": "llm_auto_send", "value": False})["ok"]
    assert api.post("/api/llm_config", {"enabled": True, "auto_send": False})["ok"]
    cfg = api.snapshot()["config"]
    assert cfg["llm_enabled"] is True and cfg["llm_auto_send"] is False


def test_llm_profiles_roundtrip(api):
    profiles = [
        {"name": "Claude Code", "base_url": "claude-cli", "model": "sonnet", "api_key": "cli", "enabled": False},
        {"name": "Codex", "base_url": "codex-cli", "model": "", "api_key": "cli", "enabled": False},
    ]
    assert api.post("/api/llm_profiles", {"mode": "fallback", "profiles": profiles})["ok"]
    snap = api.snapshot()
    shown = [p["base_url"] for p in snap.get("config", {}).get("llm_profiles", [])]
    assert shown[:2] == ["claude-cli", "codex-cli"]


def test_campaign_start_stop_stays_offline(api):
    res = api.post("/api/campaigns/e2ecamp2/start", {"account_idx": 0})
    assert res.get("ok", True), res
    time.sleep(3)
    assert api.post("/api/campaigns/e2ecamp2/stop")["ok"]
    # всё, что стенд пытался достать снаружи, заблокировано и записано; сервер жив
    assert api.get("/api/status") is not None
    outside = [b for b in api.stand.blocked() if "hh.ru" not in b and "openrouter" not in b]
    assert not outside, outside


def test_empty_stand_requires_connection(empty_api):
    snap = empty_api.snapshot()
    assert not snap.get("accounts")
    assert empty_api.get("/api/campaigns")["campaigns"] == []


def test_session_add_explains_errors(api):
    # куки из cmd-формата Windows распознаются: дальше стенд не пускает в сеть, но это уже не ошибка разбора
    cmd = 'curl ^"https://hh.ru/x^" -b ^"hhtoken=A; _xsrf=B^"'
    r = api.post("/api/session/add", {"cookies": cmd})
    assert r["status"] == "error" and "Не удалось найти куки" not in r["message"], r
    r = api.post("/api/session/add", {"cookies": 'fetch("https://hh.ru/x", {"credentials": "include"});'})
    assert "fetch" in r["message"], r
    r = api.post("/api/session/add", {"cookies": "curl 'https://i.hh.ru/x.js' -b '_xsrf=B; other=1'"})
    assert "hhtoken" in r["message"], r
