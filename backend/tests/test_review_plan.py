"""复习资料「详版」规划逻辑的离线测试。

详版 = ① 排大纲 → ② 逐章生成 → ③ 补全局信息。这里只测纯函数：
大纲与各集内容如何对应、丢集/超限怎么兜底、三步产出如何拼装。
（真正调模型的部分不在 CI 里跑）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.services import review_material as rm


def _ep(page, title="", topics=None):
    return {
        "page": page,
        "title": title or ("第 %d 集" % page),
        "exam_points": [],
        "chapters": [{"title": t, "key_points": []} for t in (topics or [])],
    }


def test_episode_digest_is_compact():
    d = rm.episode_digest([_ep(1, "第一讲", ["函数", "极限"])])
    assert d[0]["episode"] == 1
    assert "函数" in d[0]["topics"] and "极限" in d[0]["topics"]
    assert len(d[0]["topics"]) <= 12
    print("digest OK")


def test_plan_chapters_maps_and_fills_missing():
    distilled = [_ep(i) for i in range(1, 6)]
    outline = {"chapters": [
        {"title": "第一章 基础", "intro": "x", "episodes": [1, 2]},
        {"title": "第二章 进阶", "intro": "y", "episodes": [3, 4]},
    ]}
    plans = rm.plan_chapters(outline, distilled)
    assert [p["title"] for p in plans] == ["第一章 基础", "第二章 进阶"]
    # 第 5 集被模型漏掉 → 必须补进最后一章，绝不能丢集
    assert plans[-1]["pages"] == [3, 4, 5], plans[-1]
    assert sorted(p for pl in plans for p in pl["pages"]) == [1, 2, 3, 4, 5]
    print("plan-fill OK")


def test_plan_chapters_fallback_per_episode():
    distilled = [_ep(i) for i in (1, 2, 3)]
    plans = rm.plan_chapters({}, distilled)                     # 大纲为空
    assert len(plans) == 3 and all(len(p["pages"]) == 1 for p in plans)
    plans2 = rm.plan_chapters({"chapters": [{"title": "x", "episodes": [99]}]}, distilled)  # 集号对不上
    assert len(plans2) == 3, plans2
    assert sorted(p for pl in plans2 for p in pl["pages"]) == [1, 2, 3]
    print("plan-fallback OK")


def test_plan_chapters_caps_and_splits():
    distilled = [_ep(i) for i in range(1, 41)]
    outline = {"chapters": [{"title": "第%d章" % i, "episodes": [i]} for i in range(1, 41)]}
    plans = rm.plan_chapters(outline, distilled, max_chapters=5)
    # 先并章再拆章：总章数允许略超上限（合并出来的那章还会被拆开），但**每章集数必须受控**
    # ——否则单章请求的输入/输出又会过大，回到"整章被截断成空"的老问题
    per = rm.MAX_EPISODES_PER_CHAPTER
    assert len(plans) <= 4 + -(-40 // per), len(plans)
    assert all(len(p["pages"]) <= per for p in plans), [len(p["pages"]) for p in plans]
    assert sorted(p for pl in plans for p in pl["pages"]) == list(range(1, 41))

    # 单章 20 集 → 按 per 集一段切开；这里要用"只有 20 集"的数据，
    # 否则多出来的 20 集会被正确地补进最后一章，段数自然不同
    distilled20 = [_ep(i) for i in range(1, 21)]
    outline2 = {"chapters": [{"title": "大章", "episodes": list(range(1, 21))}]}
    plans2 = rm.plan_chapters(outline2, distilled20)
    expect = [per] * (20 // per) + ([20 % per] if 20 % per else [])
    assert [len(p["pages"]) for p in plans2] == expect, [(p["title"], len(p["pages"])) for p in plans2]
    assert "（续" in plans2[1]["title"], plans2[1]["title"]
    assert sorted(p for pl in plans2 for p in pl["pages"]) == list(range(1, 21))
    print("plan-cap OK")


def test_plan_chapters_splits_by_content_size():
    """体积约束（关键）：集数没超上限，但内容很大时单次请求会撑爆 8192 输出上限 —— 必须按体积再切。
    实测：大学物理 1 集的正文输出就有 5000 tokens，凑 4 集必然截断。"""
    big = "内容" * 3000                     # 每集约 6000 字
    distilled = [_ep(i) for i in (1, 2, 3)]
    for d in distilled:
        d["chapters"] = [{"title": big, "key_points": []}]
    outline = {"chapters": [{"title": "大章", "episodes": [1, 2, 3]}]}
    plans = rm.plan_chapters(outline, distilled)
    assert len(plans) == 3, [(p["title"], len(p["pages"])) for p in plans]
    assert all(len(p["pages"]) == 1 for p in plans), [len(p["pages"]) for p in plans]
    assert sorted(p for pl in plans for p in pl["pages"]) == [1, 2, 3]
    assert plans[1]["title"].endswith("（续1）")
    print("plan-size-budget OK")


def test_truncated_chapter_is_split_not_emptied():
    """回归：单章正文被 max_tokens 截断时，必须**自动对半拆章**，
    绝不能像以前那样留一个空章节还标成"完成"（实测 25 章里 22 章是空的）。"""
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent.parent))
    from backend.app.services import review_material as rm
    from backend.app.services.llm.base import BaseLLM, LLMTruncatedError

    class SplitLLM(BaseLLM):
        def __init__(self):
            super().__init__("fake")
            self.calls = []

        def chat(self, messages, temperature=0.3, **kwargs):
            prompt = messages[-1]["content"]
            self.calls.append(prompt)
            if "章节目录" in prompt or "只做一件事" in prompt:
                return '{"title": "测试", "chapters": [{"title": "第一章 电磁学", "intro": "", "episodes": [1, 2]}]}'
            if "练习题" in prompt:
                return '{"quiz": [{"no": 1, "type": "single", "difficulty": "basic", "stem": "题", "options": ["A","B"]}], "answers": [{"no": 1, "answer": "A"}]}'
            if "只写这一章的正文" in prompt:
                # 含两集的那次一律截断，逼出"对半拆"
                if "第1集" in prompt and "第2集" in prompt:
                    raise LLMTruncatedError("模型输出被截断（达到输出上限 max_tokens=8192）")
                return ('{"chapter": {"title": "第一章 电磁学", "intro": "", '
                        '"sections": [{"heading": "1.1 电场", "type": "concept", '
                        '"blocks": [{"type": "text", "content": "内容"}]}], "quiz": []}, '
                        '"appendix": {}}')
            if "全局信息" in prompt or "只补全局信息" in prompt:
                return '{"title": "测试资料", "subject": "general", "overview": "o", "usage_guide": "u"}'
            return "{}"

    distilled = [
        {"page": 1, "title": "第1集", "exam_points": [], "chapters": [{"title": "电场", "key_points": []}]},
        {"page": 2, "title": "第2集", "exam_points": [], "chapters": [{"title": "电势", "key_points": []}]},
    ]
    data = rm._generate_full(999999, SplitLLM(), "general", "测试合集", distilled)
    chapters = data["chapters"]
    assert len(chapters) >= 2, chapters                       # 被拆成了两章
    assert all((c.get("sections") or []) for c in chapters), "不能有空章节：" + str(chapters)
    assert not any("没能生成出内容" in w for w in (data.get("_warnings") or [])), data.get("_warnings")
    # 拆出来的两章各自都要有测验
    assert all((c.get("quiz") or []) for c in chapters), [c.get("quiz") for c in chapters]
    assert len(data["answers"]) == len(chapters)
    print("split-on-truncation OK")


def test_assemble_material():
    chapters = [{"title": "第一章"}]
    answers = [{"chapter_index": 1, "no": 1, "answer": "A"}]
    appendices = [
        {"formula_sheet": [{"name": "a", "latex": "x^2"}], "glossary": [{"term": "T", "definition": "d"}],
         "flash_cards": [{"front": "F", "back": "B"}]},
        {"formula_sheet": [{"name": "重复", "latex": "x^2"}], "glossary": [{"term": "T2", "definition": "d2"}],
         "flash_cards": []},
    ]
    data = rm.assemble_material({"title": "标题", "overview": "o", "usage_guide": "u"}, chapters, answers,
                                appendices, [{"episode": 1, "title": "t", "covered_in": ["第一章"]}],
                                fallback_title="兜底")
    assert data["title"] == "标题" and data["overview"] == "o" and data["usage_guide"] == "u"
    assert data["chapters"] == chapters and data["answers"] == answers
    assert len(data["appendix"]["formula_sheet"]) == 1, "同一公式应去重"
    assert len(data["appendix"]["glossary"]) == 2
    assert data["appendix"]["source_map"][0]["episode"] == 1

    empty = rm.assemble_material(None, [], [], [], [])
    assert empty["title"] == "" and empty["chapters"] == []
    assert empty["appendix"] == {"formula_sheet": [], "glossary": [], "flash_cards": [], "source_map": []}
    fallback = rm.assemble_material(None, chapters, answers, appendices, [], fallback_title="兜底")
    assert fallback["title"] == "兜底"
    print("assemble OK")


def test_single_dense_episode_splits_by_inner_chapters():
    """第二级拆分：一集本身就太长时（实测有单集 1.28 万字），
    要能拆到"这一集内部的章"这一层，而不是直接放弃成空章节。"""
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent.parent))
    from backend.app.services import review_material as rm
    from backend.app.services.llm.base import BaseLLM, LLMTruncatedError

    class DenseLLM(BaseLLM):
        def __init__(self):
            super().__init__("fake")

        def chat(self, messages, temperature=0.3, **kwargs):
            prompt = messages[-1]["content"]
            if "只做一件事" in prompt:
                return '{"title": "测试", "chapters": [{"title": "第一章 密集内容", "intro": "", "episodes": [1]}]}'
            if "练习题" in prompt:
                return '{"quiz": [{"no": 1, "type": "single", "difficulty": "basic", "stem": "题", "options": ["A"]}], "answers": [{"no": 1, "answer": "A"}]}'
            if "只写这一章的正文" in prompt:
                # 内部两个章都在 → 模拟"单集也太长"，触发第二级拆分
                if "内部甲" in prompt and "内部乙" in prompt:
                    raise LLMTruncatedError("模型输出被截断（达到输出上限 max_tokens=8192）")
                return ('{"chapter": {"title": "第一章 密集内容", "intro": "", '
                        '"sections": [{"heading": "1.1", "type": "concept", '
                        '"blocks": [{"type": "text", "content": "内容"}]}]}, "appendix": {}}')
            if "只补全局信息" in prompt:
                return '{"title": "测试资料", "subject": "general", "overview": "o", "usage_guide": "u"}'
            return "{}"

    distilled = [{
        "page": 1, "title": "第1集", "exam_points": [],
        "chapters": [
            {"title": "内部甲", "key_points": [], "sections": [{"heading": "1.1", "type": "concept",
             "blocks": [{"type": "text", "content": "内容" * 500}]}]},
            {"title": "内部乙", "key_points": [], "sections": [{"heading": "1.2", "type": "concept",
             "blocks": [{"type": "text", "content": "内容" * 500}]}]},
        ],
    }]
    data = rm._generate_full(999999, DenseLLM(), "general", "测试合集", distilled)
    chapters = data["chapters"]
    assert len(chapters) == 2, [(c.get("title"), len(c.get("sections") or [])) for c in chapters]
    assert all((c.get("sections") or []) for c in chapters), chapters
    print("split-by-inner-chapters OK")


if __name__ == "__main__":
    test_episode_digest_is_compact()
    test_plan_chapters_maps_and_fills_missing()
    test_plan_chapters_fallback_per_episode()
    test_plan_chapters_caps_and_splits()
    test_assemble_material()
    test_plan_chapters_splits_by_content_size()
    test_truncated_chapter_is_split_not_emptied()
    test_single_dense_episode_splits_by_inner_chapters()
    print("ALL_REVIEW_PLAN_TESTS_PASSED")
