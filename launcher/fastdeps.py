"""快速依赖安装：镜像测速 + 并发下载 wheel + 本地安装。

为什么不用 pip 直接装：
  * pip 是串行下载，单连接只有几十 kB/s 时，上百 MB 要等很久；
  * 各家 PyPI 镜像速度差异极大，写死一个（或按固定顺序重试）常常挑不到最快的。

这里的流程：
  1. 并发探测多个镜像，挑最快的（读同一个索引页，比吞吐量）；
  2. pip install --dry-run --report - 解析出所有待装 wheel 的 URL（不下载）；
  3. 线程池并发下载 wheel 到本地目录（带速度/剩余时间回调，可取消）；
  4. pip install --no-index --find-links=<目录> 本地安装，不再联网；
  任何一步失败都返回 False，由调用方回退到普通 pip 安装。

只依赖标准库：既能被启动器 import，也能命令行独立运行（start.ps1 / start.sh 用）。
"""
import argparse
import concurrent.futures
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from typing import Callable, List, Optional, Tuple

# 常用 PyPI 镜像（含官方源兜底）。顺序无所谓，最终按实测速度排序。
DEFAULT_MIRRORS: List[Tuple[str, str]] = [
    ("阿里云", "https://mirrors.aliyun.com/pypi/simple/"),
    ("清华大学", "https://pypi.tuna.tsinghua.edu.cn/simple"),
    ("中科大", "https://pypi.mirrors.ustc.edu.cn/simple/"),
    ("腾讯云", "https://mirrors.cloud.tencent.com/pypi/simple/"),
    ("华为云", "https://repo.huaweicloud.com/repository/pypi/simple/"),
    ("官方 PyPI", "https://pypi.org/simple/"),
]

PROBE_PATH = "numpy/"          # 索引页够大，适合测吞吐
PROBE_MAX_BYTES = 2 * 1024 * 1024
PROBE_MAX_SECONDS = 4.0
UA = "Mozilla/5.0 (compatible; BiliLearn-AI/1.0)"

ProgressCB = Callable[[float, str], None]     # (0~1，-1 表示未知; 展示文案)
LogCB = Callable[[str], None]
CancelCheck = Callable[[], bool]


def pip_env() -> dict:
    """给 pip 子进程用的环境：强制 UTF-8，避免中文/GBK 控制台下 rich 进度条崩溃。

    pip 在「非中文代码页 + 管道输出」时会走到 Windows 控制台 API，
    遇到 box-drawing 字符就抛 UnicodeEncodeError；PYTHONUTF8=1 可彻底绕开。
    """
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    env["PIP_NO_INPUT"] = "1"
    return env


def _noop_log(_msg: str) -> None:
    pass


def _noop_progress(_fraction: float, _text: str) -> None:
    pass


def _never_cancel() -> bool:
    return False


