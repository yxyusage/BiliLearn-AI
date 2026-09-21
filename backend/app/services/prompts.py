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
