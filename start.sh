#!/usr/bin/env bash
# BiliLearn-AI 一键启动（macOS / Linux）
set -e
cd "$(dirname "$0")"

export HF_ENDPOINT=https://hf-mirror.com

echo "============================================"
echo "  BiliLearn-AI 一键启动（首次运行需几分钟）"
echo "============================================"

# 智能代理检测：系统代理可用则保留，失效则自动绕过
bypass_dead_proxy() {
  local p="${HTTPS_PROXY:-${https_proxy:-${HTTP_PROXY:-${http_proxy:-}}}}"
  [ -z "$p" ] && return 0
  local host port
  host=$(echo "$p" | sed -E 's#^https?://##' | cut -d: -f1)
  port=$(echo "$p" | sed -E 's#^https?://##' | cut -d: -f2 | cut -d/ -f1)
  [ -z "$port" ] && port=80
  if (echo > "/dev/tcp/$host/$port") >/dev/null 2>&1; then
    echo "[OK] 系统代理可用"
  else
    echo "[WARN] 系统代理 $host:$port 不可达，已自动绕过"
    unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy
  fi
}
bypass_dead_proxy

if ! command -v python3 >/dev/null 2>&1; then
  echo "[错误] 未检测到 python3，请先安装 Python 3.10+"
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "[1/4] 首次运行：创建虚拟环境..."
  python3 -m venv .venv
fi

# 依赖：requirements.txt 有更新时重新安装（用时间戳戳记，避免每次启动都装）
if [ ! -f ".venv/.requirements.stamp" ] || [ "backend/requirements.txt" -nt ".venv/.requirements.stamp" ]; then
  echo "[2/4] 安装后端依赖（约 1-3 分钟）..."
  MIRRORS=(
    "https://mirrors.aliyun.com/pypi/simple/"
    "https://pypi.tuna.tsinghua.edu.cn/simple"
    "https://pypi.org/simple/"
  )
  installed=0
  for m in "${MIRRORS[@]}"; do
    echo "  尝试 $m ..."
    if .venv/bin/pip install -r backend/requirements.txt -i "$m" \
        --default-timeout=20 --retries 2 --disable-pip-version-check \
        --trusted-host mirrors.aliyun.com \
        --trusted-host pypi.tuna.tsinghua.edu.cn \
        --trusted-host pypi.org; then
      installed=1
      break
    fi
  done
  if [ "$installed" -ne 1 ]; then
    echo "[错误] 依赖安装失败，请检查网络"
    exit 1
  fi
  cp backend/requirements.txt .venv/.requirements.stamp
fi

# 前端：缺少构建产物时安装并构建
if [ ! -f "frontend/dist/index.html" ]; then
  if ! command -v npm >/dev/null 2>&1; then
    echo "[错误] 未检测到 npm，请先安装 Node.js 18+"
    exit 1
  fi
  echo "[3/4] 构建前端（约 2-5 分钟）..."
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
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir backend
