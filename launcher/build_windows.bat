@echo off
chcp 65001 >nul
echo ============================================
echo   BiliLearn-AI Launcher - Windows Build
echo ============================================
echo.

cd /d "%~dp0"

echo [1/3] 安装打包依赖...
pip install pyinstaller customtkinter pillow pystray requests -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo 依赖安装失败
    pause
    exit /b 1
)

echo.
echo [2/3] 打包中...
pyinstaller --noconfirm --onefile --windowed ^
    --name "BiliLearn-AI-Launcher" ^
    --hidden-import customtkinter ^
    --hidden-import PIL ^
    --hidden-import pystray ^
    main.py

if errorlevel 1 (
    echo 打包失败
    pause
    exit /b 1
)

echo.
echo [3/3] 完成!
echo 输出文件: dist\BiliLearn-AI-Launcher.exe
echo.
pause
