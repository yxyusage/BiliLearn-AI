"""本地离线语音转写（可选能力）。

依赖：pip install faster-whisper（自带 PyAV，解码音频不需要系统 ffmpeg）。
无官方字幕的视频在用户开启转写后走此通道。

模型来源：faster-whisper 首次使用时会从 HuggingFace 下载 CTranslate2 权重。
国内网络直连 huggingface.co 经常是「连接超时」（WinError 10060），所以这里做了三层处理：
1) 尊重已有的 HF_ENDPOINT 环境变量（start.ps1 / start.sh / 启动器都会默认给国内镜像）；
2) 设置项 hf_endpoint 可显式指定 auto / mirror / official / 自定义地址；
3) auto 模式下官方源失败会自动改用 hf-mirror.com 重试一次。
"""
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import yt_dlp

from .bilibili import cookie_file, video_url
from .netutil import clear_proxy_env, has_proxy_env, restore_proxy_env

HF_MIRROR = "https://hf-mirror.com"
HF_OFFICIAL = "https://huggingface.co"

# 模型进程级缓存，避免每集都重新加载（加载一次大模型可达数十秒）
_MODELS: Dict[str, object] = {}
_MODEL_LOCK = threading.Lock()


class ModelDownloadError(RuntimeError):
    """语音识别模型下载失败：需要给出用户能照做的建议，而不是笼统的「网络中断」。"""


_MODEL_HINT = (
    "语音识别模型下载失败（模型托管在 huggingface.co，国内网络直连经常超时）。"
    "可任选一种方式解决：①「设置 → 语音模型下载源」选「国内镜像 hf-mirror.com」；"
    "②设置环境变量 HF_ENDPOINT=https://hf-mirror.com 后重启程序；"
    "③给本机挂一个可用的代理。"
    "临时办法：改用带官方字幕的视频（有字幕就不需要本地转写）。"
)


def resolve_endpoints(mode: str = "") -> List[Tuple[str, str]]:
    """把设置里的下载源解析成 [(endpoint, 说明)] 的尝试顺序。

    - "" / auto  ：已设 HF_ENDPOINT 就用它，否则先官方源、失败再自动切国内镜像
    - mirror     ：直接用 hf-mirror.com
    - official   ：只用官方源
    - 其它        ：当成自定义地址直接用
    """
    mode = (mode or "").strip()
    if mode in ("", "auto"):
        env = (os.environ.get("HF_ENDPOINT") or "").strip()
        if env:
            return [(env, env)]
        return [(HF_OFFICIAL, "HuggingFace 官方源"), (HF_MIRROR, "国内镜像 hf-mirror.com")]
    if mode == "mirror":
        return [(HF_MIRROR, "国内镜像 hf-mirror.com")]
    if mode == "official":
        return [(HF_OFFICIAL, "HuggingFace 官方源")]
    return [(mode, mode)]


def harden_hf_env() -> None:
    """让 HuggingFace 模型下载在「国内镜像 + 公共模型」场景下更可靠。

    三个已知坑（用户实际报过 / 本地实测）：

    1. **Xet 协议**：huggingface_hub 1.x 对大文件走新的 Xet 存储（hf_xet），
       而镜像站不代理 Xet —— 大文件会去连真实的 cas-server.xethub.hf.co 并
       返回 401 Unauthorized（报错形如
       "File reconstruction error: CAS Client Error: ... 401 Unauthorized,
       domain: https://cas-server.xethub.hf.co/..."）。
       下载公共模型用普通 HTTPS 就够了，所以直接关掉 Xet。
    2. **隐式 token**：本机 hf 缓存里若有失效 token，下载公共仓库反而会 401，禁用它。
    3. **下载超时**：默认只有 10 秒，国内慢网很容易断，放宽到 60 秒。

    全部用 setdefault / 只往放宽的方向改：用户自己设过就尊重用户。
    """
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "60")
    os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "30")
    def _truthy(name: str, default: str = "1") -> bool:
        return str(os.environ.get(name, default)).strip().lower() in ("1", "true", "yes", "on")

    try:
        import huggingface_hub.constants as hf_const

        # constants 是「导入时读一次环境变量」，已导入的情况下要同步补丁才生效。
        # 值取自环境变量本身，这样用户显式写成 0/false 时不会被我们强行打开。
        hf_const.HF_HUB_DISABLE_XET = _truthy("HF_HUB_DISABLE_XET")
        hf_const.HF_HUB_DISABLE_IMPLICIT_TOKEN = _truthy("HF_HUB_DISABLE_IMPLICIT_TOKEN")
        if getattr(hf_const, "HF_HUB_DOWNLOAD_TIMEOUT", 10) < 60:
            hf_const.HF_HUB_DOWNLOAD_TIMEOUT = 60
        if getattr(hf_const, "HF_HUB_ETAG_TIMEOUT", 10) < 30:
            hf_const.HF_HUB_ETAG_TIMEOUT = 30
    except Exception:  # noqa: BLE001  huggingface_hub 没装时不影响其它功能
        pass


