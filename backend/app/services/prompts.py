"""学科 Prompt 模板库：统一约束 JSON 输出与 HH:MM:SS 时间戳。"""

SUBJECTS = {
    "general": "通用课程",
    "english": "英语",
    "math": "数理类（高数/线代/概率论/物理）",
    "cs": "计算机类（组成原理/数据结构/算法/编程）",
    "liberal": "文科类",
}

NOTE_STYLES = {
    "general": "按「核心概念 → 讲解要点 → 重点考点」组织",
    "english": "按「听力原文 → 语言点 → 词汇短语 → 考点」组织",
    "math": "按「核心定义 → 定理推导 → 适用条件 → 经典例题 → 易错易混点」组织",
    "cs": "按「核心概念 → 原理/代码逻辑 → 易错坑点 → 性能优化」组织",
    "liberal": "按「核心概念 → 理论框架 → 案例分析 → 考点汇总」组织",
}

SYSTEM_PROMPT = (
    "你是「BiliLearn-AI」的资深学习助教，擅长把视频课程内容整理成结构化学习笔记。"
    "你只能输出严格合法的 JSON，禁止输出任何多余文字、解释或 Markdown 代码块。"
    "所有时间戳必须使用 HH:MM:SS 格式（例如 00:12:34），且必须来自我提供的字幕时间戳，禁止编造。"
    "数学公式用 LaTeX 表示：行内公式用 $...$，独立公式用 $$...$$。"
    "代码片段直接以普通文本缩进形式给出。"
)


def _subject(subject: str) -> str:
    return SUBJECTS.get(subject, SUBJECTS["general"])


