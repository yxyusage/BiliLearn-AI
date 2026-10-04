#!/bin/bash
echo "============================================"
echo "  BiliLearn-AI Launcher - macOS Build"
echo "============================================"
echo ""

cd "$(dirname "$0")"

echo "[1/3] 安装打包依赖..."
pip3 install pyinstaller customtkinter pillow pystray requests -i https://pypi.tuna.tsinghua.edu.cn/simple
if [ $? -ne 0 ]; then
    echo "依赖安装失败"
    exit 1
fi

echo ""
echo "[2/3] 打包中..."
pyinstaller --noconfirm --onefile --windowed \
    --name "BiliLearn-AI-Launcher" \
    --hidden-import customtkinter \
    --hidden-import PIL \
    --hidden-import pystray \
    main.py

if [ $? -ne 0 ]; then
    echo "打包失败"
    exit 1
fi

echo ""
echo "[3/3] 完成!"
echo "输出文件: dist/BiliLearn-AI-Launcher.app"
echo ""
