"""
BotManager — core bot logic with per-account worker threads.
"""

import asyncio
import aiohttp
import ssl
import re
import random
from datetime import datetime, timedelta
from collections import deque
import time
import threading
import requests

from app.logging_utils import log_debug, _is_login_page

from app.config import (
    CONFIG, accounts_data,
    save_config, load_config, save_accounts, load_accounts,
    _url_entry, _url_pages_map,
    DEFAULT_LLM_SKIP_PATTERNS, LLM_QUESTION_MARKERS,
)

from app.storage import (
    _load_cache, _cache_applied, _cache_lock,
    add_applied, is_applied, add_test_vacancy, is_test, get_stats,
    load_browser_sessions, save_browser_sessions,
    upsert_interview, get_no_chat_neg_ids,
    get_campaign, set_campaign_stats, CAMPAIGN_PARAM_KEYS,
)

from app.oauth import (
    _oauth_apply,
)

from app.hh_api import (
    get_headers, parse_ids, parse_vacancy_meta, parse_salaries,
    parse_work_schedules, extract_search_query,
)

from app.llm import generate_llm_reply
from app.notify import notify_interview, notify_response, notify_error

from app.hh_apply import (
    _resolve_letter,
    send_response_async, fill_and_submit_questionnaire,
    _check_vacancy_before_apply, check_limit, touch_resume,
)

from app.hh_chat import (
    _fetch_chat_list, _build_thread_from_chat_item, _check_chat_locked,
    _fetch_chat_history,
    send_negotiation_message,
)

from app.hh_resume import (
    fetch_all_resume_texts, fetch_resume_stats, fetch_resume_view_history,
    _resume_cache, _RESUME_CACHE_TTL,
)

from app.hh_negotiations import (
    fetch_hh_negotiations_stats, fetch_hh_possible_offers,
    fetch_applied_vacancy_ids,
)

from app.state import AccountState


# -- Async page fetcher (used only by BotManager) --

async def fetch_page(session, url, sem):
    async with sem:
        try:
            await asyncio.sleep(0.05)
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                html = await r.text()
                log_debug(f"✅ URL: {url} | Статус: {r.status} | Размер: {len(html)}")
                return html
        except Exception as e:
            log_debug(f"❌ ОШИБКА при загрузке: {url} | {type(e).__name__}: {e}")
            return ""


# ============================================================
# Хелперы per-campaign настроек
# ============================================================

def _as_int(v) -> int:
    """Безопасно привести значение к int (строка из формы и т.п.), иначе 0."""
    try:
        return int(v)
    except (ValueError, TypeError):
        return 0


def _split_csv(s) -> list:
    """Строку 'a, b; c' или список → список непустых слов."""
    if not s:
        return []
    if isinstance(s, list):
        return [str(x).strip() for x in s if str(x).strip()]
    return [w.strip() for w in str(s).replace(';', ',').split(',') if w.strip()]


# Поля настройки кампании — отдаются в снапшоте для pre-fill единой формы
_CAMPAIGN_FIELDS = [
    "resume_hash", "resume_hash_2", "search_query", "region", "remote_only",
    "salary_from", "experience", "daily_limit_max", "total_limit",
    "industry", "schedule", "employment", "stop_words", "limit_24_7",
    "salary_only", "accredited_it", "strict_title_match", "ai_cover_letter",
    "ai_answers", "gender", "phone", "tg",
    "batch_responses", "response_delay", "skip_inconsistent", "llm_cover_letter_prompt",
]


def _campaign_snapshot(src: dict) -> dict:
    """Извлечь поля настройки кампании из acc/ts для снапшота (pre-fill формы)."""
    return {f: src.get(f) for f in _CAMPAIGN_FIELDS}


# ============================================================
# BOT MANAGER
# ============================================================

