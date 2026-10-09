import os
import sys
import json
import time
import socket
import shutil
import threading
import subprocess
import webbrowser
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

import customtkinter as ctk
import requests

# 快速依赖安装（镜像测速 + 并发下载）；既能被 import，也能命令行单独跑
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
import fastdeps  # noqa: E402

VERSION = "1.8.2"
APP_NAME = "BiliLearn-AI"
GITHUB_REPO = "yxyusage/BiliLearn-AI"
DEFAULT_PORT = 8000

def _find_app_dir(start: Path) -> Path:
    """向上查找真正包含 backend/app/main.py 的项目根目录。

    这样把 BiliLearn-AI-Launcher.exe 放在项目根目录、或 launcher/dist/ 这类
    子目录里都能正确找到后端；完全找不到时退回起始目录并给出原有提示。
    """
    for candidate in [start] + list(start.parents)[:3]:
        if (candidate / "backend" / "app" / "main.py").exists():
            return candidate
    return start


if getattr(sys, "frozen", False):
    APP_DIR = _find_app_dir(Path(sys.executable).parent)
else:
    APP_DIR = _find_app_dir(Path(__file__).parent.parent)

CONFIG_PATH = APP_DIR / "launcher_config.json"
VENV_DIR = APP_DIR / ".venv"
BACKEND_DIR = APP_DIR / "backend"
FRONTEND_DIR = APP_DIR / "frontend"
def _resolve_data_dir():
    """与后端 config.py 保持一致：默认放在用户主目录下，升级不会丢笔记。

    旧版本的数据在 backend/data，若那里还有数据库且新目录还没有，
    先指向旧目录（后端首次启动会自动搬过去）。
    """
    env_dir = (os.environ.get("BILI_DATA_DIR") or "").strip()
    if env_dir:
        return Path(env_dir).expanduser()
    target = Path.home() / "BiliLearn-AI"
    if (target / "bililearn.db").exists():
        return target
    legacy = BACKEND_DIR / "data"
    if (legacy / "bililearn.db").exists():
        return legacy
    return target


# 真实数据目录（与后端 config.DATA_DIR 一致）
DATA_DIR = _resolve_data_dir()
REQUIREMENTS_STAMP = VENV_DIR / ".requirements.stamp"

PROXY_KEYS = ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy")


def _proxy_alive(proxy_url, timeout=1.5):
    try:
        parsed = urlparse(proxy_url)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if not host:
            return False
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def build_subprocess_env():
    """返回子进程环境变量。代理可用则保留，失效代理自动移除。"""
    env = os.environ.copy()
    proxy = env.get("HTTPS_PROXY") or env.get("https_proxy") or env.get("HTTP_PROXY") or env.get("http_proxy")
    if proxy:
        if _proxy_alive(proxy):
            return env, True
        for key in PROXY_KEYS:
            env.pop(key, None)
        return env, False
    return env, None

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

COLORS = {
    "bg": "#1a1a2e",
    "bg_card": "#16213e",
    "bg_input": "#0f3460",
    "accent": "#0d9488",
    "accent_hover": "#14b8a6",
    "text": "#e2e8f0",
    "text_dim": "#94a3b8",
    "success": "#10b981",
    "warning": "#f59e0b",
    "error": "#ef4444",
}


def load_config():
    default = {
        "api_key": "",
        "model": "deepseek-chat",
        "base_url": "https://api.deepseek.com/v1",
        "port": DEFAULT_PORT,
        "theme": "dark",
        "auto_open_browser": True,
        "minimize_to_tray": True,
    }
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            default.update(saved)
        except Exception:
            pass
    # 迁移旧配置里保存的非官方模型名
    if default.get("model") in ("", "deepseek-v4-pro"):
        default["model"] = "deepseek-chat"
    return default


def save_config(config):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def get_python_executable():
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def get_pip_executable():
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "pip.exe"
    return VENV_DIR / "bin" / "pip"


def find_system_python():
    """定位系统 Python。

    打包成 exe 后 sys.executable 指向 exe 自身而非 Python，必须从 PATH 查找。
    """
    if not getattr(sys, "frozen", False):
        return sys.executable
    for name in ("python", "python3"):
        path = shutil.which(name)
        if path:
            return path
    return ""


