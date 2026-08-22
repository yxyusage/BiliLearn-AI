"""测试 DOCX / XMind 构建。"""
import io
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.services.export import build_note_docx, build_note_xmind

note = {
    "title": "测试课程",
    "summary": "摘要内容",
    "chapters": [{"title": "第一章", "points": [
        {"content": "知识点 $x^2$", "time_stamp": "00:00:05", "important": True},
    ]}],
}
docx = build_note_docx(note, "math", {"words": [{"word": "test", "phonetic": "/t/", "meaning": "测试", "sentence": "s", "time_stamp": "00:00:05"}], "pronunciations": []}, {"bvid": "BV1", "page": 1, "subject_name": "数理", "created_at": "2025-01-01"})
assert docx[:2] == b"PK", "docx should be zip"
print("DOCX_OK", len(docx))

xmind = build_note_xmind(note)
assert xmind[:2] == b"PK"
with zipfile.ZipFile(io.BytesIO(xmind)) as z:
    names = z.namelist()
    assert "content.json" in names
    content = z.read("content.json").decode("utf-8")
    assert "测试课程" in content and "第一章" in content
print("XMIND_OK", len(xmind), names)
print("EXPORTS2_ALL_OK")