def human_size(num: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(num) < 1024.0 or unit == "GB":
            return ("%.1f %s" % (num, unit)) if unit != "B" else ("%d B" % num)
        num /= 1024.0
    return "%.1f GB" % num


def human_speed(bytes_per_sec: float) -> str:
    return human_size(bytes_per_sec) + "/s"


def human_eta(seconds: float) -> str:
    if seconds <= 0 or seconds != seconds or seconds > 24 * 3600:
        return "--:--"
    seconds = int(seconds)
    if seconds >= 3600:
        return "%d:%02d:%02d" % (seconds // 3600, (seconds % 3600) // 60, seconds % 60)
    return "%d:%02d" % (seconds // 60, seconds % 60)


# ---------------------------------------------------------------- 镜像测速

def _probe_one(name: str, base_url: str, deadline: float) -> Tuple[str, str, float, float]:
    """返回 (名称, 地址, 字节/秒, 首字节延迟秒)。探测失败返回速度 0。"""
    url = base_url.rstrip("/") + "/" + PROBE_PATH
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    started = time.monotonic()
    first_byte = 0.0
    read = 0
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            while read < PROBE_MAX_BYTES:
                if time.monotonic() >= deadline:
                    break
                chunk = resp.read(262144)
                if not chunk:
                    break
                if not first_byte:
                    first_byte = time.monotonic() - started
                read += len(chunk)
    except Exception:  # noqa: BLE001  镜像不可用就跳过
        return name, base_url, 0.0, 0.0
    elapsed = max(time.monotonic() - started, 0.001)
    # 读得太少（多半是连接就慢或直接失败）视为不可用
    if read < 64 * 1024:
        return name, base_url, read / elapsed, first_byte
    return name, base_url, read / elapsed, first_byte


def probe_mirrors(mirrors: Optional[List[Tuple[str, str]]] = None,
                  log: LogCB = _noop_log) -> List[Tuple[str, str, float]]:
    """并发测速，返回按速度从快到慢排序的 [(名称, 地址, 字节/秒)]。"""
    mirrors = mirrors or DEFAULT_MIRRORS
    deadline = time.monotonic() + PROBE_MAX_SECONDS
    results: List[Tuple[str, str, float]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(mirrors)) as pool:
        futures = [pool.submit(_probe_one, n, u, deadline) for n, u in mirrors]
        for fut in concurrent.futures.as_completed(futures):
            name, url, speed, ttfb = fut.result()
            results.append((name, url, speed))
            log("  测速 %s：%s（首字节 %.2fs）" % (name, human_speed(speed) if speed else "不可用", ttfb))
    results.sort(key=lambda item: item[2], reverse=True)
    return results


# ---------------------------------------------------------------- 解析待装 wheel

def resolve_wheels(python_exe: str, requirements: str, index_url: str,
                   log: LogCB = _noop_log) -> List[str]:
    """用 pip --dry-run --report 得到所有待装 wheel 的下载地址（不下载）。"""
    cmd = [
        python_exe, "-m", "pip", "install",
        "--dry-run", "--quiet", "--report", "-",
        "--only-binary=:all:",
        "--disable-pip-version-check",
        "--progress-bar", "off", "--no-color", "--no-input",
        "-i", index_url, "-r", requirements,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                          encoding="utf-8", errors="replace", env=pip_env())
    if proc.returncode != 0:
        raise RuntimeError("解析依赖失败：" + (proc.stderr or proc.stdout or "")[-300:])
    urls = parse_report(proc.stdout)
    log("  待安装 wheel：%d 个" % len(urls))
    return urls


def parse_report(text: str) -> List[str]:
    """从 pip --report 的 JSON 里取出所有待装 wheel 的下载地址。"""
    start = text.find("{")
    if start < 0:
        raise RuntimeError("pip --report 没有返回 JSON")
    report = json.loads(text[start:])
    urls: List[str] = []
    for item in report.get("install") or []:
        info = item.get("download_info") or {}
        url = info.get("url") or ""
        # is_direct 是用户直接指定的 URL（如本地文件），不走镜像下载
        if url.endswith(".whl") and not item.get("is_direct"):
            urls.append(url)
    if not urls:
        raise RuntimeError("没有解析到任何 wheel")
    return urls


# ---------------------------------------------------------------- 并发下载

def _head_size(url: str) -> int:
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=8) as resp:
            return int(resp.headers.get("Content-Length") or 0)
    except Exception:  # noqa: BLE001
        return 0


def _download_one(url: str, dest_dir: str, workers: int = 3) -> Tuple[str, int]:
    """下载单个文件（失败自动重试）。返回 (本地路径, 字节数)。"""
    name = url.rsplit("/", 1)[-1] or "pkg.whl"
    if "?" in name:
        name = name.split("?", 1)[0]
    target = os.path.join(dest_dir, name)
    if os.path.exists(target) and os.path.getsize(target) > 0:
        return target, os.path.getsize(target)
    last_err: Optional[Exception] = None
    for _ in range(workers):
        tmp = target + ".part"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as resp, open(tmp, "wb") as out:
                shutil.copyfileobj(resp, out, length=1024 * 256)
            os.replace(tmp, target)
            return target, os.path.getsize(target)
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except OSError:
                pass
            time.sleep(0.5)
    raise RuntimeError("下载失败 %s：%s" % (name, last_err))


def download_all(urls: List[str], dest_dir: str, workers: int = 8,
                 log: LogCB = _noop_log, progress: ProgressCB = _noop_progress,
                 cancel: CancelCheck = _never_cancel) -> int:
    """并发下载全部 wheel，边下边报进度（含速度与剩余时间）。返回成功个数。"""
    os.makedirs(dest_dir, exist_ok=True)
    log("  探测文件大小...")
    total = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for size in pool.map(_head_size, urls):
            total += size
    known_total = total if total > 0 else 0

    done = 0
    finished = 0
    started = time.monotonic()
    lock = threading.Lock()

    def _tick(path: str, size: int) -> None:
        nonlocal done, finished
        with lock:
            done += size
            finished += 1
            elapsed = max(time.monotonic() - started, 0.001)
            speed = done / elapsed
            if known_total:
                fraction = min(0.99, done / float(known_total))
                eta = human_eta((known_total - done) / speed) if speed > 0 else "--:--"
                text = "已下载 %s/%s · %s · 还需 %s" % (
                    human_size(done), human_size(known_total), human_speed(speed), eta)
            else:
                fraction = min(0.99, finished / float(len(urls)))
                text = "已下载 %s（%d/%d 个）· %s" % (
                    human_size(done), finished, len(urls), human_speed(speed))
            log("  " + text + " · " + os.path.basename(path))
            progress(fraction, text)

    failures: List[str] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_download_one, u, dest_dir): u for u in urls}
        for fut in concurrent.futures.as_completed(futures):
            if cancel():
                raise RuntimeError("用户取消")
            url = futures[fut]
            try:
                path, size = fut.result()
                _tick(path, size)
            except Exception as exc:  # noqa: BLE001
                failures.append(str(exc))
    if failures:
        raise RuntimeError("；".join(failures[:3]))
    return finished