def _no_window_flag():
    return subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def _pid_on_port(port: int) -> int:
    """返回正在监听该端口的进程 PID（取不到返回 0）。"""
    try:
        if sys.platform == "win32":
            out = subprocess.run(
                ["netstat", "-ano", "-p", "TCP"],
                capture_output=True, text=True, creationflags=_no_window_flag()
            ).stdout
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 5 and parts[0].upper() == "TCP" and parts[3].upper() == "LISTENING":
                    if parts[1].endswith(":" + str(port)):
                        return int(parts[4])
        else:
            out = subprocess.run(["lsof", "-ti", "tcp:" + str(port)],
                                 capture_output=True, text=True).stdout
            first = [x for x in out.strip().splitlines() if x.strip()]
            if first:
                return int(first[0])
    except Exception:
        pass
    return 0


def _health_ok(port: int, timeout: float = 1.5) -> bool:
    """探测该端口上跑的是不是本项目的服务。"""
    try:
        resp = requests.get("http://127.0.0.1:{}/api/health".format(port), timeout=timeout)
        return resp.json().get("app") == APP_NAME
    except Exception:
        return False


def _kill_pid(pid: int) -> bool:
    """结束进程（Windows 连同子进程一起结束）。"""
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                           capture_output=True, creationflags=_no_window_flag())
        else:
            os.kill(pid, 15)
        return True
    except Exception:
        return False


