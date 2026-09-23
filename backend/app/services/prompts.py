"""学科 Prompt 模板库：统一约束 JSON 输出与 HH:MM:SS 时间戳。"""

SUBJECTS = {
    "general": "通用课程",
    "english": "英语",
    "math": "数理类（高数/线代/概率论/物理）",
    "cs": "计算机类（组成原理/数据结构/算法/编程）",
    "liberal": "文科类",
}

NOTE_STYLES = {
    "general": "按「概念定义 → 原理讲解 → 示例 → 结论小结」的教材顺序组织小节",
    "english": "按「语言点/语法概念 → 例句讲解 → 用法归纳 → 易错提醒」组织，不要照抄听力原文",
    "math": "严格按「核心定义 → 定理/公式推导（分步）→ 经典例题（题干+完整解答）→ 结论与适用条件 → 易错易混点」组织",
    "cs": "按「核心概念 → 原理/代码逻辑（给代码与分步讲解）→ 运行示例 → 易错坑点」组织",
    "liberal": "按「核心概念 → 理论框架 → 对比辨析（表格）→ 案例分析 → 结论考点」组织",
}

SECTION_TYPE_GUIDE = (
    "小节 type 只能取：definition（定义/术语严谨陈述）、concept（概念与原理讲解）、"
    "derivation（公式或定理的推导证明，用 steps+formula 呈现完整过程）、"
    "example（例题，blocks 依次给题干 text、解答 steps、答案/点评 quote）、"
    "code（代码教学，必须含 code 块）、comparison（对比辨析，必须含 table 块）、"
    "conclusion（结论与规律总结）、keypoints（要点罗列，兜底类型）。"
)

