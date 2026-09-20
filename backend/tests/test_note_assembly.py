"""离线单元测试：长视频笔记生成的章节拼装与知识点保全（不依赖网络与 API Key）。

背景
----
原实现让「汇总（reduce）」步骤把全部知识点原样重写一遍，而大模型的输出上限
远小于输入上限（DeepSeek 为 8192 token），长视频必然超出上限被截断，返回的
JSON 不完整，最终报「JSON 解析失败」并生成失败。

现改为：汇总步骤只输出「章节划分方案」（章节标题 + 小节编号归属 + 概述 +
脑图），知识点正文由 _assemble_chapters() 从原始小节里按编号搬运。这样
输出量降到原来的约十分之一，且**时间戳完全不经过模型**，不可能被改写或
编造。

本文件验证两件事：
  1. _assemble_chapters() 在各种异常输入下都不丢知识点；
  2. generate_note() 在模型给出的章节划分残缺/非法时，仍然完整保留所有知识点。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.services.note_generator import _assemble_chapters, generate_note


def _sec(title, texts):
    return {
        "title": title,
        "points": [
            {"content": t, "time_stamp": f"00:00:{i:02d}", "important": True}
            for i, t in enumerate(texts, start=1)
        ],
    }


SECTIONS = [
    _sec("第一节", ["a1", "a2"]),
    _sec("第二节", ["b1", "b2"]),
    _sec("第三节", ["c1", "c2"]),
]
TOTAL_POINTS = 6


def _count(chapters):
    return sum(len(c["points"]) for c in chapters)


# ────────────────────────── _assemble_chapters 的四种情况 ──────────────────────────

def test_assemble_normal():
    plan = [{"title": "第一章", "sections": [1, 2]}, {"title": "第二章", "sections": [3]}]
    out = _assemble_chapters(plan, SECTIONS)
    assert [c["title"] for c in out] == ["第一章", "第二章"], out
    assert _count(out) == TOTAL_POINTS, out
    assert len(out[0]["points"]) == 4 and len(out[1]["points"]) == 2, out
    print("章节拼装-正常划分 OK", [(c["title"], len(c["points"])) for c in out])


def test_assemble_recovers_missing_index():
    """模型漏写编号：漏掉的小节必须兜底补回，不能丢内容。"""
    out = _assemble_chapters([{"title": "只写了一章", "sections": [1]}], SECTIONS)
    assert _count(out) == TOTAL_POINTS, out
    assert out[-1]["title"] == "补充要点", out
    assert len(out[-1]["points"]) == 4, out
    print("章节拼装-漏编号兜底 OK", [(c["title"], len(c["points"])) for c in out])


def test_assemble_ignores_invalid_indexes():
    """编号非法/越界/重复：既不丢点，也不能重复计入。"""
    plan = [{"title": "X", "sections": [1, 1, 99, -5, "abc", None]}]
    out = _assemble_chapters(plan, SECTIONS)
    assert _count(out) == TOTAL_POINTS, out
    assert len(out[0]["points"]) == 2, out          # 编号 1 只计一次
    print("章节拼装-非法编号 OK", [(c["title"], len(c["points"])) for c in out])


def test_assemble_without_plan():
    """模型完全没给出章节划分：全部内容进入兜底章节。"""
    for empty in (None, [], "not-a-list", [{"title": "x"}], [{"sections": "bad"}]):
        out = _assemble_chapters(empty, SECTIONS)
        assert _count(out) == TOTAL_POINTS, (empty, out)
    print("章节拼装-无划分兜底 OK")


def test_assemble_scalar_index():
    """模型把数组写成单个数字（常见格式抖动）：应能容错。"""
    out = _assemble_chapters([{"title": "单章", "sections": 1}], SECTIONS)
    assert _count(out) == TOTAL_POINTS, out
    print("章节拼装-标量编号容错 OK")


# ────────────────────────── generate_note 端到端（假 LLM）──────────────────────────

class _FakeLLM:
    """假模型：按提示词内容区分「分段」与「汇总」两种调用。"""

    def __init__(self, reduce_payload):
        self.reduce_payload = reduce_payload
        self.chunk_calls = 0
        self.reduce_calls = 0

    def chat_json(self, messages, **kwargs):
        text = "".join(str(m.get("content") or "") for m in messages)
        if "目录与框架" in text:
            self.reduce_calls += 1
            return self.reduce_payload
        self.chunk_calls += 1
        return {"sections": SECTIONS}


SUBS = [
    {"start": 0.0, "end": 2.0, "text": "第一句话"},
    {"start": 2.0, "end": 4.0, "text": "第二句话"},
]


def test_generate_note_preserves_all_points():
    """汇总给出正常划分：全部知识点、标题、概述、脑图都应保留。"""
    llm = _FakeLLM({
        "title": "测试课程笔记",
        "summary": "这是概述。",
        "chapters": [{"title": "第一章", "sections": [1, 2]}, {"title": "第二章", "sections": [3]}],
        "mindmap": ["graph TD", '  t_000001["A"] --> t_000002["B"]'],
    })
    note = generate_note(SUBS, "general", llm, "测试视频")
    assert note["title"] == "测试课程笔记"
    assert note["summary"] == "这是概述。"
    assert _count(note["chapters"]) == TOTAL_POINTS, note["chapters"]
    assert "graph TD" in note["mindmap"]
    assert llm.reduce_calls == 1
    print("生成笔记-正常 OK", note["title"], _count(note["chapters"]), "个知识点")


def test_generate_note_survives_bad_reduce():
    """模型汇总输出残缺/非法时：笔记仍须完整，不得丢知识点、不得抛错。"""
    for bad in (
        {},
        {"title": "T"},
        {"chapters": []},
        {"chapters": "oops"},
        {"chapters": [{"title": "只有一章", "sections": [1]}]},
        {"chapters": [{"title": "全错", "sections": [999]}]},
        None,
    ):
        llm = _FakeLLM(bad)
        note = generate_note(SUBS, "general", llm, "测试视频")
        assert _count(note["chapters"]) == TOTAL_POINTS, (bad, note["chapters"])
    print("生成笔记-汇总残缺仍保全知识点 OK")


def test_generate_note_requires_subtitles():
    try:
        generate_note([], "general", _FakeLLM({}), "空")
    except ValueError as exc:
        assert "字幕为空" in str(exc)
    else:
        raise AssertionError("字幕为空时应当抛 ValueError")
    print("生成笔记-空字幕报错 OK")


if __name__ == "__main__":
    test_assemble_normal()
    test_assemble_recovers_missing_index()
    test_assemble_ignores_invalid_indexes()
    test_assemble_without_plan()
    test_assemble_scalar_index()
    test_generate_note_preserves_all_points()
    test_generate_note_survives_bad_reduce()
    test_generate_note_requires_subtitles()
    print("ALL_NOTE_TESTS_PASSED")
