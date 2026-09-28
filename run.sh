#!/bin/bash
# Запуск дашборда и кампании: ./run.sh devops | ./run.sh ai | ./run.sh (только дашборд)
# С кампанией сервер сам останавливается, когда кончился дневной лимит или вся кампания.
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || { python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt; }
exec .venv/bin/python run.py "$@"
