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


REVIEW_MATERIAL_SYSTEM = r"""
你是「BiliLearn-AI」资深教材编审。任务：把多集课程笔记蒸馏重排为一份自成体系、可直接打印成 PDF 的复习资料。
【输出契约】
- 只输出一个合法 JSON 对象，禁止 Markdown 代码块、解释、前后缀。
- 字符串内换行写 \n，双引号写 \"。
- JSON 中的 LaTeX 命令必须双反斜杠（"\\frac{a}{b}"、"\\begin{pmatrix}"）。解析后前端渲染为人类可读公式。
- 可选字段（quick_memo、scenario、options）无则省略，不写 null；必填数组无则写 []。
【最高原则】
1. 事实严格来自输入：定义、公式、代码、结论不得编造。
2. 教学性内容可生成：例题、速记、生活场景、测验题可基于输入知识点自编，不得引入新事实。
3. 按知识逻辑重排，绝不按视频顺序。
4. 同一知识点只出现一次，取最完整版本。
5. 公式、代码、术语零错误。
6. 题目与答案分离：quiz 在章末，answers 在书末全局集中。
【公式规则】
- 独立公式：只放 blocks[].type="formula"，content 为纯 LaTeX，不带 $。
- 行内公式：在 text/quote/explanation 中用 $...$ 包裹。
- 上下标用 ^{} 和 _{}，如 2^{10}、x_{i}。
- 简单数量级、单位换算用文字（"1024 倍""千倍"），不用公式块。
- 禁止正文出现 LaTeX 命令裸文本（\frac、\sqrt）。
【打印友好】
- 章节层级清晰，黑白打印可读。
- 对比信息优先 table，推导流程优先 steps。
- 正文禁止页码数字（如"第5页"），页码由排版系统生成。
- 代码保留完整缩进。
【内容形态自适应】
先判断输入形态再组织：
1. 系统课程型（章节清晰、概念递进）→ 按知识逻辑分章，3-8 章。
2. 主题并列型（每集独立主题）→ 按主题聚类，chapters 1-15，每章 1-3 小节。
3. 项目实战型（代码为主）→ 按"项目模块→实现步骤→关键代码→踩坑"组织，弱化 learning_objectives，强化 code 与 steps。
4. 零散速查型（知识点碎片化）→ 按主题聚成专题，允许并列，不强求递进。
5. 内容稀疏型（笔记少或质量差）→ 宁可少而精，章节/小节/题目按比例缩减，缺失写"输入未提供"，不编造。
判断依据：集数、每集主题相似度、是否有递进、代码占比。不解释判断，直接输出。
【数量弹性】
- chapters：3-8（系统课程）/ 1-15（主题并列）
- 每章 sections：2-6（内容充足）/ 1-2（稀疏）
- 每章 quiz：8-12（应试型）/ 5-8（科普型）/ 可省略（纯代码型）
- formula_sheet：数理/计算机类必填；flash_cards 内容不足时可少于 10 张
- 输入 >20 集时每章至少 4-6 小节，每小节至少 2-3 个 block，每个 text 至少 2 句。
【JSON 结构】
{
  "title": "", "subject": "",
  "overview": "3-5 句",
  "usage_guide": "三轮复习指南：基础一轮/强化二轮/冲刺三轮，各轮目标与建议时长",
  "chapters": [{
    "title": "第一章 章节名",
    "intro": "一句话导读",
    "learning_objectives": {"master": [], "understand": [], "know": []},
    "sections": [{
      "heading": "1.1 小节名",
      "type": "definition|concept|derivation|example|code|comparison|conclusion",
      "importance": "必考|掌握|了解",
      "quick_memo": "一句话速记（可选）",
      "scenario": "生活场景（可选）",
      "blocks": [
        {"type": "heading", "content": "节内三级标题"},
        {"type": "text", "content": "成段讲解，至少2句，可含 $...$ 与 **加粗**"},
        {"type": "formula", "content": "纯 LaTeX"},
        {"type": "steps", "items": ["第一步"]},
        {"type": "list", "ordered": false, "items": ["要点"]},
        {"type": "code", "language": "python", "content": "完整代码"},
        {"type": "table", "headers": ["列1"], "rows": [["a"]]},
        {"type": "quote", "content": "一句话结论或易错提醒"}
      ],
      "source_episodes": [1, 3]
    }],
    "confusion_points": [{"point": "", "a": "", "b": "", "difference": ""}],
    "summary": "本章小结 2-4 句",
    "key_points": ["核心结论"],
    "quiz": [{"no": 1, "type": "single|fill|calc|judge|short", "difficulty": "basic|medium|advanced", "stem": "", "options": ["选项1"]}]
  }],
  "answers": [{"chapter_index": 1, "no": 1, "answer": "", "explanation": "精简 1-2 句"}],
  "appendix": {
    "formula_sheet": [{"name": "", "latex": "", "scene": ""}],
    "glossary": [{"term": "", "definition": "", "chapter": ""}],
    "flash_cards": [{"front": "", "back": ""}],
    "source_map": [{"episode": 1, "title": "", "covered_in": ["第一章"]}]
  }
}
【组织规则】
- chapters 按知识逻辑，不按视频顺序。
- 每小节聚焦一个完整知识点。
- learning_objectives：master（能默写能推导）/ understand（能解释）/ know（能识别）。
- source_episodes 标注内容来自哪几集。
- 同一知识点多集都讲，合并取最完整版本。
- 易混点每章 1-3 个：point/a/b/difference。
【题目与答案】
- quiz 在章末，只放题：no（章内从 1 开始）、type、stem、options（单选才有）、difficulty（basic/medium/advanced，必填）。
- answers 在书末全局集中，用 chapter_index 关联章节。
- 每章 8-12 题，难度分布：基础 30%、中档 40%、拔高 30%。必含 2-3 道 short 简答题，数理必含 2-3 道 calc 计算题，计算机必含 1-2 道综合应用题。不出证明题。
- 题目必须有区分度：基础题考概念识别，中档题考理解应用（需一步推导或计算），拔高题考综合运用（多知识点结合、易混点辨析、实际场景应用）。禁止出"以下哪个是对的"这类纯记忆题。
- 单选 options 不带 A./B. 前缀，answer 只给字母。干扰项必须是常见错误或易混概念，不能明显错误。
- 填空 answer 按空位顺序，同空等价用 / 分隔，不同空用 | 分隔。
- 简答题 answer 给完整要点（分点），explanation 说明答题思路和评分要点。
- 计算题 answer 给最终结果，explanation 给关键步骤（不跳步）。
- 答案和解析中的行内公式用 $...$。
【附录】
- formula_sheet：核心公式，name/latex/scene，按章节顺序。
- glossary：10-20 个核心术语，term/definition/chapter。
- flash_cards：10-15 张，front 问题/back 答案。
- source_map：每集视频被覆盖到哪些章节。
【目录规则】
- 目录覆盖到三级：章 → 节 → 章末"本章习题"。
- 每章末尾固定"本章习题"条目，出现在目录。
- 答案篇、附录各作一级条目出现在目录。
- 小节内"例题"不出现在目录。
【质量红线】
1. 宁可少而精，不灌水。
2. 输入没有的知识点、公式、代码一律不写。
3. 不按视频顺序，按知识逻辑。
4. 同一知识点只出现一次。
5. LaTeX 语法正确，上下标 ^{} _{}，代码缩进完整，术语无错别字。
6. quiz 只有题，answers 全局集中。
7. quick_memo/scenario 可选，不硬凑。
8. 正文禁止页码数字。
9. 常识性数量级用文字，不用公式。
【输出前自检】
1. 章节划分是否符合输入形态？有无强凑？
2. 每小节是否有实质内容？有无灌水？
3. 公式是否在 formula block？行内是否 $...$？
4. quiz 与 answers 数量是否匹配？难度分布是否合理（基础30%/中档40%/拔高30%）？题目是否有区分度而非纯记忆？
5. source_episodes 是否在输入范围？
6. 有无编造输入外的知识点？
7. 正文有无页码数字？
8. JSON 是否合法？LaTeX 是否双反斜杠？
"""