# 模块导入即生效，越早越好
harden_hf_env()


def apply_endpoint(endpoint: str) -> None:
    """让后续的 HuggingFace 下载走指定端点。

    huggingface_hub 的 constants.ENDPOINT 是「导入时读一次环境变量」，
    所以除了写环境变量，还要在已导入的情况下同步补丁模块常量，否则重试无效。
    """
    harden_hf_env()  # 每次切换端点都确保加固项还在（别被其它库覆盖掉）
    if endpoint:
        os.environ["HF_ENDPOINT"] = endpoint
    else:
        os.environ.pop("HF_ENDPOINT", None)
    try:
        import huggingface_hub.constants as hf_const

        base = (endpoint or getattr(hf_const, "_HF_DEFAULT_ENDPOINT", HF_OFFICIAL)).rstrip("/")
        hf_const.ENDPOINT = base
        hf_const.HUGGINGFACE_CO_URL_TEMPLATE = base + "/{repo_id}/resolve/{revision}/{filename}"
    except Exception:  # noqa: BLE001  huggingface_hub 还没装也不用炸
        pass


def model_repo_id(model_name: str) -> str:
    """faster-whisper 的简短名字 → HuggingFace 仓库 id（取不到就原样返回）。"""
    name = model_name or "base"
    try:
        from faster_whisper.utils import _MODELS  # noqa: PLC2701  私有映射，取不到就降级

        return _MODELS.get(name, name)
    except Exception:  # noqa: BLE001
        return name


def model_cached(model_name: str) -> bool:
    """模型是否已经下载到本地缓存（用于给出「正在下载模型」的准确提示）。"""
    repo_id = model_repo_id(model_name).replace("/", "--")
    candidates = []
    try:
        import huggingface_hub.constants as hf_const

        candidates.append(Path(getattr(hf_const, "HF_HUB_CACHE", "")))
    except Exception:  # noqa: BLE001
        pass
    hf_home = os.environ.get("HF_HOME")
    if hf_home:
        candidates.append(Path(hf_home) / "hub")
    candidates.append(Path.home() / ".cache" / "huggingface" / "hub")
    for base in candidates:
        try:
            # CTranslate2 权重文件是判断"下没下过"最可靠的标志
            if any((Path(base) / ("models--" + repo_id)).rglob("model.bin")):
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def _default_loader(name: str):
    from faster_whisper import WhisperModel

    # 固定 CPU 推理（device=auto 在无 CUDA 库的机器上会因 cublas 缺失而失败）
    return WhisperModel(name, device="cpu", compute_type="int8")


def load_model(name: str, endpoint_mode: str = "", loader: Optional[Callable[[str], object]] = None):
    """按下载源策略加载模型；官方源失败会自动改用镜像重试。"""
    loader = loader or _default_loader
    errors: List[str] = []
    for endpoint, label in resolve_endpoints(endpoint_mode):
        apply_endpoint(endpoint)
        try:
            return loader(name)
        except ImportError as exc:
            raise RuntimeError("未安装 faster-whisper。请先执行 pip install faster-whisper 后重试") from exc
        except Exception as exc:  # noqa: BLE001
            errors.append(label + "：" + str(exc)[:200])
    detail = errors[-1] if errors else "未知错误"
    raise ModelDownloadError(_MODEL_HINT + "\n（最后失败：" + detail + "）")


def _get_model(model_name: str, endpoint_mode: str = ""):
    name = model_name or "base"
    with _MODEL_LOCK:
        if name not in _MODELS:
            _MODELS[name] = load_model(name, endpoint_mode)
        return _MODELS[name]



