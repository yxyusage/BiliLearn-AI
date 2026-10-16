"""NO_PROXY / Cookie 归一化的离线回归测试（不联网）。

覆盖两个会让后端"整个网络层"失效的输入：

1. NO_PROXY 里带方括号的 IPv6（``[::1]``）或 IPv6 CIDR（``::1/128``）——
   httpx 0.28 的 get_environment_proxies 会生成 ``all://*[::1]`` /
   ``all://[::1/128]``，URLPattern 解析时抛 InvalidURL，导致**任何**
   ``httpx.Client()`` 都构造不出来。Clash Verge / mihomo 默认导出
   ``no_proxy=127.0.0.1,localhost,::1,[::1]``，命中面很广。

2. 浏览器 Cookie 表格 Ctrl+A 整表复制得到的是 TSV，首行是中文表头
   （名称/值/域/路径），原样塞进请求头会抛
   ``UnicodeEncodeError: 'ascii' codec can't encode characters``。
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.services import bilibili, netutil


# ---------------------------------------------------------------- NO_PROXY

def test_sanitize_removes_brackets():
    """带方括号的 IPv6 必须被归一化成裸字面量，否则 httpx 构造 Client 就崩。"""
    saved = {k: os.environ.get(k) for k in ("NO_PROXY", "no_proxy")}
    try:
        os.environ["NO_PROXY"] = "127.0.0.1,localhost,::1,[::1]"
        os.environ["no_proxy"] = "127.0.0.1,localhost,::1,[::1]"
        netutil.sanitize_no_proxy()
        assert os.environ["NO_PROXY"] == "127.0.0.1,localhost,::1,::1", os.environ["NO_PROXY"]
        assert "[" not in os.environ["NO_PROXY"]
        assert "[" not in os.environ["no_proxy"]
        print("sanitize-brackets OK")
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_sanitize_strips_port_and_cidr():
    """[::1]:8080 与 ::1/128 也要变成可解析形式，且不能拼出新的合法 IPv6。"""
    cases = {
        "[::1]:8080": "::1",
        "[2001:db8::1]:443": "2001:db8::1",
        "::1/128": "::1",
        "2001:db8::/32": "2001:db8::",
    }
    for raw, want in cases.items():
        got = netutil._normalize_no_proxy_entry(raw)
        assert got == want, f"{raw!r} -> {got!r}，期望 {want!r}"
        # 关键回归：不能把 [::1]:8080 变成 "::1:8080"（那是另一个合法 IPv6 地址）
        assert got != "::1:8080"
    print("sanitize-port-cidr OK")


def test_sanitize_is_noop_for_normal_values():
    """正常的域名 / IPv4 / IPv4 CIDR / scheme / * 必须逐字节不动。"""
    for raw in (
        "127.0.0.1,localhost,::1",
        "example.com,.example.com",
        "192.168.0.0/16,10.0.0.0/8",
        "http://example.com",
        "*",
        "",
    ):
        saved = {k: os.environ.get(k) for k in ("NO_PROXY", "no_proxy")}
        try:
            os.environ["NO_PROXY"] = raw
            os.environ["no_proxy"] = raw
            netutil.sanitize_no_proxy()
            assert os.environ["NO_PROXY"] == raw, f"{raw!r} 被改成了 {os.environ['NO_PROXY']!r}"
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
    print("sanitize-noop OK")


def test_client_constructs_after_sanitize():
    """端到端：脏 NO_PROXY 下 Client() 会抛异常；清理后必须能构造。

    httpx 不在时跳过（测试仍算通过），避免 CI 因环境差异红掉。
    """
    try:
        import httpx
    except ImportError:
        print("client-constructs SKIP (httpx 未安装)")
        return

    saved = {k: os.environ.get(k) for k in ("NO_PROXY", "no_proxy")}
    try:
        dirty = "127.0.0.1,localhost,::1,[::1]"
        os.environ["NO_PROXY"] = dirty
        os.environ["no_proxy"] = dirty
        crashed = False
        try:
            httpx.Client()
        except Exception:  # noqa: BLE001 这里就是要它崩
            crashed = True
        assert crashed, "脏 NO_PROXY 下 httpx.Client() 竟然没报错？"

        netutil.sanitize_no_proxy()
        client = httpx.Client()  # 清理后必须能构造
        client.close()
        print("client-constructs OK")
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ----------------------------------------------------------------- Cookie

def test_normalize_cookie_tsv_with_chinese_header():
    """Edge 整表复制（TSV + 中文表头）必须被解析成合法 cookie。"""
    raw = "名称\t值\t域\t路径\nSESSDATA\tFAKE123\t.bilibili.com\t/\nbili_jct\tFAKE456\t.bilibili.com\t/"
    out = bilibili.normalize_cookie(raw)
    assert out == "SESSDATA=FAKE123; bili_jct=FAKE456", out
    assert all(ord(ch) < 128 for ch in out), "结果必须是纯 ASCII"
    assert bilibili.has_sessdata(raw), "应当能从原始文本识别出 SESSDATA"
    print("normalize-tsv OK")


def test_normalize_cookie_drops_non_ascii_values():
    """值里混入中文（或 … 之类）时必须剔除该条，而不是原样抛 UnicodeEncodeError。"""
    raw = "SESSDATA=FAKE123; 中文名=测试; bili_jct=FAKE456"
    out = bilibili.normalize_cookie(raw)
    assert out == "SESSDATA=FAKE123; bili_jct=FAKE456", out
    assert "中文名" not in out
    print("normalize-nonascii OK")


def test_normalize_cookie_keeps_valid_forms():
    """标准形式不能被破坏：分号、换行、引号、空值项都要正确处理。"""
    cases = {
        "SESSDATA=FAKE123; bili_jct=FAKE456; DedeUserID=789":
            "SESSDATA=FAKE123; bili_jct=FAKE456; DedeUserID=789",
        "SESSDATA=FAKE123;\nbili_jct=FAKE456":
            "SESSDATA=FAKE123; bili_jct=FAKE456",
        'SESSDATA="FAKE123"; bili_jct="FAKE456"':
            "SESSDATA=FAKE123; bili_jct=FAKE456",
        "SESSDATA=FAKE123; empty=; bili_jct=FAKE456":
            "SESSDATA=FAKE123; bili_jct=FAKE456",
        "SESSDATA\tFAKE123":
            "SESSDATA=FAKE123",
    }
    for raw, want in cases.items():
        got = bilibili.normalize_cookie(raw)
        assert got == want, f"{raw!r} -> {got!r}，期望 {want!r}"
    print("normalize-valid OK")


def test_normalize_cookie_rejects_garbage():
    """解析不出任何有效项时返回空串（由调用方给出可读提示，而不是抛异常）。"""
    for raw in ("", "   ", "名称 值 域 路径", ";;;", "==="):
        assert bilibili.normalize_cookie(raw) == "", repr(raw)
    print("normalize-garbage OK")


def test_verify_cookie_never_raises_ascii():
    """回归：脏输入下 verify_cookie 必须返回结论 dict，不能抛 UnicodeEncodeError。"""
    dirty = [
        "名称\t值\t域\t路径\nSESSDATA\tFAKE\t.bilibili.com\t/",
        "SESSDATA=FAKE; 中文=测试",
        "名称 值 域 路径",
    ]
    for raw in dirty:
        r = bilibili.verify_cookie(raw)
        assert isinstance(r, dict)
        assert "message" in r and "has_sessdata" in r
        msg = r["message"].lower()
        assert "ascii" not in msg and "codec" not in msg, r["message"]
    print("verify-cookie-no-raise OK")


def test_cookie_file_uses_normalized_value():
    """cookie_file 也必须走归一化，否则 yt-dlp 会拿到带中文表头的文件。

    注意：文件头的注释行本来就是中文（上游既有行为），这里只校验**数据行**。
    """
    try:
        path = bilibili.cookie_file("名称\t值\nSESSDATA\tFAKE123\nbili_jct\tFAKE456")
        assert path, "应当生成 cookie 文件"
        text = Path(path).read_text(encoding="utf-8")
        data_rows = [ln for ln in text.splitlines() if ln and not ln.startswith("#")]
        assert len(data_rows) == 2, data_rows
        for row in data_rows:
            assert all(ord(ch) < 128 for ch in row), f"数据行含非 ASCII：{row!r}"
        fields = {r.split("\t")[5]: r.split("\t")[6] for r in data_rows}
        assert fields["SESSDATA"] == "FAKE123"
        assert fields["bili_jct"] == "FAKE456"
        print("cookie-file-normalized OK")
    finally:
        bilibili.clear_cookie_file()


if __name__ == "__main__":
    test_sanitize_removes_brackets()
    test_sanitize_strips_port_and_cidr()
    test_sanitize_is_noop_for_normal_values()
    test_client_constructs_after_sanitize()
    test_normalize_cookie_tsv_with_chinese_header()
    test_normalize_cookie_drops_non_ascii_values()
    test_normalize_cookie_keeps_valid_forms()
    test_normalize_cookie_rejects_garbage()
    test_verify_cookie_never_raises_ascii()
    test_cookie_file_uses_normalized_value()
    print("ALL_NET_COOKIE_TESTS_PASSED")