class BotManager:
    def __init__(self):
        self.paused = False
        self._stop_event = threading.Event()
        self.account_states: list[AccountState] = []
        self.activity_log: deque = deque(maxlen=100)
        self.recent_responses: deque = deque(maxlen=100)
        self.llm_log: deque = deque(maxlen=200)    # LLM reply history
        self.vacancy_queues: dict = {}
        self._start_time: datetime = None
        self.temp_sessions: list = load_browser_sessions()  # сессии из браузера (персистентные)
        self._migrate_campaigns_pending = True  # сид кампаний из сессий при первом обращении
        self.temp_states: dict[int, AccountState] = {}  # temp_idx → AccountState для активных сессий
        # Global dedup across all accounts: {(cur_pid, neg_id, last_msg_id)}
        # Prevents double-sends when multiple accounts share the same HH user (same cur_pid)
        self._llm_sent_global: set = set()
        self._llm_sent_lock = threading.Lock()
        # HR contacts collected from contactInfo during pre-checks
        self.hr_contacts: list = []  # capped at 500
        self._hr_contacts_lock = threading.Lock()
        # Очередь черновиков ответов на подтверждение (runtime, не персистится).
        # draft_id → {draft_id, neg_id, topic_id, employer, vacancy_title,
        #             employer_msg, draft, ts, _state, _key, _global_key, _cur_pid}
        self.llm_pending: dict = {}
        self._llm_pending_lock = threading.Lock()

    def _build_session_urls(self, ts: dict) -> list[str]:
        from app.hh_api import build_search_url
        resume_hash = ts.get("resume_hash", "")
        # If campaign has search query, use the builder.
        # Несколько запросов через запятую → отдельный URL на каждый
        # ("инженер, engineer" ищет и по-русски, и по-английски).
        raw_query = (ts.get("search_query") or "").strip()
        if raw_query:
            terms = [q.strip() for q in raw_query.split(",") if q.strip()]
            if len(terms) <= 1:
                return [build_search_url(ts)]
            return [build_search_url(ts, query=term) for term in terms]
            
        # Fallback to resume based URL
        resume_url = f"https://hh.ru/search/vacancy?resume={resume_hash}&order_by=publication_time&items_on_page=20"
        urls = [resume_url]
        for item in CONFIG.url_pool:
            entry = _url_entry(item)
            if entry["url"] and "resume=" not in entry["url"]:
                urls.append(entry["url"])
        return urls

    def activate_session(self, temp_idx: int) -> bool:
        """Запустить браузерную сессию как полноценный бот-аккаунт."""
        if temp_idx < 0 or temp_idx >= len(self.temp_sessions):
            return False
        ts = self.temp_sessions[temp_idx]
        if not ts.get("resume_hash"):
            return False
        if temp_idx in self.temp_states:
            return True  # уже запущен
        # Include all campaign fields from ts
        acc = dict(ts)
        acc.update({
            "name": ts["name"],
            "short": ts.get("short", ts["name"]),
            "color": "yellow",
            "resume_hash": ts["resume_hash"],
            "letter": ts.get("letter", ""),
            "cookies": ts.get("cookies", {}),
            "urls": self._build_session_urls(ts),
        })
        state = AccountState(acc)
        self.temp_states[temp_idx] = state
        ts["bot_active"] = True
        save_browser_sessions(self.temp_sessions)
        log_debug(f"activate_session({temp_idx}): starting threads...")
        t1 = threading.Thread(target=self._run_account_worker, args=(900 + temp_idx, state), daemon=True, name=f"worker-{temp_idx}")
        t2 = threading.Thread(target=self._fetch_hh_stats_worker, args=(900 + temp_idx, state), daemon=True, name=f"stats-{temp_idx}")
        t1.start()
        t2.start()
        log_debug(f"activate_session({temp_idx}): threads started t1={t1.is_alive()} t2={t2.is_alive()}")
        self._add_log(state.short, "yellow", f"Сессия {ts['name']} запущена как бот", "success")
        return True

    def _get_apply_acc(self, idx: int) -> dict | None:
        """Вернуть acc dict для apply-эндпоинтов (обычный или временный аккаунт)"""
        if 0 <= idx < len(self.account_states):
            return dict(self.account_states[idx].acc)
        temp_idx = idx - len(self.account_states)
        if 0 <= temp_idx < len(self.temp_sessions):
            return dict(self.temp_sessions[temp_idx])
        return None

    def _get_apply_state(self, idx: int):
        """Вернуть AccountState или None для temp-сессий"""
        if 0 <= idx < len(self.account_states):
            return self.account_states[idx]
        return None

    def start(self):
        _load_cache()
        load_config()
        self._start_time = datetime.now()
        # Load recent responses from applied_vacancies into deque
        try:
            with _cache_lock:
                if _cache_applied:
                    all_items = []
                    for acc_name, vacancies in _cache_applied.items():
                        if isinstance(vacancies, dict):
                            for vid, info in vacancies.items():
                                if isinstance(info, dict):
                                    all_items.append({
                                        "id": vid, "title": info.get("title", ""),
                                        "company": info.get("company", ""),
                                        "time": (info.get("at", "") or "")[:16].replace("T", " "),
                                        "icon": "✅", "acc": acc_name,
                                    })
                    # Sort by time, take last 100
                    all_items.sort(key=lambda x: x.get("time", ""), reverse=True)
                    for item in all_items[:100]:
                        self.recent_responses.append(item)
                    log_debug(f"Loaded {len(self.recent_responses)} recent responses from cache")
        except Exception as e:
            log_debug(f"Failed to load recent responses: {e}")
        self.account_states = [AccountState(acc) for acc in accounts_data]
        for i, state in enumerate(self.account_states):
            t1 = threading.Thread(
                target=self._run_account_worker, args=(i, state), daemon=True
            )
            t2 = threading.Thread(
                target=self._fetch_hh_stats_worker, args=(i, state), daemon=True
            )
            t1.start()
            t2.start()
        # Авто-активация браузерных сессий, которые были запущены до перезапуска
        log_debug(f"start(): {len(self.temp_sessions)} temp sessions to check")
        for i, ts in enumerate(self.temp_sessions):
            log_debug(f"start(): session {i}: bot_active={ts.get('bot_active')}, resume_hash={bool(ts.get('resume_hash'))}")
            if ts.get("bot_active") and ts.get("resume_hash"):
                ts["paused"] = False  # Reset pause on startup
                try:
                    result = self.activate_session(i)
                    log_debug(f"start(): activate_session({i}) = {result}")
                except Exception as e:
                    log_debug(f"start(): activate_session({i}) ERROR: {e}")
        self._add_log("", "", "\U0001f680 Бот запущен", "success")

    def stop(self):
        self._stop_event.set()

    def toggle_pause(self):
        self.paused = not self.paused
        msg = "⏸️ Пауза" if self.paused else "▶️ Продолжение"
        level = "warning" if self.paused else "success"
        self._add_log("", "", msg, level)

    def toggle_account_pause(self, idx: int):
        state = None
        if 0 <= idx < len(self.account_states):
            state = self.account_states[idx]
        else:
            temp_idx = idx - len(self.account_states)
            state = self.temp_states.get(temp_idx)
        if state:
            state.paused = not state.paused
            if not state.paused:
                # Reset hard stop / limit so worker can continue
                state.hard_stopped = False
                state.limit_exceeded = False
                state.limit_reset_time = None
            msg = (
                f"⏸️ Аккаунт {state.short} приостановлен"
                if state.paused
                else f"▶️ Аккаунт {state.short} возобновлён"
            )
            self._add_log(state.short, state.color, msg, "warning" if state.paused else "success")

    def _resolve_state(self, idx: int):
        """AccountState по idx (постоянный аккаунт или активная temp-сессия), иначе None."""
        if 0 <= idx < len(self.account_states):
            return self.account_states[idx]
        temp_idx = idx - len(self.account_states)
        return self.temp_states.get(temp_idx)

    def arm_campaign(self, idx: int) -> dict:
        """Подтвердить и запустить кампанию: с этого момента воркер может слать отклики
        строго до total_limit. Для неактивной temp-сессии сначала активирует её."""
        state = self._resolve_state(idx)
        if state is None:
            # temp-сессия ещё не активирована как бот — активируем
            temp_idx = idx - len(self.account_states)
            if 0 <= temp_idx < len(self.temp_sessions):
                if not self.activate_session(temp_idx):
                    return {"ok": False, "error": "Не удалось активировать сессию (нет резюме?)"}
                state = self.temp_states.get(temp_idx)
        if state is None:
            return {"ok": False, "error": "Аккаунт не найден"}
        state.campaign_sent = 0
        state.paused = False
        state.hard_stopped = False
        state.limit_exceeded = False
        state.limit_reset_time = None
        state._needs_applied_sync = True  # перед сбором подтянуть уже-отклинутые с HH
        state.armed = True
        state.status = "idle"
        tl = int(state.acc.get("total_limit") or 0)
        state.status_detail = f"Кампания запущена (цель: {tl} откликов)" if tl else "Кампания запущена (без лимита)"
        self._add_log(state.short, state.color,
            f"▶ Кампания запущена" + (f" — цель {tl} откликов" if tl else " (без лимита)"), "success")
        return {"ok": True, "armed": True, "total_limit": tl, "campaign_sent": 0}

    def migrate_campaigns_from_sessions(self):
        """Если библиотека кампаний пуста — завести по одной кампании на сессию из её
        текущего конфига (чтобы существующая настройка пользователя не потерялась)."""
        from app.storage import list_campaigns, upsert_campaign
        try:
            if list_campaigns():
                return
            for ts in self.temp_sessions:
                if not ts.get("search_query"):
                    continue
                ck = ts.get("cookies", {}) or {}
                skey = next((ck.get(k) for k in ("hhuid", "crypted_hhuid", "iap.uid") if ck.get(k)), None)
                camp = {"name": ts.get("search_query") or "Кампания", "session_key": skey}
                for k in CAMPAIGN_PARAM_KEYS:
                    if k in ts:
                        camp[k] = ts[k]
                upsert_campaign(camp)
        except Exception as e:
            log_debug(f"migrate_campaigns_from_sessions: {e}")

    def reconcile_campaign_statuses(self):
        """После рестарта сервера все воркеры разоружены (armed — runtime-флаг).
        Любая кампания, помеченная в библиотеке как 'running', на деле уже не идёт —
        сбрасываем её в 'stopped', чтобы статус не завис навсегда."""
        from app.storage import list_campaigns, set_campaign_stats
        try:
            live = set()
            for st in list(self.account_states) + list(self.temp_states.values()):
                if getattr(st, "armed", False) and getattr(st, "active_campaign_id", None):
                    live.add(st.active_campaign_id)
            for c in list_campaigns():
                if c.get("status") == "running" and c.get("id") not in live:
                    set_campaign_stats(c["id"], status="stopped",
                                       finished_at=datetime.now().isoformat())
        except Exception as e:
            log_debug(f"reconcile_campaign_statuses: {e}")

    def backfill_applied_campaign_ids(self):
        """Привязать исторические отклики (без campaign_id) к старейшей кампании их
        аккаунта. Отклики, отправленные ДО введения кампаний, иначе показывались бы
        как 0. Старейшая кампания аккаунта = миграция исходного конфига, который их и
        слал. Безопасно: пустые campaign_id заполняются один раз, не перезаписываются."""
        from app.storage import list_campaigns, backfill_campaign_id
        try:
            # account_name -> старейшая кампания (по created_at)
            oldest = {}
            for c in list_campaigns():
                idx = self.idx_for_session_key(c.get("session_key"))
                if idx is None:
                    continue
                acc = self._get_apply_acc(idx) or {}
                name = acc.get("name")
                if not name:
                    continue
                cur = oldest.get(name)
                if cur is None or (c.get("created_at", "") < cur.get("created_at", "")):
                    oldest[name] = c
            for name, camp in oldest.items():
                n = backfill_campaign_id(name, camp["id"])
                if n:
                    log_debug(f"backfill_applied_campaign_ids: {name} → «{camp.get('name')}»: {n} откликов")
        except Exception as e:
            log_debug(f"backfill_applied_campaign_ids: {e}")

    def session_key_for_idx(self, idx: int):
        """Стабильный ключ HH-аккаунта (hhuid…) для сессии по combined idx."""
        acc = self._get_apply_acc(idx) or {}
        ck = acc.get("cookies", {}) or {}
        for k in ("hhuid", "crypted_hhuid", "iap.uid"):
            if ck.get(k):
                return ck[k]
        return None

    def idx_for_session_key(self, session_key: str):
        """Combined idx сессии по её session_key (hhuid…). None если не найдена."""
        if not session_key:
            return None
        for ti, ts in enumerate(self.temp_sessions):
            ck = ts.get("cookies", {}) or {}
            if any(ck.get(k) == session_key for k in ("hhuid", "crypted_hhuid", "iap.uid")):
                return len(self.account_states) + ti
        return None

    def _persist_campaign_stats(self, state, status: str):
        """Записать статистику запуска в кампанию библиотеки (sent/skipped/errors + status)."""
        cid = getattr(state, "active_campaign_id", None)
        if not cid:
            return
        fin = datetime.now().isoformat() if status in ("finished", "stopped") else None
        try:
            set_campaign_stats(
                cid, sent=state.campaign_sent, skipped=state.campaign_skipped,
                errors=state.campaign_errors, finished_at=fin, status=status,
            )
        except Exception as e:
            log_debug(f"_persist_campaign_stats {cid}: {e}")

    def start_campaign(self, idx: int, campaign_id: str) -> dict:
        """Запустить кампанию из библиотеки: загрузить её параметры в сессию и встать на armed.
        Активна одна кампания на аккаунт (сессия = один воркер)."""
        camp = get_campaign(campaign_id)
        if not camp:
            return {"ok": False, "error": "Кампания не найдена"}
        state = self._resolve_state(idx)
        if state is None:
            temp_idx = idx - len(self.account_states)
            if 0 <= temp_idx < len(self.temp_sessions):
                if not self.activate_session(temp_idx):
                    return {"ok": False, "error": "Не удалось активировать сессию (нет резюме?)"}
                state = self.temp_states.get(temp_idx)
        if state is None:
            return {"ok": False, "error": "Аккаунт не найден"}
        # Если на этой сессии уже крутилась другая кампания — зафиксировать её как остановленную
        if state.active_campaign_id and state.active_campaign_id != campaign_id:
            self._persist_campaign_stats(state, "stopped")
        # Загрузить параметры кампании в сессию
        for k in CAMPAIGN_PARAM_KEYS:
            if k in camp:
                state.acc[k] = camp[k]
        try:
            state.acc["urls"] = self._build_session_urls(state.acc)
        except Exception:
            pass
        state.active_campaign_id = campaign_id
        from app.state import _calculate_daily_limit
        state.active_daily_limit = _calculate_daily_limit(state.acc)  # дневной лимит из кампании, а не из сессии
        # дневной лимит у каждой кампании свой: считаем только её сегодняшние отклики
        from app.storage import get_applied_list
        today = datetime.now().strftime("%Y-%m-%d")
        state.daily_date = today
        state.daily_sent = sum(1 for a in get_applied_list(5000)
                               if a.get("account") == state.acc.get("name")
                               and a.get("campaign_id") == campaign_id
                               and str(a.get("at", "")).startswith(today))
        state.campaign_sent = 0
        state.campaign_skipped = 0
        state.campaign_errors = 0
        state.paused = False
        state.hard_stopped = False
        state.limit_exceeded = False
        state.limit_reset_time = None
        state._needs_applied_sync = True
        state.armed = True
        state.status = "idle"
        tl = int(state.acc.get("total_limit") or 0)
        state.status_detail = f"Кампания «{camp.get('name','')}» запущена" + (f" (цель: {tl})" if tl else "")
        set_campaign_stats(campaign_id, sent=0, skipped=0, errors=0,
                           started_at=datetime.now().isoformat(), finished_at=None, status="running")
        self._add_log(state.short, state.color,
            f"▶ Кампания «{camp.get('name','')}» запущена" + (f" — цель {tl}" if tl else ""), "success")
        return {"ok": True, "armed": True, "total_limit": tl, "campaign_id": campaign_id}

    def disarm_campaign(self, idx: int) -> dict:
        """Остановить кампанию: воркер перестаёт слать (уходит в «Ожидает запуска»)."""
        state = self._resolve_state(idx)
        if state is None:
            return {"ok": False, "error": "Аккаунт не найден"}
        state.armed = False
        state.status = "idle"
        state.status_detail = "Остановлено пользователем"
        self._persist_campaign_stats(state, "stopped")
        self._add_log(state.short, state.color, "⏹ Кампания остановлена", "warning")
        return {"ok": True, "armed": False}

    # ── Очередь подтверждения ответов в чатах ──────────────────────────────
    def _msg_needs_no_reply(self, text: str) -> bool:
        """True, если сообщение HR не требует ответа (вежливая отписка без вопроса)."""
        if not text:
            return False
        low = text.lower()
        if any(m in low for m in LLM_QUESTION_MARKERS):
            return False
        patterns = CONFIG.llm_skip_patterns or DEFAULT_LLM_SKIP_PATTERNS
        for pat in patterns:
            try:
                if re.search(pat, low, re.IGNORECASE):
                    return True
            except re.error:
                continue
        return False

    def llm_pending_list(self) -> list:
        """Снапшот очереди черновиков (только сериализуемые поля)."""
        with self._llm_pending_lock:
            return [
                {k: v for k, v in d.items() if not k.startswith("_")}
                for d in self.llm_pending.values()
            ]

    def llm_send_drafts(self, ids=None) -> dict:
        """Отправить черновики из очереди. ids=None ⇒ все; иначе список draft_id."""
        with self._llm_pending_lock:
            targets = (list(self.llm_pending.values()) if ids is None
                       else [self.llm_pending[i] for i in ids if i in self.llm_pending])
        sent, failed = 0, 0
        for d in targets:
            state = d["_state"]
            neg_id = d["neg_id"]
            try:
                ok = send_negotiation_message(state.acc, neg_id, d["draft"], topic_id=d.get("topic_id", ""))
            except Exception as e:
                log_debug(f"llm_send_drafts {neg_id}: {e}")
                ok = False
            if ok and ok != "chat_not_found":
                state.llm_replied_msgs.add(d["_key"])
                state.llm_replied_count += 1
                with self._llm_sent_lock:
                    self._llm_sent_global.add(d["_global_key"])
                upsert_interview(neg_id, acc=state.short, acc_color=state.color,
                                 llm_reply=d["draft"], llm_sent=True)
                self._add_log(state.short, state.color,
                    f"\U0001f916 Ответ отправлен → {d['employer']}: {d['draft'][:60]}…", "success", neg_id=neg_id)
                with self._llm_pending_lock:
                    self.llm_pending.pop(d["draft_id"], None)
                sent += 1
                time.sleep(3)  # rate limit между отправками
            else:
                failed += 1
                self._add_log(state.short, state.color,
                    f"\U0001f916 Не удалось отправить → {d['employer']} (оставлено в очереди)", "warning", neg_id=neg_id)
        return {"ok": True, "sent": sent, "failed": failed, "remaining": len(self.llm_pending)}

    def llm_edit_draft(self, draft_id: str, text: str) -> dict:
        with self._llm_pending_lock:
            d = self.llm_pending.get(draft_id)
            if not d:
                return {"ok": False, "error": "Черновик не найден"}
            d["draft"] = text
        return {"ok": True}

    def llm_discard_drafts(self, ids) -> dict:
        """Убрать черновики без отправки (пометить отвеченными, чтобы не возвращались)."""
        removed = 0
        with self._llm_pending_lock:
            for i in (ids or []):
                d = self.llm_pending.pop(i, None)
                if d:
                    d["_state"].llm_replied_msgs.add(d["_key"])
                    removed += 1
        return {"ok": True, "removed": removed, "remaining": len(self.llm_pending)}

    def toggle_account_llm(self, idx: int):
        state = None
        if 0 <= idx < len(self.account_states):
            state = self.account_states[idx]
        else:
            temp_idx = idx - len(self.account_states)
            state = self.temp_states.get(temp_idx)
        if state:
            state.llm_enabled = not state.llm_enabled
            msg = (
                f"\U0001f916 LLM включён для {state.short}"
                if state.llm_enabled
                else f"\U0001f916 LLM выключен для {state.short}"
            )
            self._add_log(state.short, state.color, msg, "info")

    def toggle_account_oauth(self, idx: int):
        state = None
        if 0 <= idx < len(self.account_states):
            state = self.account_states[idx]
        else:
            temp_idx = idx - len(self.account_states)
            state = self.temp_states.get(temp_idx)
        if state:
            state.use_oauth = not state.use_oauth
            mode = "OAuth" if state.use_oauth else "Web"
            self._add_log(state.short, state.color, f"{mode} откликов для {state.short}", "info")
            # Persist to account data
            state.acc["use_oauth"] = state.use_oauth
            if 0 <= idx < len(accounts_data):
                accounts_data[idx]["use_oauth"] = state.use_oauth
                save_accounts()
            else:
                temp_idx = idx - len(self.account_states)
                if 0 <= temp_idx < len(self.temp_sessions):
                    self.temp_sessions[temp_idx]["use_oauth"] = state.use_oauth
                    save_browser_sessions(self.temp_sessions)

    def trigger_resume_touch(self, idx: int):
        if 0 <= idx < len(self.account_states):
            self.account_states[idx].next_resume_touch = datetime.now()
        else:
            temp_idx = idx - len(self.account_states)
            if temp_idx in self.temp_states:
                self.temp_states[temp_idx].next_resume_touch = datetime.now()

    def toggle_resume_touch(self, idx: int) -> bool:
        state = None
        if 0 <= idx < len(self.account_states):
            state = self.account_states[idx]
        else:
            temp_idx = idx - len(self.account_states)
            if temp_idx in self.temp_states:
                state = self.temp_states[temp_idx]
        if state:
            state.resume_touch_enabled = not state.resume_touch_enabled
            return state.resume_touch_enabled
        return False

    def _add_log(self, acc_short: str, acc_color: str, message: str, level: str = "info", neg_id: str = ""):
        entry = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "acc": acc_short,
            "color": acc_color,
            "message": message,
            "level": level,
        }
        if neg_id:
            entry["neg_id"] = str(neg_id)
        self.activity_log.appendleft(entry)

    def _add_acc_event(self, state: AccountState, icon: str, etype: str,
                        title: str, company: str, extra: str = ""):
        state.acc_event_log.appendleft({
            "time": datetime.now().strftime("%H:%M"),
            "icon": icon,
            "type": etype,
            "title": title[:45],
            "company": company[:25],
            "extra": extra[:70],
        })

    def _check_auto_pause(self, state: AccountState):
        """Авто-пауза при превышении лимита ошибок подряд."""
        n = CONFIG.auto_pause_errors
        if n > 0 and state.consecutive_errors >= n:
            state.paused = True
            self._add_log(
                state.short, state.color,
                f"⛔ Авто-пауза: {n} ошибок подряд. Снимите вручную.",
                "error",
            )

    def _add_response(
        self,
        state: AccountState,
        vid: str,
        title: str,
        company: str,
        result: str,
        salary: str = "",
    ):
        result_icons = {
            "sent": "✅",
            "test": "\U0001f9ea",
            "already": "\U0001f504",
            "limit": "\U0001f6ab",
            "error": "❌",
        }
        self.recent_responses.appendleft({
            "time": datetime.now().strftime("%H:%M:%S"),
            "acc": state.short,
            "color": state.color,
            "id": vid,
            "title": title,
            "company": company,
            "salary": salary,
            "result": result,
            "icon": result_icons.get(result, "❓"),
        })
        # Telegram notifications for key events
        if result == "sent":
            notify_response(title, company, state.short)
        elif result == "error":
            notify_error(title, company, "ошибка отправки", state.short)

    def get_state_snapshot(self) -> dict:
        """Full JSON snapshot for WS broadcast"""
        now = datetime.now()
        uptime = int((now - self._start_time).total_seconds()) if self._start_time else 0

        # All states: regular + temp sessions (for global_stats, vacancy_queues)
        all_states = list(self.account_states) + list(self.temp_states.values())

        accounts = []
        for i, s in enumerate(self.account_states):
            next_touch_str = ""
            if s.next_resume_touch:
                rem = (s.next_resume_touch - now).total_seconds()
                if rem > 0:
                    h = int(rem // 3600)
                    m = int((rem % 3600) // 60)
                    next_touch_str = f"{s.next_resume_touch.strftime('%H:%M')} ({h}ч{m}м)"
                else:
                    next_touch_str = "сейчас!"

            hh_updated_str = ""
            if s.hh_stats_updated:
                ago = int((now - s.hh_stats_updated).total_seconds() / 60)
                hh_updated_str = (
                    f"{ago}м назад" if ago < 60 else f"{ago // 60}ч{ago % 60}м назад"
                )

            accounts.append({
                "idx": i,
                "name": s.name,
                "short": s.short,
                "color": s.color,
                "status": s.status,
                "status_detail": s.status_detail,
                "sent": s.sent,
                "total_applied": len((_cache_applied or {}).get(s.name, {})),
                "tests": s.tests,
                "errors": s.errors,
                "already_applied": s.already_applied,
                "found_vacancies": s.found_vacancies,
                "current_vacancy_title": s.current_vacancy_title,
                "current_vacancy_company": s.current_vacancy_company,
                "current_vacancy_idx": s.current_vacancy_idx,
                "total_vacancies": s.total_vacancies,
                "salary_skipped": s.salary_skipped,
                "questionnaire_sent": s.questionnaire_sent,
                "limit_exceeded": s.limit_exceeded,
                "paused": s.paused,
                "next_resume_touch": next_touch_str,
                "resume_touch_status": s.resume_touch_status,
                "resume_touch_enabled": s.resume_touch_enabled,
                "letter": s.acc.get("letter", ""),
                "urls": s.acc.get("urls", []),
                "url_pages": s.acc.get("url_pages", {}),
                "hh_interviews": s.hh_interviews,
                "hh_interviews_recent": s.hh_interviews_recent,
                "hh_viewed": s.hh_viewed,
                "hh_discards": s.hh_discards,
                "hh_not_viewed": s.hh_not_viewed,
                "hh_unread_by_employer": s.hh_unread_by_employer,
                "hh_stats_updated": hh_updated_str,
                "hh_stats_loading": s.hh_stats_loading,
                "hh_interviews_list": s.hh_interviews_list[:20],
                "hh_possible_offers": s.hh_possible_offers[:10],
                "action_history": list(s.action_history),
                "resume_views_7d": s.resume_views_7d,
                "resume_views_new": s.resume_views_new,
                "resume_shows_7d": s.resume_shows_7d,
                "resume_invitations_7d": s.resume_invitations_7d,
                "resume_invitations_new": s.resume_invitations_new,
                "resume_next_touch_seconds": s.resume_next_touch_seconds,
                "resume_free_touches": s.resume_free_touches,
                "resume_global_invitations": s.resume_global_invitations,
                "resume_new_invitations_total": s.resume_new_invitations_total,
                "acc_event_log": list(s.acc_event_log),
                "apply_tests": s.apply_tests,
                "consecutive_errors": s.consecutive_errors,
                "url_stats": dict(s.url_stats),
                "cookies_expired": s.cookies_expired,
                "llm_enabled": s.llm_enabled,
                "llm_status": s.llm_status,
                "llm_replied_count": s.llm_replied_count,
                "llm_pending_chats": s.llm_pending_chats,
                "use_oauth": s.use_oauth,
                "daily_sent": s.daily_sent,
                "daily_limit": s.active_daily_limit if hasattr(s, "active_daily_limit") else 0,
                "hard_stopped": s.hard_stopped,
                "armed": s.armed,
                "campaign_sent": s.campaign_sent,
                "campaign_skipped": s.campaign_skipped,
                "campaign_errors": s.campaign_errors,
                "active_campaign_id": s.active_campaign_id,
                "is_temp": False,
                "all_resumes": s.acc.get("all_resumes", []),
                "resume_pdf_name": s.acc.get("resume_pdf_name", ""),
                **_campaign_snapshot(s.acc),
            })

        # Temp browser sessions — append after regular accounts
        base_idx = len(self.account_states)
        for i, ts in enumerate(self.temp_sessions):
            idx = base_idx + i
            state = self.temp_states.get(i)
            if state:
                # Активная сессия — реальные данные из AccountState
                s = state
                nrt = s.next_resume_touch.strftime("%H:%M") if s.next_resume_touch else ""
                ts_hh_updated_str = ""
                if s.hh_stats_updated:
                    ago = int((now - s.hh_stats_updated).total_seconds() / 60)
                    ts_hh_updated_str = (
                        f"{ago}м назад" if ago < 60 else f"{ago // 60}ч{ago % 60}м назад"
                    )
                accounts.append({
                    "idx": idx,
                    "name": s.acc["name"],
                    "short": s.acc.get("short", ""),
                    "color": "yellow",
                    "temp": True,
                    "bot_active": True,
                    "resume_hash": s.acc.get("resume_hash", ""),
                    "letter": s.acc.get("letter", ""),
                    "urls": s.acc.get("urls", []),
                    "url_pages": s.acc.get("url_pages", {}),
                    "status": s.status,
                    "status_detail": s.status_detail,
                    "sent": s.sent,
                    "total_applied": len((_cache_applied or {}).get(s.acc["name"], {})),
                    "tests": s.tests,
                    "errors": s.errors,
                    "already_applied": s.already_applied,
                    "found_vacancies": s.found_vacancies,
                    "current_vacancy_title": s.current_vacancy_title,
                    "current_vacancy_company": s.current_vacancy_company,
                    "current_vacancy_idx": s.current_vacancy_idx,
                    "total_vacancies": s.total_vacancies,
                    "salary_skipped": s.salary_skipped,
                    "questionnaire_sent": s.questionnaire_sent,
                    "limit_exceeded": s.limit_exceeded,
                    "paused": s.paused,
                    "next_resume_touch": nrt,
                    "resume_touch_status": s.resume_touch_status,
                    "resume_touch_enabled": s.resume_touch_enabled,
                    "hh_interviews": s.hh_interviews,
                    "hh_interviews_recent": s.hh_interviews_recent,
                    "hh_viewed": s.hh_viewed,
                    "hh_discards": s.hh_discards,
                    "hh_not_viewed": s.hh_not_viewed,
                    "hh_unread_by_employer": s.hh_unread_by_employer,
                    "hh_stats_updated": ts_hh_updated_str,
                    "hh_stats_loading": s.hh_stats_loading,
                    "hh_interviews_list": s.hh_interviews_list[:20],
                    "hh_possible_offers": s.hh_possible_offers[:10],
                    "action_history": list(s.action_history),
                    "resume_views_7d": s.resume_views_7d,
                    "resume_views_new": s.resume_views_new,
                    "resume_shows_7d": s.resume_shows_7d,
                    "resume_invitations_7d": s.resume_invitations_7d,
                    "resume_invitations_new": s.resume_invitations_new,
                    "resume_next_touch_seconds": s.resume_next_touch_seconds,
                    "resume_free_touches": s.resume_free_touches,
                    "resume_global_invitations": s.resume_global_invitations,
                    "resume_new_invitations_total": s.resume_new_invitations_total,
                    "acc_event_log": list(s.acc_event_log),
                    "apply_tests": s.apply_tests,
                    "consecutive_errors": s.consecutive_errors,
                    "url_stats": dict(s.url_stats),
                    "cookies_expired": s.cookies_expired,
                    "llm_enabled": s.llm_enabled,
                    "use_oauth": s.use_oauth,
                    "daily_sent": s.daily_sent,
                    "daily_limit": s.active_daily_limit if hasattr(s, "active_daily_limit") else 0,
                    "hard_stopped": s.hard_stopped,
                    "armed": s.armed,
                    "campaign_sent": s.campaign_sent,
                    "campaign_skipped": s.campaign_skipped,
                    "campaign_errors": s.campaign_errors,
                    "active_campaign_id": s.active_campaign_id,
                    "is_temp": True,
                    "all_resumes": s.acc.get("all_resumes", []),
                "resume_pdf_name": s.acc.get("resume_pdf_name", ""),
                    **_campaign_snapshot(s.acc),
                })
            else:
                # Неактивная сессия — заглушка
                accounts.append({
                    "idx": idx,
                    "name": ts.get("name", f"Браузер #{i+1}"),
                    "short": ts.get("short", f"Браузер#{i+1}"),
                    "color": "yellow",
                    "temp": True,
                    "bot_active": False,
                    "resume_hash": ts.get("resume_hash", ""),
                    "all_resumes": ts.get("all_resumes", []),
                "resume_pdf_name": ts.get("resume_pdf_name", ""),
                    "letter": ts.get("letter", ""),
                    "status": "—", "status_detail": "", "sent": 0, "tests": 0,
                    "errors": 0, "already_applied": 0, "found_vacancies": 0,
                    "current_vacancy_title": "", "current_vacancy_company": "",
                    "current_vacancy_idx": 0, "total_vacancies": 0,
                    "salary_skipped": 0, "questionnaire_sent": 0,
                    "limit_exceeded": False, "paused": False,
                    "next_resume_touch": "", "resume_touch_status": "",
                    "hh_interviews": 0, "hh_viewed": 0, "hh_discards": 0,
                    "hh_not_viewed": 0, "hh_unread_by_employer": 0,
                    "hh_stats_updated": "", "hh_stats_loading": False,
                    "hh_interviews_list": [], "hh_possible_offers": [], "action_history": [],
                    "resume_views_7d": 0, "resume_views_new": 0, "resume_shows_7d": 0,
                    "resume_invitations_7d": 0, "resume_invitations_new": 0,
                    "resume_next_touch_seconds": 0, "resume_free_touches": 0,
                    "resume_global_invitations": 0, "resume_new_invitations_total": 0,
                    "acc_event_log": [],
                    "apply_tests": bool(ts.get("apply_tests", False)),
                    "consecutive_errors": 0,
                    "url_stats": {},
                    "cookies_expired": False,
                    "llm_enabled": True,
                    "use_oauth": bool(ts.get("use_oauth", False)),
                    "daily_sent": 0,
                    "daily_limit": 0,
                    "hard_stopped": False,
                    "armed": False,
                    "campaign_sent": 0,
                    "campaign_skipped": 0,
                    "campaign_errors": 0,
                    "active_campaign_id": None,
                    "is_temp": True,
                    **_campaign_snapshot(ts),
                })

        storage_stats = get_stats()

        return {
            "type": "state_update",
            "uptime_seconds": uptime,
            "paused": self.paused,
            "accounts": accounts,
            "recent_responses": list(self.recent_responses),
            "log": list(self.activity_log),
            "llm_log": list(self.llm_log),
            "llm_pending": self.llm_pending_list(),
            "config": {
                "pages_per_url": CONFIG.pages_per_url,
                "response_delay": CONFIG.response_delay,
                "pause_between_cycles": CONFIG.pause_between_cycles,
                "batch_responses": CONFIG.batch_responses,
                "limit_check_interval": CONFIG.limit_check_interval,
                "min_salary": CONFIG.min_salary,
                "auto_pause_errors": CONFIG.auto_pause_errors,
                "auto_apply_tests": CONFIG.auto_apply_tests,
                "use_oauth_apply": CONFIG.use_oauth_apply,
                "daily_apply_limit": CONFIG.daily_apply_limit,
                "stop_on_hh_limit": CONFIG.stop_on_hh_limit,
                "llm_check_interval": CONFIG.llm_check_interval,
                "allowed_schedules": CONFIG.allowed_schedules,
                "title_blacklist": CONFIG.title_blacklist,
                "title_whitelist": CONFIG.title_whitelist,
                "questionnaire_templates": CONFIG.questionnaire_templates,
                "questionnaire_default_answer": CONFIG.questionnaire_default_answer,
                "letter_templates": CONFIG.letter_templates,
                "url_pool": CONFIG.url_pool,
                "skip_inconsistent": CONFIG.skip_inconsistent,
                "filter_agencies": CONFIG.filter_agencies,
                "filter_low_competition": CONFIG.filter_low_competition,
                "search_period_days": CONFIG.search_period_days,
                "llm_enabled": CONFIG.llm_enabled,
                "llm_auto_send": CONFIG.llm_auto_send,
                "llm_fill_questionnaire": CONFIG.llm_fill_questionnaire,
                "llm_use_cover_letter": CONFIG.llm_use_cover_letter,
                "llm_use_resume": CONFIG.llm_use_resume,
                "llm_model": CONFIG.llm_model,
                "llm_base_url": CONFIG.llm_base_url,
                # Note: don't include llm_api_key in snapshot for security
                "llm_profiles": [
                    {"name": p.get("name", ""), "base_url": p.get("base_url", ""),
                     "model": p.get("model", ""), "enabled": p.get("enabled", True)}
                    for p in (CONFIG.llm_profiles or [])
                ],
                "llm_profile_mode": CONFIG.llm_profile_mode,
            },
            "global_stats": {
                "total_sent": sum(s.sent for s in all_states),
                "total_tests": sum(s.tests for s in all_states),
                "total_errors": sum(s.errors for s in all_states),
                "total_found": sum(s.found_vacancies for s in all_states),
                "storage_total": storage_stats["total"],
                "storage_tests": storage_stats["tests"],
            },
            "vacancy_queues": {
                s.short: {
                    "remaining": max(0, len(s.vacancies_queue) - s.current_vacancy_idx),
                    "next": s.vacancies_queue[s.current_vacancy_idx: s.current_vacancy_idx + 5]
                    if s.vacancies_queue
                    else [],
                }
                for s in all_states
            },
        }

    def _run_account_worker(self, idx: int, state: AccountState) -> None:
        """Thread worker for an account — auto-restarts on crash"""
        while not self._stop_event.is_set() and not getattr(state, '_deleted', False):
            try:
                self._run_account_worker_inner(idx, state)
                break  # normal exit
            except Exception as e:
                log_debug(f"WORKER CRASHED [{state.short}]: {e}")
                import traceback
                log_debug(traceback.format_exc())
                state.status = "error"
                state.status_detail = f"Перезапуск через 30с ({str(e)[:30]})"
                self._add_log(state.short, state.color, f"⚠️ Worker упал: {str(e)[:50]}. Перезапуск через 30с", "error")
                time.sleep(30)
                state.status = "idle"
                state.status_detail = "Перезапущен после ошибки"
                self._add_log(state.short, state.color, "\U0001f504 Worker перезапущен", "info")

    def _run_account_worker_inner(self, idx: int, state: AccountState) -> None:
        acc = state.acc

        while not self._stop_event.is_set() and not state._deleted:
            # Global + per-account pause
            while (self.paused or state.paused) and not self._stop_event.is_set() and not state._deleted:
                # Auto-reset daily limit pause when new day starts
                if state.hard_stopped:
                    today = datetime.now().strftime("%Y-%m-%d")
                    if state.daily_date != today:
                        from app.state import _calculate_daily_limit
                        state.active_daily_limit = _calculate_daily_limit(state.acc)
                        state.daily_sent = 0
                        state.daily_date = today
                        state.hard_stopped = False
                        state.paused = False
                        state.limit_exceeded = False
                        state.limit_reset_time = None
                        state.status = "idle"
                        state.status_detail = "Новый день — лимит сброшен"
                        self._add_log(state.short, state.color,
                            "\U0001f305 Новый день! Лимит сброшен, продолжаю работу", "success")
                        break
                if state.hard_stopped:
                    state.status = "limit"
                    if state.active_daily_limit > 0 and state.daily_sent >= state.active_daily_limit:
                        state.status_detail = f"Дневной лимит: {state.daily_sent}/{state.active_daily_limit}. Сброс завтра в 00:00"
                    else:
                        state.status_detail = "Лимит HH. Сброс завтра в 00:00"
                elif state.limit_exceeded:
                    state.status = "limit"
                    if state.limit_reset_time:
                        remaining = int((state.limit_reset_time - datetime.now()).total_seconds())
                        if remaining > 0:
                            state.status_detail = f"Лимит HH. Проверка через {remaining // 60}м{remaining % 60:02d}с"
                        else:
                            state.status_detail = "Лимит HH. Проверка сейчас..."
                    else:
                        state.status_detail = "Лимит HH. Проверка через 1м"
                else:
                    state.status = "idle"
                    state.status_detail = "Пауза пользователем"
                time.sleep(1)

            if self._stop_event.is_set():
                break

            now = datetime.now()

            # === АВТОПОДНЯТИЕ РЕЗЮМЕ ===
            if state.resume_touch_enabled:
                should_touch = False
                if state.next_resume_touch is None:
                    should_touch = True
                elif now >= state.next_resume_touch:
                    should_touch = True

                if should_touch:
                    self._add_log(state.short, state.color, "\U0001f4e4 Поднимаю резюме...", "info")
                    success, message = touch_resume(acc)

                    if success:
                        state.resume_touch_status = "✅ Поднято!"
                        state.last_resume_touch = now
                        state.next_resume_touch = now + timedelta(hours=4)
                        self._add_log(
                            state.short, state.color,
                            f"✅ Резюме поднято! Следующее в {state.next_resume_touch.strftime('%H:%M')}",
                            "success",
                        )
                    else:
                        state.resume_touch_status = f"⏳ {message}"
                        state.next_resume_touch = now + timedelta(hours=4)
                        self._add_log(
                            state.short, state.color,
                            f"\U0001f4e4 {message}. Повтор в {state.next_resume_touch.strftime('%H:%M')}",
                            "warning",
                        )

            # === ПРОВЕРКА ЛИМИТА ===
            if state.limit_exceeded:
                # If no reset time set, schedule a check soon
                if not state.limit_reset_time:
                    state.limit_reset_time = now + timedelta(minutes=1)

                if now >= state.limit_reset_time:
                    state.status = "checking"
                    state.status_detail = "Проверка сброса лимита..."
                    self._add_log(state.short, state.color, "\U0001f50d Проверяю сброс лимита...", "info")

                    if not check_limit(acc):
                        state.limit_exceeded = False
                        state.limit_reset_time = None
                        state.paused = False
                        state.hard_stopped = False
                        state.status_detail = ""
                        self._add_log(
                            state.short, state.color, "✅ Лимит сброшен! Продолжаю работу", "success"
                        )
                    else:
                        state.limit_reset_time = now + timedelta(minutes=CONFIG.limit_check_interval)
                        state.status = "limit"
                        state.status_detail = f"Проверка в {state.limit_reset_time.strftime('%H:%M')}"
                        self._add_log(
                            state.short, state.color,
                            f"⏳ Лимит ещё активен, попробую в {state.limit_reset_time.strftime('%H:%M')}",
                            "warning",
                        )
                        time.sleep(60)
                        continue
                else:
                    state.status = "limit"
                    remaining = int((state.limit_reset_time - now).total_seconds())
                    state.status_detail = f"Проверка через {remaining}с"
                    time.sleep(30)
                    continue

            # === ГЕЙТ A: кампания должна быть подтверждена (armed) ===
            # Пока пользователь явно не запустил кампанию — НИКАКОГО сбора и отправки.
            # armed — runtime-флаг (False при старте процесса), поэтому рестарт безопасен.
            if not state.armed:
                state.status = "idle"
                state.status_detail = "Ожидает запуска кампании"
                time.sleep(2)
                continue

            # === СИНХРОНИЗАЦИЯ УЖЕ-ОТКЛИНУТЫХ С HH (один раз за запуск кампании) ===
            # Источник истины — список переговоров hh.ru. Ловит и ручные отклики,
            # сделанные вне инструмента, чтобы фильтр сбора их исключил.
            if state._needs_applied_sync:
                state._needs_applied_sync = False
                try:
                    state.status_detail = "Синхронизация откликов с HH…"
                    hh_vids = fetch_applied_vacancy_ids(acc)
                    new_cnt = 0
                    for vid in hh_vids:
                        if not is_applied(acc["name"], vid):
                            new_cnt += 1
                        add_applied(acc["name"], vid)
                    self._add_log(state.short, state.color,
                        f"\U0001f504 Синхронизировано {len(hh_vids)} откликов с HH (новых {new_cnt})", "info")
                except Exception as e:
                    log_debug(f"applied sync {state.short}: {e}")

            # === СБОР ВАКАНСИЙ (ПАРАЛЛЕЛЬНО) ===
            # Если у аккаунта нет своих URL — используем глобальный пул
            effective_urls = acc.get("urls") or [_url_entry(u)["url"] for u in CONFIG.url_pool]
            state.total_urls = len(effective_urls)

            state.status = "collecting"
            state.status_detail = "Начинаю параллельный сбор..."
            state.cycle_start_time = now
            state.vacancies_by_url = {}
            state.vacancy_meta = {}  # Сброс метаданных вакансий для нового цикла

            self._add_log(
                state.short, state.color,
                f"\U0001f4e5 Параллельный сбор: {len(effective_urls)} URL × {CONFIG.pages_per_url} стр",
                "info",
            )

            try:
                results_by_url, salary_map, schedule_map = asyncio.run(self._collect_all_urls_parallel(state))
            except Exception as e:
                log_debug(f"COLLECT CRASH [{state.short}]: {e}")
                import traceback
                log_debug(traceback.format_exc())
                state.status = "error"
                state.status_detail = f"Ошибка сбора: {str(e)[:50]}"
                time.sleep(60)
                continue
            state.vacancy_salaries = salary_map
            state.vacancy_schedules = schedule_map

            all_vacancies = []
            for url in effective_urls:
                url_vacancies = results_by_url.get(url, set())
                state.vacancies_by_url[url] = len(url_vacancies)
                all_vacancies.extend(url_vacancies)

                query = extract_search_query(url)
                if url_vacancies:
                    self._add_log(state.short, state.color, f"\U0001f4ca {query}: {len(url_vacancies)}", "info")
            # Сохраняем статистику по URL для снапшота
            state.url_stats = dict(state.vacancies_by_url)

            unique_vacancies = set(all_vacancies)
            total_collected = len(unique_vacancies)

            self._add_log(
                state.short, state.color,
                f"\U0001f4ca Всего собрано: {len(all_vacancies)} ({total_collected} уникальных)",
                "info",
            )

            if not unique_vacancies:
                state.status = "waiting"
                state.status_detail = "Нет вакансий"
                state.wait_until = now + timedelta(minutes=2)
                self._add_log(
                    state.short, state.color,
                    "⚠️ Не найдено ни одной вакансии, пауза 2 мин",
                    "warning",
                )
                time.sleep(120)
                continue

            # ── Эффективные настройки кампании: acc-override → глобальный CONFIG ──
            eff_min_salary = _as_int(acc.get("salary_from")) or CONFIG.min_salary
            eff_salary_only = bool(acc.get("salary_only"))
            if acc.get("schedule"):
                eff_schedules = [acc["schedule"]]
            elif acc.get("remote_only"):
                eff_schedules = ["remote"]
            else:
                eff_schedules = CONFIG.allowed_schedules
            eff_blacklist = _split_csv(acc.get("stop_words")) or CONFIG.title_blacklist
            if acc.get("strict_title_match") and acc.get("search_query"):
                # Пословно: достаточно вхождения любого слова любого запроса
                # в название (запятая разделяет запросы: "инженер, engineer").
                # HH-поиск уже сужен search_field=name; это страховка пост-фильтра.
                eff_whitelist = acc["search_query"].replace(",", " ").split()
            else:
                eff_whitelist = CONFIG.title_whitelist
            eff_apply_tests = state.apply_tests or bool(acc.get("ai_answers")) or CONFIG.auto_apply_tests
            eff_batch = _as_int(acc.get("batch_responses")) or CONFIG.batch_responses
            eff_delay = _as_int(acc["response_delay"]) if acc.get("response_delay") not in (None, "") else CONFIG.response_delay
            eff_skip_inconsistent = bool(acc["skip_inconsistent"]) if "skip_inconsistent" in acc else CONFIG.skip_inconsistent

            def _apply_pause():
                """Рандомизированная пауза между откликами — чтобы не отправлять пачку
                мгновенно (анти-burst/анти-детект). Минимум ~3с + джиттер."""
                base = max(int(eff_delay or 0), 3)
                time.sleep(random.uniform(base, base + 4))

            # Фильтрация
            filtered = []
            already_count = 0
            test_count = 0
            salary_skipped = 0
            schedule_skipped = 0
            title_skipped = 0
            apply_tests = eff_apply_tests

            def _title_allowed(vid):
                """Стоп-слова — по названию И по компании; whitelist (запрос) — по названию."""
                meta = state.vacancy_meta.get(vid, {})
                title = (meta.get("title") or "").lower()
                company = (meta.get("company") or "").lower()
                bl = [w.lower() for w in eff_blacklist if w.strip()]
                if bl and any(w in title or w in company for w in bl):
                    return False
                wl = [w.lower() for w in eff_whitelist if w.strip()]
                if wl and not any(w in title for w in wl):
                    return False
                return True

            def _schedule_blocked(vid):
                if not eff_schedules:
                    return False
                sched = schedule_map.get(vid, set())
                return bool(sched) and not sched.intersection(eff_schedules)

            def _salary_ok(vid):
                sal = salary_map.get(vid)
                if sal is None:
                    # без зарплаты пропускаем, если не включено «только с зарплатой»;
                    # нижнюю границу hh уже отфильтровал параметром salary= в поиске
                    return not eff_salary_only
                return sal >= eff_min_salary

            for vid in unique_vacancies:
                if is_applied(acc["name"], vid):
                    already_count += 1
                    state.already_applied += 1
                    state.campaign_skipped += 1
                elif (is_test(vid) or state._test_failures.get(vid, 0) >= 2) and not apply_tests:
                    test_count += 1
                    state.tests += 1
                    state.campaign_skipped += 1
                elif not _title_allowed(vid):
                    title_skipped += 1
                    state.campaign_skipped += 1
                elif _schedule_blocked(vid):
                    schedule_skipped += 1
                    state.schedule_skipped += 1
                    state.campaign_skipped += 1
                elif not _salary_ok(vid):
                    salary_skipped += 1
                    state.salary_skipped += 1
                    state.campaign_skipped += 1
                else:
                    filtered.append(vid)

            sal_msg = f", \U0001f4b0 зарплата {salary_skipped}" if (eff_min_salary > 0 or eff_salary_only) else ""
            sched_msg = f", \U0001f3e2 формат {schedule_skipped}" if eff_schedules else ""
            title_msg = f", \U0001f6ab стоп-слова {title_skipped}" if (eff_blacklist or eff_whitelist) else ""
            self._add_log(
                state.short, state.color,
                f"\U0001f50d Фильтрация: ✅ уже {already_count}, \U0001f9ea тест {test_count}{sal_msg}{sched_msg}{title_msg}, \U0001f195 новые {len(filtered)}",
                "info",
            )

            if not filtered:
                state.status = "waiting"
                state.status_detail = "Нет новых вакансий"
                state.wait_until = now + timedelta(minutes=2)
                self._add_log(
                    state.short, state.color,
                    f"⚠️ Все вакансии уже обработаны ({already_count} откликов, {test_count} тестов), пауза 2 мин",
                    "warning",
                )
                time.sleep(120)
                continue

            random.shuffle(filtered)

            # Hot leads priority: fetch possible_job_offers and put matching vacancies first
            try:
                r_offers = requests.get(
                    "https://hh.ru/shards/applicant/negotiations/possible_job_offers",
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Accept": "application/json",
                        "X-Xsrftoken": acc.get("cookies", {}).get("_xsrf", ""),
                        "Referer": "https://hh.ru/applicant/negotiations",
                    },
                    cookies=acc.get("cookies", {}), verify=False, timeout=10,
                )
                if r_offers.status_code == 200:
                    offers_data = r_offers.json()
                    offer_items = offers_data if isinstance(offers_data, list) else offers_data.get("possibleJobOffers", [])
                    offer_vids = set()
                    for o in offer_items:
                        vid_val = o.get("vacancyId", "")
                        if vid_val:
                            offer_vids.add(str(vid_val))
                    if offer_vids:
                        hot = [v for v in filtered if v in offer_vids]
                        cold = [v for v in filtered if v not in offer_vids]
                        filtered = hot + cold
                        if hot:
                            self._add_log(state.short, state.color,
                                f"\U0001f525 {len(hot)} горячих лидов в начале очереди", "success")
            except Exception:
                pass

            state.vacancies_queue = filtered
            state.total_vacancies = len(filtered)
            state.found_vacancies += len(all_vacancies)

            self._add_log(
                state.short, state.color,
                f"✅ Найдено {len(filtered)} новых вакансий для отклика!",
                "success",
            )
            self.vacancy_queues[state.short] = {
                "vacancies": filtered,
                "current": 0,
                "color": state.color,
            }

            # === ОТПРАВКА ОТКЛИКОВ (ПАКЕТАМИ) ===
            state.status = "applying"
            state.status_detail = f"0/{state.total_vacancies}"

            batch_size = eff_batch
            i = 0

            while i < len(filtered):
                if self._stop_event.is_set() or self.paused or state.paused or state.limit_exceeded:
                    break

                batch = filtered[i: i + batch_size]
                state.current_vacancy_idx = i + 1
                state.status_detail = (
                    f"{i + 1}-{min(i + batch_size, len(filtered))}/{state.total_vacancies}"
                )

                if state.short in self.vacancy_queues:
                    self.vacancy_queues[state.short]["current"] = i

                # === ГЕЙТ B: лимит откликов кампании (total_limit) ===
                tl = int(state.acc.get("total_limit") or 0)
                if tl > 0 and state.campaign_sent >= tl:
                    state.armed = False
                    state.status = "done"
                    state.status_detail = f"Кампания завершена: {state.campaign_sent}/{tl} откликов"
                    self._persist_campaign_stats(state, "finished")
                    self._add_log(state.short, state.color,
                        f"✅ Кампания завершена: отправлено {state.campaign_sent} из {tl}. Снято с запуска.", "success")
                    break

                # Daily limit check
                today = datetime.now().strftime("%Y-%m-%d")
                if state.daily_date != today:
                    state.daily_sent = 0
                    state.daily_date = today
                    state.hard_stopped = False
                    # Cleanup unbounded dicts on new day
                    if len(state._test_failures) > 500:
                        state._test_failures.clear()
                    if len(state._msg_consecutive) > 500:
                        state._msg_consecutive.clear()
                if state.active_daily_limit > 0 and state.daily_sent >= state.active_daily_limit:
                    state.hard_stopped = True
                    state.paused = True
                    state.status = "limit"
                    state.status_detail = f"Дневной лимит: {state.daily_sent}/{state.active_daily_limit}. Сброс завтра в 00:00"
                    self._add_log(state.short, state.color,
                        f"\U0001f6d1 Дневной лимит {state.active_daily_limit} откликов. Пауза до завтра 00:00.", "error")
                    break

                # Pre-check: skip inconsistent vacancies if enabled
                if eff_skip_inconsistent:
                    checked_batch = []
                    for vid in batch:
                        precheck = _check_vacancy_before_apply(acc, vid)
                        if not precheck["ok"]:
                            meta = state.vacancy_meta.get(vid, {})
                            display_title = (meta.get("title") or vid)[:40]
                            state.inconsistent_skipped += 1
                            self._add_log(state.short, state.color,
                                f"⏭ {display_title}: пропуск ({precheck['reason']})", "warning")
                        else:
                            checked_batch.append(vid)
                            # Collect HR contact info if available
                            contact = precheck.get("contact")
                            if contact and (contact.get("email") or contact.get("fio")):
                                meta = state.vacancy_meta.get(vid, {})
                                entry = {
                                    "vacancy_id": vid,
                                    "title": meta.get("title", ""),
                                    "company": meta.get("company", ""),
                                    "fio": contact.get("fio", ""),
                                    "email": contact.get("email", ""),
                                    "phone": contact.get("phone", ""),
                                    "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                    "account": state.short,
                                }
                                with self._hr_contacts_lock:
                                    if len(self.hr_contacts) < 500:
                                        self.hr_contacts.append(entry)
                    batch = checked_batch
                    if not batch:
                        i += batch_size
                        continue

                if len(batch) > 1:
                    self._add_log(
                        state.short, state.color,
                        f"\U0001f4e4 Пакет {len(batch)} откликов: {', '.join(batch[:3])}{'...' if len(batch) > 3 else ''}",
                        "info",
                    )

                # Choose apply method: OAuth API or Web (per-account or global)
                if state.use_oauth or CONFIG.use_oauth_apply:
                    # OAuth: synchronous, one by one (API doesn't support batch)
                    results = []
                    for vid in batch:
                        try:
                            result = _oauth_apply(acc, vid, asyncio.run(_resolve_letter(acc, vid)))
                            results.append(result)
                        except Exception as e:
                            results.append(e)
                        _apply_pause()  # пауза после каждого отклика
                else:
                    # Web: async batch via aiohttp
                    def _make_send_batch(b):
                        async def send_batch():
                            tasks = [send_response_async(acc, vid) for vid in b]
                            return await asyncio.gather(*tasks, return_exceptions=True)
                        return send_batch
                    results = asyncio.run(_make_send_batch(batch)())

                for j, (vid, result_data) in enumerate(zip(batch, results)):
                    if isinstance(result_data, Exception):
                        state.errors += 1
                        state.campaign_errors += 1
                        state.consecutive_errors += 1
                        err_msg = str(result_data)[:60]
                        self._add_log(state.short, state.color, f"❌ {vid}: {err_msg}", "error")
                        self._add_acc_event(state, "❌", "error", vid, "", err_msg)
                        self._check_auto_pause(state)
                        continue

                    result, info = result_data
                    state.current_vacancy_id = vid

                    if result == "sent":
                        state.sent += 1
                        state.campaign_sent += 1  # счётчик кампании (для total_limit)
                        # Daily counter
                        today = datetime.now().strftime("%Y-%m-%d")
                        if state.daily_date != today:
                            state.daily_sent = 0
                            state.daily_date = today
                            state.hard_stopped = False
                        state.daily_sent += 1
                        state.consecutive_errors = 0  # сброс счётчика ошибок
                        # Дополняем info мета-данными из поиска если API не вернул title
                        if not info.get("title"):
                            meta_fb = state.vacancy_meta.get(vid, {})
                            info = {**meta_fb, **info}
                        meta_src = state.vacancy_meta.get(vid, {})
                        info.setdefault("source_url", meta_src.get("source_url"))
                        info.setdefault("source_query", meta_src.get("source_query"))
                        if state.active_campaign_id:
                            info["campaign_id"] = state.active_campaign_id
                        add_applied(acc["name"], vid, info)

                        # Collect HR contact if available
                        contact = info.get("contact", {})
                        if contact and (contact.get("email") or contact.get("fio")):
                            with self._hr_contacts_lock:
                                if len(self.hr_contacts) < 500:
                                    self.hr_contacts.append({
                                        "vacancy_id": vid,
                                        "title": info.get("title", ""),
                                        "company": info.get("company", ""),
                                        "fio": contact.get("fio", ""),
                                        "email": contact.get("email", ""),
                                        "phone": contact.get("phone", ""),
                                        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                        "acc": state.short,
                                    })

                        title = info.get("title", "Неизвестно")
                        company = info.get("company", "?")
                        sal_from = info.get("salary_from")
                        sal_to = info.get("salary_to")
                        salary = ""
                        if sal_from or sal_to:
                            salary = f"{sal_from or '?'} - {sal_to or '?'}"

                        state.current_vacancy_title = title
                        state.current_vacancy_company = company
                        state.action_history.append(f"✅ {title[:30]}")

                        self._add_response(state, vid, title, company, "sent", salary)
                        self._add_log(
                            state.short, state.color,
                            f"✅ {title[:40]} @ {company[:20]}",
                            "success",
                        )
                        self._add_acc_event(state, "✅", "sent", title or vid, company,
                                            salary if salary else "")

                    elif result == "test":
                        title = info.get("title", "")
                        company = info.get("company", "")
                        display_title = title[:40] if title else vid

                        if not eff_apply_tests:
                            # Откликаться на тесты выключено — пропускаем
                            state.tests += 1
                            add_test_vacancy(vid, title, company,
                                             acc["name"], acc.get("resume_hash", ""))
                            state.action_history.append(f"⏭️ {display_title[:25]}")
                            self._add_response(state, vid, title, company, "test")
                            self._add_log(state.short, state.color,
                                          f"⏭️ Тест пропущен: {display_title}", "info")
                            self._add_acc_event(state, "⏭️", "test_skip",
                                                title or vid, company, "пропущено")
                        else:
                            # Пробуем автозаполнить опрос
                            q_result, q_info = asyncio.run(fill_and_submit_questionnaire(
                                acc, vid, vacancy_title=title, company=company))
                            if q_result == "sent":
                                state.sent += 1
                                state.questionnaire_sent += 1
                                state.consecutive_errors = 0
                                # Daily counter
                                today = datetime.now().strftime("%Y-%m-%d")
                                if state.daily_date != today:
                                    state.daily_sent = 0
                                    state.daily_date = today
                                    state.hard_stopped = False
                                state.daily_sent += 1
                                state.current_vacancy_title = title
                                state.current_vacancy_company = company
                                state.action_history.append(f"\U0001f4dd {display_title[:25]}")
                                self._add_response(state, vid, title, company, "sent")
                                self._add_log(state.short, state.color,
                                              f"\U0001f4dd Опрос пройден: {display_title}", "success")
                                q_info_full = {**state.vacancy_meta.get(vid, {}), **info}
                                if state.active_campaign_id:
                                    q_info_full["campaign_id"] = state.active_campaign_id
                                add_applied(acc["name"], vid, q_info_full)
                                answer_preview = CONFIG.questionnaire_default_answer[:50]
                                self._add_acc_event(state, "\U0001f4dd", "questionnaire",
                                                    title or vid, company,
                                                    f"Ответ: {answer_preview}")
                            elif q_result == "limit":
                                state.limit_exceeded = True
                                state.limit_reset_time = datetime.now() + timedelta(
                                    minutes=CONFIG.limit_check_interval
                                )
                                state.status = "limit"
                                state.status_detail = f"Проверка в {state.limit_reset_time.strftime('%H:%M')}"
                                self._add_log(state.short, state.color,
                                              f"\U0001f6ab ЛИМИТ при опросе! Повторная попытка в {state.limit_reset_time.strftime('%H:%M')}",
                                              "error")
                                break
                            else:
                                # Не удалось — считаем неудачи
                                state._test_failures[vid] = state._test_failures.get(vid, 0) + 1
                                if state._test_failures[vid] >= 2:
                                    # Permanently mark as failed test after 2 attempts
                                    add_test_vacancy(vid, title, company,
                                                     acc["name"], acc.get("resume_hash", ""))
                                state.tests += 1
                                state.action_history.append(f"\U0001f9ea {display_title[:25]}")
                                self._add_response(state, vid, title, company, "test")
                                self._add_log(state.short, state.color,
                                              f"\U0001f9ea Тест (не пройден, попытка {state._test_failures[vid]}): {display_title}", "warning")
                                self._add_acc_event(state, "\U0001f9ea", "test",
                                                    title or vid, company, "не пройден")

                    elif result == "already":
                        state.already_applied += 1
                        already_info = state.vacancy_meta.get(vid, {})
                        add_applied(acc["name"], vid, already_info if already_info else None)
                        state.action_history.append(f"\U0001f504 {vid}")
                        self._add_response(state, vid, "", "", "already")

                    elif result == "limit":
                        state.limit_exceeded = True
                        if CONFIG.stop_on_hh_limit:
                            # Hard stop — no retries
                            state.hard_stopped = True
                            state.paused = True
                            state.status = "limit"
                            state.status_detail = "\U0001f6d1 Лимит HH — остановлен до завтра"
                            self._add_log(
                                state.short, state.color,
                                f"\U0001f6d1 ЛИМИТ HH! Бот остановлен. Сбросится в 00:00 МСК. Снимите паузу вручную.",
                                "error",
                            )
                        else:
                            state.limit_reset_time = datetime.now() + timedelta(
                                minutes=CONFIG.limit_check_interval
                            )
                            state.status = "limit"
                            state.status_detail = f"Проверка в {state.limit_reset_time.strftime('%H:%M')}"
                            self._add_log(
                                state.short, state.color,
                                f"\U0001f6ab ЛИМИТ! Повторная попытка в {state.limit_reset_time.strftime('%H:%M')}",
                                "error",
                            )
                        break

                    elif result == "auth_error":
                        if state.use_oauth or CONFIG.use_oauth_apply:
                            # OAuth mode — don't stop, just log warning
                            self._add_log(
                                state.short, state.color,
                                "⚠️ Web cookies истекли (OAuth откликов продолжает работать)", "warning",
                            )
                            state.consecutive_errors += 1
                            self._check_auto_pause(state)
                        else:
                            state.cookies_expired = True
                            state.paused = True
                            self._add_log(
                                state.short, state.color,
                                "⚠️ Куки протухли! Обновите куки и снимите паузу.", "error",
                            )
                            self._add_acc_event(state, "⚠️", "error", "Авторизация", "", "Обновите куки")
                            break

                    elif result == "error":
                        state.errors += 1
                        state.consecutive_errors += 1
                        state.action_history.append(f"❌ {vid}")
                        self._add_response(state, vid, "", "", "error")
                        raw = info.get("raw", "")[:80] if info else ""
                        exc = info.get("exception", "") if info else ""
                        debug_info = raw or exc or "unknown"
                        self._add_log(state.short, state.color, f"❌ {vid}: {debug_info}", "error")
                        self._add_acc_event(state, "❌", "error", vid, "", debug_info[:60])
                        self._check_auto_pause(state)

                if state.limit_exceeded:
                    break

                i += batch_size
                if i < len(filtered):
                    _apply_pause()  # пауза между пачками откликов

            # Очистка
            state.current_vacancy_id = ""
            state.current_vacancy_title = ""
            state.current_vacancy_company = ""
            if state.short in self.vacancy_queues:
                self.vacancy_queues[state.short] = {
                    "vacancies": [],
                    "current": 0,
                    "color": state.color,
                }

            if not state.limit_exceeded:
                state.status = "waiting"
                state.status_detail = "Цикл завершён"
                state.wait_until = datetime.now() + timedelta(seconds=CONFIG.pause_between_cycles)
                self._add_log(
                    state.short, state.color,
                    f"⏳ Цикл завершён, пауза {CONFIG.pause_between_cycles}с",
                    "info",
                )
                time.sleep(CONFIG.pause_between_cycles)

    async def _collect_all_urls_parallel(self, state: AccountState) -> tuple:
        """
        Параллельный сбор вакансий со ВСЕХ URL и страниц одновременно.
        Возвращает (results_by_url: dict[url, set[ids]], salary_map: dict[vid, int|None], schedule_map: dict[vid, set])
        """
        acc = state.acc
        xsrf = acc.get("cookies", {}).get("_xsrf", "")
        if not xsrf:
            return {}, {}, {}
        headers = get_headers(xsrf)
        sem = asyncio.Semaphore(CONFIG.max_concurrent * 3)

        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        connector = aiohttp.TCPConnector(ssl=ssl_context, limit=CONFIG.max_concurrent * 3)

        all_tasks = []
        url_pages = _url_pages_map()
        acc_url_pages = acc.get("url_pages", {})  # per-account override
        effective_urls = acc.get("urls") or [_url_entry(u)["url"] for u in CONFIG.url_pool]
        # Build extra search filter params from config
        # Note: HH only accepts ONE label param; low_competition takes priority
        extra_params = ""
        if CONFIG.filter_low_competition:
            extra_params += "&label=low_performance"
        elif CONFIG.filter_agencies:
            extra_params += "&label=not_from_agency"
        if CONFIG.search_period_days > 0:
            extra_params += f"&search_period={CONFIG.search_period_days}"
        for url_idx, url in enumerate(effective_urls):
            pages = acc_url_pages.get(url) or url_pages.get(url, CONFIG.pages_per_url)
            sep = "&" if "?" in url else "?"
            for page in range(pages):
                page_url = f"{url}{sep}page={page}{extra_params}"
                all_tasks.append((url_idx, url, page, page_url))

        total_tasks = len(all_tasks)
        results_by_url = {url: [] for url in effective_urls}
        salary_map = {}
        completed = 0

        async with aiohttp.ClientSession(
            headers=headers, cookies=acc["cookies"], connector=connector
        ) as session:
            async def fetch_one(url_idx, url, page, page_url):
                nonlocal completed
                html = await fetch_page(session, page_url, sem)
                completed += 1
                state.current_url_idx = url_idx
                state.current_url = url
                state.current_page = page + 1
                state.status_detail = f"Загрузка {completed}/{total_tasks}"
                if html and _is_login_page(html):
                    if not (state.use_oauth or CONFIG.use_oauth_apply):
                        state.cookies_expired = True
                    return url, set(), {}, {}, {}
                if html:
                    ids = parse_ids(html)
                    salaries = parse_salaries(html, ids)
                    meta = parse_vacancy_meta(html)
                    schedules = parse_work_schedules(html, ids)
                    return url, ids, salaries, meta, schedules
                return url, set(), {}, {}, {}

            tasks = [
                fetch_one(url_idx, url, page, page_url)
                for url_idx, url, page, page_url in all_tasks
            ]
            task_results = await asyncio.gather(*tasks, return_exceptions=True)

            schedule_map = {}
            url_queries = {}
            for result in task_results:
                if isinstance(result, Exception):
                    log_debug(f"❌ Ошибка при загрузке: {result}")
                    continue
                url, ids, salaries, meta, schedules = result
                results_by_url[url].extend(ids)
                salary_map.update(salaries)
                state.vacancy_meta.update(meta)
                # Запоминаем источник (поисковый URL/запрос) для каждой вакансии.
                # setdefault → первый URL, на котором встретилась вакансия, побеждает.
                query = url_queries.get(url)
                if query is None:
                    query = extract_search_query(url)
                    url_queries[url] = query
                for vid in ids:
                    entry = state.vacancy_meta.setdefault(vid, {})
                    entry.setdefault("source_url", url)
                    entry.setdefault("source_query", query)
                for vid, sched_set in schedules.items():
                    if sched_set:
                        schedule_map.setdefault(vid, set()).update(sched_set)

        return {url: set(ids) for url, ids in results_by_url.items()}, salary_map, schedule_map

    def _process_llm_replies(self, state: AccountState) -> None:
        """Check recent unread negotiations for employer messages and auto-reply using LLM."""
        if not state.llm_enabled:
            return
        # Non-blocking: if another thread is already processing this account, skip
        if not state._llm_lock.acquire(blocking=False):
            log_debug(f"LLM [{state.short}]: уже выполняется, пропуск")
            return
        try:
            self._process_llm_replies_inner(state)
        finally:
            state._llm_lock.release()

    def _process_llm_replies_inner(self, state: AccountState) -> None:
        """Inner implementation — called only when _llm_lock is held."""
        replied = 0

        # Sync _llm_no_chat from persisted DB (catches 409 failures from previous sessions)
        state._llm_no_chat.update(get_no_chat_neg_ids())

        # Fetch recent chat pages sorted by last activity. Chats needing reply
        # (employer just wrote) will always be near the top.
        self._add_log(state.short, state.color, "\U0001f916 LLM: загружаю список чатов…", "info")
        log_debug(f"LLM [{state.short}]: загружаю чат-лист")
        items_by_id, display_info, cur_pid = _fetch_chat_list(state.acc, max_pages=3)
        log_debug(f"LLM [{state.short}]: чат-лист загружен, {len(items_by_id)} чатов")

        # Process items that need a reply: NEGOTIATION type, unread, from employer, not rejection
        candidates = []
        skipped_ours = 0
        skipped_system = 0
        skipped_read = 0
        skipped_locked = 0
        for item_id, item in items_by_id.items():
            if item.get("type") != "NEGOTIATION":
                continue
            unread = item.get("unreadCount", 0)
            last_msg = item.get("lastMessage") or {}
            sender_id = last_msg.get("participantId", "")
            last_text = (last_msg.get("text") or "")[:40]
            wf = last_msg.get("workflowTransition") or {}
            from_employer = bool(sender_id and cur_pid and sender_id != cur_pid)
            # Early check: known 409 (persisted from DB or current session)
            if item_id in state._llm_no_chat:
                skipped_locked += 1
                log_debug(f"LLM [{state.short}] {item_id}: 409-закрыт, пропуск кандидата")
                continue
            # Early check: chat locked via text/flags (employer disabled messaging or invite-only)
            if _check_chat_locked(item):
                skipped_locked += 1
                log_debug(f"LLM [{state.short}] {item_id}: чат заблокирован, пропуск кандидата «{last_text}»")
                continue
            # Early check: writePossibility from chatik API
            write_poss = (item.get("writePossibility") or {}).get("name", "")
            if write_poss not in ("ENABLED_FOR_ALL", "ENABLED_FOR_ALL_BY_EMPLOYER", ""):
                skipped_locked += 1
                log_debug(f"LLM [{state.short}] {item_id}: writePossibility={write_poss}, пропуск")
                continue
            if unread == 0:
                if from_employer and not wf:
                    last_msg_id_early = str((item.get("lastMessage") or {}).get("id", ""))
                    key_early = (str(item_id), last_msg_id_early)
                    if key_early not in state.llm_replied_msgs:
                        log_debug(f"LLM [{state.short}] {item_id}: unread=0 но от работодателя, не отвечали — добавляю кандидатом: «{last_text}»")
                    else:
                        skipped_read += 1
                        di = display_info.get(str(item_id), {})
                        upsert_interview(str(item_id), acc=state.short, acc_color=state.color,
                                         employer=di.get("subtitle", ""), vacancy_title=di.get("title", ""),
                                         chat_status="waiting_hr")
                        log_debug(f"LLM [{state.short}] {item_id}: unread=0, от работодателя, уже отвечали, пропуск: «{last_text}»")
                        continue
                else:
                    skipped_read += 1
                    continue
            if cur_pid and sender_id == cur_pid:
                skipped_ours += 1
                log_debug(f"LLM [{state.short}] {item_id}: unread={unread}, последнее наше, пропуск")
                di = display_info.get(str(item_id), {})
                upsert_interview(str(item_id), acc=state.short, acc_color=state.color,
                                 employer=di.get("subtitle", ""), vacancy_title=di.get("title", ""),
                                 chat_status="waiting_hr")
                continue
            if wf:
                wf_id = wf.get("id", "") if isinstance(wf, dict) else ""
                if isinstance(wf_id, str) and wf_id:
                    skipped_system += 1
                    log_debug(f"LLM [{state.short}] {item_id}: unread={unread}, системное событие wf={wf_id!r}, пропуск")
                    continue
                log_debug(f"LLM [{state.short}] {item_id}: unread={unread}, wf.id={wf_id!r} (числовой, реальное сообщение)")
            log_debug(f"LLM [{state.short}] {item_id}: ✅ кандидат unread={unread}, от={sender_id}, «{last_text}» | "
                      f"keys={list(item.keys())} canSend={item.get('canSendMessage')} state={item.get('state')} "
                      f"permissions={item.get('permissions')} actions={item.get('actions')}")
            candidates.append(item_id)

        log_debug(f"LLM [{state.short}]: {len(candidates)} кандидатов (прочитанных: {skipped_read}, наших: {skipped_ours}, системных: {skipped_system})")
        if not candidates:
            state.llm_pending_chats = 0
            state.llm_status = f"\U0001f4a4 Нет новых (наших: {skipped_ours}, закр.: {skipped_locked})"
            self._add_log(state.short, state.color,
                f"\U0001f916 LLM: нет новых сообщений (прочит.: {skipped_read}, наших: {skipped_ours}, сист.: {skipped_system}, закрыт: {skipped_locked})", "info")
            return

        state.llm_pending_chats = len(candidates)
        state.llm_status = f"\U0001f504 Обработка {len(candidates)} чатов..."
        self._add_log(state.short, state.color, f"\U0001f916 LLM: {len(candidates)} чатов требуют ответа", "info")

        for i, neg_id in enumerate(candidates[:15]):  # limit to 15 per cycle
            if not state.llm_enabled or not CONFIG.llm_enabled:
                self._add_log(state.short, state.color, f"\U0001f916 LLM: выключен в процессе цикла, прерываю", "warning")
                break
            try:
                if neg_id in state._llm_no_chat:
                    item = items_by_id.get(neg_id, {})
                    info = display_info.get(str(neg_id), {})
                    emp = (info.get("subtitle") or neg_id).strip(" ,")[:25]
                    self._add_log(state.short, state.color,
                        f"\U0001f916 [{emp}] \U0001f512 переписка закрыта, пропуск", "warning", neg_id=neg_id)
                    continue

                item = items_by_id.get(neg_id)
                if not item:
                    log_debug(f"LLM [{state.short}] {neg_id}: не найден в items_by_id, пропуск")
                    continue
                thread = _build_thread_from_chat_item(item, display_info, cur_pid, neg_id)
                employer_short = thread.get("employer_name", neg_id)[:25]
                if thread.get("error"):
                    self._add_log(state.short, state.color, f"\U0001f916 [{employer_short}] ошибка треда: {thread['error']}", "error", neg_id=neg_id)
                    continue

                employer = thread.get("employer_name", neg_id)[:35]
                employer_msg = thread.get("last_employer_msg", "")
                vacancy_title = thread.get("vacancy_title", "")

                if not thread.get("needs_reply") and not thread.get("chat_locked"):
                    raw_item = items_by_id.get(neg_id, {})
                    raw_unread = raw_item.get("unreadCount", 0)
                    raw_last = raw_item.get("lastMessage") or {}
                    raw_sender = raw_last.get("participantId", "")
                    if raw_unread == 0 and cur_pid and raw_sender and raw_sender != cur_pid:
                        thread["needs_reply"] = True
                        if not employer_msg:
                            employer_msg = (raw_last.get("text") or "").strip()
                            thread["last_employer_msg"] = employer_msg

                if thread.get("chat_locked"):
                    lock_reason = thread["chat_locked"]
                    log_debug(f"LLM [{state.short}] {neg_id}: переписка недоступна — {lock_reason!r}")
                    self._add_log(state.short, state.color,
                        f"\U0001f916 [{employer_short}] \U0001f512 переписка недоступна, пропуск", "warning", neg_id=neg_id)
                    state.llm_replied_msgs.add((neg_id, "locked"))
                    upsert_interview(neg_id, acc=state.short, acc_color=state.color, chat_status="locked")
                    continue

                upsert_interview(neg_id, acc=state.short, acc_color=state.color,
                                 employer=employer, vacancy_title=vacancy_title,
                                 employer_last_msg=employer_msg if employer_msg else None,
                                 needs_reply=bool(thread.get("needs_reply")))

                if not thread.get("needs_reply"):
                    log_debug(f"LLM [{state.short}] {neg_id}: ответ не нужен (последнее сообщение — от соискателя)")
                    upsert_interview(neg_id, acc=state.short, acc_color=state.color, chat_status="waiting_hr")
                    self._add_log(state.short, state.color, f"\U0001f916 [{employer_short}] последнее сообщение наше, пропуск", "info", neg_id=neg_id)
                    continue
                last_msg_id = thread["last_msg_id"]
                key = (neg_id, last_msg_id)
                if key in state.llm_replied_msgs:
                    log_debug(f"LLM [{state.short}] {neg_id}: уже отвечали на msg {last_msg_id}")
                    self._add_log(state.short, state.color, f"\U0001f916 [{employer_short}] уже отвечали в этой сессии, пропуск", "info", neg_id=neg_id)
                    continue
                # Черновик по этому чату уже ждёт подтверждения в очереди — не регенерируем
                draft_id = f"{state.short}:{neg_id}"
                with self._llm_pending_lock:
                    if draft_id in self.llm_pending:
                        log_debug(f"LLM [{state.short}] {neg_id}: черновик уже в очереди подтверждения, пропуск")
                        continue
                # Сообщение не требует ответа (вежливая отписка/уведомление без вопроса)
                if self._msg_needs_no_reply(employer_msg):
                    state.llm_replied_msgs.add(key)
                    upsert_interview(neg_id, acc=state.short, acc_color=state.color, chat_status="waiting_hr")
                    self._add_log(state.short, state.color,
                        f"\U0001f916 [{employer_short}] не требует ответа — пропуск", "info", neg_id=neg_id)
                    continue
                _skip_until = state._llm_temp_skip.get(key, 0)
                if time.time() < _skip_until:
                    mins = max(1, int((_skip_until - time.time()) / 60))
                    self._add_log(state.short, state.color,
                        f"\U0001f916 [{employer_short}] повтор через ~{mins}м (ошибка в предыдущем цикле)", "info", neg_id=neg_id)
                    log_debug(f"LLM [{state.short}] {neg_id}: temp_skip до {_skip_until:.0f}")
                    continue
                global_key = (cur_pid, neg_id, last_msg_id)
                with self._llm_sent_lock:
                    if global_key in self._llm_sent_global:
                        log_debug(f"LLM [{state.short}] {neg_id}: уже отправлено другим аккаунтом (pid={cur_pid})")
                        self._add_log(state.short, state.color, f"\U0001f916 [{employer_short}] уже отправлено другим аккаунтом, пропуск", "info")
                        state.llm_replied_msgs.add(key)
                        continue

                progress = f"[{i+1}/{min(len(candidates),15)}]"
                self._add_log(state.short, state.color,
                    f"\U0001f916 {progress} [{employer_short}]: «{employer_msg[:50]}»", "info", neg_id=neg_id)
                log_debug(f"LLM [{state.short}] {progress} {neg_id} ({employer_short}): загружаю историю чата")
                cover_letter = state.acc.get("letter", "") if CONFIG.llm_use_cover_letter else ""
                # Fetch resume for LLM context
                if CONFIG.llm_use_resume:
                    rh = state.acc.get("resume_hash", "")
                    _cached = rh and rh in _resume_cache and (time.time() - _resume_cache[rh][1] < _RESUME_CACHE_TTL)
                    resume_text = fetch_all_resume_texts(state.acc)
                    if resume_text:
                        src = "кэш" if _cached else "загружено"
                        two = " ×2" if state.acc.get("resume_hash_2") else ""
                        self._add_log(state.short, state.color,
                            f"\U0001f916 \U0001f4c4 Резюме в контексте LLM ({src}{two}, {len(resume_text)} симв.)", "info", neg_id=neg_id)
                    else:
                        self._add_log(state.short, state.color,
                            f"\U0001f916 \U0001f4c4 Резюме не удалось загрузить — LLM работает без него", "warning", neg_id=neg_id)
                else:
                    resume_text = ""
                full_history = _fetch_chat_history(state.acc, neg_id, max_messages=20)
                conversation = full_history if full_history else thread["messages"]

                _last_emp_raw = None
                if full_history:
                    for msg_raw in reversed(full_history):
                        if msg_raw.get("sender") == "employer":
                            _last_emp_raw = msg_raw
                            break
                _raw_actions = (_last_emp_raw or {}).get("actions") or {}
                _text_buttons = _raw_actions.get("text_buttons", [])
                _is_bot_msg = (_last_emp_raw or {}).get("is_bot", False)
                if _text_buttons:
                    btn_text = _text_buttons[0].get("text", "ДА")
                    for b in _text_buttons:
                        t_lower = b.get("text", "").lower()
                        if t_lower in ("да", "yes", "согласен", "подтверждаю", "готов", "готова"):
                            btn_text = b["text"]
                            break
                    log_debug(f"LLM [{state.short}] {neg_id}: робот-рекрутер, кнопки={[b.get('text') for b in _text_buttons]}, отвечаю '{btn_text}'")
                    self._add_log(state.short, state.color,
                        f"\U0001f916 [{employer_short}] \U0001f916 Робот → '{btn_text}'", "info", neg_id=neg_id)
                    upsert_interview(neg_id, acc=state.short, acc_color=state.color,
                                     employer=employer_short, vacancy_title=vacancy_title,
                                     chat_status="robot")
                    ok = send_negotiation_message(state.acc, neg_id, btn_text)
                    if ok and ok != "chat_not_found":
                        state.llm_replied_msgs.add(key)
                        replied += 1
                        ts = datetime.now().strftime("%H:%M")
                        self.llm_log.appendleft({
                            "time": ts, "acc": state.short, "color": state.color,
                            "employer": employer_short, "vacancy_title": vacancy_title,
                            "neg_id": neg_id, "employer_msg": employer_msg[:50],
                            "bot_reply": f"\U0001f916 Кнопка: {btn_text}", "sent": True,
                        })
                    elif ok == "chat_not_found":
                        state._llm_no_chat.add(neg_id)
                        state.llm_replied_msgs.add(key)
                        log_debug(f"LLM [{state.short}] {neg_id}: робот-кнопка 409, чат закрыт — добавлен в _llm_no_chat")
                    elif not ok:
                        state._llm_temp_skip[key] = time.time() + 1800
                    continue

                has_employer_msg = any(m.get("sender") == "employer" for m in conversation)
                last_real_sender = conversation[-1].get("sender") if conversation else None
                if not has_employer_msg:
                    log_debug(f"LLM [{state.short}] {neg_id}: нет реальных сообщений работодателя (только системные), пропуск")
                    state.llm_replied_msgs.add(key)
                    continue
                if last_real_sender == "applicant":
                    log_debug(f"LLM [{state.short}] {neg_id}: последнее реальное сообщение наше — уже ответили, пропуск")
                    state.llm_replied_msgs.add(key)
                    continue
                _consecutive_ours = 0
                for _cm in reversed(conversation):
                    if _cm.get("sender") == "applicant":
                        _consecutive_ours += 1
                    else:
                        break
                state._msg_consecutive[neg_id] = _consecutive_ours
                if _consecutive_ours >= 4:
                    log_debug(f"LLM [{state.short}] {neg_id}: in_a_row_limit: {_consecutive_ours} сообщений без ответа HR, пропуск")
                    self._add_log(state.short, state.color,
                        f"\U0001f916 [{employer_short}] ⚠️ in_a_row_limit: {_consecutive_ours} сообщения без ответа HR, пропуск", "warning", neg_id=neg_id)
                    state.llm_replied_msgs.add(key)
                    continue
                log_debug(f"LLM [{state.short}] {neg_id}: история {len(conversation)} сообщений, резюме {len(resume_text)} симв., отправляю в LLM")
                self._add_log(state.short, state.color,
                    f"\U0001f916 {progress} [{employer_short}]: история {len(conversation)} сообщ., жду LLM…", "info", neg_id=neg_id)
                reply_text = generate_llm_reply(conversation, thread.get("employer_name", ""), cover_letter, resume_text)
                # LLM решил, что ответ не нужен (вежливость/уведомление без вопроса)
                if reply_text and "[NO_REPLY]" in reply_text.upper():
                    state.llm_replied_msgs.add(key)
                    upsert_interview(neg_id, acc=state.short, acc_color=state.color, chat_status="waiting_hr")
                    self._add_log(state.short, state.color,
                        f"\U0001f916 [{employer_short}] LLM: ответ не требуется — пропуск", "info", neg_id=neg_id)
                    continue
                if not reply_text:
                    self._add_log(state.short, state.color, f"\U0001f916 [{employer_short}] LLM вернул пустой ответ, повтор через 30м", "warning", neg_id=neg_id)
                    log_debug(f"LLM [{state.short}] {neg_id}: пустой ответ от LLM, ставим temp_skip 30м")
                    state._llm_temp_skip[key] = time.time() + 1800
                    continue
                log_debug(f"LLM [{state.short}] {neg_id}: ответ получен ({len(reply_text)} симв.)")

                ts = datetime.now().strftime("%d.%m %H:%M")

                if CONFIG.llm_auto_send:
                    with self._llm_sent_lock:
                        if global_key in self._llm_sent_global:
                            log_debug(f"LLM [{state.short}] {neg_id}: другой поток уже отправил (pid={cur_pid}), пропуск")
                            self._add_log(state.short, state.color, f"\U0001f916 [{employer_short}] другой аккаунт уже отправил, пропуск", "info")
                            state.llm_replied_msgs.add(key)
                            continue
                        self._llm_sent_global.add(global_key)
                    self._add_log(state.short, state.color,
                        f"\U0001f916 [{employer_short}] отправляю: «{reply_text[:60]}»", "info", neg_id=neg_id)
                    log_debug(f"LLM [{state.short}] {neg_id}: отправляю сообщение в chatik")
                    ok = send_negotiation_message(state.acc, neg_id, reply_text, topic_id=thread.get("topic_id", ""))
                    if ok == "chat_not_found":
                        with self._llm_sent_lock:
                            self._llm_sent_global.discard(global_key)
                        state.llm_replied_msgs.add(key)
                        state._llm_no_chat.add(neg_id)
                        upsert_interview(neg_id, acc=state.short, acc_color=state.color,
                                         employer=employer, vacancy_title=vacancy_title,
                                         chat_not_found=True)
                        self._add_log(state.short, state.color,
                            f"\U0001f916 [{employer_short}] \U0001f512 переписка закрыта (409), пропуск", "warning", neg_id=neg_id)
                        continue
                    if ok:
                        state.llm_replied_msgs.add(key)
                        state._msg_consecutive[neg_id] = state._msg_consecutive.get(neg_id, 0) + 1
                        replied += 1
                        upsert_interview(neg_id, acc=state.short, acc_color=state.color,
                                         llm_reply=reply_text, llm_sent=True)
                        self._add_log(state.short, state.color,
                            f"\U0001f916 Авто-ответ → {employer}: {reply_text[:60]}…", "success", neg_id=neg_id)
                        self.llm_log.appendleft({
                            "time": ts, "acc": state.short, "color": state.color,
                            "employer": employer, "vacancy_title": vacancy_title,
                            "neg_id": neg_id, "employer_msg": employer_msg,
                            "bot_reply": reply_text, "sent": True,
                        })
                    else:
                        with self._llm_sent_lock:
                            self._llm_sent_global.discard(global_key)
                        state._llm_temp_skip[key] = time.time() + 1800
                        upsert_interview(neg_id, acc=state.short, acc_color=state.color,
                                         llm_reply=reply_text, llm_sent=False)
                        self._add_log(state.short, state.color,
                            f"\U0001f916 Черновик (ошибка отправки, повтор ~30м) → {employer}: {reply_text[:60]}…", "warning", neg_id=neg_id)
                        self.llm_log.appendleft({
                            "time": ts, "acc": state.short, "color": state.color,
                            "employer": employer, "vacancy_title": vacancy_title,
                            "neg_id": neg_id, "employer_msg": employer_msg,
                            "bot_reply": reply_text, "sent": False,
                        })
                else:
                    # Режим очереди: черновик НЕ отправляем, кладём на подтверждение.
                    # llm_replied_msgs НЕ трогаем — пометим только после реальной отправки.
                    with self._llm_pending_lock:
                        self.llm_pending[draft_id] = {
                            "draft_id": draft_id,
                            "neg_id": neg_id,
                            "topic_id": thread.get("topic_id", ""),
                            "employer": employer,
                            "vacancy_title": vacancy_title,
                            "employer_msg": employer_msg,
                            "draft": reply_text,
                            "ts": ts,
                            "acc": state.short,
                            "color": state.color,
                            "_state": state,
                            "_key": key,
                            "_global_key": global_key,
                        }
                    upsert_interview(neg_id, acc=state.short, acc_color=state.color,
                                     llm_reply=reply_text, llm_sent=False)
                    self._add_log(state.short, state.color,
                        f"\U0001f916 Черновик в очередь [{employer}]: {reply_text[:80]}…", "info", neg_id=neg_id)
                    self.llm_log.appendleft({
                        "time": ts, "acc": state.short, "color": state.color,
                        "employer": employer, "vacancy_title": vacancy_title,
                        "neg_id": neg_id, "employer_msg": employer_msg,
                        "bot_reply": reply_text, "sent": False,
                    })

                time.sleep(3)  # rate limit between messages
            except Exception as e:
                log_debug(f"_process_llm_replies {neg_id}: {e}")
                try:
                    with self._llm_sent_lock:
                        to_remove = {gk for gk in self._llm_sent_global if gk[1] == neg_id}
                        self._llm_sent_global -= to_remove
                except Exception:
                    pass

        state.llm_replied_count += replied
        if replied:
            state.llm_status = f"✅ {replied} ответов отправлено"
            log_debug(f"LLM auto-reply [{state.short}]: {replied} ответов отправлено")
        elif candidates:
            state.llm_status = f"⏳ {len(candidates)} чатов, 0 отправлено"

    def _fetch_hh_stats_worker(self, idx: int, state: AccountState) -> None:
        """Thread worker for HH stats polling"""
        try:
            self._fetch_hh_stats_worker_inner(idx, state)
        except Exception as e:
            log_debug(f"STATS WORKER CRASHED [{state.short}]: {e}")
            import traceback
            log_debug(traceback.format_exc())

    def _fetch_hh_stats_worker_inner(self, idx: int, state: AccountState) -> None:
        while not self._stop_event.is_set():
            while self.paused and not self._stop_event.is_set() and not getattr(state, '_deleted', False):
                time.sleep(2)
            if self._stop_event.is_set() or getattr(state, '_deleted', False):
                break

            state.hh_stats_loading = True
            try:
                stats = fetch_hh_negotiations_stats(state.acc)
                if stats.get("auth_error"):
                    state.cookies_expired = True
                    self._add_log(
                        state.short, state.color,
                        "⚠️ Куки протухли! (HH stats) Обновите куки.", "error",
                    )
                    state.hh_stats_loading = False
                    self._stop_event.wait(max(CONFIG.llm_check_interval * 60, 120))
                    continue
                old_interviews = state.hh_interviews
                state.hh_interviews = stats["interview"]
                state.hh_interviews_recent = stats["recent_interview"]
                state.hh_viewed = stats["viewed"]
                state.hh_not_viewed = stats["not_viewed"]
                state.hh_discards = stats["discard"]
                state.hh_interviews_list = stats["interviews_list"]
                # Telegram notification for new interviews
                if stats.get("recent_interview", 0) > state.hh_interviews_recent:
                    for inv in stats.get("interviews_list", [])[:3]:
                        notify_interview(inv.get("text", "")[:60], inv.get("company", "") or "", state.short)
                state.hh_interview_neg_ids = stats.get("neg_ids", [])
                state.hh_unread_by_employer = stats.get("unread_by_employer", 0)

                for neg_id in state.hh_interview_neg_ids:
                    upsert_interview(neg_id, acc=state.short, acc_color=state.color)
                if len(state.hh_interview_neg_ids) == len(stats["interviews_list"]):
                    for neg_id, item in zip(state.hh_interview_neg_ids, stats["interviews_list"]):
                        parts = item.get("text", "").rsplit(" ", 1)
                        upsert_interview(neg_id, acc=state.short, acc_color=state.color,
                                         vacancy_title=item.get("text", ""))

                offers = fetch_hh_possible_offers(state.acc)
                state.hh_possible_offers = offers

                rs = fetch_resume_stats(state.acc)
                state.resume_views_7d = rs["views"]
                state.resume_views_new = rs["views_new"]
                state.resume_shows_7d = rs["shows"]
                state.resume_invitations_7d = rs["invitations"]
                state.resume_invitations_new = rs["invitations_new"]
                state.resume_next_touch_seconds = rs["next_touch_seconds"]
                state.resume_free_touches = rs["free_touches"]
                state.resume_global_invitations = rs["global_invitations"]
                state.resume_new_invitations_total = rs["new_invitations_total"]

                state.resume_view_history = fetch_resume_view_history(state.acc, limit=100)

                state.hh_stats_updated = datetime.now()

                if old_interviews > 0 and stats["interview"] > old_interviews:
                    new_count = stats["interview"] - old_interviews
                    self._add_log(
                        state.short, state.color,
                        f"\U0001f3af НОВОЕ ПРИГЛАШЕНИЕ! (+{new_count} интервью)",
                        "success",
                    )

                log_debug(
                    f"HH stats {state.short}: {stats['interview']} интервью, "
                    f"{rs['views']} просмотров резюме, {rs['new_invitations_total']} новых инвайтов"
                )

                if self.paused or state.paused:
                    log_debug(f"LLM [{state.short}]: пропуск — на паузе")
                    state.hh_stats_loading = False
                    time.sleep(max(CONFIG.llm_check_interval * 60, 120))
                    continue

                _has_llm = CONFIG.llm_api_key or any(
                    p.get("api_key") for p in (CONFIG.llm_profiles or []) if p.get("enabled", True)
                )
                _neg_count = len(state.hh_interview_neg_ids)
                if not CONFIG.llm_enabled:
                    log_debug(f"LLM [{state.short}]: пропуск — глобально выключено")
                elif not _has_llm:
                    self._add_log(state.short, state.color, "\U0001f916 LLM: нет API ключа ни в одном профиле", "warning")
                elif not state.llm_enabled:
                    log_debug(f"LLM [{state.short}]: пропуск — выключено для аккаунта")
                else:
                    if _neg_count:
                        self._add_log(state.short, state.color, f"\U0001f916 LLM: проверяю {_neg_count} переговоров…", "info")
                    else:
                        self._add_log(state.short, state.color, "\U0001f916 LLM: нет переговоров в статусе Интервью, проверяю чаты…", "info")
                    self._process_llm_replies(state)
            except Exception as e:
                log_debug(f"HH stats fetch error ({state.short}): {e}")
            finally:
                state.hh_stats_loading = False

            time.sleep(max(CONFIG.llm_check_interval * 60, 120))