def _decode(path: str, model_name: Optional[str], language: Optional[str],
            endpoint_mode: str = "", progress=None, beam: int = 1) -> List[dict]:
    """对本地音视频文件做一次转写（PyAV 解码，不依赖系统 ffmpeg）。

    progress(已转写秒数, 总秒数)：逐段回调，用来给界面**真实进度**。
    以前转写期间只写一句"耗时较长"的静态文案，加上前端进度条封顶 35%，
    长视频（比如 1 小时）看起来就像卡死了。
    """
    model = _get_model(model_name or "base", endpoint_mode)
    try:
        segments, info = model.transcribe(
            path,
            language=language or None,  # None = 自动检测
            # beam 5 → 1：CPU 上大约快 2-3 倍，讲课音频的识别质量差别很小。
            # 可用设置项 whisper_beam 改回 5（更准但更慢）。
            beam_size=max(1, int(beam or 1)),
            vad_filter=True,  # 过滤静音/片头片尾噪声
        )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "音频解码失败：该文件可能没有音轨，或编码格式不受支持（" + str(exc) + "）"
        ) from exc
    total = float(getattr(info, "duration", 0) or 0)
    out: List[dict] = []
    for s in segments:
        out.append({"start": float(s.start), "end": float(s.end), "text": s.text.strip()})
        if progress:
            try:
                progress(float(s.end), total)
            except Exception:  # noqa: BLE001  进度上报失败不影响转写
                pass
    if progress:
        try:
            progress(total or 0, total or 0)
        except Exception:  # noqa: BLE001
            pass
    return out


def transcribe_file(path: str, model_name: Optional[str] = None, language: Optional[str] = None,
                    endpoint_mode: str = "", progress=None, beam: int = 1) -> List[dict]:
    """直接转写本地视频/音频文件（mp4/mkv/flv/m4a/mp3 等，取决于 PyAV 解码支持）。"""
    if not path or not os.path.isfile(path):
        raise RuntimeError("本地文件不存在或已被移动：" + str(path))
    return _decode(path, model_name, language, endpoint_mode, progress=progress, beam=beam)


def _download_audio_with_retry(url: str, ydl_opts: dict, attempts: int = 3) -> None:
    """下载音轨，失败自动重试。

    yt-dlp 默认的 socket 读超时只有 20 秒，B站音频流稍微卡一下就会
    "The read operation timed out" 直接失败；加上重试后同一篇笔记不必重头再来
    （yt-dlp 会续传 .part 文件）。
    """
    last: Optional[Exception] = None
    for i in range(attempts):
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            return
        except Exception as exc:  # noqa: BLE001
            last = exc
            if i < attempts - 1:
                time.sleep(2 * (i + 1))
    raise RuntimeError(last)


def transcribe(bvid: str, page: int = 1, model_name: Optional[str] = None, language: Optional[str] = None,
               cookie: str = "", endpoint_mode: str = "", progress=None, beam: int = 1) -> List[dict]:
    url = video_url(bvid, page)

    with tempfile.TemporaryDirectory() as tmp:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,  # 关键：只处理当前分P，避免合集整单下载
            # 直接下载音轨（DASH m4a 单流），无需 ffmpeg 合并/转码
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "outtmpl": os.path.join(tmp, "audio.%(ext)s"),
            # 网络加固：默认读超时 20 秒、重试次数少，音频流卡一下就整篇失败
            "socket_timeout": 60,
            "retries": 10,
            "fragment_retries": 10,
            "extractor_retries": 5,
            "file_access_retries": 3,
            "continuedl": True,  # 保留 .part，重试时能续传
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
                "Referer": "https://www.bilibili.com/",
            },
        }
        # 登录态用 yt-dlp 原生 cookiefile（设置里的 B站 Cookie），比塞 Cookie 头可靠
        cooked = cookie_file(cookie)
        if cooked:
            ydl_opts["cookiefile"] = cooked
        try:
            _download_audio_with_retry(url, ydl_opts)
        except Exception as exc:  # noqa: BLE001
            if has_proxy_env():
                saved = clear_proxy_env()
                try:
                    _download_audio_with_retry(url, ydl_opts)
                except Exception as exc2:  # noqa: BLE001
                    raise RuntimeError("音频下载失败：" + str(exc2)) from exc2
                finally:
                    restore_proxy_env(saved)
            else:
                raise RuntimeError("音频下载失败：" + str(exc)) from exc
        files = [f for f in os.listdir(tmp) if f.startswith("audio.")]
        if not files:
            raise RuntimeError("音频下载失败：未找到音频文件")

        return _decode(os.path.join(tmp, files[0]), model_name, language, endpoint_mode,
                       progress=progress, beam=beam)
