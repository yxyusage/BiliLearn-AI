"""B站链接归一化回归测试（离线，不联网）。

背景：用户粘贴的是 B站「分享」出来的短链（https://b23.tv/xxxx），它本身不含 BV 号。
旧版 extract_bvid() 匹配不到时会**兜底返回原始输入**，于是短链被当成 BV 号一路带下去，
最终拼出 https://www.bilibili.com/video/https://b23.tv/xxxx 这种畸形地址，
yt-dlp 报 "Unsupported URL"，前端显示「生成已暂停（网络中断）」。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.services import bilibili


def test_extract_bvid_basics():
    assert bilibili.extract_bvid("https://www.bilibili.com/video/BV1YE411D7nH?p=86") == "BV1YE411D7nH"
    assert bilibili.extract_bvid("BV1YE411D7nH") == "BV1YE411D7nH"
    assert bilibili.extract_bvid("bilibili.com/video/BV1YE411D7nH") == "BV1YE411D7nH"
    assert bilibili.extract_bvid("https://www.bilibili.com/video/av170001") == "av170001"
    assert bilibili.extract_bvid("") == ""
    print("extract-basics OK")


def test_extract_bvid_never_returns_raw_input():
    """关键回归：取不到 BV 号必须返回空串，绝不能把原始链接当成编号。"""
    raw = "https://www.bilibili.com/list/ml123456"
    got = bilibili.extract_bvid(raw)
    assert got != raw, "又把原始链接当 BV 号返回了"
    assert got == "", got
    print("never-raw-input OK")


def test_short_link_is_expanded():
    """短链要能取出 BV 号（这里把展开函数换掉，避免测试依赖网络）。"""
    original = bilibili.expand_short_link
    bilibili.expand_short_link = lambda url, timeout=10.0: (
        "https://www.bilibili.com/video/BV11XhF6REBv/?p=7&share_source=COPY" if "b23.tv" in url else url
    )
    try:
        assert bilibili.extract_bvid("https://b23.tv/SPap0F0") == "BV11XhF6REBv"
        assert bilibili.normalize_video_input("https://b23.tv/SPap0F0").endswith("BV11XhF6REBv/?p=7&share_source=COPY")
    finally:
        bilibili.expand_short_link = original
    print("short-link OK")


def test_video_url_validation():
    """拼地址前必须校验，否则又会拼出畸形 URL。"""
    assert bilibili.video_url("BV1YE411D7nH") == "https://www.bilibili.com/video/BV1YE411D7nH"
    assert bilibili.video_url("BV1YE411D7nH", 86) == "https://www.bilibili.com/video/BV1YE411D7nH?p=86"
    assert bilibili.video_url("av170001") == "https://www.bilibili.com/video/av170001"
    for bad in ("", "https://b23.tv/SPap0F0", "https://www.bilibili.com/video/BV1YE411D7nH", "abc"):
        try:
            bilibili.video_url(bad)
            raise AssertionError("应当报错：" + bad)
        except bilibili.VideoError:
            pass
    print("video-url OK")


def test_non_short_url_makes_no_request():
    """普通链接不该触发短链展开（避免多余网络请求）。"""
    called = []
    original = bilibili.expand_short_link
    bilibili.expand_short_link = lambda url, timeout=10.0: (called.append(url), url)[1]
    try:
        assert bilibili.extract_bvid("https://www.bilibili.com/video/BV1YE411D7nH") == "BV1YE411D7nH"
        assert bilibili.normalize_video_input("https://www.bilibili.com/video/BV1YE411D7nH?p=2") == \
            "https://www.bilibili.com/video/BV1YE411D7nH?p=2"
        assert called == [], called
    finally:
        bilibili.expand_short_link = original
    print("no-extra-request OK")


if __name__ == "__main__":
    test_extract_bvid_basics()
    test_extract_bvid_never_returns_raw_input()
    test_short_link_is_expanded()
    test_video_url_validation()
    test_non_short_url_makes_no_request()
    print("ALL_BILI_LINK_TESTS_PASSED")
