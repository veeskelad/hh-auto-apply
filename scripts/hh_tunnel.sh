#!/bin/bash
# launchd com.iam.hh-tunnel на Маке: обратный SOCKS-тоннель Мак → сервер.
# Бот на сервере ходит в hh через HH_PROXY=socks5h://127.0.0.1:18790, и hh видит домашний адрес
# Мака (с него же вход в ego), а не адрес дата-центра, который hh считает ботом.
#   scripts/hh_tunnel.sh [хост] [порт]      по умолчанию aisy-core 18790
# Мак спит или без сети — тоннеля нет, бот на сервере ждёт и напрямую в hh не ходит.
set -u
HOST="${1:-aisy-core}"
PORT="${2:-18790}"

# Обрыв (сон Мака) оставляет на сервере зависший sshd, который держит порт. Освобождаем порт,
# только если его держит sshd: чужие процессы (другие тоннели на других портах) не трогаем.
/usr/bin/ssh -o BatchMode=yes -o ConnectTimeout=15 "$HOST" \
  "pid=\$(ss -ltnpH 'sport = :$PORT' | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2); \
   if [ -n \"\$pid\" ] && [ \"\$(ps -o comm= -p \$pid)\" = sshd ]; then kill \$pid; fi; true" || exit 1

exec /usr/bin/ssh -N -o BatchMode=yes -o ExitOnForwardFailure=yes -o ConnectTimeout=15 \
  -o ServerAliveInterval=20 -o ServerAliveCountMax=3 -o TCPKeepAlive=yes \
  -R "127.0.0.1:$PORT" "$HOST"
