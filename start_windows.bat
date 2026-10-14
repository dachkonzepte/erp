@echo off
setlocal
cd /d %~dp0
if not exist .venv\Scripts\activate.bat (
  echo Die virtuelle Umgebung fehlt. Bitte zuerst setup_windows.bat ausfuehren.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
rem Seit 1.8.107: ausdruecklich lokaler Betrieb ueber reines HTTP -- ohne ERP_ENV waere das Anmelde-Cookie Secure (siehe .env.example)
set ERP_ENV=development
start "" http://127.0.0.1:8000
uvicorn app.main:app --host 127.0.0.1 --port 8000
