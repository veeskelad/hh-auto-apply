"""
HH.ru negotiations: fetch stats, possible offers, auto-decline discards.
"""

import re
import json
import requests
from datetime import datetime, timedelta

from app.logging_utils import log_debug, _is_login_page
from app.hh_resume import parse_hh_lux_ssr


def fetch_hh_negotiations_stats(acc: dict, max_pages: int = 20) -> dict:
    """Получить статистику откликов с hh.ru (парсинг HTML)"""
    cookies = acc["cookies"]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://hh.ru/applicant/negotiations",
    }

    result = {
        "interview": 0,
        "recent_interview": 0,  # только последние 60 дней
        "viewed": 0,
        "not_viewed": 0,
        "discard": 0,
        "interviews_list": [],
        "neg_ids": [],
        "auth_error": False,
        "unread_by_employer": 0,  # count of negotiations where employer hasn't read our messages
    }
    cutoff = datetime.now().astimezone() - timedelta(days=60)

    # ── Шаг 1: точный счёт интервью через state=INTERVIEW фильтр ──────────────
    for page in range(max_pages):
        try:
            resp = requests.get(
                f"https://hh.ru/applicant/negotiations?filter=all&state=INTERVIEW&page={page}",
                cookies=cookies,
                headers=headers,
                timeout=15,
            )
            if resp.status_code != 200:
                if resp.status_code in (401, 403) or _is_login_page(resp.text):
                    result["auth_error"] = True
                break
            body = resp.text
            if _is_login_page(body):
                result["auth_error"] = True
                break

            # Extract negotiation IDs: HH renders items as buttons (no href links),
            # IDs are stored as chatId in the page's embedded JSON
            page_neg_ids = re.findall(r'"chatId"\s*:\s*(\d+)', body)
            for nid in page_neg_ids:
                if nid not in result["neg_ids"]:
                    result["neg_ids"].append(nid)

            parts = re.split(r'data-qa="negotiations-item"', body)
            if len(parts) <= 1:
                break

            items_on_page = 0
            for item in parts[1:]:
                items_on_page += 1
                item = re.sub(r'^[^>]*>', '', item, count=1)

                result["interview"] += 1

                # chatId per item
                neg_id_match = re.search(r'"chatId"\s*:\s*(\d+)', item)
                item_neg_id = neg_id_match.group(1) if neg_id_match else ""
                if item_neg_id and item_neg_id not in result["neg_ids"]:
                    result["neg_ids"].append(item_neg_id)

                # Извлекаем текст для списка
                clean = re.sub(r'<svg[\s\S]*?</svg>', '', item)
                clean = re.sub(r'<[^>]*>', ' ', clean, flags=re.DOTALL)
                clean = re.sub(r'\s+', ' ', clean).strip()
                text_body = re.sub(r'^(Собеседование|Приглашение|Интервью)\s*', '', clean)
                text_body = re.split(
                    r'\s+(?:сегодня\b|вчера\b|Был\s+онлайн|позавчера\b|\d+\s+\w+\s+назад)',
                    text_body
                )[0].strip()

                date_match = re.search(r'datetime="([^"]+)"', item)
                date_str = ""
                is_recent = True
                if date_match:
                    try:
                        dt = datetime.fromisoformat(date_match.group(1).replace("Z", "+00:00"))
                        date_str = dt.strftime("%d.%m")
                        is_recent = dt >= cutoff
                    except Exception:
                        date_str = date_match.group(1)[:10]
                if is_recent:
                    result["recent_interview"] += 1
                result["interviews_list"].append({
                    "text": text_body[:120],
                    "date": date_str,
                    "recent": is_recent,
                    "neg_id": item_neg_id,
                })

            if items_on_page == 0:
                break

        except Exception as e:
            log_debug(f"fetch_hh_negotiations_stats interviews page={page} error: {e}")
            break

    if result["auth_error"]:
        return result

    # ── Шаг 2: просмотры / отказы с общей страницы ────────────────────────────
    for page in range(max_pages):
        try:
            resp = requests.get(
                f"https://hh.ru/applicant/negotiations?page={page}",
                cookies=cookies,
                headers=headers,
                timeout=15,
            )
            if resp.status_code != 200:
                break
            body = resp.text
            if _is_login_page(body):
                break

            # On first page, extract SSR data for conversationUnreadByEmployerCount
            if page == 0:
                try:
                    ssr = parse_hh_lux_ssr(body)
                    topic_list = ssr.get("topicList", [])
                    if isinstance(topic_list, list):
                        for topic in topic_list:
                            if isinstance(topic, dict):
                                cnt = topic.get("conversationUnreadByEmployerCount", 0)
                                if isinstance(cnt, int) and cnt > 0:
                                    result["unread_by_employer"] += 1
                except Exception:
                    pass

            parts = re.split(r'data-qa="negotiations-item"', body)
            if len(parts) <= 1:
                break

            items_on_page = 0
            for item in parts[1:]:
                items_on_page += 1
                item = re.sub(r'^[^>]*>', '', item, count=1)
                clean = re.sub(r'<svg[\s\S]*?</svg>', '', item)
                clean = re.sub(r'<[^>]*>', ' ', clean, flags=re.DOTALL)
                clean = re.sub(r'\s+', ' ', clean).strip()
                first_word = clean.split(' ')[0] if clean else ''

                if first_word in ('Отказ', 'Отклонено', 'Отклонён'):
                    result["discard"] += 1
                elif clean.startswith('Просмотрен'):
                    result["viewed"] += 1
                elif first_word not in ('Собеседование', 'Приглашение', 'Интервью'):
                    result["not_viewed"] += 1

            if items_on_page == 0:
                break

        except Exception as e:
            log_debug(f"fetch_hh_negotiations_stats general page={page} error: {e}")
            break

    return result