# ---------------------------------------------------------------- 本地安装

def install_from_dir(python_exe: str, requirements: str, wheel_dir: str,
                     log: LogCB = _noop_log) -> None:
    cmd = [
        python_exe, "-m", "pip", "install",
        "--no-index", "--find-links", wheel_dir,
        "--disable-pip-version-check",
        "--progress-bar", "off", "--no-color", "--no-input",
        "-r", requirements,
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, bufsize=1, encoding="utf-8", errors="replace",
                            env=pip_env())
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            log("  " + line)
    if proc.wait() != 0:
        raise RuntimeError("本地安装失败（退出码 %s）" % proc.returncode)


# ---------------------------------------------------------------- 主流程

def install(python_exe: str, requirements: str, log: LogCB = _noop_log,
            progress: ProgressCB = _noop_progress, cancel: CancelCheck = _never_cancel,
            mirrors: Optional[List[Tuple[str, str]]] = None, workers: int = 8) -> bool:
    """快速安装依赖；成功返回 True，任何一步出问题返回 False（调用方回退普通 pip）。"""
    workdir = tempfile.mkdtemp(prefix="bililearn_wheels_")
    try:
        log("[测速] 并发探测 PyPI 镜像...")
        ranked = probe_mirrors(mirrors, log)
        usable = [r for r in ranked if r[2] > 0]
        if not usable:
            log("  所有镜像都不可用，改用普通 pip 安装")
            return False
        name, index_url, speed = usable[0]
        log("[选择] %s（%s）" % (name, human_speed(speed)))

        log("[1/3] 解析依赖清单...")
        progress(0.02, "解析依赖清单...")
        urls = resolve_wheels(python_exe, requirements, index_url, log)

        log("[2/3] 并发下载 %d 个 wheel（%d 线程）..." % (len(urls), workers))
        count = download_all(urls, workdir, workers=workers, log=log,
                             progress=progress, cancel=cancel)

        log("[3/3] 本地安装（不再联网）...")
        progress(0.99, "本地安装中...")
        install_from_dir(python_exe, requirements, workdir, log)
        log("  完成，共 %d 个 wheel" % count)
        return True
    except Exception as exc:  # noqa: BLE001
        log("[提示] 快速安装未成功（%s），回退普通 pip 安装" % str(exc)[:200])
        return False
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="BiliLearn-AI 快速依赖安装")
    parser.add_argument("--python", required=True, help="目标环境的 python 可执行文件")
    parser.add_argument("--requirements", required=True, help="requirements.txt 路径")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--mirror", default="", help="指定镜像地址；留空自动测速")
    args = parser.parse_args()

    mirrors = None
    if args.mirror:
        mirrors = [("指定镜像", args.mirror)]

    def log(msg: str) -> None:
        print(msg, flush=True)

    last = [0.0]

    def progress(fraction: float, text: str) -> None:
        now = time.monotonic()
        if now - last[0] < 0.5:      # 限流，避免刷屏
            return
        last[0] = now
        if fraction >= 0:
            print("  [%3d%%] %s" % (int(fraction * 100), text), flush=True)

    ok = install(args.python, args.requirements, log=log, progress=progress, mirrors=mirrors)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
