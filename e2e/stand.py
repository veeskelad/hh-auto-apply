"""Изолированный стенд дашборда для e2e: копия данных из фикстур, свой порт, без выхода наружу.

    python e2e/stand.py              поднять стенд с фикстурами и ждать Ctrl+C
    python e2e/stand.py --empty      то же без аккаунтов (экран подключения)
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "e2e" / "fixtures" / "data"
PORT = int(os.environ.get("E2E_PORT", "8010"))


class Stand:
    def __init__(self, empty: bool = False, port: int = PORT):
        self.empty = empty
        self.port = port
        self.base = f"http://127.0.0.1:{port}"
        self.dir = Path(tempfile.mkdtemp(prefix="hh-e2e-"))
        self.block_log = self.dir / "blocked.log"
        self.proc = None

    def __enter__(self):
        for name in ("app", "static", "web_app.py"):
            (self.dir / name).symlink_to(ROOT / name)
        data = self.dir / "data"
        if self.empty:
            data.mkdir()
        else:
            shutil.copytree(FIXTURES, data)
        env = {**os.environ, "PORT": str(self.port), "HOST": "127.0.0.1", "PYTHONUTF8": "1",
               "PYTHONPATH": str(ROOT / "e2e" / "offline"), "E2E_BLOCK_LOG": str(self.block_log),
               "DASHBOARD_PASSWORD": "", "OPENROUTER_API_KEY": ""}
        log = open(self.dir / "server.log", "ab")
        self.proc = subprocess.Popen([sys.executable, "web_app.py"], cwd=self.dir, env=env,
                                     stdout=log, stderr=subprocess.STDOUT)
        deadline = time.time() + 30
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError(f"стенд упал, лог: {self.dir / 'server.log'}")
            try:
                urllib.request.urlopen(self.base + "/", timeout=2)
                return self
            except Exception:
                time.sleep(0.5)
        raise RuntimeError("стенд не поднялся за 30 с")

    def blocked(self) -> list:
        return self.block_log.read_text(encoding="utf-8").splitlines() if self.block_log.exists() else []

    def __exit__(self, *exc):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        if not os.environ.get("E2E_KEEP"):
            shutil.rmtree(self.dir, ignore_errors=True)


if __name__ == "__main__":
    with Stand(empty="--empty" in sys.argv) as s:
        print(f"Стенд: {s.base}  (данные: {s.dir / 'data'})")
        try:
            s.proc.wait()
        except KeyboardInterrupt:
            pass
