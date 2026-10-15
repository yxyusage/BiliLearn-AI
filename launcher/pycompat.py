"""Python 版本与「依赖装不上」的判断（纯标准库，可单独运行）。

为什么单独拆出来：
- 启动器（tkinter）、start.ps1、start.sh 都需要同一套判断，不该各写一份；
- 只依赖标准库 —— 测试可以直接 import，不用拉起 GUI。

背景（两位用户实测踩到）：
1. Python 3.15 alpha：`ctranslate2` / `onnxruntime` / `av` 这类**编译型包**还没有对应 wheel，
   pip 直接报 ResolutionImpossible / no matching distribution。旧版启动器只会说
   "请检查网络连接"，把用户引到了完全错误的方向。
2. 残留/损坏的 Python 路径：venv 报
   "did not find executable at '...\\Python315\\python.exe'"，因为装着 3.15 alpha 又卸了。

用法：
    python pycompat.py --check                 # 检查当前解释器
    python pycompat.py --check --python <exe>  # 检查指定解释器
    python pycompat.py --check --json          # 输出 JSON（供脚本解析）
退出码：0 = 可用；1 = 不可用（附可读原因）。
"""
import argparse
import json
import os
import re
import subprocess
import sys
from typing import Iterable, List, Optional, Tuple

SUPPORTED_MIN = (3, 10)
SUPPORTED_MAX = (3, 13)      # 与 backend/app/routers/diagnose.py 里的版本检查保持一致
RECOMMENDED = "3.12"
DOWNLOAD_URL = "https://www.python.org/downloads/"

# 编译型依赖：新 Python 发布后它们最晚跟上，是"版本太新装不上"的典型
WHEEL_LAG_PACKAGES = ("ctranslate2", "onnxruntime", "av", "tokenizers", "pydantic-core", "PyMuPDF")


def parse_version(text: str) -> Tuple[int, ...]:
    """从 "3.12.4" / "Python 3.15.0a3" 这类文本里取出版本号。"""
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", str(text or ""))
    if not m:
        return ()
    return tuple(int(x) for x in m.groups() if x is not None)


def check_version(version: Iterable[int]) -> Tuple[str, str]:
    """返回 (level, message)。level ∈ ok / old / too_new / unknown。"""
    ver = tuple(version or ())
    if len(ver) < 2:
        return "unknown", "无法识别 Python 版本"
    shown = ".".join(str(x) for x in ver)
    # 只比前两段：否则 (3, 13, 9) > (3, 13) 会被判成"版本太新"
    ver = ver[:2]
    if ver < SUPPORTED_MIN:
        return "old", (
            "Python 版本过低（当前 " + shown + "）：本项目需要 Python "
            + "%d.%d 及以上，推荐 %s。\n下载地址 %s" % (SUPPORTED_MIN[0], SUPPORTED_MIN[1], RECOMMENDED, DOWNLOAD_URL)
        )
    if ver > SUPPORTED_MAX:
        return "too_new", (
            "Python 版本太新（当前 " + shown + "）：本项目目前支持到 Python "
            + "%d.%d，推荐 %s。\n" % (SUPPORTED_MAX[0], SUPPORTED_MAX[1], RECOMMENDED)
            + "原因：本地语音转写依赖的 " + "、".join(WHEEL_LAG_PACKAGES[:3])
            + " 等编译型包，官方还没为这个 Python 版本发布预编译包，"
            + "安装会在依赖解析阶段直接失败（不是网络问题）。\n"
            + "解决办法：安装 Python " + RECOMMENDED
            + "（安装时务必勾选 “Add python.exe to PATH”），"
            + "并在「设置 → 应用 → 已安装的应用」里卸载 3.14/3.15 等预发布版本，然后重启程序。\n"
            + "下载地址 " + DOWNLOAD_URL
        )
    return "ok", "Python " + shown + "（受支持）"


def probe_python(path: str, timeout: float = 10.0) -> Tuple[bool, str, str]:
    """确认解释器真的可用：文件存在 + 能跑起来。返回 (ok, 版本串, 失败原因)。"""
    if not path:
        return False, "", "路径为空"
    if not os.path.isfile(path):
        return False, "", "文件不存在（可能是卸载后残留的 Python 路径）"
    try:
        out = subprocess.run(
            [path, "-c", "import sys; print('%d.%d.%d' % sys.version_info[:3])"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
        )
    except Exception as exc:  # noqa: BLE001
        return False, "", "无法运行：" + str(exc)[:160]
    if out.returncode != 0:
        return False, "", "无法运行：" + ((out.stderr or out.stdout or "").strip()[:160] or "退出码 " + str(out.returncode))
    return True, (out.stdout or "").strip(), ""


def _packages_in(text: str) -> List[str]:
    found = []
    for pkg in WHEEL_LAG_PACKAGES:
        if re.search(r"(?<![0-9A-Za-z_.-])" + re.escape(pkg) + r"(?![0-9A-Za-z_.-])", text, re.I):
            found.append(pkg)
    skip = {"python", "the", "and", "your", "environment", "requirement", "these", "packages"}
    for m in re.finditer(
        r"(?:no matching distribution found for|could not find a version that satisfies the requirement"
        r"|requires)\s+([A-Za-z0-9_.\-]{3,40})",
        text, re.I,
    ):
        name = m.group(1)
        if name.lower() not in skip and name not in found:
            found.append(name)
    return found[:4]


def classify_pip_failure(text: str) -> Tuple[str, str]:
    """把 pip 的输出翻译成"用户能照着做"的说明。返回 (kind, message)。

    kind ∈ too_new / network / unknown
    """
    raw = str(text or "")
    low = raw.lower()
    tricky = ("resolutionimpossible" in low
              or "no matching distribution" in low
              or "could not find a version that satisfies" in low)
    if tricky:
        pkgs = _packages_in(raw)
        names = "、".join(pkgs) if pkgs else "部分依赖"
        return "too_new", (
            "依赖没有匹配当前 Python 版本的预编译包（" + names + "）—— 这不是网络问题。\n"
            "请改用 Python " + RECOMMENDED + "（支持 " + "%d.%d ~ %d.%d" % (SUPPORTED_MIN[0], SUPPORTED_MIN[1], SUPPORTED_MAX[0], SUPPORTED_MAX[1])
            + "）：安装时勾选 “Add python.exe to PATH”，"
            + "并卸载 3.14/3.15 等预发布版本后重启程序。\n下载地址 " + DOWNLOAD_URL
        )
    network_keys = ("timed out", "timeout", "connection", "temporary failure",
                    "network is unreachable", "could not fetch", "connection reset",
                    "ssl", "proxy", "name or service not known", "server certificate")
    if any(k in low for k in network_keys):
        return "network", "网络问题：下载依赖超时或连接失败。换个网络（或检查代理）后重试即可。"
    return "unknown", ""


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Python 版本可用性检查")
    ap.add_argument("--check", action="store_true", help="检查解释器（默认当前解释器）")
    ap.add_argument("--python", default="", help="要检查的解释器路径")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    args = ap.parse_args(argv)
    path = args.python or sys.executable
    ok, ver, err = probe_python(path)
    if not ok:
        level, msg = "broken", "无法使用该 Python（" + path + "）：" + err
    else:
        level, msg = check_version(parse_version(ver))
    if args.json:
        print(json.dumps({"ok": level == "ok", "level": level, "version": ver, "path": path, "message": msg},
                         ensure_ascii=False))
    else:
        print(msg)
    return 0 if level == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
