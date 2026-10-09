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

# PyInstaller 在 macOS 上按模式产出不同：--windowed 可能生成 .app 包，--onefile 只生成可执行文件。
# 这里按实际产物提示，避免"说的 .app 其实是二进制"。
if [ -d "dist/BiliLearn-AI-Launcher.app" ]; then
    echo "输出: dist/BiliLearn-AI-Launcher.app（可双击运行）"
    echo "把整个 .app 放到项目根目录（与 backend/、frontend/ 同级）后双击即可。"
elif [ -f "dist/BiliLearn-AI-Launcher" ]; then
    chmod +x "dist/BiliLearn-AI-Launcher"
    echo "输出: dist/BiliLearn-AI-Launcher（可执行文件，不是 .app）"
    echo "把它放到项目根目录（与 backend/、frontend/ 同级），然后执行 ./BiliLearn-AI-Launcher"
else
    echo "未找到打包产物，请检查上面的 PyInstaller 日志"
    exit 1
fi
echo ""
