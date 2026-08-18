"""离线冒烟测试：字幕解析 / 导出 / 时间戳（不依赖网络与 API Key）。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.services.bilibili import _clean_sub_text, _parse_json_sub, _parse_srt_vtt, extract_bvid
from backend.app.services.export import build_anki_apkg, markdown_to_pdf_bytes, render_note_markdown, words_to_csv
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
    note = {
        "title": "测试笔记",
        "summary": "这是摘要",
        "chapters": [{
            "title": "第一章",
            "points": [{"content": "知识点 A $x^2$", "time_stamp": "00:00:05", "important": True}],
        }],
        "mindmap": "mindmap\n  根((测试))",
    }
    words = {"words": [{"word": "test", "phonetic": "/test/", "meaning": "测试", "sentence": "this is a test", "time_stamp": "00:00:05"}], "pronunciations": []}
    md = render_note_markdown(note, "math", words)
    assert "第一章" in md and "00:00:05" in md and "mermaid" in md and "生词本" in md
    pdf = markdown_to_pdf_bytes(md, "测试")
    assert len(pdf) > 1000 and pdf[:4] == b"%PDF"
    apkg = build_anki_apkg(words["words"], "测试生词本")
    assert apkg[:2] == b"PK"
    csv_text = words_to_csv(words["words"])
    assert csv_text.startswith(chr(0xFEFF) + "word") and "hello" not in csv_text and "test" in csv_text
    print("exports OK", {"md": len(md), "pdf": len(pdf), "apkg": len(apkg), "csv": len(csv_text)})


if __name__ == "__main__":
    test_extract_bvid()
    test_srt()
    test_vtt()
    test_bili_json()
    test_timestamp()
    test_exports()
    print("ALL_UNIT_TESTS_PASSED")
