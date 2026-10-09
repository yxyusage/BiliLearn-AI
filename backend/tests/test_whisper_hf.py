"""语音模型下载源策略测试（离线，不联网）。

背景：faster-whisper 首次使用要从 huggingface.co 下载权重，国内直连经常「连接超时」
（WinError 10060）。这里覆盖：
1. auto / mirror / official / 自定义 四种模式解析出的尝试顺序；
2. 官方源失败后会自动改用国内镜像重试；
3. 全部失败时抛出带「可操作建议」的 ModelDownloadError，而不是笼统的网络中断。
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.services import whisper


def _clear_env():
    os.environ.pop("HF_ENDPOINT", None)


def test_resolve_endpoints():
    _clear_env()
    auto = whisper.resolve_endpoints("")
    assert [e for e, _ in auto] == [whisper.HF_OFFICIAL, whisper.HF_MIRROR], auto
    assert whisper.resolve_endpoints("auto") == auto

    # 已经设了环境变量就直接用它（start.ps1 / start.sh / 启动器都会设）
    os.environ["HF_ENDPOINT"] = "https://example.com/hf"
    assert [e for e, _ in whisper.resolve_endpoints("")] == ["https://example.com/hf"]
    _clear_env()

    assert [e for e, _ in whisper.resolve_endpoints("mirror")] == [whisper.HF_MIRROR]
    assert [e for e, _ in whisper.resolve_endpoints("official")] == [whisper.HF_OFFICIAL]
    assert [e for e, _ in whisper.resolve_endpoints("https://my.mirror/hf")] == ["https://my.mirror/hf"]
    print("resolve-endpoints OK")


def test_apply_endpoint_patches_hf_hub():
    _clear_env()
    whisper.apply_endpoint(whisper.HF_MIRROR)
    assert os.environ["HF_ENDPOINT"] == whisper.HF_MIRROR
    try:
        import huggingface_hub.constants as hf_const

        assert hf_const.ENDPOINT == whisper.HF_MIRROR, hf_const.ENDPOINT
        assert hf_const.HUGGINGFACE_CO_URL_TEMPLATE.startswith(whisper.HF_MIRROR)
    except ImportError:
        pass
    _clear_env()
    print("apply-endpoint OK")


def test_load_model_falls_back_to_mirror():
    _clear_env()
    calls = []

    def loader(name):
        calls.append(os.environ.get("HF_ENDPOINT", ""))
        if len(calls) == 1:
            raise RuntimeError("Got: ConnectTimeout: [WinError 10060] 连接尝试失败")
        return "MODEL-" + name

    model = whisper.load_model("base", "auto", loader=loader)
    assert model == "MODEL-base"
    assert calls == [whisper.HF_OFFICIAL, whisper.HF_MIRROR], calls
    _clear_env()
    print("fallback-to-mirror OK")


def test_load_model_reports_actionable_error():
    _clear_env()

    def loader(name):
        raise RuntimeError("Got: ConnectTimeout: [WinError 10060] 连接尝试失败")

    try:
        whisper.load_model("base", "auto", loader=loader)
        raise AssertionError("应当抛出 ModelDownloadError")
    except whisper.ModelDownloadError as exc:
        msg = str(exc)
        assert "HF_ENDPOINT" in msg, msg
        assert "hf-mirror" in msg, msg
        assert "连接超时" in msg or "超时" in msg, msg
        assert "WinError 10060" in msg, msg
    _clear_env()
    print("actionable-error OK")


def test_model_download_error_is_not_network_error():
    """模型下载失败不能被判成"网络中断，待恢复"（否则合集会被挂成 paused）。"""
    from backend.app.routers.notes import _is_network_error

    err = whisper.ModelDownloadError(whisper._MODEL_HINT + "（最后失败：ConnectTimeout）")
    assert _is_network_error(err) is False, "ModelDownloadError 被误判成网络中断"
    # 对照：普通连接超时仍然要算网络中断
    assert _is_network_error(RuntimeError("ConnectTimeout: [WinError 10060]")) is True
    print("not-network-error OK")


def test_model_helpers():
    assert whisper.model_repo_id("base") == "Systran/faster-whisper-base"
    assert whisper.model_cached("definitely-not-a-real-model-xyz") is False
    _clear_env()
    print("model-helpers OK")


if __name__ == "__main__":
    try:
        test_resolve_endpoints()
        test_apply_endpoint_patches_hf_hub()
        test_load_model_falls_back_to_mirror()
        test_load_model_reports_actionable_error()
        test_model_download_error_is_not_network_error()
        test_model_helpers()
    finally:
        _clear_env()
    print("ALL_WHISPER_HF_TESTS_PASSED")
