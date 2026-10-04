@echo off
title BiliLearn-AI Launcher
cd /d "%~dp0"
chcp 65001 >nul

where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.10+ 并在安装时勾选 "Add Python to PATH"
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" goto CREATE_VENV
call ".venv\Scripts\activate.bat"
powershell -NoProfile -Command "if ((Test-Path 'backend\requirements.txt') -and ((-not (Test-Path '.venv\.requirements.stamp')) -or ((Get-Item 'backend\requirements.txt').LastWriteTime -gt (Get-Item '.venv\.requirements.stamp').LastWriteTime))) { exit 1 } else { exit 0 }"
if errorlevel 1 goto INSTALL_DEPS
goto CHECK_FRONTEND

:CREATE_VENV
echo [First run] Creating virtual environment...
python -m venv .venv
if errorlevel 1 (
    echo [错误] 创建虚拟环境失败
    pause
    exit /b 1
)
call ".venv\Scripts\activate.bat"

:INSTALL_DEPS
echo [Deps] Installing/upgrading dependencies (2-5 minutes on first run)...
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
if errorlevel 1 (
    echo [错误] 依赖安装失败，请检查网络连接
    pause
    exit /b 1
)
copy /y backend\requirements.txt .venv\.requirements.stamp >nul

:CHECK_FRONTEND
set NEED_BUILD=0
if not exist "frontend\node_modules" set NEED_BUILD=1
powershell -NoProfile -Command "if (Test-Path 'frontend\dist\index.html') { $newest = Get-ChildItem -Recurse -File -Path frontend\src, frontend\package.json -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1; if ($newest -and $newest.LastWriteTime -gt (Get-Item 'frontend\dist\index.html').LastWriteTime) { exit 1 } else { exit 0 } } else { exit 1 }"
if errorlevel 1 set NEED_BUILD=1
if not "%NEED_BUILD%"=="1" goto START

where npm >nul 2>nul
if errorlevel 1 (
    echo [错误] 未检测到 Node.js/npm，无法构建前端页面，请先安装 Node.js 18+
    pause
    exit /b 1
)

echo [Frontend] Code changed or build missing, rebuilding...
pushd frontend
if not exist "node_modules" call npm install
call npm run build
if errorlevel 1 (
    echo [错误] 前端构建失败
    popd
    pause
    exit /b 1
)
popd

:START
echo [Start] Launching at http://localhost:8000 ...
start "" /min cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:8000"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir backend