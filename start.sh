#!/usr/bin/env bash
# BiliLearn-AI 一键启动（macOS / Linux）
set -e
cd "$(dirname "$0")"

# 语音识别模型默认走国内镜像：huggingface.co 在国内经常连不上，首次转写会卡在下载模型。
# 已经自己设过 HF_ENDPOINT 就尊重用户设置（也可在网页「设置 → 模型下载源」里改）。
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"

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
        --timeout=60 --retries 5 --disable-pip-version-check \
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

# 前端：缺少构建产物、或源码比产物新时，重新构建（与 start.ps1 行为一致）
need_frontend=0
if [ ! -f "frontend/dist/index.html" ]; then
  need_frontend=1
else
  newest_src=$(find frontend/src frontend/package.json -type f -newer frontend/dist/index.html 2>/dev/null | head -n 1 || true)
  if [ -n "$newest_src" ]; then need_frontend=1; fi
fi
if [ "$need_frontend" -eq 1 ]; then
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

APP_VERSION=$(sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' frontend/package.json 2>/dev/null | head -n 1 || true)
DATA_DIR="${BILI_DATA_DIR:-$HOME/BiliLearn-AI}"
echo "============================================"
echo "  服务已启动 http://localhost:8000"
echo "  版本       v${APP_VERSION}"
echo "  数据目录   ${DATA_DIR}"
echo "  模型源     ${HF_ENDPOINT}"
echo "  （升级/重新解压不会丢笔记，可在网页「设置」页导出/导入存档）"
echo "  按 Ctrl+C 停止"
echo "============================================"
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir backend
