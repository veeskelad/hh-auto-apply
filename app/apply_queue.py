"""Очередь откликов «бот готовит — владелец жмёт» (решение владельца 14.11.2026).

hh пропускает около 13 автоматических откликов за 24 часа, дальше капча (`.tasks/captcha-why.md`).
В режиме очереди (CONFIG.manual_apply или поле кампании manual_apply) бот не отправляет отклик
в hh: письмо и ответы анкеты ложатся сюда, @ninjiu_bot присылает карточку, отклик на hh владелец
отправляет сам. «Отправил» в боте записывает вакансию в отклики (storage.add_applied).

data/apply_queue.json: {"next_id": N, "items": {"<id>": {...}}}
status: open — ждёт владельца, done — отправил, skipped — пропустил.
Пишет только процесс дашборда (бот ходит через API), поэтому хватает блокировки потока.
"""
import json
import threading
from datetime import datetime
from pathlib import Path

from app.logging_utils import log_debug

QUEUE_FILE = Path("data") / "apply_queue.json"
STATUSES = ("open", "done", "skipped")

_lock = threading.Lock()
_cache: dict = None


def _load() -> dict:
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
        except FileNotFoundError:
            _cache = {}
        except (OSError, ValueError) as e:
            log_debug(f"⚠️ apply_queue: не прочитал {QUEUE_FILE}: {e}")
            _cache = {}
        _cache.setdefault("next_id", 1)
        _cache.setdefault("items", {})
    return _cache


def _save() -> None:
    QUEUE_FILE.parent.mkdir(exist_ok=True, parents=True)
    tmp = QUEUE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(_cache, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(QUEUE_FILE)


def reset_cache() -> None:
    """Для тестов: перечитать файл при следующем обращении."""
    global _cache
    with _lock:
        _cache = None


def find(account: str, vid: str) -> dict:
    with _lock:
        for it in _load()["items"].values():
            if it["account"] == account and it["vacancy_id"] == str(vid):
                return dict(it)
    return {}


def is_queued(account: str, vid: str) -> bool:
    """Вакансия уже в очереди (в любом статусе): бот её второй раз не готовит."""
    return bool(find(account, vid))


def add(account: str, vid: str, info: dict) -> dict:
    """Положить подготовленный отклик. Повтор той же вакансии возвращает уже лежащую запись."""
    vid = str(vid)
    with _lock:
        q = _load()
        for it in q["items"].values():
            if it["account"] == account and it["vacancy_id"] == vid:
                return dict(it)
        iid = str(q["next_id"])
        q["next_id"] += 1
        item = {
            "id": iid, "account": account, "vacancy_id": vid,
            "title": info.get("title", ""), "company": info.get("company", ""),
            "salary": info.get("salary", ""),
            "url": f"https://hh.ru/vacancy/{vid}",
            "response_url": f"https://hh.ru/applicant/vacancy_response?vacancyId={vid}",
            "letter": info.get("letter", ""), "qa": info.get("qa") or [],
            "note": info.get("note", ""), "campaign_id": info.get("campaign_id"),
            "meta": info.get("meta") or {},
            "status": "open", "created_at": datetime.now().isoformat(timespec="seconds"),
            "closed_at": None,
        }
        q["items"][iid] = item
        _save()
        return dict(item)


def items(status: str = "") -> list:
    """Записи по возрастанию id; status='' — все."""
    with _lock:
        out = [dict(it) for it in _load()["items"].values() if not status or it["status"] == status]
    return sorted(out, key=lambda it: int(it["id"]))


def get(iid: str) -> dict:
    with _lock:
        it = _load()["items"].get(str(iid))
        return dict(it) if it else {}


def close(iid: str, status: str) -> dict:
    """open → done | skipped. Возвращает запись ({} — нет такой). Закрытую повторно не меняет."""
    if status not in ("done", "skipped"):
        raise ValueError(status)
    with _lock:
        it = _load()["items"].get(str(iid))
        if not it:
            return {}
        if it["status"] == "open":
            it["status"] = status
            it["closed_at"] = datetime.now().isoformat(timespec="seconds")
            _save()
        return dict(it)
