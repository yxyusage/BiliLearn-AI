from app.services.quiz_generator import normalize_question


def test_mislabeled_calculation_is_calc():
    q = normalize_question(
        {
            "type": "judge",
            "difficulty": "basic",
            "stem": "某住宅地暖地面构造中，保温板厚 20mm，混凝土回填层厚 50mm（含地暖管），粘贴层厚 25mm。求此时地面总厚度（单位：mm），并判断相比常规构造增加了多少 mm。",
            "options": ["正确", "错误"],
            "answer": "105mm；增加 10mm",
            "explanation": "总厚度=20+50+25=105mm。",
            "knowledge_point": "地暖系统构造",
            "time_stamp": "00:00",
        }
    )
    assert q["type"] == "calc"
    assert q["answer"] == "105mm；增加 10mm"


def test_real_judge_stays_judge():
    q = normalize_question(
        {
            "type": "judge",
            "stem": "拉格朗日中值定理要求函数在闭区间连续、开区间可导。",
            "options": ["正确", "错误"],
            "answer": "正确",
            "explanation": "",
            "time_stamp": "",
        }
    )
    assert q["type"] == "judge"
    assert q["answer"] == "正确"


def test_calc_with_options_stays_calc():
    q = normalize_question(
        {
            "type": "calc",
            "stem": "求 2+2 的结果。",
            "options": ["3", "4"],
            "answer": "4",
            "explanation": "",
            "time_stamp": "",
        }
    )
    assert q["type"] == "calc"
