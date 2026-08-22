# 竞品调研：bilibili-video-notes-skill 与 BibiGPT

调研时间：2025-08 | 对照项目：BiliLearn-AI

## 1. asdhabdua/bilibili-video-notes-skill（GitHub，42 stars）

**定位**：命令行工具，把 B站网课视频自动生成「带截图的 DOCX 学习笔记」，专为 AI Agent（Hermes / Claude Code / Codex）直接调用设计。

**技术亮点**
| 亮点 | 说明 | BiliLearn-AI 现状 |
| --- | --- | --- |
| 全覆盖抽帧 | 每 10 秒一帧，不丢画面 | 我们按笔记时间戳取 8 帧 |
| OCR + 感知哈希去重 | 129 帧 → 20-40 帧，去掉重复画面 | 我们没有帧去重 |
| AI 视觉打分精选 | 每知识点挑最完整一帧（7-12 张） | 我们没有打分 |
| 截图嵌入笔记 | 关键帧直接进 DOCX 笔记正文 | 公式识别有帧，但笔记正文无图 |
| AI 字幕下载 | 明确使用 SESSDATA Cookie 换取 B站 AI 字幕 | 我们 Cookie 已支持但未试 AI 字幕接口 |
| DOCX 导出 | Word 格式输出 | 我们只有 MD/PDF/Anki/CSV |
| 本地视频支持 | 可直接处理本地 mp4 | 我们只支持 B站链接 |
| Agent 工程化 | SKILL.md / CLAUDE.md / AGENTS.md，AI 助手可一键调用 | 我们没有 |

## 2. BibiGPT（bibigpt.co，商业 SaaS）

**定位**：多平台 AI 总结工具矩阵（217 个工具：AI总结/字幕转写/视频/音频/图像/对比/趋势），覆盖 YouTube/B站/TikTok/抖音/快手/Podcast/会议。

**功能亮点（按对我们的可借鉴度排序）**
| 亮点 | 说明 | 借鉴价值 |
| --- | --- | --- |
| B站 → XMind 思维导图导出 | 生成可下载的 .xmind 文件 | 高：我们只有 Mermaid 预览 |
| AI 视频问答 | 直接对视频内容提问（无需先做笔记） | 高：我们需先生成笔记 |
| 字幕转写下载 | 纯字幕文件下载导出 | 中：我们可加 .srt 导出 |
| Obsidian 笔记入库 | Markdown + frontmatter 一键导入 Obsidian | 中：我们导出加 frontmatter 即可 |
| Study Guide Maker | 学习资料自动生成（课程讲义/闪卡） | 中：类似我们的自测，可加"讲义"模式 |
| 图片文字总结 | 截图/照片一键 AI 提炼 | 低：超出视频笔记定位 |
| 217 工具矩阵 | 全媒体覆盖（YouTube/TikTok/音频/会议） | 低：开源项目无需铺量，但 yt-dlp 天然支持多平台，可顺带开放 |

## 3. 差异化总结

**我们领先**：时间戳全链路跳转 + 内嵌播放器、分学科模板、阶梯自测+逐题AI批改、错题本/复盘/艾宾浩斯计划、合集批量+全课程知识图谱、AI 答疑（图示化）、深色主题、双布局、本地部署开源免费。

**对方领先（值得借鉴）**：DOCX 导出、XMind 导出、笔记内嵌关键帧截图、帧去重+AI精选算法、带 Cookie 的 AI 字幕、本地视频支持、AI Agent 直接调用（SKILL.md）、纯字幕导出、直接视频问答。

## 4. 按需添加清单（建议优先级）

### P0 高价值
1. **DOCX 导出**（python-docx）：结构化笔记 → 带样式的 Word 文档（考研党刚需）
2. **XMind 导出**：生成 .xmind 文件（zip 结构手写 content.json 即可）或导出缩进大纲文本
3. **笔记内嵌关键帧截图**（可选开关）：复用帧提取，按章节插入 1-2 张关键帧到笔记正文

### P1 中价值
4. **AI 字幕抓取升级**：配置 Cookie 后尝试 B站 player/v2 AI 字幕接口（很多"无字幕"视频其实有 AI 字幕，只是游客拿不到）
5. **SKILL.md**：让 Claude Code/Cursor/Codex 等 AI 助手能直接操作本项目
6. **视频直接问答**：未生成笔记时，用字幕作为上下文直接提问
7. **纯字幕导出**：.srt / .txt 下载
8. **Obsidian 导出**：Markdown 导出加 YAML frontmatter（tags/source/date）

### P2 锦上添花
9. **本地视频文件支持**：拖入 mp4 → 转写 + 笔记（yt-dlp 改为本地文件即可，复用 whisper）
10. **帧去重升级**：抽帧后感知哈希去重 + AI 打分精选（替代固定时间戳取样）
11. **讲义模式**：类似 Study Guide Maker，一键生成"课前预习讲义/课后复习卡"
12. **多平台顺带支持**：yt-dlp 天然支持 YouTube/抖音，可在解析层放开（B站专项逻辑之外）

> 建议先做 P0 三项：改动集中在 export 层与帧复用，风险小、见效快，且直接命中"考研党要 Word 笔记"的核心场景。
