@echo off
rem Dashboard + campaign: run.bat devops, run.bat ai, run.bat (dashboard only).
rem With a campaign the server stops by itself when the daily or total limit is reached.
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  py -3.11 -m venv .venv || python -m venv .venv || exit /b 1
  .venv\Scripts\python -m pip install -q -r requirements.txt || exit /b 1
)
.venv\Scripts\python run.py %*
