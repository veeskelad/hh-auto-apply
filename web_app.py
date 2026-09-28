"""HH.RU Auto Response Bot - FastAPI Web Dashboard"""
import os
from pathlib import Path


def _load_dotenv():
    """Минимальная загрузка .env в окружение (без внешних зависимостей).

    Выполняется ДО импорта app, т.к. модули читают os.environ на этапе импорта.
    Существующие переменные окружения имеют приоритет (setdefault).
    """
    env = Path(".env")
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip())


_load_dotenv()

from app.hh_transport import install as _install_hh_transport

_install_hh_transport()

from app.routes import app  # noqa: E402
import uvicorn  # noqa: E402

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host=os.environ.get("HOST", "127.0.0.1"), port=port, log_level="info")
