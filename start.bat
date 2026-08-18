@echo off
title BiliLearn-AI Launcher
cd /d "%~dp0"

rem China mirror for whisper model download
set HF_ENDPOINT=https://hf-mirror.com

echo.
echo  ============================================
echo   BiliLearn-AI one-click launcher
echo   first run takes a few minutes
echo  ============================================
echo.

rem 1. check python
python --version >nul 2>nul
if not errorlevel 1 goto :py_ok
echo  [ERROR] Python not found.
echo          Install from https://www.python.org/downloads/
echo          and check "Add Python to PATH".
pause
exit /b 1
:py_ok

rem 2. create venv once
if exist .venv goto :venv_ok
echo  [1/4] Creating virtual environment...
python -m venv .venv
:venv_ok

rem 3. install deps once
if exist .venv\Lib\site-packages\fastapi goto :deps_ok
echo  [2/4] Installing backend dependencies, 1-3 min...
.venv\Scripts\pip install -r backend\requirements.txt -q
:deps_ok

rem 4. build frontend once
if exist frontend\dist goto :fe_ok
echo  [3/4] Building frontend, 2-5 min...
pushd frontend
call npm install --no-audit --no-fund >nul 2>nul
call npm run build >nul 2>nul
popd
:fe_ok

rem 5. auto clean port 8000 if stale python instance running
netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul 2>nul
if errorlevel 1 goto :port_ok
echo  [INFO] Port 8000 is busy, closing old instance...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING"') do call :kill_port %%p
timeout /t 2 /nobreak >nul
:port_ok

echo  [4/4] Starting server, browser will open http://localhost:8000
echo        close this window to stop
start "" /b cmd /c "timeout /t 4 /nobreak >nul & start http://localhost:8000"
.venv\Scripts\python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
pause
goto :eof

:kill_port
tasklist /FI "PID eq %1" /FO CSV /NH | findstr /i "python" >nul 2>nul
if errorlevel 1 goto :eof
taskkill /F /PID %1 >nul 2>nul
goto :eof
