"""离线冒烟测试：字幕解析 / 导出 / 时间戳（不依赖网络与 API Key）。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.services.bilibili import _clean_sub_text, _parse_json_sub, _parse_srt_vtt, extract_bvid
from backend.app.services.export import build_anki_apkg, render_note_html, render_note_markdown, words_to_csv
from backend.app.services.note_generator import normalize_note
from backend.app.services.quiz_generator import judge_fill, normalize_fill_answer
from backend.app.utils.timestamp import hms_to_seconds, normalize_hms, seconds_to_hms


def test_extract_bvid():
    assert extract_bvid("https://www.bilibili.com/video/BV1GJ411x7h7?p=2") == "BV1GJ411x7h7"
    assert extract_bvid("BV1xx411c7mD") == "BV1xx411c7mD"
    print("bvid OK")


def test_srt():
    srt = "1\n00:00:01,500 --> 00:00:04,000\nhello <i>world</i>\n\n2\n00:01:00,000 --> 00:01:03,500\nsecond line\n"
    items = _parse_srt_vtt(srt)
    assert len(items) == 2
    assert items[0]["text"] == "hello world"
    assert abs(items[0]["start"] - 1.5) < 1e-6
    print("srt OK", items[0])


def test_vtt():
    vtt = "WEBVTT\n\n00:00:03.000 --> 00:00:06.000\n你好世界\n"
    items = _parse_srt_vtt(vtt)
    assert items[0]["text"] == "你好世界"
    print("vtt OK")


def test_bili_json():
    body = {"body": [{"from": 10.5, "to": 13.2, "content": "第一条字幕"}, {"from": 14, "to": 16, "content": "第二条"}]}
    items = _parse_json_sub(body)
    assert len(items) == 2 and items[0]["text"] == "第一条字幕"
    ms = {"body": [{"from": 15000, "to": 19000, "content": "毫秒字幕"}]}
    items2 = _parse_json_sub(ms)
    assert abs(items2[0]["start"] - 15.0) < 1e-6
    assert _clean_sub_text("  a   b  ") == "a b"
    print("bili-json OK")


def test_timestamp():
    assert seconds_to_hms(754.6) == "00:12:35"
    assert hms_to_seconds("00:12:34") == 754
    assert normalize_hms("1:05") == "00:01:05"
    assert normalize_hms(90) == "00:01:30"
    print("timestamp OK")


def test_exports():
    legacy = {
        "title": "测试笔记",
        "summary": "这是摘要",
        "chapters": [{
            "title": "第一章",
            "points": [{"content": "知识点 A $x^2$", "time_stamp": "00:00:05", "important": True}],
        }],
        "mindmap": "mindmap\n  根((测试))",
    }
    note = normalize_note(legacy)
    secs = note["chapters"][0]["sections"]
    assert secs and secs[0]["blocks"]
    words = {"words": [{"word": "test", "phonetic": "/test/", "meaning": "测试", "sentence": "this is a test", "time_stamp": "00:00:05"}], "pronunciations": []}
    md = render_note_markdown(note, "math", words)
    assert "第一章" in md and "00:00:05" in md and "mermaid" in md and "生词本" in md
    page = render_note_html(note, "math", words)
    assert "b-formula" in page or "知识点" in page
    # 填空题判分
    answer = normalize_fill_answer(["牛顿 / Newton", "f=ma / F=ma"])
    ok1, _ = judge_fill(answer, ["newton", "F = ma"])
    ok2, per = judge_fill(answer, ["牛顿", "e=mc2"])
    assert ok1 and not ok2 and per == [True, False]
    apkg = build_anki_apkg(words["words"], "测试生词本")
    assert apkg[:2] == b"PK"
    csv_text = words_to_csv(words["words"])
    assert csv_text.startswith(chr(0xFEFF) + "word") and "hello" not in csv_text and "test" in csv_text
    print("exports OK", {"md": len(md), "html": len(page), "apkg": len(apkg), "csv": len(csv_text)})


if __name__ == "__main__":
    test_extract_bvid()
    test_srt()
    test_vtt()
    test_bili_json()
    test_timestamp()
    test_exports()
    print("ALL_UNIT_TESTS_PASSED")
