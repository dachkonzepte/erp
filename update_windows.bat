@echo off
setlocal
cd /d %~dp0
set APP_VERSION=unbekannt
if exist VERSION set /p APP_VERSION=<VERSION
if not exist .venv\Scripts\activate.bat (
  echo Keine bestehende Python-Umgebung gefunden.
  echo Bitte stattdessen setup_windows.bat ausfuehren.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Update fehlgeschlagen.
  pause
  exit /b 1
)
echo.
echo Update auf DACHKONZEPTE ERP Version %APP_VERSION% abgeschlossen.
echo Jetzt start_windows.bat ausfuehren.
pause
