@echo off
setlocal
cd /d %~dp0
where python >nul 2>nul
if not errorlevel 1 goto use_python
where py >nul 2>nul
if not errorlevel 1 goto use_py
goto pythonmissing

:use_python
set PYTHON_CMD=python
goto setup

:use_py
set PYTHON_CMD=py -3
goto setup

:setup
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
echo Python wurde nicht gefunden.
echo Bitte Python 3.12 oder neuer installieren und "Add Python to PATH" aktivieren.
pause
exit /b 1

:setupfailed
echo Einrichtung fehlgeschlagen. Bitte die Fehlermeldung oben pruefen.
pause
exit /b 1
