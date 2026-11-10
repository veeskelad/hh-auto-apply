#!/usr/bin/env python3
"""Прогон кампаний по очереди на уже запущенном дашборде — для cron (Hermes, systemd timer).

    python3 scripts/hh_cron.py devops Ai-engineer      кампании по частям имени, по очереди
    python3 scripts/hh_cron.py --max-hours 3 devops

На одном аккаунте активна одна кампания, поэтому они идут друг за другом: следующая стартует,
когда у текущей кончился дневной лимит или вся кампания. Счётчик «отправлено сегодня» общий
для аккаунта: у второй кампании daily_limit должен быть больше, чем у первой. Протухший вход или лимит hh —
остановка всех. Печатает [SILENT], если всё штатно (итог дня — в hh_digest.py), иначе строку
с проблемой.
"""
import argparse
import asyncio
import json
import os
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

BASE = os.environ.get("HH_API_BASE", "http://127.0.0.1:8000")


def http(method: str, path: str, body: dict = None):
    data = json.dumps(body).encode() if body is not None else (b"" if method == "POST" else None)
    req = urllib.request.Request(BASE + path, method=method, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8") or "null")


async def _snapshot() -> dict:
    import websockets
    async with websockets.connect(BASE.replace("http", "ws") + "/ws") as ws:
        d = json.loads(await asyncio.wait_for(ws.recv(), 15))
        return d.get("data", d)


def accounts() -> list:
    try:
        return asyncio.run(_snapshot()).get("accounts", [])
    except Exception:
        return []


def run_campaign(cid: str, name: str, deadline: float) -> str:
    """'' — кампания дошла до лимита; иначе причина остановки."""
    res = http("POST", f"/api/campaigns/{cid}/start")
    if not (res or {}).get("ok", True) and res.get("error"):
        return f"«{name}» не запустилась: {res['error']}"
    time.sleep(90)  # дать воркеру сменить статус прошлой кампании
    while time.time() < deadline:
        for a in accounts():
            if a.get("cookies_expired"):
                return "вход в hh.ru протух"
            detail = str(a.get("status_detail", ""))
            if a.get("status") == "captcha":
                return "hh просит капчу"
            if a.get("status") == "limit" or detail.startswith("Кампания завершена"):
                return ""
            if "лимит hh" in detail.lower() or "negotiations-limit" in detail:
                return "hh: исчерпан дневной лимит откликов аккаунта"
        time.sleep(60)
    return f"«{name}» не уложилась во время, остановлена"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="+")
    ap.add_argument("--max-hours", type=float, default=3.0, help="на каждую кампанию")
    ap.add_argument("--notify", action="store_true", help="проблему записать уведомлением в data/notifications")
    a = ap.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from app.hh_transport import proxy_alive
    _load_env()
    cool = captcha_cooldown()
    if cool:
        print(f"⏳ hh: капча была {cool}, кампании сегодня не стартуют (пауза 20 ч)")
        return 0
    if not proxy_alive():
        msg = "⏳ hh: тоннель с Мака не поднят (Мак спит или без сети), кампании сегодня не стартовали"
        print(msg)
        if a.notify:
            _notify(msg)
        return 1
    try:
        camps = http("GET", "/api/campaigns")
    except Exception as e:
        print(f"⚠️ hh: дашборд не отвечает ({e})")
        return 1
    camps = camps if isinstance(camps, list) else camps.get("campaigns", [])
    problems = []
    for name in a.names:
        camp = next((c for c in camps if name.lower() in c.get("name", "").lower()), None)
        if not camp:
            problems.append(f"кампания «{name}» не найдена")
            continue
        why = run_campaign(camp["id"], camp["name"], time.time() + a.max_hours * 3600)
        try:
            http("POST", f"/api/campaigns/{camp['id']}/stop")
        except Exception:
            pass
        if why:
            problems.append(why)
            if "вход" in why or "лимит откликов аккаунта" in why or "капч" in why:
                break
    msg = "⚠️ hh: " + "; ".join(problems) if problems else "[SILENT]"
    print(msg)
    if problems and a.notify:
        _notify(msg)
    return 1 if problems else 0


def captcha_cooldown(hours: float = 20) -> str:
    """Время последней капчи, если она была меньше hours часов назад, иначе ''.
    10.11: повторные запуски после капчи только продлевали флаг isBot на аккаунте."""
    d = Path(__file__).resolve().parent.parent / "data" / "notifications"
    last = None
    for f in d.glob("*_error.json") if d.exists() else []:
        try:
            n = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if n.get("subtype") == "captcha":
            ts = datetime.fromisoformat(n.get("timestamp", "1970-01-01"))
            last = ts if last is None or ts > last else last
    if last and (datetime.now() - last).total_seconds() < hours * 3600:
        return last.strftime("%d.%m %H:%M")
    return ""


def _notify(msg: str) -> None:
    """Запуск в фоне: вывод никто не читает, поэтому проблема уходит уведомлением."""
    d = Path(__file__).resolve().parent.parent / "data" / "notifications"
    d.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    (d / f"{now:%Y%m%d_%H%M%S_%f}_error.json").write_text(json.dumps({
        "type": "error", "title": "", "company": "", "message": msg, "account": "",
        "timestamp": now.isoformat(), "delivered": False}, ensure_ascii=False), encoding="utf-8")


def _load_env() -> None:
    """HH_PROXY и прочее из .env проекта (cron не наследует окружение службы)."""
    env = Path(__file__).resolve().parent.parent / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


if __name__ == "__main__":
    sys.exit(main())
