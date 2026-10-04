import os
import sys
import json
import time
import shutil
import threading
import subprocess
import webbrowser
from pathlib import Path
from datetime import datetime

import customtkinter as ctk
import requests

VERSION = "1.7.0"
APP_NAME = "BiliLearn-AI"
GITHUB_REPO = "yxyusage/BiliLearn-AI"
DEFAULT_PORT = 8000

if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).parent
else:
    APP_DIR = Path(__file__).parent.parent

CONFIG_PATH = APP_DIR / "launcher_config.json"
VENV_DIR = APP_DIR / ".venv"
BACKEND_DIR = APP_DIR / "backend"
FRONTEND_DIR = APP_DIR / "frontend"
# 真实数据目录是 backend/data（与后端 config.DATA_DIR 一致）
DATA_DIR = BACKEND_DIR / "data"
REQUIREMENTS_STAMP = VENV_DIR / ".requirements.stamp"

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


class ServiceManager:
    def __init__(self, log_callback, status_callback):
        self.log = log_callback
        self.set_status = status_callback
        self.process = None
        self.running = False

    def check_python(self):
        python = find_system_python()
        if not python:
            return False
        try:
            result = subprocess.run(
                [python, "--version"],
                capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False

    def check_venv(self):
        return get_python_executable().exists()

    def create_venv(self):
        python = find_system_python()
        if not python:
            self.log("未找到系统 Python，无法创建虚拟环境")
            return False
        self.log("创建虚拟环境...")
        try:
            subprocess.run(
                [python, "-m", "venv", str(VENV_DIR)],
                check=True, capture_output=True, text=True
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
        self.log("安装 Python 依赖...")
        pip = str(get_pip_executable())
        req = str(BACKEND_DIR / "requirements.txt")

        mirrors = [
            ("清华镜像", "https://pypi.tuna.tsinghua.edu.cn/simple"),
            ("阿里云镜像", "https://mirrors.aliyun.com/pypi/simple/"),
            ("官方 PyPI", "https://pypi.org/simple/"),
        ]

        for name, url in mirrors:
            self.log(f"  尝试 {name}...")
            try:
                result = subprocess.run(
                    [pip, "install", "-r", req, "-i", url,
                     "--trusted-host", "pypi.tuna.tsinghua.edu.cn",
                     "--trusted-host", "mirrors.aliyun.com",
                     "--trusted-host", "pypi.org"],
                    capture_output=True, text=True, timeout=600
                )
                if result.returncode == 0:
                    self.log(f"  {name} 安装成功")
                    try:
                        shutil.copyfile(req, REQUIREMENTS_STAMP)
                    except Exception:
                        pass
                    return True
                self.log(f"  {name} 失败: {result.stderr[-200:]}")
            except subprocess.TimeoutExpired:
                self.log(f"  {name} 超时")
            except Exception as e:
                self.log(f"  {name} 错误: {e}")
        return False

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
        self.set_status("构建前端页面...", COLORS["warning"])
        if not (FRONTEND_DIR / "node_modules").exists():
            self.log("安装前端依赖（npm install，首次较慢）...")
            try:
                r = subprocess.run(
                    [npm, "install", "--no-audit", "--no-fund"],
                    cwd=str(FRONTEND_DIR), shell=use_shell,
                    capture_output=True, text=True, timeout=1800
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
                capture_output=True, text=True, timeout=1800
            )
        except subprocess.TimeoutExpired:
            self.log("npm run build 超时")
            return False
        if r.returncode != 0:
            self.log("npm run build 失败: " + (r.stderr or r.stdout or "")[-200:])
            return False
        return dist_index.exists()

    def start(self, port, config):
        if self.running:
            return

        self.set_status("检查环境...", COLORS["warning"])

        if not self.check_python():
            self.log("错误：未检测到 Python，请先安装 Python 3.10+")
            self.set_status("启动失败", COLORS["error"])
            return

        if not self.check_venv():
            self.set_status("创建虚拟环境...", COLORS["warning"])
            if not self.create_venv():
                self.set_status("启动失败", COLORS["error"])
                return

        self.set_status("安装依赖...", COLORS["warning"])
        if not self.install_dependencies():
            self.log("依赖安装失败，请检查网络连接")
            self.set_status("启动失败", COLORS["error"])
            return

        self.set_status("构建前端...", COLORS["warning"])
        if not self.build_frontend_if_needed():
            self.log("前端构建失败，页面将无法访问")
            self.set_status("启动失败", COLORS["error"])
            return

        self.set_status("启动服务...", COLORS["warning"])
        self.log(f"启动后端服务 (端口 {port})...")

        # 后端读取的是 BILI_ 前缀的环境变量（见 backend/app/config.py）
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        if config.get("api_key"):
            env["BILI_DEEPSEEK_API_KEY"] = config["api_key"]
        if config.get("base_url"):
            env["BILI_DEEPSEEK_BASE_URL"] = config["base_url"]
        if config.get("model"):
            env["BILI_DEEPSEEK_MODEL"] = config["model"]

        python_exe = str(get_python_executable())
        cmd = [python_exe, "-m", "uvicorn", "app.main:app",
               "--host", "0.0.0.0", "--port", str(port)]

        try:
            self.process = subprocess.Popen(
                cmd, cwd=str(BACKEND_DIR), env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, encoding="utf-8", errors="replace"
            )
            self.running = True
            self.set_status("运行中", COLORS["success"])
            self.log(f"服务已启动: http://localhost:{port}")

            threading.Thread(target=self._read_output, daemon=True).start()
            threading.Thread(target=self._wait_for_exit, daemon=True).start()

            time.sleep(2)
            if config.get("auto_open_browser", True):
                webbrowser.open(f"http://localhost:{port}")

        except Exception as e:
            self.log(f"启动服务失败: {e}")
            self.set_status("启动失败", COLORS["error"])

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
        self.service = ServiceManager(self._log, self._set_status)
        self.tray_icon = None

        self.title(f"{APP_NAME} 启动器 v{VERSION}")
        self.geometry("520x680")
        self.resizable(False, False)
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
            card, width=400, height=8,
            progress_color=COLORS["accent"],
            fg_color=COLORS["bg_input"]
        )
        self.progress.set(0)
        self.progress.grid(row=1, column=0, padx=30, pady=(0, 16))

        self.start_btn = ctk.CTkButton(
            card, text="启动服务",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=48, corner_radius=12,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=self._toggle_service
        )
        self.start_btn.grid(row=2, column=0, padx=30, pady=(0, 24))

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
            self.start_btn.configure(text="启动服务", fg_color=COLORS["accent"])
            self.progress.set(0)
        else:
            self.start_btn.configure(text="停止服务", fg_color=COLORS["error"])
            self.progress.set(0.3)
            threading.Thread(
                target=self.service.start,
                args=(self.config.get("port", DEFAULT_PORT), self.config),
                daemon=True
            ).start()

    def _set_status(self, text, color):
        self.status_label.configure(text=text, text_color=color)
        if text == "运行中":
            self.progress.set(1)
        elif text == "已停止":
            self.progress.set(0)
        else:
            self.progress.set(0.5)

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
