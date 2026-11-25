@echo off
setlocal
cd /d %~dp0
rem seit 1.11.27: Python 3.14 wie auf dem Server -- zuerst der Starter py mit 3.14, sonst python, wenn es 3.14 ist
where py >nul 2>nul
if not errorlevel 1 goto use_py
where python >nul 2>nul
if not errorlevel 1 goto use_python
goto pythonmissing

:use_python
set PYTHON_CMD=python
goto setup

:use_py
set PYTHON_CMD=py -3.14
goto setup

:setup
%PYTHON_CMD% -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 14) else 1)"
if errorlevel 1 goto pythonmissing
%PYTHON_CMD% --version
%PYTHON_CMD% -m venv .venv
if errorlevel 1 goto setupfailed
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 goto setupfailed
echo.
echo Einrichtung abgeschlossen.
echo Danach start_windows.bat ausfuehren.
pause
exit /b 0

:pythonmissing
echo Python 3.14 wurde nicht gefunden.
echo Bitte Python 3.14 installieren (wie auf dem Server, https://www.python.org/downloads/).
pause
exit /b 1

:setupfailed
echo Einrichtung fehlgeschlagen. Bitte die Fehlermeldung oben pruefen.
pause
exit /b 1