def _extract_topic_vacancy_id(topic: dict) -> str:
    """Достать ID вакансии из одного topic переговоров (несколько возможных мест)."""
    if not isinstance(topic, dict):
        return ""
    v = topic.get("vacancy", {})
    if isinstance(v, dict):
        for k in ("id", "vacancyId", "@id"):
            val = v.get(k)
            if val:
                return str(val)
    # Запасной вариант: ищем /vacancy/<id> или "vacancyId":<id> в сериализованном topic
    try:
        blob = json.dumps(topic, ensure_ascii=False)
    except Exception:
        blob = str(topic)
    m = re.search(r'/vacancy/(\d+)', blob) or re.search(r'"vacancyId"\s*:\s*"?(\d+)', blob)
    return m.group(1) if m else ""


def fetch_applied_vacancy_ids(acc: dict, max_pages: int = 30) -> set:
    """
    Собрать ID всех вакансий, на которые с этого аккаунта уже есть отклик на hh.ru
    (источник истины — список переговоров). Ловит и ручные отклики, сделанные
    вне этого инструмента. Возвращает set строковых vacancy_id.
    """
    cookies = acc.get("cookies", {})
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://hh.ru/applicant/negotiations",
    }
    vids: set = set()
    for page in range(max_pages):
        try:
            resp = requests.get(
                f"https://hh.ru/applicant/negotiations?page={page}",
                cookies=cookies, headers=headers, verify=False, timeout=15,
            )
            if resp.status_code != 200 or _is_login_page(resp.text):
                break
            ssr = parse_hh_lux_ssr(resp.text)
            topic_list = ssr.get("topicList")
            if not isinstance(topic_list, list):
                topic_list = ssr.get("applicantNegotiations", {}).get("topicList", [])
            if not topic_list:
                break
            page_found = 0
            for topic in topic_list:
                vid = _extract_topic_vacancy_id(topic)
                if vid:
                    vids.add(vid)
                    page_found += 1
            # Меньше полной страницы тем — дальше нет смысла листать
            if len(topic_list) < 10:
                break
        except Exception as e:
            log_debug(f"fetch_applied_vacancy_ids page={page} error: {e}")
            break
    return vids


def fetch_negotiation_status_map(acc: dict, max_pages: int = 15) -> dict:
    """
    {vacancy_id: статус} по реальным переговорам hh.ru через фильтры состояния.
    INTERVIEW → «Приглашение», DISCARD → «Отказ». Остальные отклики (не в карте)
    вызывающий код помечает «Отправлен».
    """
    cookies = acc.get("cookies", {})
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://hh.ru/applicant/negotiations",
    }
    status_map: dict = {}
    for state, label in (("DISCARD", "Отказ"), ("INTERVIEW", "Приглашение")):
        for page in range(max_pages):
            try:
                r = requests.get(
                    f"https://hh.ru/applicant/negotiations?state={state}&page={page}",
                    cookies=cookies, headers=headers, verify=False, timeout=15,
                )
                if r.status_code != 200 or _is_login_page(r.text):
                    break
                ssr = parse_hh_lux_ssr(r.text)
                topics = ssr.get("topicList")
                if not isinstance(topics, list):
                    topics = ssr.get("applicantNegotiations", {}).get("topicList", [])
                if not topics:
                    break
                for t in topics:
                    vid = _extract_topic_vacancy_id(t)
                    if vid:
                        status_map[vid] = label
                if len(topics) < 10:
                    break
            except Exception as e:
                log_debug(f"fetch_negotiation_status_map {state} p{page}: {e}")
                break
    return status_map