def chunk_prompt(subject: str, transcript: str, chunk_no: int, total: int):
    user = (
        "下面是一段带时间戳的课程字幕（第 " + str(chunk_no) + "/" + str(total) + " 段，学科："
        + _subject(subject) + "）。\n"
        "请把这段内容整理为小节笔记，只输出 JSON：\n"
        '{"sections":[{"title":"小节标题","points":[{"content":"知识点精炼描述","time_stamp":"HH:MM:SS","important":true}]}]}\n'
        "要求：\n"
        "1. 每个知识点必须携带对应字幕的 time_stamp，格式 HH:MM:SS；\n"
        "2. 笔记组织方式：" + NOTE_STYLES.get(subject, NOTE_STYLES["general"]) + "；\n"
        "3. important=true 表示重点/考点；\n"
        "4. 用自己的话精炼，保留关键术语、公式和结论，不要遗漏重要内容。\n\n"
        "字幕：\n" + transcript
    )
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def reduce_prompt(subject: str, section_summaries: str, video_title: str):
    user = (
        "课程《" + str(video_title or "未命名课程") + "》（学科：" + _subject(subject)
        + "）已被分成若干段整理，下面是各段的小节笔记 JSON：\n" + section_summaries + "\n\n"
        "请汇总生成整节课的最终笔记，只输出 JSON：\n"
        '{"title":"笔记标题","summary":"3到5句内容概述",'
        '"chapters":[{"title":"章节标题","points":[{"content":"知识点","time_stamp":"HH:MM:SS","important":true}]}],'
        '"mindmap":["graph TD","  t_000137[\"知识点短语\"] --> t_000156[\"知识点短语\"]"]}\n'
        "要求：\n"
        "1. 合并相同主题的小节，按学习逻辑重排章节顺序；\n"
        "2. 完整保留每个知识点的 time_stamp（HH:MM:SS），禁止编造或删除；\n"
        "3. 笔记组织方式：" + NOTE_STYLES.get(subject, NOTE_STYLES["general"]) + "；\n"
        "4. mindmap 是字符串数组，每行一条 Mermaid flowchart 代码（第一行 graph TD），用箭头 --> 把 10-20 个节点串联成树状知识框架；\n"
        "5. 每个节点 id 必须是 t_ 加该知识点真实字幕时间的 HHMMSS 六位数字（如 t_000137），"
        "节点显示文字用方括号括起的简短中文短语（如 t_000137[\"电子位置不确定\"]），不要输出注释。"
    )
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def quiz_prompt(subject: str, note_json: str, per_tier: int = 3):
    user = (
        "以下是一份课程结构化笔记（学科：" + _subject(subject) + "）的 JSON：\n" + note_json + "\n\n"
        "请基于笔记内容生成阶梯式自测题，共三个难度档：基础档（概念判断、单选题）、中档（计算题、简答题）、"
        "拔高档（证明题、综合应用题），每档 " + str(per_tier) + " 道，只输出 JSON：\n"
        '{"questions":[{"difficulty":"basic","type":"single","stem":"题目",'
        '"options":["A. 选项","B. 选项","C. 选项","D. 选项"],'
        '"answer":"正确答案","explanation":"解析","knowledge_point":"对应知识点","time_stamp":"HH:MM:SS"}]}\n'
        "要求：\n"
        "1. difficulty 只能取 basic / medium / advanced，且必须覆盖全部三档；\n"
        "2. 单选题 type=single，answer 必须是 options 中某一项的完整原文；"
        "计算/简答/证明题 type=calc/short/proof，answer 为参考解答；\n"
        "3. 每题必须携带对应知识点的 time_stamp（HH:MM:SS，来自笔记中的时间戳）；\n"
        "4. 解析要说明解题思路，并指出常见错误。"
    )
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def english_extras_prompt(transcript: str, note_json: str):
    user = (
        "以下是英语课程的笔记（JSON）与带时间戳的字幕节选：\n" + note_json + "\n\n字幕节选：\n"
        + transcript[:8000] + "\n\n"
        "请输出英语专项内容，只输出 JSON：\n"
        '{"words":[{"word":"单词","phonetic":"音标","meaning":"中文释义","sentence":"文中原句","time_stamp":"HH:MM:SS"}],'
        '"pronunciations":[{"phenomenon":"连读/弱读/失去爆破","sentence":"原句","time_stamp":"HH:MM:SS"}]}\n'
        "要求：\n"
        "1. words 提取 10 到 20 个核心/高频/考点词汇，sentence 必须是字幕原句，time_stamp 为该句时间；\n"
        "2. pronunciations 标注连读、弱读、失去爆破等语音现象，对应到具体句子与时间戳；\n"
        "3. 所有 time_stamp 必须是字幕中真实存在的时间，格式 HH:MM:SS。"
    )
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def quiz_judge_prompt(stem: str, qtype: str, options, reference_answer: str, user_answer: str, knowledge_point: str = ""):
    user = (
        "你是一名大学课程助教，负责批改学生的自测题并讲解。\n"
        "题目：" + str(stem) + "\n"
        "题型：" + str(qtype) + "\n"
    )
    if options:
        user += "选项：" + "；".join(str(o) for o in options) + "\n"
    user += (
        "参考答案：" + str(reference_answer) + "\n"
        "学生答案：" + str(user_answer) + "\n"
        "知识点：" + (knowledge_point or "") + "\n\n"
        "请判断学生答案是否正确，并给出讲解。只输出 JSON：\n"
        '{"correct":true,"feedback":"判断理由 + 解题思路讲解：对在哪里/错在哪里、如何一步步得到正确答案、易错点提醒"}'
    )
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def quiz_explain_prompt(stem: str, options, correct_answer: str, is_correct: bool):
    user = (
        "请为下面这道已批改的自测题给出讲解。只输出 JSON：\n"
        '{"feedback":"讲解文字"}\n\n'
        "题目：" + str(stem) + "\n"
    )
    if options:
        user += "选项：" + "；".join(str(o) for o in options) + "\n"
    user += "正确答案：" + str(correct_answer) + "\n"
    user += "学生本次" + ("答对" if is_correct else "答错") + "。请讲解：为什么正确选项是对的、其余选项错在哪里、涉及的核心概念。"
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def mindmap_prompt(note_json: str):
    user = (
        "以下是一份课程结构化笔记的 JSON：\n" + note_json + "\n\n"
        "请基于笔记生成知识框架图（Mermaid flowchart），只输出 JSON：\n"
        '{"mindmap":["graph TD","  t_000137[\\"知识点短语\\"] --> t_000156[\\"知识点短语\\"]"]}\n'
        "要求：\n"
        "1. 第一行是 graph TD，用箭头 --> 把 10-20 个节点串联成树状知识框架；\n"
        "2. 每个节点 id 必须是 t_ 加该知识点真实时间戳的 HHMMSS 六位数字（如 t_000137），节点显示文字用方括号括起的简短中文短语；\n"
        "3. 按「先主干后分支」组织层级，同一主题的节点放在一起；\n"
        "4. 不要输出任何注释或代码块标记。"
    )
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


