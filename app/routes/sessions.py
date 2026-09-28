"""
Browser session routes (temporary accounts added via cookie paste).
"""

import asyncio
import re

import requests
from fastapi import APIRouter, Request

from app.config import accounts_data
from app.storage import save_browser_sessions
from app.hh_resume import parse_hh_lux_ssr, _hh_ssr_str
from app.instances import bot

from app.routes.accounts import _parse_cookies_str, _AUTH_COOKIE_KEYS


router = APIRouter()


def _validate_and_profile(raw_cookie_line: str) -> dict:
    """
    Синхронно проверяет сессию и вытаскивает профиль из SSR.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://hh.ru/",
        "Cookie": raw_cookie_line,
    }
    try:
        r = requests.get(
            "https://hh.ru/applicant/resumes",
            headers=headers,
            verify=False,
            timeout=15,
            allow_redirects=True,
        )
    except Exception as e:
        return {"ok": False, "error": f"Ошибка сети: {e}"}

    if r.status_code != 200:
        hint = " — возможно, сессия устарела или нужно войти заново" if r.status_code in (401, 403) else ""
        return {"ok": False, "error": f"Сессия невалидна: HTTP {r.status_code}{hint}"}

    ssr = parse_hh_lux_ssr(r.text)

    name = ""
    for path in [
        lambda s: f"{s.get('account',{}).get('firstName','')} {s.get('account',{}).get('lastName','')}".strip(),
        lambda s: f"{s.get('hhidAccount',{}).get('firstName','')} {s.get('hhidAccount',{}).get('lastName','')}".strip(),
        lambda s: s.get("currentUser", {}).get("fullName", ""),
    ]:
        try:
            v = path(ssr)
            if v:
                name = v
                break
        except Exception:
            pass

    all_resumes = []
    for res in ssr.get("applicantResumes", []):
        h = (
            res.get("_attributes", {}).get("hash", "") or
            res.get("resume", {}).get("hash", "") or ""
        )
        title = (
            res.get("_attributes", {}).get("title", "") or
            res.get("title", "") or
            res.get("resume", {}).get("title", "") or ""
        )
        if h:
            all_resumes.append({"hash": h, "title": title or "Резюме"})

    if not all_resumes:
        # hh перенаправляет /applicant/resumes на /applicant/profile/me, где списка резюме
        # в SSR нет: берём хеши из ссылок, название — со страницы самого резюме
        for h in dict.fromkeys(re.findall(r"/resume/([0-9a-f]{38})", r.text)):
            try:
                rr = requests.get(f"https://hh.ru/resume/{h}", headers=headers, timeout=15)
                res = parse_hh_lux_ssr(rr.text)
                res = res.get("applicantResume") or res.get("resume") or {}
                title = _hh_ssr_str(res.get("title"))
            except Exception:
                title = ""
            all_resumes.append({"hash": h, "title": title or "Резюме"})

    latest = ssr.get("latestResumeHash", "")
    if latest:
        resume_hash = latest
        if not any(r["hash"] == latest for r in all_resumes):
            all_resumes.insert(0, {"hash": latest, "title": "Резюме"})
    elif all_resumes:
        resume_hash = all_resumes[0]["hash"]
    else:
        resume_hash = ""

    return {"ok": True, "name": name or "Браузер", "resume_hash": resume_hash, "all_resumes": all_resumes}


@router.get("/api/sessions")
async def api_sessions():
    """Список браузерных сессий без cookies."""
    base_idx = len(bot.account_states)
    return [
        {
            "idx": base_idx + i,
            "name": s.get("name", f"Браузер #{i+1}"),
            "short": s.get("short", ""),
            "resume_hash": s.get("resume_hash", ""),
            "all_resumes": s.get("all_resumes", []),
            "letter": s.get("letter", ""),
            "temp": True,
            "bot_active": s.get("bot_active", False),
        }
        for i, s in enumerate(bot.temp_sessions)
    ]


# Стабильные идентификаторы HH-пользователя в куках (один человек = один аккаунт)
_HH_UID_KEYS = ("hhuid", "crypted_hhuid", "iap.uid")


def _same_hh_account(new_cookies: dict, new_all_resumes: list, ts: dict) -> bool:
    """Та же HH-учётка? По стабильному uid из куки ИЛИ по пересечению списка резюме
    (резюме принадлежат ровно одному аккаунту)."""
    ts_cookies = ts.get("cookies", {}) or {}
    for k in _HH_UID_KEYS:
        nv = new_cookies.get(k)
        if nv and ts_cookies.get(k) == nv:
            return True
    new_hashes = {r.get("hash") for r in (new_all_resumes or []) if r.get("hash")}
    ts_hashes = {r.get("hash") for r in (ts.get("all_resumes") or []) if r.get("hash")}
    if ts.get("resume_hash"):
        ts_hashes.add(ts["resume_hash"])
    return bool(new_hashes & ts_hashes)


@router.post("/api/session/add")
async def api_session_add(body: dict):
    """Добавить временную сессию из браузера по строке cookies."""
    cookie_str = body.get("cookies", "").strip()
    if not cookie_str:
        return {"status": "error", "message": "Строка cookies пустая"}

    cookies, raw_cookie_line = _parse_cookies_str(cookie_str)

    if not cookies or not raw_cookie_line:
        return {"status": "error", "message": "Не удалось распознать cookies — вставьте cURL целиком или строку Cookie: ..."}
    if "hhtoken" not in cookies:
        return {"status": "error", "message": "Не найден hhtoken — вставьте полный cURL (правая кнопка на запросе → Copy as cURL)"}
    if "_xsrf" not in cookies:
        return {"status": "error", "message": "Не найден _xsrf"}

    loop = asyncio.get_event_loop()
    profile = await loop.run_in_executor(None, _validate_and_profile, raw_cookie_line)

    if not profile["ok"]:
        return {"status": "error", "message": profile["error"]}

    display_name = body.get("name", "").strip() or profile["name"]
    all_resumes = profile.get("all_resumes", [])

    selected_hash = body.get("resume_hash", "").strip()
    if selected_hash and any(r["hash"] == selected_hash for r in all_resumes):
        resume_hash = selected_hash
    else:
        resume_hash = profile["resume_hash"]

    letter = body.get("letter", "").strip()
    if not letter:
        for acc in accounts_data:
            if acc.get("resume_hash") == resume_hash:
                letter = acc.get("letter", "")
                break

    auth_cookies = {k: v for k, v in cookies.items() if k in _AUTH_COOKIE_KEYS}

    # Дедуп по HH-АККАУНТУ (не по резюме): один человек = одна сессия. Обновление
    # куки того же аккаунта обновляет существующую сессию, а не плодит дубликаты.
    for i, ts in enumerate(bot.temp_sessions):
        if _same_hh_account(auth_cookies, all_resumes, ts):
            ts["name"] = display_name
            ts["short"] = display_name.split()[0] if display_name.split() else display_name
            ts["all_resumes"] = all_resumes
            ts["cookies"] = auth_cookies
            # resume_hash меняем только если пользователь явно выбрал другое резюме;
            # иначе сохраняем текущее резюме сессии (его кампания).
            if selected_hash and any(r["hash"] == selected_hash for r in all_resumes):
                ts["resume_hash"] = selected_hash
            elif not ts.get("resume_hash"):
                ts["resume_hash"] = resume_hash
            if letter:
                ts["letter"] = letter
            if i in bot.temp_states:
                bot.temp_states[i].acc["cookies"] = auth_cookies
                bot.temp_states[i].acc["all_resumes"] = all_resumes
                if letter:
                    bot.temp_states[i].acc["letter"] = letter
            save_browser_sessions(bot.temp_sessions)
            return {
                "status": "ok",
                "message": f"Сессия обновлена: {ts['name']}",
                "idx": len(bot.account_states) + i,
                "name": ts["name"],
                "resume_hash": resume_hash,
            }

    idx_in_temp = len(bot.temp_sessions)
    temp_acc = {
        "name": f"{display_name}",
        "short": f"{display_name.split()[0] if display_name.split() else display_name}",
        "color": "yellow",
        "resume_hash": resume_hash,
        "all_resumes": all_resumes,
        "letter": letter,
        "cookies": auth_cookies,
        "urls": [],
    }
    bot.temp_sessions.append(temp_acc)
    save_browser_sessions(bot.temp_sessions)

    return {
        "status": "ok",
        "message": f"Сессия добавлена: {temp_acc['name']}",
        "idx": len(bot.account_states) + idx_in_temp,
        "name": temp_acc["name"],
        "resume_hash": resume_hash,
    }


@router.patch("/api/session/{idx}")
async def api_session_patch(idx: int, body: dict):
    temp_idx = idx - len(bot.account_states)
    if 0 <= temp_idx < len(bot.temp_sessions):
        ts = bot.temp_sessions[temp_idx]
        
        # Allowed fields to update directly
        fields = [
            "letter", "resume_hash", "resume_hash_2", "search_query", "region", "remote_only",
            "salary_from", "experience", "daily_limit", "daily_limit_max", "total_limit",
            "industry", "schedule", "employment", "stop_words", "limit_24_7",
            "salary_only", "accredited_it", "strict_title_match", "ai_cover_letter",
            "ai_answers", "gender", "phone", "tg",
            "batch_responses", "response_delay", "skip_inconsistent", "llm_cover_letter_prompt"
        ]
        
        for f in fields:
            if f in body:
                ts[f] = body[f]
                if temp_idx in bot.temp_states:
                    bot.temp_states[temp_idx].acc[f] = body[f]
                    
        if "resume_hash" in body and temp_idx in bot.temp_states:
            bot.temp_states[temp_idx].acc["urls"] = bot._build_session_urls(ts)
            
        if "search_query" in body and temp_idx in bot.temp_states:
            bot.temp_states[temp_idx].acc["urls"] = bot._build_session_urls(ts)

        save_browser_sessions(bot.temp_sessions)
        return {"status": "ok"}
    return {"status": "error", "message": "Не найдено"}

@router.post("/api/session/{idx}/activate")
async def api_session_activate(idx: int):
    """Запустить браузерную сессию как бот-аккаунт."""
    temp_idx = idx - len(bot.account_states)
    if temp_idx < 0 or temp_idx >= len(bot.temp_sessions):
        return {"status": "error", "message": "Не найдено"}
    ts = bot.temp_sessions[temp_idx]
    if not ts.get("resume_hash"):
        return {"status": "error", "message": "Сначала найдите резюме (нажмите \U0001f504)"}
    ok = bot.activate_session(temp_idx)
    if ok:
        return {"status": "ok", "message": f"Сессия {ts['name']} запущена как бот"}
    return {"status": "error", "message": "Не удалось запустить"}


@router.post("/api/session/{idx}/refresh")
async def api_session_refresh(idx: int):
    """Перепрофилировать сессию: обновить имя и resume_hash из HH."""
    temp_idx = idx - len(bot.account_states)
    if temp_idx < 0 or temp_idx >= len(bot.temp_sessions):
        return {"status": "error", "message": "Не найдено"}
    ts = bot.temp_sessions[temp_idx]
    raw_line = ts.get("_raw_cookie_line", "") or "; ".join(f"{k}={v}" for k, v in ts.get("cookies", {}).items())
    loop = asyncio.get_event_loop()
    profile = await loop.run_in_executor(None, _validate_and_profile, raw_line)
    if not profile["ok"]:
        return {"status": "error", "message": profile.get("error", "Ошибка")}
    if profile["resume_hash"]:
        bot.temp_sessions[temp_idx]["resume_hash"] = profile["resume_hash"]
    if profile.get("all_resumes"):
        bot.temp_sessions[temp_idx]["all_resumes"] = profile["all_resumes"]
    if profile["name"] and profile["name"] != "Браузер":
        old_name = ts.get("name", "")
        suffix = ""
        bot.temp_sessions[temp_idx]["name"] = profile["name"] + suffix
    save_browser_sessions(bot.temp_sessions)
    return {"status": "ok", "resume_hash": profile["resume_hash"], "name": profile["name"]}


@router.delete("/api/session/{idx}")
async def api_session_delete(idx: int):
    temp_idx = idx - len(bot.account_states)
    if 0 <= temp_idx < len(bot.temp_sessions):
        removed = bot.temp_sessions.pop(temp_idx)
        if temp_idx in bot.temp_states:
            bot.temp_states[temp_idx]._deleted = True
        new_temp_states = {}
        for old_i, state in bot.temp_states.items():
            if old_i == temp_idx:
                continue
            new_i = old_i - 1 if old_i > temp_idx else old_i
            new_temp_states[new_i] = state
        bot.temp_states = new_temp_states
        save_browser_sessions(bot.temp_sessions)
        return {"status": "ok", "message": f"Сессия удалена: {removed.get('name')}"}
    return {"status": "error", "message": "Не найдено"}


@router.post("/api/session/{idx}/profile")
async def api_session_profile(idx: int, request: Request):
    """Обновить профиль браузерной сессии (name, short, color, resume_hash)."""
    temp_idx = idx - len(bot.account_states)
    if not (0 <= temp_idx < len(bot.temp_sessions)):
        return {"ok": False, "error": "Сессия не найдена"}
    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "error": "bad json"}
    ts = bot.temp_sessions[temp_idx]
    for field in ("name", "short", "color", "resume_hash"):
        if field in body and isinstance(body[field], str) and body[field].strip():
            ts[field] = body[field].strip()
    if temp_idx in bot.temp_states:
        state = bot.temp_states[temp_idx]
        state.name = ts.get("name", state.name)
        state.short = ts.get("short", state.short)
        state.color = ts.get("color", state.color)
        state.acc.update({k: ts[k] for k in ("name", "short", "color", "resume_hash") if k in ts})
    save_browser_sessions(bot.temp_sessions)
    return {"ok": True}
