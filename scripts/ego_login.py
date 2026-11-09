"""Вход в hh.ru через браузер ego lite: куки уходят прямо в дашборд бота.

    python scripts/ego_login.py                    дашборд на этом компьютере (127.0.0.1:8000)
    python scripts/ego_login.py --target aisy-core дашборд на сервере, через ssh-туннель

Не вошёл в hh.ru — скрипт откроет страницу входа в ego lite и попросит запустить его ещё раз.
Значения кук не печатаются: их забирает и отправляет сам ego-browser.
"""
import argparse
import json
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
TUNNEL_PORT = 18000


def _port_open(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _dashboard_alive(base: str) -> bool:
    try:
        with urllib.request.urlopen(base + "/api/sessions", timeout=5) as r:
            return r.status == 200
    except Exception:
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="local", help="local или имя ssh-хоста (aisy-core)")
    ap.add_argument("--port", type=int, default=8000, help="порт дашборда на целевой машине")
    ap.add_argument("--name", default="", help="имя аккаунта в дашборде (по умолчанию из профиля hh)")
    a = ap.parse_args()

    tunnel = None
    if a.target == "local":
        base = f"http://127.0.0.1:{a.port}"
    else:
        if _port_open(TUNNEL_PORT):
            print(f"✗ порт {TUNNEL_PORT} занят, закрой старый туннель")
            return 2
        tunnel = subprocess.Popen(["ssh", "-N", "-o", "ExitOnForwardFailure=yes",
                                   "-L", f"{TUNNEL_PORT}:127.0.0.1:{a.port}", a.target])
        for _ in range(40):
            if _port_open(TUNNEL_PORT):
                break
            time.sleep(0.25)
        base = f"http://127.0.0.1:{TUNNEL_PORT}"
    try:
        if not _dashboard_alive(base):
            print(f"✗ дашборд не отвечает на {a.target}:{a.port}. Запусти бота и повтори.")
            return 2
        if sys.platform == "darwin":
            subprocess.run(["open", "-a", "ego lite"], check=False)
        cfg = {"base": base, "name": a.name}
        script = f"globalThis.__CFG = {json.dumps(cfg)};\n" + (HERE / "ego_login.mjs").read_text(encoding="utf-8")
        r = subprocess.run(["ego-browser", "nodejs"], input=script, capture_output=True, text=True,
                           encoding="utf-8", timeout=180)
        line = next((l[l.index("EGO_LOGIN "):] for l in (r.stdout + "\n" + r.stderr).splitlines()
                     if "EGO_LOGIN " in l), None)
        if not line:
            print("✗ ego-browser не вернул результат:\n" + (r.stderr or r.stdout)[-1500:])
            return 2
        res = json.loads(line[len("EGO_LOGIN "):])
        mark = "✓" if res.get("ok") else "✗"
        print(f"{mark} {res.get('message', '')}")
        if res.get("ok"):
            print(f"  аккаунт: {res.get('name')} (idx {res.get('idx')}), куки: {', '.join(res.get('keys', []))}")
        return 0 if res.get("ok") else (3 if res.get("need_login") else 1)
    finally:
        if tunnel:
            tunnel.terminate()


if __name__ == "__main__":
    sys.exit(main())
