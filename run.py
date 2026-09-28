"""Запуск дашборда и кампании на macOS, Linux и Windows.

    python run.py            только дашборд
    python run.py devops     дашборд + кампания, в имени которой есть «devops»

С кампанией сервер сам останавливается, когда кончился дневной лимит или вся кампания.
Обычно вызывается из run.sh или run.bat, которые готовят .venv.
"""
import asyncio
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASE = "http://127.0.0.1:8000"


def keep_awake(pid: int) -> None:
    """Компьютер не засыпает, пока жив сервер."""
    if sys.platform == "darwin":
        subprocess.Popen(["caffeinate", "-i", "-w", str(pid)])
    elif sys.platform == "win32":
        import ctypes
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)


def http(method: str, path: str):
    req = urllib.request.Request(BASE + path, method=method, data=b"" if method == "POST" else None)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8") or "null")


def wait_ready(server: subprocess.Popen) -> bool:
    while server.poll() is None:
        try:
            urllib.request.urlopen(BASE + "/", timeout=2)
            return True
        except Exception:
            time.sleep(1)
    return False


def find_campaign(name: str) -> str:
    d = http("GET", "/api/campaigns")
    d = d if isinstance(d, list) else d.get("campaigns", [])
    return next((c["id"] for c in d if name.lower() in c.get("name", "").lower()), "")


async def _campaign_done() -> bool:
    import websockets
    async with websockets.connect(BASE.replace("http", "ws") + "/ws") as ws:
        d = json.loads(await asyncio.wait_for(ws.recv(), 10))
        d = d.get("data", d)
        return any(a.get("status") == "limit" or str(a.get("status_detail", "")).startswith("Кампания завершена")
                   for a in d.get("accounts", []))


def campaign_done() -> bool:
    try:
        return asyncio.run(_campaign_done())
    except Exception:
        return False


def main() -> int:
    os.chdir(ROOT)
    sys.stdout.reconfigure(line_buffering=True)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))  # kill тоже гасит сервер
    (ROOT / "data").mkdir(exist_ok=True)
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}  # кириллица в данных на Windows
    log = open(ROOT / "data" / "server.log", "ab")
    server = subprocess.Popen([sys.executable, "web_app.py"], stdout=log, stderr=subprocess.STDOUT, env=env)
    try:
        keep_awake(server.pid)
        if not wait_ready(server):
            print("Дашборд не запустился, смотри data/server.log")
            return 1
        print(f"Дашборд: {BASE}")

        if len(sys.argv) < 2:
            server.wait()
            return 0

        cid = find_campaign(sys.argv[1])
        if not cid:
            print(f"Кампания «{sys.argv[1]}» не найдена")
            return 1
        print(http("POST", f"/api/campaigns/{cid}/start"))

        while server.poll() is None:
            time.sleep(60)
            if campaign_done():
                print(f"{datetime.now():%H:%M} Отклики на сегодня закончились, сервер остановлен")
                return 0
        return 0
    except KeyboardInterrupt:
        return 0
    finally:
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(10)
            except subprocess.TimeoutExpired:
                server.kill()


if __name__ == "__main__":
    sys.exit(main())
