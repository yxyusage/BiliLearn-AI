"""B站 Cookie 单元测试（离线，不联网）：

1. Cookie 字符串能转成 yt-dlp 认的 Netscape cookie 文件；
2. 解析视频时确实把 cookiefile 交给了 yt-dlp（而不是塞在 http_headers 里）；
3. 能识别出 Cookie 里有没有登录凭证 SESSDATA。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.services import bilibili


def test_has_sessdata():
    assert bilibili.has_sessdata("a=1; SESSDATA=xxx; b=2")
    assert bilibili.has_sessdata("sessdata=xxx")
    assert not bilibili.has_sessdata("a=1; b=2")
    assert not bilibili.has_sessdata("")
    print("has-sessdata OK")


def test_cookie_file_format():
    path = bilibili.cookie_file("SESSDATA=abc123; bili_jct=def456; buvid3=xyz")
    assert path, "应当生成 cookie 文件"
    p = Path(path)
    assert p.exists()
    text = p.read_text(encoding="utf-8")
    assert "Netscape HTTP Cookie File" in text
    rows = [ln for ln in text.splitlines() if ln and not ln.startswith("#")]
    assert len(rows) == 3, rows
    fields = {row.split("\t")[5]: row.split("\t")[6] for row in rows}
    assert fields["SESSDATA"] == "abc123"
    assert fields["bili_jct"] == "def456"
    for row in rows:
        parts = row.split("\t")
        assert parts[0] == ".bilibili.com" and parts[2] == "/" and parts[6]
    print("cookie-file OK", path)


def test_empty_cookie():
    assert bilibili.cookie_file("") == ""
    assert bilibili.cookie_file("   ") == ""
    assert bilibili.cookie_file(";;;") == ""
    print("empty-cookie OK")


def test_parse_video_passes_cookiefile():
    """关键回归：Cookie 必须通过 cookiefile 交给 yt-dlp，而不是塞在 http_headers。"""
    captured = {}

    class FakeYDL:
        def __init__(self, opts):
            captured.clear()
            captured.update(opts)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def extract_info(self, url, download=False):
            return {"_type": "video", "title": "测试视频", "uploader": "UP"}

    original = bilibili.yt_dlp.YoutubeDL
    bilibili.yt_dlp.YoutubeDL = FakeYDL
    try:
        info = bilibili.parse_video("https://www.bilibili.com/video/BV1xx411c7mD", "SESSDATA=abc123; bili_jct=1")
    finally:
        bilibili.yt_dlp.YoutubeDL = original

    assert info["bvid"] == "BV1xx411c7mD"
    cookiefile = captured.get("cookiefile")
    assert cookiefile, "yt-dlp 没拿到 cookiefile：" + repr(list(captured.keys()))
    assert Path(cookiefile).exists()
    assert "SESSDATA\tabc123" in Path(cookiefile).read_text(encoding="utf-8")
    assert "Cookie" not in (captured.get("http_headers") or {}), "不应再手动塞 Cookie 头"
    print("parse-video-cookiefile OK")


if __name__ == "__main__":
    try:
        test_has_sessdata()
        test_cookie_file_format()
        test_empty_cookie()
        test_parse_video_passes_cookiefile()
    finally:
        # 测试写的是假 Cookie，别把它留在磁盘上被后续请求用掉
        bilibili.clear_cookie_file()
    print("ALL_BILI_COOKIE_TESTS_PASSED")
