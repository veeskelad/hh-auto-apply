#!/bin/bash
# Раз в неделю (launchd com.iam.hh-ego-login на Маке): свежий вход в hh из ego lite → бот на сервере.
# Не вышло — уведомление в aisy через data/notifications на сервере (его доставляет Hermes).
#   scripts/ego_login_weekly.sh [хост]      по умолчанию aisy-core
# Журнал: ~/Library/Logs/hh-ego-login.log. Значения кук не печатаются (их передаёт ego_login.py).
set -u
cd "$(dirname "$0")/.." || exit 1
TARGET="${1:-aisy-core}"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
PY=/Library/Frameworks/Python.framework/Versions/3.11/bin/python3
[ -x "$PY" ] || PY=python3

# Основная копия — эталон на main: подтянуть только перемоткой, свои правки не трогать
if [ "$(git branch --show-current 2>/dev/null)" = main ] && git fetch -q origin main 2>/dev/null; then
  git merge -q --ff-only origin/main 2>/dev/null || true
fi

was_running=$(osascript -e 'application "ego lite" is running' 2>/dev/null)
out=$("$PY" scripts/ego_login.py --target "$TARGET" 2>&1)
code=$?
echo "$(date '+%F %T') code=$code $(printf '%s' "$out" | tail -2 | tr '\n' ' ')"

if [ "$code" -ne 0 ]; then
  if [ "$code" -eq 3 ]; then subtype=auth; else subtype=""; fi
  msg="🔑 Еженедельная передача входа в hh не прошла (код $code): $(printf '%s' "$out" | tail -1 | cut -c1-200)"
  b64=$(printf '%s' "$msg" | base64 | tr -d '\n')
  ssh -o BatchMode=yes -o ConnectTimeout=20 "$TARGET" "python3 - $b64 $subtype" <<'PY'
import base64, datetime, json, pathlib, sys
msg = base64.b64decode(sys.argv[1]).decode()
sub = sys.argv[2] if len(sys.argv) > 2 else ""
d = pathlib.Path.home() / "projects/hh-auto-apply/data/notifications"
d.mkdir(parents=True, exist_ok=True)
now = datetime.datetime.now()
n = {"type": "error", "title": "", "company": "", "message": msg, "account": "",
     "timestamp": now.isoformat(), "delivered": False}
if sub:
    n["subtype"] = sub
(d / f"{now:%Y%m%d_%H%M%S_%f}_error.json").write_text(json.dumps(n, ensure_ascii=False), encoding="utf-8")
PY
fi

# ego был закрыт до нас — закрыть обратно; при code=3 вкладка входа ждёт человека, не закрываем
if [ "$was_running" = "false" ] && [ "$code" -ne 3 ]; then
  osascript -e 'quit app "ego lite"' >/dev/null 2>&1
fi
exit "$code"