FORMULA_SYSTEM = (
    "你是理科板书/课件识别助手。看到关键帧图片后："
    "1. 提取画面中出现的所有公式，输出为标准 LaTeX（行内形式，不额外包裹 $）；"
    "2. 对每个公式用一句话说明含义；"
    "3. 提取画面中的板书要点/关键文字，输出 1-3 条简短短语（图形/文字内容也要提取）；"
    "4. 只输出 JSON：{\"formulas\":[{\"latex\":\"...\",\"description\":\"...\"}],\"notes\":[\"...\"]}；"
    "5. 画面中没有公式则 formulas 为空数组。"
)


def collection_map_prompt(course_title: str, summaries_json: str):
    user = (
        "以下是整门课程《" + str(course_title) + "》各集笔记的摘要"
        "（JSON，含页码、章节标题与知识点时间戳）：\n" + summaries_json + "\n\n"
        "请生成全课程知识体系，只输出 JSON：\n"
        '{"mindmap":["graph TD","  p1_000137[\\"知识点短语\\"] --> p2_000245[\\"知识点短语\\"]],'
        '"exam_points":[{"point":"考点","importance":"必考","page":1,"time_stamp":"HH:MM:SS","reason":"理由"}]}\n'
        "要求：\n"
        "1. mindmap 是 Mermaid graph TD 字符串数组，按「主题 → 章节 → 知识点」分层串联 15-30 个节点，"
        "箭头表达前置知识 → 后续知识的关系；\n"
        "2. 节点 id 必须是 p页码_HHMMSS（如 p1_000137），节点文字为简短中文短语，禁止输出注释；\n"
        "3. exam_points 汇总全课程考点 10-20 条，importance 只能取 必考/掌握/了解 三档，"
        "page 与 time_stamp 必须来自笔记真实数据；\n"
        "4. exam_points 按重要程度从高到低排列。"
    )
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


CHAT_SYSTEM = (
    "你是「BiliLearn-AI」的学习助教。基于笔记回答学生问题，必须遵守：\n"
    "1. 简洁：先给一句话结论，再分点解释，全文不超过 150 字，不要客套话；\n"
    "2. 结构化：用要点列表或分步说明，重要术语用 **加粗**；\n"
    "3. 图示化：问题涉及流程、对比、分类、层级关系时，必须附一个 Mermaid 代码块"
    "（graph TD 或 flowchart），代码块用三个反引号包裹并标注 mermaid，节点文字简短；\n"
    "4. 中文回答，通俗易懂；笔记没有的信息请说明并给出一般性解释。\n\n"
    "笔记内容：\n{note}"
)


def review_prompt(note_json: str, wrong_json: str):
    user = (
        "以下是课程笔记（JSON）和用户的错题记录（JSON）：\n笔记：\n" + note_json + "\n\n错题：\n"
        + wrong_json + "\n\n"
        "请做学习复盘分析，只输出 JSON：\n"
        '{"weak_points":[{"point":"薄弱知识点","reason":"错题表现分析","priority":"high",'
        '"replay_timestamps":["HH:MM:SS"],"suggestion":"复习建议"}],"summary":"总体评价与鼓励"}\n'
        "要求：\n"
        "1. 找出错误背后的共性薄弱知识点，priority 取 high / medium / low；\n"
        "2. replay_timestamps 给出笔记中对应知识点的复习时间点（HH:MM:SS）；\n"
        "3. 按优先级从高到低排列 weak_points。"
    )
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]