def fetch_hh_possible_offers(acc: dict) -> list:
    """Получить список компаний, готовых пригласить (JSON API)"""
    cookies = acc["cookies"]
    xsrf = cookies.get("_xsrf", "")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "X-XsrfToken": xsrf,
        "Accept": "application/json",
        "Referer": "https://hh.ru/applicant/negotiations",
    }
    try:
        resp = requests.get(
            "https://hh.ru/shards/applicant/negotiations/possible_job_offers",
            cookies=cookies,
            headers=headers,
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            offers = []
            for item in data if isinstance(data, list) else data.get("items", []):
                name = item.get("name", "")
                vacancy_names = [v.get("name", "") for v in item.get("vacancies", [])]
                offers.append({"name": name, "vacancyNames": vacancy_names})
            return offers
    except Exception as e:
        log_debug(f"fetch_hh_possible_offers error: {e}")
    return []


_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")


def _discard_topics(acc: dict) -> tuple:
    """Отклики с отказом работодателя: (topics, total) со страницы «Отказ»."""
    ck = acc.get("cookies", {})
    topics, total = [], None
    for page in range(10):
        r = requests.get("https://hh.ru/applicant/negotiations", params={"state": "DISCARD", "page": page},
                         headers={"User-Agent": _UA}, cookies=ck, timeout=40)
        if r.status_code != 200 or _is_login_page(r.text):
            raise RuntimeError(f"страница отказов: HTTP {r.status_code}")
        an = parse_hh_lux_ssr(r.text).get("applicantNegotiations", {})
        total = an.get("total") if total is None else total
        page_topics = an.get("topicList") or []
        topics += page_topics
        if not page_topics or page + 1 >= int(an.get("pageCount") or 1):
            break
    return topics, total or 0


def trash_discards(acc: dict, limit: int = 50, pause: tuple = (2.0, 4.0)) -> dict:
    """Удалить отклики с отказом работодателя кнопкой hh «Удалить» (переезжают во вкладку «Удалённые»).

    Запрос как у сайта (записан 11.11.2026): POST /applicant/negotiations/trash, multipart
    topic, query=?state=DISCARD, substate=HIDE, заголовки X-Xsrftoken и X-GIB-* из кук Group-IB.
    Результат сверяется по счётчику «Отказ» до и после. → {"before", "deleted", "after", "failed"}
    """
    import random
    import time
    ck = acc.get("cookies", {})
    topics, before = _discard_topics(acc)
    hdr = {"User-Agent": _UA, "X-Xsrftoken": ck.get("_xsrf", ""), "X-Requested-With": "XMLHttpRequest",
           "Accept": "application/json", "X-hhtmSource": "negotiation_list",
           "Referer": "https://hh.ru/applicant/negotiations?state=DISCARD",
           "X-GIB-FGSSCgib-w-hh": ck.get("fgsscgib-w-hh", ""), "X-GIB-GSSCgib-w-hh": ck.get("gsscgib-w-hh", "")}
    deleted, failed = 0, []
    for t in topics[:limit]:
        act = next((a for a in t.get("actions") or [] if a.get("name") == "delete" and a.get("href")), None)
        if not act or t.get("lastState") != "DISCARD":
            continue
        tid = str(t.get("id"))
        try:
            r = requests.post("https://hh.ru" + act["href"], headers=hdr, cookies=ck, timeout=30,
                              files={"topic": (None, tid), "query": (None, "?state=DISCARD"),
                                     "substate": (None, act.get("substate") or "HIDE")})
            if r.status_code == 200 and "isBot" not in r.text:
                deleted += 1
            else:
                failed.append(f"{t.get('vacancyId')}: HTTP {r.status_code}")
                if "isBot" in r.text:
                    break  # капча: дальше бесполезно
        except Exception as e:
            failed.append(f"{t.get('vacancyId')}: {str(e)[:80]}")
        time.sleep(random.uniform(*pause))
    _, after = _discard_topics(acc)
    log_debug(f"trash_discards: отказов было {before}, удалено {deleted}, стало {after}, ошибок {len(failed)}")
    return {"before": before, "deleted": deleted, "after": after, "failed": failed}


def auto_decline_discards(acc: dict) -> int:
    """Совместимость со старой кнопкой дашборда: удалить отказы, вернуть сколько удалено."""
    try:
        return trash_discards(acc)["deleted"]
    except Exception as e:
        log_debug(f"auto_decline_discards error: {e}")
        return 0
