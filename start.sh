#!/usr/bin/env bash
# BiliLearn-AI 涓€閿惎鍔紙macOS / Linux锛?set -e
cd "$(dirname "$0")"

export HF_ENDPOINT=https://hf-mirror.com

echo "============================================"
echo "  BiliLearn-AI 涓€閿惎鍔紙棣栨杩愯闇€鍑犲垎閽燂級"
echo "============================================"

# 鏅鸿兘浠ｇ悊妫€娴嬶細绯荤粺浠ｇ悊鍙敤鍒欎繚鐣欙紝澶辨晥鍒欒嚜鍔ㄧ粫杩?bypass_dead_proxy() {
  local p="${HTTPS_PROXY:-${https_proxy:-${HTTP_PROXY:-${http_proxy:-}}}}"
  [ -z "$p" ] && return 0
  local host port
  host=$(echo "$p" | sed -E 's#^https?://##' | cut -d: -f1)
  port=$(echo "$p" | sed -E 's#^https?://##' | cut -d: -f2 | cut -d/ -f1)
  [ -z "$port" ] && port=80
  if (echo > "/dev/tcp/$host/$port") >/dev/null 2>&1; then
    echo "[OK] 绯荤粺浠ｇ悊鍙敤"
  else
    echo "[WARN] 绯荤粺浠ｇ悊 $host:$port 涓嶅彲杈撅紝宸茶嚜鍔ㄧ粫杩?
    unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy
  fi
}
bypass_dead_proxy

if ! command -v python3 >/dev/null 2>&1; then
  echo "[閿欒] 鏈娴嬪埌 python3锛岃鍏堝畨瑁?Python 3.10+"
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "[1/4] 棣栨杩愯锛氬垱寤鸿櫄鎷熺幆澧?.."
  python3 -m venv .venv
fi

# 渚濊禆锛歳equirements.txt 鏈夋洿鏂版椂閲嶆柊瀹夎锛堢敤鏃堕棿鎴虫埑璁帮紝閬垮厤姣忔鍚姩閮借锛?if [ ! -f ".venv/.requirements.stamp" ] || [ "backend/requirements.txt" -nt ".venv/.requirements.stamp" ]; then
  echo "[2/4] 瀹夎鍚庣渚濊禆锛堢害 1-3 鍒嗛挓锛?.."
  MIRRORS=(
    "https://mirrors.aliyun.com/pypi/simple/"
    "https://pypi.tuna.tsinghua.edu.cn/simple"
    "https://pypi.org/simple/"
  )
  installed=0
  for m in "${MIRRORS[@]}"; do
    echo "  灏濊瘯 $m ..."
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
    echo "[閿欒] 渚濊禆瀹夎澶辫触锛岃妫€鏌ョ綉缁?
    exit 1
  fi
  cp backend/requirements.txt .venv/.requirements.stamp
fi

# 鍓嶇锛氱己灏戞瀯寤轰骇鐗╂椂瀹夎骞舵瀯寤?if [ ! -f "frontend/dist/index.html" ]; then
  if ! command -v npm >/dev/null 2>&1; then
    echo "[閿欒] 鏈娴嬪埌 npm锛岃鍏堝畨瑁?Node.js 18+"
    exit 1
  fi
  echo "[3/4] 鏋勫缓鍓嶇锛堢害 2-5 鍒嗛挓锛?.."
  (cd frontend && npm install --no-audit --no-fund && npm run build)
fi

echo "[4/4] 鍚姩涓?.."

# 绔彛鍗犵敤鑷姩娓呯悊锛堜粎鍏抽棴 python 鏃у疄渚嬶級
if command -v lsof >/dev/null 2>&1; then
  PIDS=$(lsof -ti tcp:8000 2>/dev/null || true)
  if [ -n "$PIDS" ]; then
    echo "[鎻愮ず] 8000 绔彛琚棫绋嬪簭鍗犵敤锛屾鍦ㄨ嚜鍔ㄥ叧闂棫瀹炰緥..."
    for pid in $PIDS; do
      if ps -p "$pid" -o comm= 2>/dev/null | grep -qi python; then
        kill -9 "$pid" 2>/dev/null || true
      fi
    done
    sleep 2
  fi
fi

echo "娴忚鍣ㄨ闂?http://localhost:8000"
echo "      锛堟寜 Ctrl+C 鍋滄绋嬪簭锛涗笅娆¤繍琛屾湰鑴氭湰鍗冲彲鍐嶆鍚姩锛?
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir backend
