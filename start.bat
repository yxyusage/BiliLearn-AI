@echo off
title BiliLearn-AI Launcher
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" goto CREATE_VENV
call ".venv\Scripts\activate.bat"
powershell -NoProfile -Command "if ((Test-Path 'backend\requirements.txt') -and ((-not (Test-Path '.venv\.requirements.stamp')) -or ((Get-Item 'backend\requirements.txt').LastWriteTime -gt (Get-Item '.venv\.requirements.stamp').LastWriteTime))) { exit 1 } else { exit 0 }"
if errorlevel 1 goto INSTALL_DEPS
goto CHECK_FRONTEND

:CREATE_VENV
echo [First run] Creating virtual environment...
python -m venv .venv
call ".venv\Scripts\activate.bat"

:INSTALL_DEPS
echo [Deps] Installing/upgrading dependencies (2-5 minutes on first run)...
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
copy /y backend\requirements.txt .venv\.requirements.stamp >nul

:CHECK_FRONTEND
set NEED_BUILD=0
if not exist "frontend\node_modules" set NEED_BUILD=1
powershell -NoProfile -Command "if (Test-Path 'frontend\dist\index.html') { $newest = Get-ChildItem -Recurse -File -Path frontend\src, frontend\package.json -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1; if ($newest -and $newest.LastWriteTime -gt (Get-Item 'frontend\dist\index.html').LastWriteTime) { exit 1 } else { exit 0 } } else { exit 1 }"
if errorlevel 1 set NEED_BUILD=1
if not "%NEED_BUILD%"=="1" goto START

echo [Frontend] Code changed or build missing, rebuilding...
pushd frontend
if not exist "node_modules" call npm install
call npm run build
popd

:START
echo [Start] Launching at http://localhost:8000 ...
start "" http://localhost:8000
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir backend
