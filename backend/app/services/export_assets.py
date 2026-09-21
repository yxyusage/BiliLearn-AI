"""导出基础设施：本地浏览器 headless 打印 PDF、Pandoc 便携版管理、前端静态资源定位。"""
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

from ..config import DATA_DIR


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def find_browser() -> Optional[str]:
    """查找系统可用的 Chromium 内核浏览器（Edge 优先，Chrome 次之）。"""
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for path in candidates:
        if Path(path).exists():
            return path
    for name in ("msedge", "chrome", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _vendor_pandoc() -> Optional[Path]:
    base = DATA_DIR / "vendor" / "pandoc"
    if not base.exists():
        return None
    for exe in base.rglob("pandoc.exe"):
        return exe
    for exe in base.rglob("pandoc"):
        return exe
    return None


def ensure_pandoc() -> str:
    """返回可用的 pandoc 可执行文件路径；系统没有则自动下载便携版到 data/vendor。"""
    system_pandoc = shutil.which("pandoc")
    if system_pandoc:
        return system_pandoc
    vendored = _vendor_pandoc()
    if vendored:
        return str(vendored)
    return _download_pandoc()


def _download_pandoc() -> str:
    import httpx

    target = DATA_DIR / "vendor" / "pandoc"
    target.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        pattern = "windows-x86_64.zip"
    else:
        pattern = "linux-amd64.tar.gz"
    try:
        with httpx.Client(timeout=30) as client:
            meta = client.get("https://api.github.com/repos/jgm/pandoc/releases/latest").json()
            asset = next(
                (a for a in meta.get("assets", []) if a.get("name", "").endswith(pattern)),
                None,
            )
            if not asset:
                raise RuntimeError("未在最新 release 中找到 " + pattern)
            archive = target / ("pandoc" + (".zip" if pattern.endswith(".zip") else ".tar.gz"))
            with client.stream("GET", asset["browser_download_url"], follow_redirects=True, timeout=300) as resp:
                resp.raise_for_status()
                with open(archive, "wb") as f:
                    for chunk in resp.iter_bytes(1 << 16):
                        f.write(chunk)
        if archive.suffix == ".zip":
            with zipfile.ZipFile(archive) as z:
                z.extractall(target)
        else:
            subprocess.run(["tar", "-xzf", str(archive), "-C", str(target)], check=True)
        archive.unlink(missing_ok=True)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "未找到 Pandoc 且自动下载失败（约 30MB）。可手动安装 Pandoc 后重试，"
            "或从 https://github.com/jgm/pandoc/releases 下载后放入 "
            + str(target)
        ) from exc
    exe = _vendor_pandoc()
    if not exe:
        raise RuntimeError("Pandoc 下载后未找到可执行文件")
    return str(exe)


def html_to_pdf(html: str, timeout: int = 90) -> bytes:
    """用系统 Edge/Chrome 的 headless 模式把 HTML 打印为 PDF。"""
    browser = find_browser()
    if not browser:
        raise RuntimeError("未找到 Microsoft Edge 或 Google Chrome，无法导出 PDF")
    workdir = Path(tempfile.mkdtemp(prefix="bililearn_pdf_"))
    html_path = workdir / "note.html"
    pdf_path = workdir / "note.pdf"
    profile = workdir / "profile"
    html_path.write_text(html, encoding="utf-8")
    cmd = [
        browser,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-features=msEdgeWelcomeFLX,EdgeIdentityAssist,Translate",
        "--no-pdf-header-footer",
        "--print-to-pdf-no-header",
        "--virtual-time-budget=20000",
        "--user-data-dir=" + str(profile),
        "--print-to-pdf=" + str(pdf_path),
        html_path.resolve().as_uri(),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
        if not pdf_path.exists() or pdf_path.stat().st_size < 200:
            stderr = (proc.stderr or b"").decode("utf-8", "ignore")[-500:]
            raise RuntimeError("浏览器打印失败：" + stderr)
        return pdf_path.read_bytes()
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("PDF 渲染超时") from exc
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def markdown_to_docx(markdown: str, timeout: int = 90) -> bytes:
    """Pandoc 把 Markdown（含 LaTeX 公式、表格、图片）转为 docx。"""
    pandoc = ensure_pandoc()
    workdir = Path(tempfile.mkdtemp(prefix="bililearn_docx_"))
    md_path = workdir / "note.md"
    docx_path = workdir / "note.docx"
    md_path.write_text(markdown, encoding="utf-8")
    cmd = [
        pandoc,
        str(md_path),
        "-f", "markdown+tex_math_dollars+pipe_tables+raw_html",
        "-t", "docx",
        "--toc",
        "--toc-depth=2",
        "-o", str(docx_path),
        "--resource-path=" + str(workdir) + os.pathsep + str(DATA_DIR / "notes"),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
        if not docx_path.exists():
            stderr = (proc.stderr or b"").decode("utf-8", "ignore")[-500:]
            raise RuntimeError("Pandoc 转换失败：" + stderr)
        return docx_path.read_bytes()
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Word 转换超时") from exc
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def frontend_dist_asset(rel: str) -> Optional[Path]:
    """定位 frontend/node_modules 下的静态资源（KaTeX、Mermaid）。"""
    p = project_root() / "frontend" / "node_modules" / rel
    return p if p.exists() else None


def katex_assets():
    """返回 (css_uri, katex_js_uri, autorender_js_uri)；本地缺失时回退 CDN。"""
    css = frontend_dist_asset("katex/dist/katex.min.css")
    core = frontend_dist_asset("katex/dist/katex.min.js")
    js = frontend_dist_asset("katex/dist/contrib/auto-render.min.js")
    if css and core and js:
        return css.resolve().as_uri(), core.resolve().as_uri(), js.resolve().as_uri()
    cdn = "https://cdn.jsdelivr.net/npm/katex@0.16.47/dist"
    return cdn + "/katex.min.css", cdn + "/katex.min.js", cdn + "/contrib/auto-render.min.js"


def mermaid_asset() -> str:
    js = frontend_dist_asset("mermaid/dist/mermaid.min.js")
    if js:
        return js.resolve().as_uri()
    return "https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"
