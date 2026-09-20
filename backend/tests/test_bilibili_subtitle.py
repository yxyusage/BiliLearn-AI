"""离线单元测试：B站官方字幕接口的字幕归属校验（不依赖网络与 API Key）。

背景
----
player/v2 接口有时会返回**指向其它视频**的字幕 URL：文件真实存在、能正常
下载、格式完全合法，但内容与当前视频毫无关系。实测一个语文课视频拿到过
手机评测、时事行情、韩综等毫不相干的内容，最终生成出完全跑题的笔记。

正确字幕的文件路径形如 /prod/{aid}{cid}{随机后缀}，因此用「路径必须以
{aid}{cid} 开头」做硬校验。本文件覆盖该校验函数，并通过 mock httpx 验证
调用方能跳过假 URL、且在只有假 URL 时安全返回空。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.services import bilibili as bili
from backend.app.services.bilibili import _SilentLogger, _subtitle_url_matches

AID = 100
CID = 200
GOOD_PATH = f"{AID}{CID}"          # 100200
GOOD_URL = f"//aisubtitle.hdslb.com/bfs/ai_subtitle/prod/{GOOD_PATH}abc123?auth_key=x"
FOREIGN_URL = "//aisubtitle.hdslb.com/bfs/ai_subtitle/prod/999888777abc?auth_key=x"


# ────────────────────────── 纯函数：归属校验 ──────────────────────────

def test_matches_accepts_own_video():
    assert _subtitle_url_matches(GOOD_URL, AID, CID) is True
    assert _subtitle_url_matches("https://" + GOOD_URL[2:], AID, CID) is True
    assert _subtitle_url_matches("/" + GOOD_URL[2:], AID, CID) is True
    print("归属校验-接受本视频 OK")


def test_matches_rejects_foreign_video():
    assert _subtitle_url_matches(FOREIGN_URL, AID, CID) is False
    # 只匹配 cid 但 aid 不对，同样必须拒绝
    assert _subtitle_url_matches(
        "//aisubtitle.hdslb.com/bfs/ai_subtitle/prod/999200abc?auth_key=x", AID, CID
    ) is False
    print("归属校验-拒绝他视频 OK")


def test_matches_edge_cases():
    assert _subtitle_url_matches("", AID, CID) is False
    assert _subtitle_url_matches("https://example.com/x", AID, CID) is False
    assert _subtitle_url_matches(GOOD_URL, None, CID) is True       # 缺 aid 时退化为只校验 cid
    assert _subtitle_url_matches(GOOD_URL, None, None) is False     # 两个都没有 → 一律拒绝
    print("归属校验-边界情况 OK")


# ────────────────────────── mock httpx：跳过假 URL ──────────────────────────

class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _install_fake_httpx(player_payloads, sub_payloads):
    """把 bilibili 模块用到的 httpx.get 换成按 URL 分派的假实现。

    返回 (恢复函数, 计数器)。计数器记录真实发生了几次字幕文件下载。
    """
    state = {"player": 0, "sub": 0, "sub_urls": []}

    def _fake_get(url, **kwargs):
        if "web-interface/view" in url:
            return _FakeResp({
                "code": 0,
                "data": {"aid": AID, "cid": CID, "pages": [{"page": 1, "cid": CID}]},
            })
        if "player/v2" in url:
            idx = min(state["player"], len(player_payloads) - 1)
            state["player"] += 1
            return _FakeResp(player_payloads[idx])
        # 字幕文件
        state["sub_urls"].append(url)
        idx = min(state["sub"], len(sub_payloads) - 1)
        state["sub"] += 1
        return _FakeResp(sub_payloads[idx])

    original = bili.httpx.get
    bili.httpx.get = _fake_get
    return (lambda: setattr(bili.httpx, "get", original)), state


def _player_payload(url):
    return {"code": 0, "data": {"subtitle": {"subtitles": [
        {"lan": "ai-zh", "lan_doc": "中文", "subtitle_url": url},
    ]}}}


SUB_BODY = {"body": [
    {"from": 0.0, "to": 2.0, "content": "第一句"},
    {"from": 2.0, "to": 4.0, "content": "第二句"},
]}


def test_api_skips_foreign_url_and_returns_correct():
    """第 1 次返回假 URL、第 2 次返回真 URL：应跳过假的，拿到真的。"""
    restore, state = _install_fake_httpx(
        player_payloads=[_player_payload(FOREIGN_URL), _player_payload(GOOD_URL)],
        sub_payloads=[SUB_BODY],
    )
    try:
        items = bili._get_subtitles_via_api("BV1xx411c7mD", 1, "SESSDATA=fake")
    finally:
        restore()
    assert len(items) == 2, items
    assert items[0]["text"] == "第一句"
    # 关键：假 URL 绝不能被下载
    assert len(state["sub_urls"]) == 1, state["sub_urls"]
    assert GOOD_PATH in state["sub_urls"][0]
    assert "999888777" not in state["sub_urls"][0]
    print("跳过假URL并采纳真URL OK", [i["text"] for i in items])


def test_api_returns_empty_when_only_foreign():
    """只有假 URL 时：必须返回空，绝不能把别的视频内容当成当前视频的字幕。"""
    restore, state = _install_fake_httpx(
        player_payloads=[_player_payload(FOREIGN_URL)],
        sub_payloads=[SUB_BODY],
    )
    try:
        items = bili._get_subtitles_via_api("BV1xx411c7mD", 1, "SESSDATA=fake")
    finally:
        restore()
    assert items == [], items
    assert state["sub_urls"] == [], state["sub_urls"]
    print("仅假URL时安全返回空 OK")


def test_api_returns_empty_when_no_url():
    """接口返回空 URL（实测常见）时也必须安全返回空。"""
    restore, _ = _install_fake_httpx(
        player_payloads=[_player_payload("")],
        sub_payloads=[SUB_BODY],
    )
    try:
        items = bili._get_subtitles_via_api("BV1xx411c7mD", 1, "")
    finally:
        restore()
    assert items == []
    print("空URL时安全返回空 OK")


# ────────────────────────── 静默日志器 ──────────────────────────

def test_silent_logger_swallows_everything():
    """静默器要吞掉所有级别的日志，避免写 stdout/stderr 触发 BrokenPipeError。"""
    logger = _SilentLogger()
    assert logger.debug("x") is None
    assert logger.info("x") is None
    assert logger.warning("x") is None
    assert logger.error("x") is None
    print("静默日志器 OK")


if __name__ == "__main__":
    test_matches_accepts_own_video()
    test_matches_rejects_foreign_video()
    test_matches_edge_cases()
    test_api_skips_foreign_url_and_returns_correct()
    test_api_returns_empty_when_only_foreign()
    test_api_returns_empty_when_no_url()
    test_silent_logger_swallows_everything()
    print("ALL_SUBTITLE_TESTS_PASSED")
