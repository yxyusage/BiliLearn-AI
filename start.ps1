$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$APP_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $APP_DIR

function Log($msg) { Write-Host $msg }

function Test-ProxyAlive($proxyUrl) {
    try {
        $u = [Uri]$proxyUrl
        if (-not $u.Host) { return $false }
        $port = if ($u.Port -ge 0) { $u.Port } else { 80 }
        $client = New-Object System.Net.Sockets.TcpClient
        $async = $client.BeginConnect($u.Host, $port, $null, $null)
        $ok = $async.AsyncWaitHandle.WaitOne(1500)
        if ($ok -and $client.Connected) { $client.EndConnect($async); $client.Close(); return $true }
        $client.Close(); return $false
    } catch { return $false }
}

$proxyUrl = $env:HTTPS_PROXY; if (-not $proxyUrl) { $proxyUrl = $env:HTTP_PROXY }
if ($proxyUrl) {
    if (Test-ProxyAlive $proxyUrl) {
        Log "[OK] 使用系统代理"
    } else {
        Log "[WARN] 系统代理不可达，已自动绕过"
        $env:HTTP_PROXY = $null; $env:HTTPS_PROXY = $null
        $env:http_proxy = $null; $env:https_proxy = $null
        $env:ALL_PROXY = $null; $env:all_proxy = $null
    }
}

Log "============================================"
Log "  BiliLearn-AI"
Log "============================================"

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Log "[ERROR] 未检测到 Python，请先安装 Python 3.10+"
    Log "下载地址 https://www.python.org/downloads/"
    Read-Host "按回车键退出"
    exit 1
}

$pyVersion = & python -c "import sys; print('%d.%d' % sys.version_info[:2])"
Log "[OK] Python $pyVersion"

$venvPython = Join-Path $APP_DIR ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Log "[1/3] 创建虚拟环境..."
    python -m venv .venv
    Log "[1/3] 完成"
}

$reqFile = Join-Path $APP_DIR "backend\requirements.txt"
$stampFile = Join-Path $APP_DIR ".venv\.requirements.stamp"
$needInstall = $true
if ((Test-Path $stampFile) -and (Test-Path $reqFile)) {
    if ((Get-Item $stampFile).LastWriteTime -ge (Get-Item $reqFile).LastWriteTime) {
        $needInstall = $false
    }
}

if ($needInstall) {
    Log "[2/3] 安装 Python 依赖..."
    $mirrors = @(
        "https://mirrors.aliyun.com/pypi/simple/",
        "https://pypi.tuna.tsinghua.edu.cn/simple",
        "https://pypi.org/simple/"
    )
    $installed = $false
    foreach ($mirror in $mirrors) {
        Log "  尝试 $mirror ..."
        & $venvPython -m pip install -r $reqFile -i $mirror `
            --default-timeout=20 --retries 2 --disable-pip-version-check `
            --trusted-host pypi.tuna.tsinghua.edu.cn `
            --trusted-host mirrors.aliyun.com `
            --trusted-host pypi.org 2>&1 | ForEach-Object { Write-Host "  $_" }
        if ($LASTEXITCODE -eq 0) {
            $installed = $true
            break
        }
    }
    if (-not $installed) {
        Log "[ERROR] 依赖安装失败，请检查网络"
        Read-Host "按回车键退出"
        exit 1
    }
    Copy-Item $reqFile $stampFile -Force
    Log "[2/3] 完成"
} else {
    Log "[2/3] 依赖已是最新"
}

$distIndex = Join-Path $APP_DIR "frontend\dist\index.html"
$needFrontendBuild = $true
if (Test-Path $distIndex) {
    $newestSrc = Get-ChildItem -Path "frontend\src","frontend\package.json" -Recurse -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($newestSrc -and $newestSrc.LastWriteTime -le (Get-Item $distIndex).LastWriteTime) {
        $needFrontendBuild = $false
    }
}

if ($needFrontendBuild) {
    Log "[3/3] 构建前端..."
    $npm = Get-Command npm -ErrorAction SilentlyContinue
    if (-not $npm) {
        Log "[ERROR] 未检测到 Node.js/npm，请安装 Node 18+"
        Read-Host "按回车键退出"
        exit 1
    }
    Push-Location frontend
    if (-not (Test-Path "node_modules")) {
        npm install --no-audit --no-fund
    }
    npm run build
    Pop-Location
    Log "[3/3] 完成"
} else {
    Log "[3/3] 前端已是最新"
}

$listeners = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
foreach ($c in $listeners) {
    $old = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
    if ($old -and $old.ProcessName -match "python") {
        Log "[WARN] 8000 端口被旧实例占用，正在关闭..."
        Stop-Process -Id $old.Id -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
    }
}

Log "============================================"
Log "  服务已启动 http://localhost:8000"
Log "  按 Ctrl+C 停止"
Log "============================================"

Start-Job -ScriptBlock {
    Start-Sleep -Seconds 3
    Start-Process "http://localhost:8000"
} | Out-Null

& $venvPython -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir backend
