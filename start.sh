#!/usr/bin/env bash
# BiliLearn-AI 一键启动（macOS / Linux）
set -e
cd "$(dirname "$0")"

export HF_ENDPOINT=https://hf-mirror.com

echo "============================================"
echo "  BiliLearn-AI 一键启动（首次运行需几分钟）"
echo "============================================"

if ! command -v python3 >/dev/null 2>&1; then
  echo "[错误] 未检测到 python3，请先安装 Python 3.10+"
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "[1/4] 首次运行：创建虚拟环境..."
  python3 -m venv .venv
fi

if [ ! -d ".venv/lib" ] || [ ! -f ".venv/bin/uvicorn" ]; then
  echo "[2/4] 首次运行：安装后端依赖（约 1-3 分钟）..."
  .venv/bin/pip install -r backend/requirements.txt -q
fi

if [ ! -d "frontend/dist" ]; then
  echo "[3/4] 首次运行：安装并构建前端（约 2-5 分钟）..."
  (cd frontend && npm install --no-audit --no-fund && npm run build)
fi

echo "[4/4] 启动中..."

# 端口占用自动清理（仅关闭 python 旧实例）
if command -v lsof >/dev/null 2>&1; then
  PIDS=$(lsof -ti tcp:8000 2>/dev/null || true)
  if [ -n "$PIDS" ]; then
    echo "[提示] 8000 端口被旧程序占用，正在自动关闭旧实例..."
    for pid in $PIDS; do
      if ps -p "$pid" -o comm= 2>/dev/null | grep -qi python; then
        kill -9 "$pid" 2>/dev/null || true
      fi
    done
    sleep 2
  fi
fi

echo "浏览器访问 http://localhost:8000"
echo "      （按 Ctrl+C 停止程序；下次运行本脚本即可再次启动）"
.venv/bin/python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