class ServiceManager:
    def __init__(self, log_callback, status_callback, progress_callback=None):
        self.log = log_callback
        self.set_status = status_callback
        self.progress_callback = progress_callback or (lambda fraction, text: None)
        self.process = None
        self.running = False
        self.starting = False
        self._cancel_requested = False

    def set_progress(self, fraction, text=""):
        """把安装/下载进度推给界面（fraction 为 -1 表示只更新文案）。"""
        try:
            self.progress_callback(fraction, text)
        except Exception:  # noqa: BLE001
            pass

    def check_python(self):
        python = find_system_python()
        if not python:
            return False, "未找到 Python"
        try:
            result = subprocess.run(
                [python, "-c", "import sys; print('%d.%d.%d' % sys.version_info[:3])"],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            if result.returncode != 0:
                return False, "Python 无法正常运行"
            version = tuple(int(x) for x in result.stdout.strip().split("."))
            if version < (3, 10):
                return False, f"Python 版本过低（当前 {result.stdout.strip()}），需要 3.10 或更高版本"
            return True, result.stdout.strip()
        except Exception as e:
            return False, str(e)

    def check_venv(self):
        return get_python_executable().exists()

    def create_venv(self):
        python = find_system_python()
        if not python:
            self.log("未找到系统 Python，无法创建虚拟环境")
            return False
        self.log("创建虚拟环境...")
        env, proxy_state = build_subprocess_env()
        try:
            subprocess.run(
                [python, "-m", "venv", str(VENV_DIR)],
                check=True, capture_output=True, text=True, env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            self.log("虚拟环境创建完成")
            return True
        except subprocess.CalledProcessError as e:
            self.log(f"创建虚拟环境失败: {e.stderr}")
            return False

    def _deps_up_to_date(self):
        req = BACKEND_DIR / "requirements.txt"
        if not req.exists() or not REQUIREMENTS_STAMP.exists():
            return False
        return REQUIREMENTS_STAMP.stat().st_mtime >= req.stat().st_mtime

    def install_dependencies(self):
        if self._deps_up_to_date():
            self.log("依赖已是最新，跳过安装")
            return True

        env, proxy_state = build_subprocess_env()
        if proxy_state is False:
            self.log("检测到系统代理不可用，已自动绕过代理直连")
        elif proxy_state is True:
            self.log("使用系统代理")

        python = str(get_python_executable())
        req = str(BACKEND_DIR / "requirements.txt")

        # 一、快速通道：镜像测速 + 并发下载 wheel + 本地安装（见 fastdeps.py）
        self.set_status("测速并下载依赖...", COLORS["warning"])
        self.log("安装 Python 依赖（先探测最快的镜像，再并发下载）...")
        try:
            ok = fastdeps.install(
                python, req,
                log=self.log,
                progress=self._on_install_progress,
                cancel=lambda: self._cancel_requested,
            )
        except Exception as exc:  # noqa: BLE001
            self.log(f"  快速安装异常：{exc}")
            ok = False
        if ok:
            self._stamp_requirements(req)
            return True
        if self._cancel_requested:
            return False

        # 二、回退通道：普通 pip，但逐行流式输出 + 卡死看门狗（不再有 10 分钟总超时）
        self.log("改用普通 pip 安装（实时输出，长时间无响应才会判定卡死）...")
        ranked = []
        try:
            ranked = [(n, u) for n, u, s in fastdeps.probe_mirrors(log=self.log) if s > 0]
        except Exception:  # noqa: BLE001
            pass
        if not ranked:
            ranked = list(fastdeps.DEFAULT_MIRRORS)
        for name, url in ranked:
            if self._cancel_requested:
                return False
            self.log(f"  尝试 {name} ...")
            if self._pip_install_streamed(python, req, url, env):
                self._stamp_requirements(req)
                return True
            self.log(f"  {name} 失败，换下一个镜像")
        return False

    def _stamp_requirements(self, req: str) -> None:
        try:
            shutil.copyfile(req, REQUIREMENTS_STAMP)
        except Exception:  # noqa: BLE001
            pass

    def _on_install_progress(self, fraction: float, text: str) -> None:
        """fastdeps 的下载进度回调：驱动进度条 + 明细文案。"""
        if fraction >= 0:
            self.set_progress(fraction, text)

    def _pip_install_streamed(self, python: str, req: str, index_url: str, env: dict,
                              stall_seconds: int = 300) -> bool:
        """流式跑 pip install：逐行进日志，只有「长时间毫无输出」才判定卡死。

        关键点：
          * 不用 capture_output（那样日志会一直不动，像卡死）；
          * 不设总时长上限（慢网也能装完），改为监控输出间隔；
          * 强制 UTF-8 环境，避免中文/GBK 控制台下 pip 的进度条崩溃。
        """
        cmd = [
            python, "-m", "pip", "install", "-r", req, "-i", index_url,
            "--disable-pip-version-check",
            "--progress-bar", "off", "--no-color", "--no-input",
            "--default-timeout=60", "--retries", "5",
        ]
        run_env = dict(env)
        run_env.update(fastdeps.pip_env())
        state = {"last": time.monotonic(), "killed": ""}
        started = time.monotonic()
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, encoding="utf-8", errors="replace", env=run_env,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
        except Exception as exc:  # noqa: BLE001
            self.log(f"  启动 pip 失败：{exc}")
            return False

        def watchdog() -> None:
            while proc.poll() is None:
                if self._cancel_requested:
                    state["killed"] = "用户取消"
                    proc.kill()
                    return
                if time.monotonic() - state["last"] > stall_seconds:
                    state["killed"] = f"超过 {stall_seconds} 秒没有任何输出"
                    proc.kill()
                    return
                time.sleep(2)

        threading.Thread(target=watchdog, daemon=True).start()
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.rstrip()
            if not line:
                continue
            state["last"] = time.monotonic()
            self.log("  " + line)
            self.set_progress(-1, line[:120] + f"（已用 {int(time.monotonic() - started)}s）")
        code = proc.wait()
        if state["killed"]:
            self.log(f"  pip 被中断：{state['killed']}")
            return False
        return code == 0

    def build_frontend_if_needed(self):
        """前端构建产物缺失时自动构建（否则后端无页面可托管，访问 8000 会 404）。"""
        dist_index = FRONTEND_DIR / "dist" / "index.html"
        if dist_index.exists():
            return True
        npm = shutil.which("npm")
        if not npm:
            self.log("未检测到 Node.js/npm，无法构建前端页面。请先安装 Node 18+")
            return False
        use_shell = sys.platform == "win32"
        no_window = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        fe_env, _ = build_subprocess_env()
        self.set_status("构建前端页面...", COLORS["warning"])
        if not (FRONTEND_DIR / "node_modules").exists():
            self.log("安装前端依赖（npm install，首次较慢）...")
            try:
                r = subprocess.run(
                    [npm, "install", "--no-audit", "--no-fund"],
                    cwd=str(FRONTEND_DIR), shell=use_shell,
                    capture_output=True, text=True, timeout=1800, env=fe_env,
                    creationflags=no_window
                )
            except subprocess.TimeoutExpired:
                self.log("npm install 超时")
                return False
            if r.returncode != 0:
                self.log("npm install 失败: " + (r.stderr or r.stdout or "")[-200:])
                return False
        self.log("构建前端（npm run build）...")
        try:
            r = subprocess.run(
                [npm, "run", "build"],
                cwd=str(FRONTEND_DIR), shell=use_shell,
                capture_output=True, text=True, timeout=1800, env=fe_env,
                creationflags=no_window
            )
        except subprocess.TimeoutExpired:
            self.log("npm run build 超时")
            return False
        if r.returncode != 0:
            self.log("npm run build 失败: " + (r.stderr or r.stdout or "")[-200:])
            return False
        return dist_index.exists()

    def start(self, port, config):
        if self.running or self.starting:
            return

        self.starting = True
        self._cancel_requested = False
        self.set_status("检查环境...", COLORS["warning"])

        if not BACKEND_DIR.exists() or not (BACKEND_DIR / "requirements.txt").exists():
            self.log("=" * 50)
            self.log("错误：找不到后端文件！")
            self.log("")
            self.log("启动器 exe 必须和以下文件夹放在同一目录：")
            self.log("  - backend/")
            self.log("  - frontend/")
            self.log("")
            self.log("请确认你下载的是完整的便携版 ZIP，")
            self.log("并且解压后所有文件都在同一个文件夹里。")
            self.log("=" * 50)
            self.set_status("启动失败", COLORS["error"])
            self.starting = False
            return

        py_ok, py_info = self.check_python()
        if not py_ok:
            self.log(f"错误：{py_info}")
            self.log("请安装 Python 3.10 或更高版本")
            self.log("下载地址: https://www.python.org/downloads/")
            self.set_status("启动失败", COLORS["error"])
            self.starting = False
            return
        self.log(f"Python {py_info} 检测通过")

        if self._cancel_requested:
            self.starting = False
            return

        if not self.check_venv():
            self.set_status("创建虚拟环境...", COLORS["warning"])
            if not self.create_venv():
                self.set_status("启动失败", COLORS["error"])
                self.starting = False
                return

        if self._cancel_requested:
            self.starting = False
            return

        self.set_status("安装依赖...", COLORS["warning"])
        if not self.install_dependencies():
            self.log("依赖安装失败，请检查网络连接")
            self.set_status("启动失败", COLORS["error"])
            self.starting = False
            return

        if self._cancel_requested:
            self.starting = False
            return

        self.set_status("检查前端...", COLORS["warning"])
        if not self.build_frontend_if_needed():
            self.log("前端构建失败，页面将无法访问")
            self.set_status("启动失败", COLORS["error"])
            self.starting = False
            return

        if self._cancel_requested:
            self.starting = False
            return

        self.set_status("启动服务...", COLORS["warning"])
        self.log(f"启动后端服务 (端口 {port})...")

        # 后端读取的是 BILI_ 前缀的环境变量（见 backend/app/config.py）
        env, _ = build_subprocess_env()
        env["PYTHONUNBUFFERED"] = "1"
        # 语音识别模型默认走国内镜像（与 start.ps1 / start.sh 一致；用户自己设过就尊重用户）
        env.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
        if config.get("api_key"):
            env["BILI_DEEPSEEK_API_KEY"] = config["api_key"]
        if config.get("base_url"):
            env["BILI_DEEPSEEK_BASE_URL"] = config["base_url"]
        if config.get("model"):
            env["BILI_DEEPSEEK_MODEL"] = config["model"]

        # 端口被占用时先分辨是「本项目的旧实例」还是「别的程序」
        owner = _pid_on_port(port)
        if owner and owner != os.getpid():
            if _health_ok(port):
                self.log(f"[WARN] 端口 {port} 上已有本项目的旧实例（PID {owner}），正在关闭后重启...")
                _kill_pid(owner)
                time.sleep(1.5)
            else:
                self.log(f"[ERROR] 端口 {port} 已被其他程序占用（PID {owner}）")
                self.log("请在启动器「设置」里换一个端口，或先结束该程序后重试")
                self.set_status("端口被占用", COLORS["error"])
                self.starting = False
                return

        python_exe = str(get_python_executable())
        cmd = [python_exe, "-m", "uvicorn", "app.main:app",
               "--host", "0.0.0.0", "--port", str(port)]

        try:
            self.process = subprocess.Popen(
                cmd, cwd=str(BACKEND_DIR), env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, encoding="utf-8", errors="replace"
            )
            self.starting = False
            threading.Thread(target=self._read_output, daemon=True).start()

            # 等后端真正能响应健康检查再报成功：
            # 端口冲突、依赖缺失等启动错误都能在这里被抓到，而不是先报「已启动」
            ready = False
            for _ in range(30):
                if self.process.poll() is not None:
                    break
                if _health_ok(port):
                    ready = True
                    break
                time.sleep(1)

            if not ready:
                if self.process.poll() is not None:
                    self.log("[ERROR] 后台进程已退出（多半是端口冲突或依赖缺失），请查看上方日志")
                else:
                    self.log("[ERROR] 服务未能在 30 秒内就绪，请查看上方日志")
                self.running = False
                self.set_status("启动失败", COLORS["error"])
                if self.process and self.process.poll() is None:
                    self.process.terminate()
                self.process = None
                return

            self.running = True
            self.set_status("运行中", COLORS["success"])
            self.log(f"服务已就绪: http://localhost:{port}")
            threading.Thread(target=self._wait_for_exit, daemon=True).start()

            if config.get("auto_open_browser", True):
                webbrowser.open(f"http://localhost:{port}")

        except Exception as e:
            self.log(f"启动服务失败: {e}")
            self.set_status("启动失败", COLORS["error"])
            self.starting = False

    def _read_output(self):
        if not self.process:
            return
        try:
            for line in self.process.stdout:
                if line:
                    self.log(line.rstrip())
        except Exception:
            pass

    def _wait_for_exit(self):
        if not self.process:
            return
        self.process.wait()
        self.running = False
        self.process = None
        self.set_status("已停止", COLORS["text_dim"])
        self.log("服务已停止")

    def stop(self):
        if self.starting and not self.running:
            self._cancel_requested = True
            self.log("正在取消启动...")
            self.starting = False
            self.set_status("已取消", COLORS["text_dim"])
            return
        if self.process and self.running:
            self.log("停止服务...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.running = False
            self.process = None
            self.set_status("已停止", COLORS["text_dim"])


class BiliLearnLauncher(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.config = load_config()
        self.log_lines = []
        self.service = ServiceManager(self._log, self._set_status, self._set_progress)
        self.tray_icon = None

        self.title(f"{APP_NAME} 启动器 v{VERSION}")
        self.geometry("460x560")
        self.minsize(420, 500)
        self.resizable(True, True)
        self.configure(fg_color=COLORS["bg"])
        # 关闭窗口时按设置最小化到托盘
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        self._check_update_silent()

    def _on_close(self):
        if self.config.get("minimize_to_tray", True) and self._start_tray():
            self.withdraw()
        else:
            self._quit()

    def _start_tray(self):
        """创建系统托盘图标；不可用时返回 False，由调用方正常退出。"""
        if self.tray_icon:
            return True
        try:
            import pystray
        except Exception:
            self.log("未安装 pystray，关闭窗口将直接退出")
            return False
        try:
            image = self._make_tray_image()
            menu = pystray.Menu(
                pystray.MenuItem("显示主界面", lambda: self.after(0, self._show_window), default=True),
                pystray.MenuItem("退出", lambda: self.after(0, self._quit)),
            )
            self.tray_icon = pystray.Icon("bililearn-ai", image, f"{APP_NAME} 启动器", menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
            return True
        except Exception as e:
            self.log(f"托盘初始化失败：{e}")
            self.tray_icon = None
            return False

    @staticmethod
    def _make_tray_image():
        from PIL import Image, ImageDraw
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([4, 4, 60, 60], radius=14, fill=(13, 148, 136, 255))
        d.rectangle([16, 18, 40, 24], fill=(255, 255, 255, 255))
        d.rectangle([16, 30, 48, 36], fill=(255, 255, 255, 255))
        d.rectangle([16, 42, 34, 48], fill=(255, 255, 255, 255))
        return img

    def _show_window(self):
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
        except Exception:
            pass

    def _quit(self):
        try:
            self.service.stop()
        except Exception:
            pass
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
            self.tray_icon = None
        try:
            self.destroy()
        except Exception:
            pass

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent", height=100)
        header.grid(row=0, column=0, sticky="ew", padx=30, pady=(30, 10))
        header.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            header, text=APP_NAME,
            font=ctk.CTkFont(size=32, weight="bold"),
            text_color=COLORS["accent"]
        )
        title.grid(row=0, column=0, sticky="w")

        subtitle = ctk.CTkLabel(
            header, text="AI 驱动的 B 站学习助手",
            font=ctk.CTkFont(size=14),
            text_color=COLORS["text_dim"]
        )
        subtitle.grid(row=1, column=0, sticky="w", pady=(2, 0))

        version_label = ctk.CTkLabel(
            header, text=f"v{VERSION}",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_dim"]
        )
        version_label.grid(row=0, column=1, sticky="e", rowspan=2)

        card = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=16)
        card.grid(row=1, column=0, sticky="ew", padx=30, pady=10)
        card.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(
            card, text="就绪",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLORS["text_dim"]
        )
        self.status_label.grid(row=0, column=0, pady=(24, 8))

        self.progress = ctk.CTkProgressBar(
            card, width=360, height=14, corner_radius=7,
            progress_color=COLORS["accent"],
            fg_color=COLORS["bg_input"]
        )
        self.progress.set(0)
        self.progress.grid(row=1, column=0, padx=30, pady=(0, 8), sticky="ew")

        # 进度明细：真实百分比、速度、剩余时间都写在这里，避免"看起来卡死"
        self.detail_label = ctk.CTkLabel(
            card, text="",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_dim"],
            wraplength=430, justify="left", anchor="w"
        )
        self.detail_label.grid(row=2, column=0, padx=30, pady=(0, 14), sticky="ew")

        self.start_btn = ctk.CTkButton(
            card, text="启动服务",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=48, corner_radius=12,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=self._toggle_service
        )
        self.start_btn.grid(row=3, column=0, padx=30, pady=(0, 24))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="ew", padx=30, pady=(5, 10))
        for i in range(4):
            btn_frame.grid_columnconfigure(i, weight=1)

        btn_config = [
            ("设置", self._open_settings),
            ("日志", self._toggle_log),
            ("数据", self._open_data_dir),
            ("更新", self._check_update),
        ]
        for i, (text, cmd) in enumerate(btn_config):
            btn = ctk.CTkButton(
                btn_frame, text=text,
                font=ctk.CTkFont(size=13),
                height=36, corner_radius=10,
                fg_color=COLORS["bg_card"],
                hover_color=COLORS["bg_input"],
                text_color=COLORS["text"],
                command=cmd
            )
            btn.grid(row=0, column=i, padx=4)

        self.log_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=12)
        self.log_text = ctk.CTkTextbox(
            self.log_frame, height=180,
            font=ctk.CTkFont(size=11, family="Consolas"),
            fg_color=COLORS["bg"],
            text_color=COLORS["text_dim"],
            corner_radius=8
        )
        self.log_visible = False

        footer = ctk.CTkLabel(
            self, text="数据保存在本地 · 不上传任何服务器",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_dim"]
        )
        footer.grid(row=4, column=0, pady=(10, 20))

    def _toggle_service(self):
        if self.service.running:
            self.service.stop()
            self.start_btn.configure(text="启动服务", fg_color=COLORS["accent"], state="normal")
            self.progress.set(0)
        elif self.service.starting:
            self.service.stop()
            self.start_btn.configure(text="启动服务", fg_color=COLORS["accent"], state="normal")
            self.progress.set(0)
        else:
            self.start_btn.configure(text="启动中，点击取消", fg_color=COLORS["warning"])
            self.progress.set(0.1)
            threading.Thread(
                target=self._start_and_reset_btn,
                args=(self.config.get("port", DEFAULT_PORT), self.config),
                daemon=True
            ).start()

    def _start_and_reset_btn(self, port, config):
        self.service.start(port, config)
        if not self.service.running:
            self.start_btn.configure(text="启动服务", fg_color=COLORS["accent"], state="normal")
            self.progress.set(0)
        else:
            self.start_btn.configure(text="停止服务", fg_color=COLORS["error"], state="normal")
            self.progress.set(1)

    def _set_progress(self, fraction, text=""):
        """安装/下载回调：驱动真实进度条与明细文案（fraction=-1 表示只更新文案）。"""
        try:
            if fraction is not None and fraction >= 0:
                self.progress.set(max(0.0, min(1.0, float(fraction))))
            if text:
                self.detail_label.configure(text=text)
        except Exception:  # noqa: BLE001
            pass

    def _set_status(self, text, color):
        self.status_label.configure(text=text, text_color=color)
        if text == "运行中":
            self.progress.set(1)
            self.detail_label.configure(text="服务已就绪")
        elif text in ("已停止", "已取消"):
            self.progress.set(0)
            self.detail_label.configure(text="")
            try:
                self.start_btn.configure(
                    text="启动服务", fg_color=COLORS["accent"], state="normal"
                )
            except Exception:
                pass
        else:
            # 其它中间态（检查环境/安装依赖/启动服务…）不再把进度条写死成 50%，
            # 真实进度由 set_progress 回调推进，明细文案跟随状态
            self.detail_label.configure(text=text)

    def _log(self, msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {msg}"
        self.log_lines.append(line)
        if len(self.log_lines) > 500:
            self.log_lines = self.log_lines[-500:]
        if self.log_visible:
            self.log_text.configure(state="normal")
            self.log_text.insert("end", line + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")

    def _toggle_log(self):
        if self.log_visible:
            self.log_frame.grid_forget()
            self.log_visible = False
        else:
            self.log_frame.grid(row=3, column=0, sticky="ew", padx=30, pady=5)
            self.log_text.pack(fill="both", expand=True, padx=10, pady=10)
            self.log_text.configure(state="normal")
            self.log_text.delete("1.0", "end")
            for line in self.log_lines:
                self.log_text.insert("end", line + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
            self.log_visible = True

    def _open_settings(self):
        SettingsWindow(self, self.config)

    def _open_data_dir(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(DATA_DIR))
        elif sys.platform == "darwin":
            subprocess.run(["open", str(DATA_DIR)])
        else:
            subprocess.run(["xdg-open", str(DATA_DIR)])

    def _check_update(self):
        UpdateWindow(self)

    def _check_update_silent(self):
        threading.Thread(target=self._do_check_update, daemon=True).start()

    def _do_check_update(self):
        try:
            resp = requests.get(
                f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
                timeout=10
            )
            if resp.status_code == 200:
                latest = resp.json().get("tag_name", "").lstrip("v")
                if latest and self._compare_version(latest, VERSION) > 0:
                    self._log(f"发现新版本: v{latest}")
        except Exception:
            pass

    @staticmethod
    def _compare_version(v1, v2):
        try:
            p1 = [int(x) for x in v1.split(".")]
            p2 = [int(x) for x in v2.split(".")]
            for a, b in zip(p1, p2):
                if a > b:
                    return 1
                if a < b:
                    return -1
            return len(p1) - len(p2)
        except Exception:
            return 0


class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, master, config):
        super().__init__(master)
        self.master_ref = master
        self.config = config
        self.title("设置")
        self.geometry("440x520")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["bg"])
        self.transient(master)
        self.grab_set()

        self.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            self, text="设置",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=COLORS["text"]
        )
        title.grid(row=0, column=0, pady=(24, 16), sticky="w", padx=30)

        form = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=12)
        form.grid(row=1, column=0, sticky="ew", padx=30)
        form.grid_columnconfigure(0, weight=1)

        fields = [
            ("API Key", "api_key", True),
            ("Base URL", "base_url", False),
            ("模型名称", "model", False),
            ("端口", "port", False),
        ]
        self.entries = {}
        for i, (label, key, is_password) in enumerate(fields):
            ctk.CTkLabel(
                form, text=label,
                font=ctk.CTkFont(size=13),
                text_color=COLORS["text_dim"]
            ).grid(row=i * 2, column=0, sticky="w", padx=20, pady=(16 if i == 0 else 8, 4))

            entry = ctk.CTkEntry(
                form, height=38, corner_radius=8,
                fg_color=COLORS["bg_input"],
                border_color=COLORS["bg_input"],
                text_color=COLORS["text"],
                show="*" if is_password else ""
            )
            entry.insert(0, str(self.config.get(key, "")))
            entry.grid(row=i * 2 + 1, column=0, sticky="ew", padx=20, pady=(0, 8))
            self.entries[key] = entry

        self.auto_open_var = ctk.BooleanVar(value=self.config.get("auto_open_browser", True))
        ctk.CTkCheckBox(
            form, text="启动后自动打开浏览器",
            variable=self.auto_open_var,
            font=ctk.CTkFont(size=13),
            text_color=COLORS["text"],
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"]
        ).grid(row=8, column=0, sticky="w", padx=20, pady=(8, 16))

        save_btn = ctk.CTkButton(
            self, text="保存设置",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=44, corner_radius=12,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=self._save
        )
        save_btn.grid(row=2, column=0, padx=30, pady=20)

    def _save(self):
        for key, entry in self.entries.items():
            val = entry.get().strip()
            if key == "port":
                try:
                    val = int(val)
                except ValueError:
                    val = DEFAULT_PORT
            self.config[key] = val
        self.config["auto_open_browser"] = self.auto_open_var.get()
        save_config(self.config)
        self.master_ref.config = self.config
        self.destroy()


class UpdateWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("检查更新")
        self.geometry("400x280")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["bg"])
        self.transient(master)
        self.grab_set()

        self.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(
            self, text="正在检查更新...",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLORS["text"]
        )
        self.status_label.grid(row=0, column=0, pady=(60, 10))

        self.info_label = ctk.CTkLabel(
            self, text=f"当前版本: v{VERSION}",
            font=ctk.CTkFont(size=13),
            text_color=COLORS["text_dim"]
        )
        self.info_label.grid(row=1, column=0)

        self.download_btn = ctk.CTkButton(
            self, text="前往下载",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40, corner_radius=10,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=lambda: webbrowser.open(f"https://github.com/{GITHUB_REPO}/releases/latest")
        )

        threading.Thread(target=self._check, daemon=True).start()

    def _check(self):
        try:
            resp = requests.get(
                f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                latest = data.get("tag_name", "").lstrip("v")
                if latest and BiliLearnLauncher._compare_version(latest, VERSION) > 0:
                    self.status_label.configure(text=f"发现新版本 v{latest}", text_color=COLORS["success"])
                    self.info_label.configure(text=f"当前版本: v{VERSION} → 最新版本: v{latest}")
                    self.download_btn.grid(row=2, column=0, pady=20)
                else:
                    self.status_label.configure(text="已是最新版本", text_color=COLORS["success"])
            else:
                self.status_label.configure(text="检查失败", text_color=COLORS["error"])
                self.info_label.configure(text="请检查网络连接")
        except Exception as e:
            self.status_label.configure(text="检查失败", text_color=COLORS["error"])
            self.info_label.configure(text=str(e)[:50])


def main():
    app = BiliLearnLauncher()
    app.mainloop()


if __name__ == "__main__":
    main()