BLOCK_GUIDE = (
    "blocks 中每个元素 type 只能取：\n"
    '- text：讲解段落（content 为成段文字，可含行内公式 $...$ 与 **加粗**，不要只写一句话标题）；\n'
    '- formula：独立成行的公式（content 为 LaTeX 源码，不要包裹 $ 符号）；\n'
    '- steps：分步过程（items 是有序步骤数组，推导/解题流程必须用它）；\n'
    '- list：并列要点（ordered 为 false 无序列表/true 有序列表，items 为数组）；\n'
    '- code：代码（language 给语言名如 python/java/c，content 为完整代码，保留缩进）；\n'
    '- table：对比或结构化信息（headers 为表头数组，rows 为二维数组）；\n'
    '- quote：结论、易错提醒或原话引用（content 为一句话）。'
)

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
        "请把这段内容整理成「教材精编」式的小节笔记，目标是让没看过视频的学生照着就能学会，只输出 JSON：\n"
        '{"sections":[{"type":"definition","heading":"小节标题","time_stamp":"HH:MM:SS","important":false,'
        '"blocks":[{"type":"text","content":"成段讲解"}]}]}\n'
        "小节要求：\n"
        "1. " + SECTION_TYPE_GUIDE + "\n"
        "2. " + NOTE_STYLES.get(subject, NOTE_STYLES["general"]) + "；\n"
        "3. 每个小节必须携带该小节开始处字幕的 time_stamp（HH:MM:SS），必须来自字幕，禁止编造；\n"
        "4. important 只给真正的重点/考点小节，每段字幕最多 1 个；\n"
        "内容块要求：\n"
        + BLOCK_GUIDE + "\n"
        "质量红线：\n"
        "1. 必须是成体系的讲解（定义讲严谨、推导给完整步骤、例题给题干和完整解答），"
        "严禁把字幕改写成一堆零碎短句要点；\n"
        "2. 公式、术语、结论必须保留，口语化铺垫可以删；\n"
        "3. 代码、公式中的字符必须准确，不要臆造。\n\n"
        "字幕：\n" + transcript
    )
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def reduce_prompt(subject: str, section_summaries: str, video_title: str):
    user = (
        "课程《" + str(video_title or "未命名课程") + "》（学科：" + _subject(subject)
        + "）已被分成若干段整理，下面是各段的「教材精编」小节笔记 JSON：\n" + section_summaries + "\n\n"
        "请汇总生成整节课的最终笔记（同样是教材精编风格），只输出 JSON：\n"
        '{"title":"笔记标题","summary":"4到8句内容概述",'
        '"chapters":[{"title":"章节标题","time_stamp":"HH:MM:SS","intro":"本章一句话导读",'
        '"sections":[{"type":"definition","heading":"小节标题","time_stamp":"HH:MM:SS","important":false,'
        '"blocks":[{"type":"text","content":"..."}]}],'
        '"summary":"本章小结","key_points":["本章必须掌握的结论"]}],'
        '"exam_points":["全节课高频考点短句"],'
        '"mindmap":["graph TD","  t_000137[\\"知识点短语\\"] --> t_000156[\\"知识点短语\\"]"]}\n'
        "章节与小节要求：\n"
        "1. 按学习逻辑把各段小节合并、重排为 3-8 个章节，章节顺序就是学习顺序；\n"
        "2. 每个章节含 intro（可选导读）、若干 sections、章末 summary 与 key_points（2-5 条）；\n"
        "3. " + SECTION_TYPE_GUIDE + "\n"
        "4. 学科组织方式：" + NOTE_STYLES.get(subject, NOTE_STYLES["general"]) + "；\n"
        "5. 完整保留各小节真实 time_stamp（HH:MM:SS），章节 time_stamp 取其第一个小节的时间，禁止编造；\n"
        "6. blocks 规则：\n" + BLOCK_GUIDE + "\n"
        "7. exam_points 汇总全节课 5-12 条考点短句；\n"
        "8. 质量红线：内容必须是讲解而非字幕要点罗列；推导和例题要完整；宁可少而精，不要灌水。\n"
        "mindmap 要求：字符串数组，每行一条 Mermaid flowchart 代码（第一行 graph TD），"
        "用箭头 --> 把 10-20 个节点串联成树状知识框架；节点 id 必须是 t_ 加该知识点真实时间的 HHMMSS 六位数字"
        "（如 t_000137），节点显示文字用方括号括起的简短中文短语（如 t_000137[\"电子位置不确定\"]），不要输出注释。"
    )
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def quiz_prompt(subject: str, note_json: str, per_tier: int = 3):
    user = (
        "以下是一份课程「教材精编」笔记（学科：" + _subject(subject) + "）的 JSON：\n" + note_json + "\n\n"
        "请基于笔记内容生成阶梯式自测题：基础档（判断题、单选题、填空题）、中档（单选题、填空题、计算题）、"
        "拔高档（计算题、综合填空题），每档 " + str(per_tier) + " 道，只输出 JSON：\n"
        '{"questions":[{"difficulty":"basic","type":"fill","stem":"题目中用 ____ 标记空位",'
        '"answer":"第一空答案 / 第一空等价说法 | 第二空答案",'
        '"explanation":"解析","knowledge_point":"对应知识点","time_stamp":"HH:MM:SS"}]}\n'
        "要求：\n"
        "1. difficulty 只能取 basic / medium / advanced，且必须覆盖全部三档；\n"
        "2. type 只能取 single（单选）/ judge（判断）/ fill（填空）/ calc（计算），不要出简答题、证明题；\n"
        "3. 单选题 options 是 4 个不带 A./B./C./D. 前缀的纯选项文本，answer 只输出正确选项的字母（A/B/C/D）；"
        "判断题 answer 只能输出“正确”或“错误”；计算题 answer 给出最终结果；\n"
        "4. 填空题规则：题干 stem 中每个空位用连续 4 个下划线 ____ 标记（每题 1-3 个空，空位应落在关键术语、"
        "公式结果或结论上，不要挖 trivial 的词）；answer 按空位顺序给出，同一空位的多个等价答案用“ / ”分隔"
        "（如“牛顿 / Newton”），不同空位用“ | ”分隔；公式空直接给 LaTeX；\n"
        "5. 每题必须携带笔记中真实存在的 time_stamp（HH:MM:SS），找不到对应时间点时输出空字符串，严禁编造；\n"
        "6. explanation 要说明解题思路并指出常见错误；题干、选项和解答中的数学公式一律用 LaTeX（行内 $...$）。"
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
    "你是「BiliLearn-AI」的学习助教。基于下面的笔记回答学生问题，必须遵守：\n"
    "1. 先给一句话结论，再分点展开；简单问题简短回答，复杂问题（推导、原理、对比）要分步详细讲解，"
    "不要为了简短而省略关键过程；\n"
    "2. 用 Markdown 组织回答：要点用无序列表、步骤用编号列表、公式用 $...$ 或 $$...$$、代码用代码块、"
    "重要术语用 **加粗**；\n"
    "3. 仅当问题确实涉及流程、分类、层级或对比关系，且图示明显比文字更清晰时，才附 Mermaid 代码块"
    "（三个反引号开头并标注 mermaid），不要为了画图而画图；\n"
    "4. 中文回答，通俗易懂；笔记中没有依据的内容要明确说明属于一般性补充。\n\n"
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


def dictation_prompt(transcript: str):
    user = (
        "下面是带时间戳的英语听力字幕：\n" + transcript + "\n\n"
        "请设计英语精听听写练习（cloze），只输出 JSON：\n"
        '{"items":[{"sentence":"原文完整句子","blanks":["挖空的关键词，按顺序"],'
        '"answers":["第1空的参考答案，可含多个等价写法用 / 分隔"],'
        '"translation":"整句中文翻译","hint":"挖空讲解（为什么这个词重要、易错点）","time_stamp":"HH:MM:SS"}]}\n'
        "要求：\n"
        "1. 选 8-12 个句子：信息密度高、有学习价值的句子（含核心词汇/短语/语法点），"
        "句子长度 8-30 个词，避免重复挖同类的词；\n"
        "2. 每句挖 1-2 个空，优先挖核心实词（名词/动词/形容词/短语/数字），不要挖介词、冠词等虚词；\n"
        "3. sentence 必须是字幕原句（可去掉口误/语气词），blanks 给出被挖掉的词，"
        "answers 与 blanks 一一对应，同一空位多个等价写法用“ / ”分隔（如 “analyze / analyse”）；\n"
        "4. time_stamp 必须来自字幕真实时间（HH:MM:SS）；\n"
        "5. 不要整段翻译，translation 给一句自然的中文翻译即可。"
    )
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def variant_prompt(subject: str, note_json: str, question_json: str):
    user = (
        "以下是课程笔记（学科：" + _subject(subject) + "）的 JSON 节选：\n" + note_json + "\n\n"
        "请基于这道题生成 1 道「同类变式题」——考察同一个知识点，但：换数字/换参数、"
        "换情境表述、改变已知与未知（单选则换掉正确项与干扰项，填空则换空位位置或换等价问法），"
        "难度保持一致。只输出 JSON：\n"
        '{"stem":"题干（填空用 ____ 标记空位）","type":"single/judge/fill/calc","options":["选项（单选4个，不带A./B.前缀）"],'
        '"answer":"答案","explanation":"解析","knowledge_point":"知识点","time_stamp":"HH:MM:SS"}\n'
        "原题：\n" + question_json + "\n"
        "要求：\n"
        "1. type 必须与原题一致；\n"
        "2. 单选 answer 只给正确选项字母；判断 answer 只给“正确/错误”；"
        "填空 answer 按空位顺序，同空等价答案用“ / ”分隔，不同空用“ | ”分隔；计算题 answer 给最终结果；\n"
        "3. 题干中公式用 LaTeX；\n"
        "4. time_stamp 沿用原题时间戳，不编造；\n"
        "5. 不要出与原题雷同的题目（数字、情境至少一项不同）。"
    )
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def re_explain_prompt(section_text: str, note_json: str):
    user = (
        "学生看视频时卡在下面这个小节没看懂，请你「换一种讲法」帮他打通：\n"
        "规则：\n"
        "1. 先用 1-2 句话点破这个知识点最本质的一句话（能让他恍然大悟的表述）；\n"
        "2. 再用一个生活化类比或更简单的例子重新讲一遍；\n"
        "3. 最后给出一个 3 步以内的自查小问题，确认他真的懂了；\n"
        "4. 中文回答，用 Markdown（要点列表、**加粗**、公式 $...$），不要输出 JSON，"
        "不要复述笔记原文。\n\n"
        "卡住的小节内容：\n" + section_text + "\n\n"
        "所在笔记全文（供参考上下文）：\n" + note_json[:6000]
    )
    return [{"role": "system", "content": CHAT_SYSTEM.replace("{note}", note_json[:3000])}, {"role": "user", "content": user}]


REVIEW_MATERIAL_SYSTEM = (
    "你是「BiliLearn-AI」的资深教材编审，擅长把多集课程笔记蒸馏、重排成一份自成体系、可直接打印的复习资料。\n"
    "核心原则：\n"
    "1. 知识蒸馏：合并同类项、删掉口语化、保留硬核知识，知识点一个都不能少。\n"
    "2. 按知识逻辑重排：绝对不按视频顺序排列，按学科知识体系重新组织章节。\n"
    "3. 严格基于输入：所有定义、公式、代码、结论必须来自输入笔记，禁止编造。\n"
    "4. 准确零错误：公式上下标、变量符号、专业术语必须准确，禁止出现错别字或讹误（如把'传播时延'写成'传摇时延'）。\n"
    "5. 可打印：结构适合纸质打印，章节层级清晰、公式独立成行、代码有边框、对比用表格。\n"
    "输出格式：只输出严格合法的 JSON，禁止任何多余文字、解释或 Markdown 代码块。\n"
    "数学公式用 LaTeX：行内 $...$，独立公式用 $$...$$。上下标必须用 ^{} 和 _{} 正确标注（如 2^{10}、10^3），禁止写成普通数字。\n"
    "代码保留完整缩进。"
)


def review_material_prompt(course_title: str, subject: str, distilled_notes: str):
    user = (
        "以下是合集《" + str(course_title or "未命名课程") + "》（学科：" + _subject(subject)
        + "）各集笔记的蒸馏版 JSON：\n" + distilled_notes + "\n\n"
        "请把这些笔记蒸馏、重排成一份自成体系的复习资料，只输出 JSON：\n"
        '{"title":"资料标题","subject":"学科","overview":"全资料3-5句概述",'
        '"usage_guide":"复习使用指南：基础一轮/强化二轮/冲刺三轮的学习目标与建议时长",'
        '"chapters":[{"title":"第一章 章节名","intro":"本章一句话导读",'
        '"learning_objectives":{"master":["必须掌握的知识点"],"understand":["需要理解的"],"know":["只需了解的"]},'
        '"sections":[{"heading":"1.1 小节名","type":"definition|concept|derivation|example|code|comparison|conclusion",'
        '"importance":"必考|掌握|了解","quick_memo":"一句话速记（可选）","scenario":"生活场景案例（可选，不必每个小节都有）",'
        '"blocks":[{"type":"text","content":"成段讲解"},{"type":"formula","content":"LaTeX源码，上下标用^{}_{}"},'
        '{"type":"steps","items":["第一步"]},{"type":"list","ordered":false,"items":["要点"]},'
        '{"type":"code","language":"python","content":"完整代码"},{"type":"table","headers":["列1"],"rows":[["a"]]},'
        '{"type":"quote","content":"一句话结论"}],"source_pages":[1,3]}],'
        '"confusion_points":[{"point":"易混点名称","a":"概念A","b":"概念B","difference":"核心区别"}],'
        '"summary":"本章小结2-4句","key_points":["核心结论"],'
        '"quiz":[{"no":1,"type":"single|fill|calc|judge|short","stem":"题干填空用____","options":["选项1","选项2","选项3","选项4"]}]}],'
        '"answers":[{"chapter":"第一章","no":1,"answer":"答案","explanation":"精简解析1-2句"}],'
        '"appendix":{"formula_sheet":[{"name":"公式名","latex":"LaTeX","scene":"适用场景"}],'
        '"glossary":[{"term":"术语","definition":"定义","chapter":"第一章"}],'
        '"flash_cards":[{"front":"问题","back":"答案"}],'
        '"source_map":[{"page":1,"title":"第1集标题","covered_in":["第一章"]}]}}\n'
        "==== 详细规则 ====\n"
        "【整体结构】\n"
        "1. usage_guide：给出三轮复习建议（基础一轮打基础、强化二轮抓重点、冲刺三轮背考点），每轮说明学习目标和建议时长。\n"
        "2. chapters：3-8章，按知识逻辑排列，绝不按视频页码排序。\n"
        "3. answers：所有章节的答案集中放在这里（全局答案篇），不要在每章里放answers。\n"
        "4. appendix：公式表（带名称和适用场景）、术语索引、速记卡、视频来源映射。\n"
        "【章节组织】\n"
        "1. 每章2-6个小节，每个小节聚焦一个完整知识点。\n"
        "2. 【详细程度】输入的视频集数越多，资料越要详细充实。超过20集时每章至少4-6小节，每小节至少2-3个内容块（定义+推导+例题/对比），绝不能因视频多就过度精简。每个text块至少2句话，重要知识点必须完整展开，不能只给一句话结论。\n"
        "2. learning_objectives：按master（必须掌握，能默写能推导）、understand（理解原理，能解释）、know（了解概念，能识别）三级分类。\n"
        "3. 同一个知识点多个视频都讲了，必须合并成一个小节，取最完整的讲解。\n"
        "4. source_pages标注内容来自哪几集。\n"
        "【小节字段】\n"
        "1. importance：必考（★★★，考试高频出现）/掌握（★★，重要知识点）/了解（★，背景知识）。\n"
        "2. quick_memo：一句话速记，用最简短的话概括这个知识点的核心（如'协议三要素：语法定格式、语义定动作、同步定时序'）。可选，不是每个小节都要有。\n"
        "3. scenario：生活场景案例，用生活化的例子帮助理解（如'打电话对应电路交换、发微信对应分组交换'）。可选，不必每个小节都有，全资料有5-10个即可。\n"
        "4. blocks：内容块，公式必须用formula块且上下标正确，代码用code块，对比用table块，推导用steps块。\n"
        "【易混点 confusion_points】\n"
        "1. 每章1-3个易混点辨析，找出本章最容易混淆的两个概念。\n"
        "2. 格式：point（易混点名称）、a（概念A的说法）、b（概念B的说法）、difference（核心区别，一句话说清）。\n"
        "3. 例如：吞吐量vs带宽、处理时延vs排队时延、虚电路vs电路交换。\n"
        "【题目与答案分离】\n"
        "1. quiz只放题目：no（章内题号，从1开始）、type、stem、options（单选才有）。题目里不要出现答案。\n"
        "2. answers集中放在全局：chapter（所属章标题）、no（对应章内题号）、answer、explanation（精简1-2句，只说关键思路和易错点）。\n"
        "3. 每章6-9题，题型：single（单选4选项）、fill（填空____标记）、calc（计算）、judge（判断）、short（简答题）。\n"
        "4. 每章必须含1-2道short简答题（考察概念理解、原理阐述、对比分析，贴合高校期末和考研题型），其余为选择/填空/判断/计算。\n"
        "5. 数理类多出calc和fill，计算机类多出single和fill，文科类多出short。不出证明题。\n"
        
        "6. 单选options不带A./B.前缀，answer只给字母（A/B/C/D）。\n"
        "7. 填空answer按空位顺序，同空等价用/分隔，不同空用|分隔。\n"
        "8. 简答题answer给出完整参考答案要点（分点），explanation说明答题思路。\n"
        "9. 答案和解析中所有数学公式必须用$...$包裹（如$rac{\sigma}{\varepsilon_0}$、$E=mc^2$），绝不能直接写\frac等LaTeX命令而不加$。\n"
        "【学科模板】\n"
        "▼ 数理类math（高数/线代/概率论/物理）\n"
        "通用结构：定义→定理/公式→推导证明→经典例题→适用条件→易错易混对比\n"
        "- 高数：极限/导数/积分的定义与计算，公式必须独立成行且上下标正确，推导用steps分步，例题给完整计算过程，收敛/发散条件用table对比。易混点：收敛vs一致收敛、可导vs可微。\n"
        "- 线性代数：矩阵运算/行列式/向量空间/特征值，矩阵用formula块（LaTeX矩阵语法\\begin{pmatrix}），变换流程用steps，相似/合同/等价用table对比。易混点：行列式vs矩阵、秩vs维数。\n"
        "- 概率论：分布/期望/方差/大数定律，分布函数和密度函数用formula，计算用steps，各分布参数/期望/方差用table汇总。易混点：分布函数vs密度函数、独立vs不相关。\n"
        "- 物理：定律/公式/适用条件/典型模型，公式用formula，推导用steps，模型假设用quote标注。易混点：动量vs动能、电势vs电场强度。\n"
        "▼ 计算机类cs（组成原理/数据结构/算法/操作系统/网络/编程）\n"
        "通用结构：概念→原理/数据结构→算法流程→代码实现→复杂度分析→易错坑点→对比\n"
        "- 组成原理：部件结构/工作流程/性能指标，数据通路和流水线用steps，各部件功能用table对比，性能公式（CPI/加速比/Amdahl定律）用formula。易混点：CPIvs时钟周期、吞吐量vs带宽。\n"
        "- 数据结构：逻辑结构/存储结构/操作/复杂度，每种结构给定义+操作流程（steps）+复杂度（formula），顺序表/链表/栈/队列/树/图对比用table，遍历用steps。易混点：栈vs队列、深度优先vs广度优先。\n"
        "- 算法：思想/伪代码/复杂度/适用场景，思想用text，代码用code块，时间/空间复杂度用formula，分治/贪心/DP/回溯对比用table，经典例题给题干+完整代码+复杂度。易混点：贪心vs动态规划、回溯vs分支限界。\n"
        "- 操作系统：机制/算法/数据结构/状态转换，进程状态转换用steps或table，调度算法用table对比（算法/思想/优缺点/适用），死锁条件和银行家用steps，页面置换算法用table+例题。易混点：进程vs线程、死锁vs饥饿。\n"
        "- 计算机网络：协议/报文格式/工作流程/对比，协议工作流程用steps，报文格式用table（字段/长度/含义），TCP/UDP、各层设备、路由算法用table对比，三次握手/四次挥手用steps。易混点：TCPvsUDP、电路交换vs分组交换、吞吐量vs带宽。\n"
        "- 编程（Python/Java/C等）：语法/用法/最佳实践/坑点，代码完整可运行用code块，语法规则用text，易错点用quote，不同写法对比用table。易混点：值传递vs引用传递、深拷贝vs浅拷贝。\n"
        "▼ 通用类general：按「定义→原理→示例→结论→对比」组织，易混点用table或confusion_points。\n"
        "▼ 英语english：按「核心词汇→语法点→例句→用法归纳→易错提醒」组织，词汇用table（单词/音标/释义/例句），语法点用text+例句，易混点（如时态辨析、近义词辨析）用confusion_points。\n"
        "▼ 文科liberal：按「核心概念→理论框架→对比辨析→案例分析→考点结论」组织，理论框架用steps或list，不同学派/理论用table对比，易混点用confusion_points。\n"
        "【blocks规范】\n"
        "- heading：节内子标题（三级标题），content为标题文字，用于小节内进一步分层。\n"
        "- text：成段讲解，至少2句，可含行内公式$...$与**加粗**。\n"
        "- formula：独立成行公式，content纯LaTeX源码，不包$，上下标必须用^{}和_{}。简单的数量级递进（如2的10次方、10的3次方）不要用formula块，直接用文字描述（如'1024倍'、'千倍'或'1024（2的10次方）'）。\n"
        "- steps：有序步骤数组，推导/解题/算法流程必须用它。\n"
        "- list：并列要点，ordered=false无序/true有序。\n"
        "- code：代码，language给语言名，content完整代码保留缩进。\n"
        "- table：对比或结构化信息，headers表头数组，rows二维数组。\n"
        "- quote：一句话结论或易错提醒。\n"
        "【附录appendix】\n"
        "1. formula_sheet：汇总全资料核心公式（数理/计算机类必填），每个公式带name（公式名）、latex（LaTeX源码）、scene（适用场景一句话）。按章节顺序排列。\n"
        "2. glossary：术语索引，全资料10-20个核心术语，每个带term（术语）、definition（简短定义）、chapter（所在章节标题）。\n"
        "3. flash_cards：速记卡，10-15张，front是问题（如'协议三要素是什么？'），back是答案（如'语法、语义、同步'）。适合考前突击。\n"
        "4. source_map：标注每集视频内容被覆盖到了哪些章节。\n"
        "【质量红线】\n"
        "1. 宁可少而精，不要灌水：每个小节必须有实质内容。\n"
        "2. 严格基于输入：输入里没有的知识点、公式、代码，一律不写。\n"
        "3. 不按视频顺序：章节和小节按知识逻辑排列。\n"
        "4. 合并重复：同一个知识点只出现一次，取最完整版本。\n"
        "5. 公式代码零错误：LaTeX语法正确，上下标用^{}_{}，代码保留完整缩进，专业术语无错别字。\n"
        "6. 题目答案分离：quiz只有题目，answers全局集中放答案，不要在每章里放answers。\n"
        "7. quick_memo和scenario是可选字段，没有就不写，不要硬凑。\n"
        "8. 绝对禁止在正文内容中出现页码数字（如第5页、P10），页码由排版系统自动生成。\n"
        "9. 常识性的数量级、单位换算不要用行内公式$...$或上标，直接用文字+数字（如写'1024倍'而不是'$2^{10}$'，写'千倍'而不是'$10^3$'）。只有真正的数学公式才用formula块或行内公式。"
    )
    return [{"role": "system", "content": REVIEW_MATERIAL_SYSTEM}, {"role": "user", "content": user}]
