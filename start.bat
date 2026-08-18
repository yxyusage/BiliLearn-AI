@echo off
chcp 65001 >nul
title BiliLearn-AI 启动器
cd /d "%~dp0"

echo.
echo  ============================================
echo   BiliLearn-AI 一键启动（首次运行需要几分钟）
echo  ============================================
echo.

rem 国内网络加速：语音模型走镜像
set HF_ENDPOINT=https://hf-mirror.com

rem 1. 检查 Python
python --version >nul 2>nul
if errorlevel 1 (
  echo  [错误] 未检测到 Python，请先安装：https://www.python.org/downloads/
  echo         安装时务必勾选 "Add Python to PATH"
  pause
  exit /b 1
)

rem 2. 创建虚拟环境（仅第一次）
if not exist .venv (
  echo  [1/4] 首次运行：创建虚拟环境...
  python -m venv .venv
)

rem 3. 安装后端依赖（仅第一次）
if not exist .venv\Lib\site-packages\fastapi (
  echo  [2/4] 首次运行：安装后端依赖（约 1-3 分钟）...
  .venv\Scripts\pip install -r backend\requirements.txt -q
)

rem 4. 构建前端（仅第一次）
if not exist frontend\dist (
  echo  [3/4] 首次运行：安装并构建前端（约 2-5 分钟）...
  pushd frontend
  call npm install --no-audit --no-fund >nul 2>nul
  call npm run build >nul 2>nul
  popd
)

echo  [4/4] 正在启动，浏览器将自动打开 http://localhost:8000
echo        （关闭本窗口即停止程序；下次双击本文件即可再次启动）
start "" /b cmd /c "timeout /t 4 /nobreak >nul & start http://localhost:8000"
.venv\Scripts\python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
pause
