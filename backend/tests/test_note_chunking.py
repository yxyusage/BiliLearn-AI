"""笔记分段/汇总的回归测试（离线，不联网）。

背景（真实故障 #261）：23 分钟视频 → 字幕 19,870 字 → 正好切 4 段。
两级汇总的条件当时写的是「段数 > 4」，等于 4 就不拆 → **一步汇总整篇笔记** →
输出撞 8192 上限被截断，整篇失败（"模型输出被截断"）。

这里覆盖三件事：
1. 4 段且体积大 → 必须走两级汇总（不是一步）;
2. 4 段但体积小 → 一步汇总（省调用）;
3. 汇总仍被截断 → 退回"机械拼接"，必须给用户一篇笔记，而不是一个错误。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.services import note_generator as ng
from backend.app.services.llm.base import BaseLLM, LLMTruncatedError

CHUNK_MARK = "[CHUNK]"
REDUCE_MARK = "[REDUCE]"


class FakeLLM(BaseLLM):
    """按提示词标记返回：分段返回带小节的 JSON，汇总可配置为"截断"。"""

    def __init__(self, section_chars=200, truncate_reduce=False):
        super().__init__("fake")
        self.section_chars = section_chars
        self.truncate_reduce = truncate_reduce
        self.reduce_calls = 0
        self.chunk_calls = 0

    def chat(self, messages, temperature=0.3, **kwargs):
        prompt = messages[-1]["content"]
        body = "内" * self.section_chars
        if prompt.startswith(CHUNK_MARK):
            self.chunk_calls += 1
            return ('{"chapters": [{"title": "小节", "sections": '
                    '[{"heading": "h", "type": "concept", '
                    '"blocks": [{"type": "text", "content": "' + body + '"}]}]}]}')
        self.reduce_calls += 1
        if self.truncate_reduce:
            raise LLMTruncatedError("模型输出被截断（达到输出上限 max_tokens=8192）")
        return ('{"title": "测试笔记", "summary": "汇总", '
                '"chapters": [{"title": "第一章", "sections": []}]}')


def _patch_prompts():
    def chunk_prompt(subject, text, idx, total):
        return [{"role": "user", "content": CHUNK_MARK + " %d/%d" % (idx, total)}]

    def reduce_prompt(subject, js, title=""):
        return [{"role": "user", "content": REDUCE_MARK}]

    # 固定切成 4 段，避免依赖真实的切分阈值（那样段数会随字数浮动，测试不稳定）
    ng.split_subtitles = lambda subs: [subs[i:i + 10] for i in range(0, len(subs), 10)]
    ng.chunk_prompt = chunk_prompt
    ng.reduce_prompt = reduce_prompt


def _subtitles(n_chunks):
    """造 n 段字幕（每段 10 条，配合上面的固定切分）。"""
    out = []
    t = 0.0
    for _ in range(n_chunks * 10):
        out.append({"start": t, "end": t + 2, "text": "这是一句测试字幕内容"})
        t += 2
    return out


def test_big_sections_use_two_level_reduce():
    _patch_prompts()
    llm = FakeLLM(section_chars=4000)          # 每段小节很长 → 总体积超预算
    subs = _subtitles(4)
    ng.generate_note(subs, "general", llm, "测试视频")
    assert llm.chunk_calls == 4, llm.chunk_calls
    # MERGE_GROUP=2 → 2 次分批 + 1 次总汇 = 3
    assert llm.reduce_calls == 3, "体积大时必须两级汇总，实际 %d 次" % llm.reduce_calls
    print("big-sections-two-level OK")


def test_small_sections_use_single_reduce():
    _patch_prompts()
    llm = FakeLLM(section_chars=50)            # 小节很短 → 一步汇总就够了
    subs = _subtitles(4)
    ng.generate_note(subs, "general", llm, "测试视频")
    assert llm.chunk_calls == 4, llm.chunk_calls
    assert llm.reduce_calls == 1, "体积小时应一步汇总，实际 %d 次" % llm.reduce_calls
    print("small-sections-single OK")


def test_reduce_truncation_falls_back_to_mechanical_merge():
    """汇总被截断时不能整篇失败 —— 必须退回机械拼接，把内容交还给用户。"""
    _patch_prompts()
    llm = FakeLLM(section_chars=50, truncate_reduce=True)
    subs = _subtitles(2)
    note = ng.generate_note(subs, "general", llm, "测试视频")
    assert note.get("chapters"), "兜底结果必须有章节：" + str(note)[:200]
    assert "截断" in (note.get("summary") or ""), note.get("summary")
    print("reduce-truncation-fallback OK")


if __name__ == "__main__":
    test_big_sections_use_two_level_reduce()
    test_small_sections_use_single_reduce()
    test_reduce_truncation_falls_back_to_mechanical_merge()
    print("ALL_NOTE_CHUNKING_TESTS_PASSED")
