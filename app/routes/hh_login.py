"""
HH.ru login via phone/email + password.
Имитирует браузерный логин, забирает cookies и создаёт аккаунт.
"""
import json
import re
import time

import requests
from fastapi import APIRouter

from app.config import accounts_data, save_accounts, CONFIG
from app.logging_utils import log_debug
from app.hh_resume import parse_hh_lux_ssr

router = APIRouter()

_UA = "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.113 Mobile Safari/537.36"


def _hh_login(login: str, password: str) -> dict:
    """
    Пытается залогиниться на HH.ru.
    Возвращает {"status": "ok"/"error", "cookies": {...}, "message": "..."}
    """
    sess = requests.Session()
    sess.headers.update({"User-Agent": _UA})

    try:
        # Step 1: GET login page → _xsrf token
        r1 = sess.get("https://hh.ru/account/login", timeout=20, allow_redirects=True)
        if r1.status_code != 200:
            return {"status": "error", "message": f"HH не отвечает: {r1.status_code}"}

        html = r1.text

        # Ищем _xsrf в HTML
        xsrf = ""
        m = re.search(r'name=["\']_xsrf["\'][^>]*value=["\']([^"\']+)', html)
        if m:
            xsrf = m.group(1)
        if not xsrf:
            # Пробуем из кук
            xsrf = sess.cookies.get("_xsrf", "")

        if not xsrf:
            return {"status": "error", "message": "Не удалось получить _xsrf токен (возможно, HH изменил форму входа)"}

        # Step 2: POST логин
        data = {
            "backUrl": "https://hh.ru/",
            "_xsrf": xsrf,
            "failUrl": "https://hh.ru/account/login?fail=true",
        }

        # Определяем тип логина (email или телефон)
        if "@" in login:
            data["email"] = login
            data["action"] = "emailLogin"
        else:
            # Телефон — убираем всё кроме цифр
            phone = re.sub(r"[^\d+]", "", login)
            data["phone"] = phone
            data["action"] = "phoneLogin"

        data["password"] = password

        r2 = sess.post(
            "https://hh.ru/account/login",
            data=data,
            timeout=20,
            allow_redirects=True,  # Позволяем HH редиректить — так узнаем успех
        )

        # Собираем все куки из сессии
        cookies = dict(sess.cookies.get_dict())

        # 🔍 РЕАЛЬНАЯ ПРОВЕРКА: пробуем загрузить профиль
        profile = {}
        try:
            r3 = sess.get("https://hh.ru/applicant/profile", timeout=15, allow_redirects=True)
            if r3.status_code == 200:
                # Ищем fullName — признак того, что мы реально авторизованы
                m_name = re.search(r'"fullName"\s*:\s*"([^"]+)"', r3.text)
                if m_name:
                    profile["name"] = m_name.group(1)
                else:
                    # Пробуем другой вариант — "full_name"
                    m_name2 = re.search(r'"full_name"\s*:\s*"([^"]+)"', r3.text)
                    if m_name2:
                        profile["name"] = m_name2.group(1)
        except:
            pass

        # Если имя не нашли — считаем что логин не удался
        if not profile.get("name"):
            # HH перекинул на страницу логина или ошибку
            if r2.status_code in (302, 303, 301) and "fail" in r2.headers.get("Location", ""):
                return {
                    "status": "error",
                    "message": "Неверный логин/пароль или требуется подтверждение (SMS/2FA). "
                               "Попробуй через cURL с компьютера.",
                }
            if "Войти" in r2.text[:2000] or "account/login" in r2.text[:2000]:
                return {"status": "error", "message": "Неверный логин или пароль"}
            return {"status": "error", "message": "Не удалось подтвердить вход — HH не вернул профиль"}

        # ✅ Успех! Имя есть — мы авторизованы
        raw_cookie_line = "; ".join(f"{k}={v}" for k, v in cookies.items())
        log_debug(f"HH login OK: {profile['name']} ({login[:4]}...)")

        return {
            "status": "ok",
            "cookies": cookies,
            "raw_cookie_line": raw_cookie_line,
            "profile": profile,
        }

    except requests.exceptions.Timeout:
        return {"status": "error", "message": "Таймаут при подключении к HH.ru"}
    except Exception as e:
        log_debug(f"HH login error: {e}")
        return {"status": "error", "message": f"Ошибка: {str(e)[:100]}"}


@router.post("/api/hh-login")
async def api_hh_login(body: dict):
    """Вход в HH.ru по логину/паролю."""
    login = (body.get("login") or "").strip()
    password = body.get("password") or ""

    if not login or not password:
        return {"status": "error", "message": "Введи логин (email или телефон) и пароль"}

    result = _hh_login(login, password)

    if result["status"] != "ok":
        return result

    cookies = result["cookies"]
    raw_line = result.get("raw_cookie_line", "")
    profile = result.get("profile", {})

    name = profile.get("name", login.split("@")[0] if "@" in login else login)
    # Создаём аккаунт — все поля, которые нужны AccountState
    acc = {
        "cookies": cookies,
        "hhtoken": cookies.get("hhtoken", ""),
        "name": name,
        "short": name.split()[0] if name.split() else name,
        "color": "yellow",
        "urls": [],
        "resume_hash": "",
        "enabled": True,
    }

    accounts_data.append(acc)
    save_accounts()

    # 🔍 Сканируем резюме на HH
    resume_info = {}
    try:
        r_resumes = requests.get(
            "https://hh.ru/applicant/resumes",
            headers={"User-Agent": _UA, "Cookie": raw_line},
            timeout=15,
            allow_redirects=True,
        )
        if r_resumes.status_code == 200:
            ssr = parse_hh_lux_ssr(r_resumes.text)
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

            latest = ssr.get("latestResumeHash", "")
            if latest and not any(r["hash"] == latest for r in all_resumes):
                all_resumes.insert(0, {"hash": latest, "title": "Резюме"})

            resume_info["resume_hash"] = latest or (all_resumes[0]["hash"] if all_resumes else "")
            resume_info["all_resumes"] = all_resumes

            # Обновляем аккаунт
            acc["resume_hash"] = resume_info["resume_hash"]
            save_accounts()
    except Exception as e:
        log_debug(f"Resume scan error: {e}")

    from app.instances import bot
    if bot:
        try:
            bot.add_account(acc, idx=len(accounts_data) - 1)
        except:
            pass

    # Сообщение пользователю
    msg = f"✅ Успешный вход! Аккаунт «{acc['name']}» добавлен."
    if resume_info.get("resume_hash"):
        count = len(resume_info.get("all_resumes", []))
        msg += f"\n📄 Найдено резюме: {count}"
    elif acc["resume_hash"]:
        msg += "\n📄 Резюме обнаружено"

    return {
        "status": "ok",
        "message": msg,
        "account_name": acc["name"],
        "resume_hash": acc.get("resume_hash", ""),
        "resumes": resume_info.get("all_resumes", []),
    }
