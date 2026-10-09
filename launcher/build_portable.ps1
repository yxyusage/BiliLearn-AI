# 打包 Windows 便携版：BiliLearn-AI-v<版本>-portable.zip
# 用法（在项目根目录）：powershell -ExecutionPolicy Bypass -File launcher\build_portable.ps1
#
# 便携版 = 源码 + 已构建的 frontend/dist + 根目录的 BiliLearn-AI-Launcher.exe
# 不含 .venv / node_modules / 数据目录 / 构建产物：用户首次启动由启动器自动装依赖。
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $root "backend\app\main.py"))) {
    throw "找不到 backend/app/main.py，请把本脚本放在项目的 launcher 目录下运行"
}

$pkg = Get-Content (Join-Path $root "frontend\package.json") -Raw | ConvertFrom-Json
$version = $pkg.version
$zipPath = Join-Path $root ("BiliLearn-AI-v" + $version + "-portable.zip")
$stage = Join-Path ([System.IO.Path]::GetTempPath()) ("bililearn-package-" + $version)
$stageRoot = Join-Path $stage "BiliLearn-AI"

Write-Host ("=== 打包 BiliLearn-AI v" + $version + " ===")

$distIndex = Join-Path $root "frontend\dist\index.html"
if (-not (Test-Path $distIndex)) {
    Write-Host "[1/4] 前端尚未构建，执行 npm run build ..."
    Push-Location (Join-Path $root "frontend")
    if (-not (Test-Path "node_modules")) { npm install --no-audit --no-fund }
    npm run build
    Pop-Location
} else {
    Write-Host "[1/4] 复用已有 frontend/dist"
}

$exe = Join-Path $root "BiliLearn-AI-Launcher.exe"
if (-not (Test-Path $exe)) { $exe = Join-Path $root "launcher\dist\BiliLearn-AI-Launcher.exe" }
if (-not (Test-Path $exe)) {
    throw "找不到 BiliLearn-AI-Launcher.exe，请先运行 launcher\build_windows.bat 打包启动器"
}

Write-Host "[2/4] 拷贝文件到暂存目录 ..."
Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $stageRoot | Out-Null
$excludeDirs = @(
    (Join-Path $root ".git"),
    (Join-Path $root ".venv"),
    (Join-Path $root ".preview"),
    (Join-Path $root "frontend\node_modules"),
    (Join-Path $root "backend\data"),
    (Join-Path $root "launcher\build"),
    (Join-Path $root "launcher\dist"),
    (Join-Path $root "问题汇总")
)
$excludeFiles = @(
    (Join-Path $root "friend_error.png"),
    (Join-Path $root "start.bat - 快捷方式.lnk")
)
robocopy $root $stageRoot /E /XD @excludeDirs __pycache__ /XF @excludeFiles *.pyc *.zip /NFL /NDL /NJH /NJS /NP /R:1 /W:1 | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy 拷贝失败（exit=$LASTEXITCODE）" }

Copy-Item $exe (Join-Path $stageRoot "BiliLearn-AI-Launcher.exe") -Force

Write-Host "[3/4] 压缩 ..."
Remove-Item $zipPath -Force -ErrorAction SilentlyContinue
Compress-Archive -Path $stageRoot -DestinationPath $zipPath -CompressionLevel Optimal -Force

Write-Host "[4/4] 清理暂存目录 ..."
Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue

$info = Get-Item $zipPath
$files = (Get-ChildItem $zipPath).Count
Write-Host ""
Write-Host ("完成 : " + $zipPath)
Write-Host ("大小 : " + ("{0:N1} MB" -f ($info.Length / 1MB)))
Write-Host ("SHA256 : " + (Get-FileHash $zipPath -Algorithm SHA256).Hash)
