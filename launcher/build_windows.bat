@echo off
chcp 65001 >nul
echo ============================================
echo   BiliLearn-AI Launcher - Windows Build
echo ============================================
echo.

cd /d "%~dp0"

rem 优先使用项目自己的虚拟环境。
rem 用系统 PATH 里的 python 打包很容易踩坑：精简版 / Microsoft Store 版 Python 不带 tkinter，
rem 打出来的 exe 双击会直接闪退，或报 ModuleNotFoundError: No module named 'tkinter'。
set "PY=..\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

echo [1/4] 检查打包环境...
"%PY%" -c "import tkinter" 2>nul
if errorlevel 1 (
    echo.
    echo [错误] 当前 Python 没有 tkinter，打出来的启动器会闪退。
    echo        请改用项目自带的 ..\.venv，或安装 python.org 的完整版 Python。
    echo        当前解释器：
    "%PY%" -c "import sys; print('       ' + sys.executable)"
    echo.
    pause
    exit /b 1
)
"%PY%" -c "import sys; print('      使用解释器: ' + sys.executable)"

echo.
echo [2/4] 安装打包依赖...
"%PY%" -m pip install pyinstaller customtkinter pillow pystray requests --index-url https://pypi.org/simple
if errorlevel 1 (
    echo 依赖安装失败（网络不通可换回国内镜像：-i https://pypi.tuna.tsinghua.edu.cn/simple）
    pause
    exit /b 1
)

echo.
echo [3/4] 打包中...
rem 必须用 spec 打包：里面写着 fastdeps / pycompat 两个 hiddenimport。
rem 用命令行参数（--onefile --windowed ...）会重写 spec 并丢掉这两个，导致 exe 运行时报 ImportError。
"%PY%" -m PyInstaller --noconfirm BiliLearn-AI-Launcher.spec
if errorlevel 1 (
    echo 打包失败
    pause
    exit /b 1
)

echo.
echo [4/4] 完成!
echo 输出文件: dist\BiliLearn-AI-Launcher.exe
echo.
pause