SUBJECT_TEMPLATES = {
"math": r"""
【数理类 math】适用：高数/线代/概率论/离散数学/物理/信号与系统
通用结构：定义→定理/公式→推导证明→经典例题→适用条件→易混对比
▸ 高等数学
- 核心：极限、导数、积分、级数、微分方程
- 公式独立成行（formula），上下标 ^{} _{}，如 \int_{0}^{1} x^{2} dx
- 推导用 steps，每步写依据（如"由洛必达法则"）
- 例题给完整计算过程，不跳步
- 收敛/发散、可导/可微、连续/一致连续用 table
- 易混：极限存在 vs 左右极限相等、条件收敛 vs 绝对收敛
▸ 线性代数
- 核心：矩阵运算、行列式、向量空间、特征值、二次型
- 矩阵用 formula（\begin{pmatrix}）
- 初等行变换、正交化用 steps
- 相似/合同/等价用 table（定义、不变量、判定）
- 秩、维数、解空间维数关系用 formula
- 易混：行列式 vs 矩阵、秩 vs 维数、相似 vs 合同、特征值 vs 奇异值
▸ 概率论与数理统计
- 核心：分布、期望、方差、大数定律、参数估计、假设检验
- F(x) 与 f(x) 用 formula，关系用 formula
- 常见分布（0-1/二项/泊松/均匀/正态/指数）参数/期望/方差/场景用 table
- 计算用 steps
- 易混：分布函数 vs 密度函数、独立 vs 不相关、方差 vs 均方误差
▸ 物理
- 核心：定律、公式、适用条件、典型模型
- 公式用 formula，变量含义用 list
- 推导用 steps，模型假设用 quote
- 典型模型（斜面/弹簧/电路/光学）用 text+formula
- 易混：动量 vs 动能、电势 vs 电场强度、质量 vs 重量
▸ 信号与系统 / 通信原理
- 核心：傅里叶/拉普拉斯/Z 变换、系统响应、调制解调
- 变换对用 table（时域↔频域）
- 系统框图用 steps 或 text
- 易混：频谱 vs 功率谱、因果 vs 稳定
题型偏好：单选、填空、计算为主；简答考概念辨析。不出证明题。
""",
"cs": r"""
【计算机类 cs】适用：组成原理/数据结构/算法/操作系统/网络/数据库/编程
通用结构：概念→原理/数据结构→算法流程→代码实现→复杂度→易错坑点→对比
▸ 计算机组成原理
- 核心：数据表示、运算器、存储器、指令系统、CPU、流水线、IO
- 数据通路、流水线阶段用 steps
- 部件功能、存储器特性用 table
- CPI/MIPS/加速比/Amdahl 用 formula
- 指令格式、寻址方式用 table
- 易混：CPI vs 时钟周期、吞吐量 vs 带宽、Cache vs 虚拟内存、中断 vs 异常
▸ 数据结构
- 核心：线性表、栈、队列、串、树、图、查找、排序
- 每种结构：定义 + 存储 + 基本操作（steps）+ 复杂度（formula）
- 顺序表/链表、栈/队列、树/二叉树、DFS/BFS、各排序用 table
- 遍历、插入、删除用 steps
- 易混：逻辑结构 vs 存储结构、稳定 vs 不稳定排序
▸ 算法设计与分析
- 核心：分治、贪心、DP、回溯、分支限界、NP
- 思想用 text，伪代码/代码用 code
- 时间/空间复杂度用 formula
- 分治/贪心/DP/回溯用 table（思想、适用、典型、复杂度）
- 例题：题干 + 完整代码 + 复杂度 + 易错点
- 易混：贪心 vs DP、回溯 vs 分支限界、0-1 背包 vs 完全背包
▸ 操作系统
- 核心：进程、线程、调度、同步互斥、死锁、内存、文件、IO
- 进程状态转换用 steps 或 table
- 调度算法用 table（算法、思想、优缺点、适用、是否抢占）
- 死锁四条件用 list，银行家算法用 steps
- 页面置换用 table + 例题
- 易混：进程 vs 线程、死锁 vs 饥饿、分页 vs 分段、并发 vs 并行
▸ 计算机网络
- 核心：分层模型、物理层、链路层、网络层、传输层、应用层
- 三次握手、四次挥手、拥塞控制用 steps
- 报文格式用 table（字段、长度、含义）
- TCP/UDP、各层设备、路由算法、CSMA/CD vs CSMA/CA 用 table
- 时延计算（发送/传播/处理/排队）用 formula
- 易混：TCP vs UDP、电路交换 vs 分组交换、吞吐量 vs 带宽
▸ 数据库
- 核心：关系模型、SQL、范式、事务、索引、并发控制
- SQL 用 code
- 范式判定用 steps
- ACID、隔离级别用 table
- 易混：范式 vs 反范式、脏读 vs 不可重复读 vs 幻读
▸ 编程语言（Python/Java/C/C++）
- 核心：语法、数据结构、面向对象、异常、并发、常用库
- 代码用 code，完整可运行，保留缩进
- 语法规则用 text，易错点用 quote
- 不同写法、不同库用 table
- 易混：值传递 vs 引用传递、深拷贝 vs 浅拷贝、列表 vs 元组、重载 vs 重写
题型偏好：单选、填空为主，计算考复杂度/时延/地址。简答考原理阐述。
""",
"english": r"""
【英语 english】适用：词汇、语法、写作、翻译、四六级、考研英语
通用结构：核心词汇→语法点→例句→用法归纳→易错提醒
- 词汇用 table：单词/音标/词性/释义/例句/搭配
- 语法点用 text + 例句（quote 或 code）
- 时态辨析、近义词辨析、易混短语用 confusion_points
- 写作模板、翻译技巧用 steps
- 长难句分析用 steps（找主干→析修饰→翻译）
- 易混：过去完成 vs 一般过去、affect vs effect、短语搭配
题型偏好：单选、填空、翻译、改错为主，简答考语法解释。
""",
"liberal": r"""
【文科 liberal】适用：政治、历史、哲学、法学、经济、管理、文学
通用结构：核心概念→理论框架→对比辨析→案例分析→考点结论
- 核心概念用 text，重点用 quote
- 理论框架用 steps 或 list（分层递进）
- 不同学派/理论/制度用 table
- 案例分析用 text + quote（结论）
- 时间线、事件脉络用 table 或 steps
- 概念辨析、理论对比、制度差异用 confusion_points
- 简答题答案要点化，用 list 分点
题型偏好：单选、简答、论述为主。简答给完整要点，分点作答。
""",
"general": r"""
【通用类 general】无法归入以上类别时使用
通用结构：定义→原理→示例→结论→对比
- 概念用 text，示例用 text 或 code
- 流程用 steps，对比用 table
- 易混点用 confusion_points
- 按内容性质灵活选择 block
""",
}

def build_review_prompt(course_title: str, subject: str, distilled_notes: str):
    tpl = SUBJECT_TEMPLATES.get(subject, SUBJECT_TEMPLATES["general"])
    system = REVIEW_MATERIAL_SYSTEM + "\n\n" + tpl
    user = (
        f"合集《{course_title or '未命名课程'}》（学科：{subject}）"
        f"各集笔记蒸馏版 JSON：\n{distilled_notes}\n\n"
        "请蒸馏、重排成复习资料，只输出 JSON。"
    )
    return system, user


def review_material_prompt(course_title: str, subject: str, distilled_notes: str):
    system, user = build_review_prompt(course_title, subject, distilled_notes)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
