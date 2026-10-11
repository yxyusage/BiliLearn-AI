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
    # 先并章再拆章：总章数允许略超上限，但每章集数必须受控（否则单次输入又会太大）
    assert len(plans) <= 5 + 4, len(plans)
    assert all(len(p["pages"]) <= rm.MAX_EPISODES_PER_CHAPTER for p in plans), [len(p["pages"]) for p in plans]
    assert sorted(p for pl in plans for p in pl["pages"]) == list(range(1, 41))

    # 单章 20 集 → 拆成 3 段（8/8/4）；注意这里要用"只有 20 集"的数据，
    # 否则多出来的 20 集会被正确地补进最后一章，段数自然不同
    distilled20 = [_ep(i) for i in range(1, 21)]
    outline2 = {"chapters": [{"title": "大章", "episodes": list(range(1, 21))}]}
    plans2 = rm.plan_chapters(outline2, distilled20)
    assert [len(p["pages"]) for p in plans2] == [8, 8, 4], [(p["title"], len(p["pages"])) for p in plans2]
    assert plans2[1]["title"].endswith("（续）")
    assert sorted(p for pl in plans2 for p in pl["pages"]) == list(range(1, 21))
    print("plan-cap OK")


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


if __name__ == "__main__":
    test_episode_digest_is_compact()
    test_plan_chapters_maps_and_fills_missing()
    test_plan_chapters_fallback_per_episode()
    test_plan_chapters_caps_and_splits()
    test_assemble_material()
    print("ALL_REVIEW_PLAN_TESTS_PASSED")
