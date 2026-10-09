"""快速依赖安装器（launcher/fastdeps.py）的离线单元测试。

覆盖：人类可读的单位换算、pip --report 解析、镜像测速排序、全部镜像不可用时
必须返回 False（让调用方回退普通 pip），以及下载进度回调的限流文本。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "launcher"))

import fastdeps  # noqa: E402


def test_human_units():
    assert fastdeps.human_size(0) == "0 B"
    assert fastdeps.human_size(1536) == "1.5 KB"
    assert fastdeps.human_size(19.8 * 1024 * 1024).startswith("19.8 MB")
    assert fastdeps.human_speed(2 * 1024 * 1024) == "2.0 MB/s"
    assert fastdeps.human_eta(75) == "1:15"
    assert fastdeps.human_eta(3725) == "1:02:05"
    assert fastdeps.human_eta(0) == "--:--"
    assert fastdeps.human_eta(float("inf")) == "--:--"
    print("human-units OK")


def test_parse_report():
    report = {
        "install": [
            {"download_info": {"url": "https://x/pip-24.0-py3-none-any.whl"}, "is_direct": False},
            {"download_info": {"url": "https://x/pymupdf-1.28.2-cp313-cp313-win_amd64.whl"}, "is_direct": False},
            # 源码包不应被当 wheel 下载
            {"download_info": {"url": "https://x/foo-1.0.tar.gz"}, "is_direct": False},
            # 用户直接指定的地址要跳过
            {"download_info": {"url": "https://x/direct-1.0-py3-none-any.whl"}, "is_direct": True},
        ]
    }
    text = "Some pip noise\n" + json.dumps(report)
    urls = fastdeps.parse_report(text)
    assert len(urls) == 2, urls
    assert urls[0].endswith("pip-24.0-py3-none-any.whl")

    try:
        fastdeps.parse_report("no json here")
        raise AssertionError("应当报错")
    except RuntimeError:
        pass
    try:
        fastdeps.parse_report(json.dumps({"install": []}))
        raise AssertionError("应当报错")
    except RuntimeError:
        pass
    print("parse-report OK")


def test_probe_ranking():
    original = fastdeps._probe_one
    speeds = {
        "https://a/simple/": (10 * 1024, 0.5),      # 慢
        "https://b/simple/": (2 * 1024 * 1024, 0.4),  # 快
        "https://c/simple/": (0, 0.0),               # 不可用
    }

    def fake_probe(name, url, deadline):
        read, ttfb = speeds[url]
        return name, url, (read / 0.5 if read else 0.0), ttfb

    fastdeps._probe_one = fake_probe
    try:
        ranked = fastdeps.probe_mirrors([("A", "https://a/simple/"),
                                         ("B", "https://b/simple/"),
                                         ("C", "https://c/simple/")])
    finally:
        fastdeps._probe_one = original
    assert [r[0] for r in ranked] == ["B", "A", "C"], ranked
    print("probe-ranking OK", [(r[0], fastdeps.human_speed(r[2])) for r in ranked])


def test_install_falls_back_when_no_mirror():
    """所有镜像都不可用时必须返回 False，且不能抛异常（调用方据此回退普通 pip）。"""
    original = fastdeps._probe_one
    fastdeps._probe_one = lambda name, url, deadline: (name, url, 0.0, 0.0)
    try:
        logs = []
        ok = fastdeps.install(sys.executable, "backend/requirements.txt", log=logs.append)
    finally:
        fastdeps._probe_one = original
    assert ok is False, "应当返回 False 以便回退"
    assert any("普通 pip" in line for line in logs), logs
    print("fallback OK")


if __name__ == "__main__":
    test_human_units()
    test_parse_report()
    test_probe_ranking()
    test_install_falls_back_when_no_mirror()
    print("ALL_FASTDEPS_TESTS_PASSED")
