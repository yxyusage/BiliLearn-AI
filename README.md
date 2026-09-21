# BiliLearn-AI 📚

**B站全学科AI学习助手** —— 输入B站视频/合集链接，自动完成「字幕提取 → 分学科结构化笔记 → 阶梯自测 → 错题复盘 → 复习计划」的完整学习闭环，所有知识点、公式、题目、错题全程绑定视频时间戳，点击即可跳转复习片段。

> 面向大学生、考研/考证备考人群，覆盖英语、高等数学、线性代数、计算机专业课、物理等全品类大学课程。

## ✨ 核心特性

| 能力 | 说明 |
| --- | --- |
| 🎬 视频解析 | 支持单视频链接、BV号、合集/分P链接，自动解析视频信息 |
| 💬 字幕提取 | 优先抓取B站官方CC字幕（UP主上传/AI字幕），无字幕视频可选本地 faster-whisper 离线转写（无需 ffmpeg，支持中英文） |
| ⏱ 全链路时间戳 | 字幕、知识点、题目、错题统一 `HH:MM:SS` 格式，内嵌B站播放器点击直达 |
| 🎓 分学科模板 | 通用/英语/数理/计算机/文科 5 套专属笔记逻辑，拒绝通用化总结 |
| 🧠 思维导图 | 箭头式 Mermaid 知识框架，节点内置时间戳，点击任意节点直接跳转视频片段 |
| 📝 阶梯自测 | 三级题库嵌入各章节，逐题判断 + AI 批改讲解，错题自动入错题本 |
| 💬 AI 答疑 | 基于当前笔记内容的对话式提问，支持 Mermaid 图示化回答 |
| 🖥 双布局播放器 | 左右分栏（分隔条可拖动调宽）+ 视频置顶两种布局，看笔记下滑时视频始终吸顶不跟随 |
| 📄 精美导出 | 笔记型 Markdown（含目录/元信息）与结构化 PDF 排版，非字幕流水账 |
| 🩺 AI 复盘 | 基于错题自动分析薄弱点，给出复习优先级与对应视频片段 |
| 🔁 复习计划 | 按艾宾浩斯遗忘曲线自动生成复习时间表（1/2/4/7/15/30 天） |
| 🔤 英语专项 | 听力原文精校、生词提取（音标/释义/原句/时间戳）、连读/弱读/失去爆破语音现象标注、Anki 卡片导出 |
| 🎧 英语听写填空 | 从原视频字幕智能挖空（实词/短语/时态），先听后填、即时判分，附提示与译文（可开关） |
| 📚 合集批量 | 后台异步队列逐集生成、进度实时展示、已完成集复用缓存、全课程知识图谱（节点点击跨集跳转）+ 考点地图 |
| ➗ 公式识别 | 关键帧提取（无需 ffmpeg）+ 视觉大模型识别板书/课件公式，自动转换 LaTeX |
| 🌗 三套主题配色 | 纸墨青/海盐蓝/秋日橙三套配色 × 深浅模式，一键切换自动记忆 |
| 🙋「没懂」AI 换讲 | 笔记任意小节打点提问，AI 换一种更通俗的讲法，可标记已解决 |
| 🧭 学前诊断 | 打开合集后续视频前，先抽测前面几集的先修知识点，给出「可跳过 / 需先复习」建议（可开关） |
| ✨ 同类变式题 | 自测题旁一键生成 AI 变式（换数字/换情境），同一知识点多角度巩固（可开关） |
| 🔁 SM-2 动态复习 | 复习中心四档自评（重来/困难/良好/简单），按 SM-2 算法自动重排下次复习 |
| 📊 学习数据仪表盘 | 近 14 天产出、学科分布、错题掌握度、复习节奏，ECharts 可视化一屏掌握 |
| 📑 侧边吸顶目录 | 目录固定在笔记侧边，滚动时不消失，直达任意知识点 |
| 📱 手机访问 + PWA | 同一局域网手机浏览器直接访问；可添加到主屏幕、离线看已缓存笔记 |
| ➗ 数理专项 | 定理按「定义→推导→适用条件→例题→易错点」整理，公式 LaTeX 输出 |
| 💻 计算机专项 | 代码片段提取、逻辑拆解、拓展练手 |
| 📤 多格式导出 | Markdown / PDF / Word(DOCX 含关键帧截图) / XMind / Anki(.apkg) / CSV |
| 💬 AI 答疑 | 基于笔记上下文的流式对话（逐字输出），支持 Mermaid 图示化回答 |
| 🖼 关键帧嵌入 | 按章节提取视频关键帧截图，嵌入笔记与 Word/PDF 导出 |
| 🔌 灵活模型 | DeepSeek / Kimi / 通义千问 / 本地 Ollama 统一封装，密钥仅存本地 SQLite |
| 🐳 双启动 | Docker Compose 一键部署 + 原生终端启动 |

## 🏗 技术架构

- **后端**：Python 3.10+ / FastAPI / SQLAlchemy(SQLite) / yt-dlp / httpx / reportlab / genanki
- **前端**：Vue 3 / Element Plus / Mermaid.js / Vite / Pinia / Vue Router
- **AI**：统一 SDK 封装（DeepSeek、Kimi、通义千问为 OpenAI 兼容协议，Ollama 本地原生接口），长字幕自动分段 + 汇总（map-reduce），JSON 输出失败自动重试
- **存储**：SQLite（笔记/字幕缓存/配置/错题/复习计划）+ 本地 Markdown 文件同步导出

```
视频链接 → yt-dlp 解析 → 官方CC字幕(无则 whisper 转写)
   → 字幕按 6000 字分段 → 分段生成小节笔记 → 全局汇总（章节 + 脑图）
   → 分学科模板渲染 → SQLite 存储 → 前端播放器联动
   → 阶梯自测 → 错题本 → AI 薄弱复盘 → 艾宾浩斯复习计划
```

## 🚀 快速开始（零基础也能跑）

### 前提：安装两个软件（各约 2 分钟）

1. **Python**（3.10 以上）：打开 https://www.python.org/downloads/ 下载安装。
   ⚠️ Windows 安装时**务必勾选「Add Python to PATH」**（在安装窗口最下面）
2. **Node.js**（18 以上）：打开 https://nodejs.org/ 下载「LTS 长期支持版」安装，一路下一步即可

装好后可以关掉安装包，下面的操作**只需要双击一个文件**。

### 方式一（最推荐）：双击启动脚本

- **Windows**：进入项目文件夹，**双击 `start.bat`**
- **macOS / Linux**：在终端进入项目文件夹，运行 `./start.sh`

脚本会自动完成：创建环境 → 安装依赖 → 构建前端 → 启动服务 → **自动打开浏览器**（http://localhost:8000）。
第一次运行要等 2-5 分钟（在下载组件），之后每次启动只需几秒。
**关闭那个黑色窗口 = 停止程序**；下次再用时再双击一次即可。

> 提示：任何操作都需要先「进入项目文件夹」（就是你下载解压出来的 `BiliLearn-AI` 文件夹）。Windows 下在文件夹地址栏输入 `cmd` 回车可打开终端。

### 方式二：Docker（适合已安装 Docker Desktop 的用户）

```bash
cd 项目文件夹
docker compose up -d --build
# 浏览器打开 http://localhost:8000
```

### 方式三：手动运行（开发者/想改代码的人）

```bash
# 终端 1：后端
cd 项目文件夹
python -m venv .venv            # 仅第一次
.venv\Scripts\activate          # Windows；mac/Linux 用 source .venv/bin/activate
pip install -r backend/requirements.txt   # 仅第一次
uvicorn backend.app.main:app --reload --port 8000

# 终端 2：前端（仅开发时需要，生产模式可跳过）
cd frontend
npm install                     # 仅第一次
npm run dev                     # http://localhost:5173
```

生产模式（后端直接托管前端页面）：先 `cd frontend && npm run build`，再只启动后端，访问 http://localhost:8000。

### 启动后干什么

1. 打开 http://localhost:8000，点右上角「设置」→ 填一个 API Key（DeepSeek 最便宜，点输入框旁的「获取 Key ↗」直达申请页）
2. 回首页粘贴B站链接 → 解析 → 生成笔记，搞定

### 📱 手机也能用（同一局域网）

电脑启动服务后，手机连同一 WiFi / 热点，浏览器访问 `http://电脑IP:8000` 即可（PWA 支持「添加到主屏幕」）。
详细步骤（查 IP、防火墙放行、常见问题）见 [docs/手机访问指南.md](docs/手机访问指南.md)。

### 启动遇到问题？

| 现象 | 解决办法 |
| --- | --- |
| 提示「python 不是内部或外部命令」 | 重装 Python 并勾选「Add Python to PATH」，或重启电脑后再试 |
| 提示「npm 不是内部或外部命令」 | 重装 Node.js LTS 版 |
| 双击 start.bat 一闪而过 | 在项目文件夹地址栏输入 cmd 打开终端，输入 `start.bat` 看报错信息 |
| 8000 端口被占用 | 关闭占用程序，或改用 `uvicorn backend.app.main:app --port 8080` |
| 语音转写下载模型慢 | 脚本已自动使用国内镜像，无需处理 |

## 🔑 模型与功能设置

打开网页右上角「**设置**」，可配置：模型供应商与 API Key、英语听写/变式题/学前诊断三个功能开关、界面配色（纸墨青/海盐蓝/秋日橙 × 深浅模式）。

| 供应商 | API Key 获取 | 默认模型 | 说明 |
| --- | --- | --- | --- |
| DeepSeek | https://platform.deepseek.com | deepseek-chat | 性价比高，推荐 |
| Kimi | https://platform.moonshot.cn | kimi-k2.6 | 大窗口，适合长视频 |
| 通义千问 | 阿里云百炼 DashScope | qwen-plus | 国内生态 |
| Ollama | 本地，无需 Key | qwen2.5:7b | `ollama serve` 后 `ollama pull qwen2.5:7b` |

> 环境变量方式：复制 `.env.example` 为 `backend/.env` 并填写，效果相同。

## 📖 使用指南

1. **解析视频**：首页粘贴 B站视频/合集链接，选择课程类型（通用/英语/数理/计算机/文科），点击「解析视频」
2. **生成笔记**：确认字幕已获取后点击「生成笔记」，AI 分段生成带时间戳的结构化笔记（约 1-5 分钟，可关闭页面）
3. **复习笔记**：笔记页内嵌B站播放器，点击任意时间戳或脑图节点自动跳转；支持「左右分栏（分隔条可拖动）/ 视频置顶」两种布局，下滑看笔记时视频始终吸顶
4. **自测检验**：点击「生成本课自测题」后题目自动嵌入各章节下方，逐题点「判断」由 AI 批改并讲解，错题自动入错题本；旁边「✨ 变式题」可换数字/换情境再练
5. **没懂换讲**：任意小节点「🙋 没懂」，AI 用更通俗的方式重讲，理解了就标记解决
6. **英语听写**：英语笔记「听写」页签一键生成挖空听写，先听后填即时判分
7. **AI 答疑**：右上角「💬 AI 答疑」抽屉，基于当前笔记上下文随时提问
8. **薄弱复盘**：「复盘」页生成薄弱点分析（含优先级与复习片段）+ 复习计划；复习中心学完自评（重来/困难/良好/简单），系统按 SM-2 重排下次复习
9. **学习数据**：顶部「学习数据」查看产出与错题掌握趋势
10. **导出**：笔记型 Markdown（含目录）/ 结构化 PDF / Word(DOCX 含关键帧) / XMind / Anki 卡片 / CSV

### 输出文件在哪里

- 所有笔记数据保存在本地 SQLite：`backend/data/bililearn.db`（Docker 部署对应 `./data` 挂载目录）
- 每份笔记生成完成时，自动同步保存一份 Markdown 文件到：`backend/data/notes/`（如 `0001_TED-Ed_ The uncertain location of electrons.md`）
- 点击笔记页「导出 PDF / Anki / CSV」按钮下载的文件，进入浏览器默认下载目录（后端按需生成，不落盘）

## 📁 项目结构

```
BiliLearn-AI/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI 主应用
│   │   ├── config.py          # 配置（环境变量）
│   │   ├── database.py        # SQLite 连接 + 自动迁移
│   │   ├── models.py          # 数据模型（Note/Quiz/ReviewPlan/ConfusionPoint）
│   │   ├── schemas.py         # 请求/响应模型
│   │   ├── routers/           # video/notes/quiz/review/config/export/stats/collections
│   │   ├── services/
│   │   │   ├── bilibili.py    # 视频解析 + 字幕提取
│   │   │   ├── whisper.py     # 本地离线转写（可选）
│   │   │   ├── prompts.py     # 学科 Prompt 模板库（含听写/变式/换讲）
│   │   │   ├── note_generator.py  # 分段+汇总笔记生成（教材精编结构）
│   │   │   ├── quiz_generator.py  # 阶梯自测 + 变式题
│   │   │   ├── features.py    # 听写/变式/换讲 功能服务
│   │   │   ├── review.py      # 复盘 + SM-2 动态复习计划
│   │   │   ├── export.py      # Markdown/PDF/Word/Anki 导出
│   │   │   └── llm/           # 大模型统一封装（DeepSeek/Kimi/Qwen/Ollama）
│   │   └── utils/timestamp.py # HH:MM:SS 时间戳工具
│   └── requirements.txt
├── frontend/
│   ├── public/                # PWA manifest + Service Worker + 图标
│   └── src/
│       ├── views/             # Home/History/NoteDetail/Dashboard/Review/Config/Collections
│       ├── components/        # VideoPlayer/MermaidView/QuizCard/DictationCard/LatexText
│       └── utils/theme.js     # 三套配色主题系统
├── docs/
│   ├── API.md                 # 接口文档
│   └── 手机访问指南.md         # 手机访问 + 防火墙放行教程
├── docker-compose.yml
├── Dockerfile
└── start.bat / start.sh       # 一键启动脚本
```

## ✅ 真机验证

以下链路已在真实环境（Windows + DeepSeek + 通义千问免费额度）跑通：

- B站 996P 大合集解析、单P定位（TED-Ed 英语视频）
- 无字幕视频 → faster-whisper 本地转写（3.5 分钟音频约 24 秒完成）
- 英语专项笔记：听力原文/语言点/词汇短语/考点 4 章 31 个知识点 + 思维导图 + 18 个生词 + 13 处语音现象标注
- 阶梯自测 9 题（三档全齐）→ 逐题 AI 批改讲解 → 错题本（含 AI 讲解）→ 薄弱复盘（含复习片段时间戳）→ 24 条艾宾浩斯计划
- Markdown / PDF / Anki(.apkg) / CSV 四种导出全部正常
- 箭头式脑图（graph TD，节点含时间戳可点击跳转）、AI 答疑（含图示化回答）、双布局拖动分栏、深浅主题均已实测通过
- 合集批量队列、全课程知识图谱/考点地图、多模态公式识别（qwen-vl-plus）已完成端到端联调
- **v1.6 实测链路**：英语听写 12 题挖空生成（含提示/译文/时间戳）✅、变式题（AI 换题）✅、没懂换讲（打点→换讲→解决）✅、SM-2 评分重排（良好→次日复习）✅、学前诊断/学习数据仪表盘（4 统计卡 + 4 图表）✅、三套配色深色浅色截图核验 ✅、PWA manifest + Service Worker 产物 ✅

## ❓ 常见问题

**Q：解析成功但提示「未检测到官方字幕」？**
视频没有 UP 主上传字幕或 AI 字幕（标题写「CC字幕」也可能是烧录进画面的）。可在「模型配置」页开启「离线语音转写」（需 `pip install faster-whisper`），并可自选模型（tiny/base/small/medium/large）与音频语言。

**Q：语音转写模型下载很慢/失败（国内网络）？**
faster-whisper 默认从 huggingface.co 下载模型，国内可切换镜像后重试：

```bash
# Windows PowerShell
$env:HF_ENDPOINT='https://hf-mirror.com'
# macOS/Linux
export HF_ENDPOINT=https://hf-mirror.com
```

**Q：生成/导出的文件在哪里？**
数据目录：`backend/data/`。其中 `bililearn.db` 是 SQLite 数据库（笔记/字幕缓存/错题/配置），`notes/` 下是每份笔记自动同步的 Markdown 文件；网页上「导出」按钮下载的 PDF/Anki/CSV 进入浏览器下载目录。

**Q：公式识别提示 Arrearage / 账户异常 / 一直识别不到？**
公式识别依赖视觉模型（默认阿里云通义千问 qwen-vl-plus）。若提示 `Arrearage` 表示**阿里云账号欠费或免费额度已用完**：到 bailian.console.aliyun.com 检查余额/开通服务；也可在「模型配置」填写 Kimi Key，笔记页选择「Kimi 视觉模型」。

**Q：有 NVIDIA 显卡但转写报错 cublas64_12.dll 缺失？**
程序默认使用 CPU 推理（更通用）。如需 GPU 加速，请安装对应版本 CUDA 后自行修改 `backend/app/services/whisper.py` 中的 device 参数。

**Q：长视频笔记不全？**
后端自动按 6000 字符把字幕分段、逐段生成后再全局汇总；可把 `backend/app/config.py` 中 `subtitle_chunk_chars` 调小。长视频建议用大窗口模型（Kimi 32k）。

**Q：生成失败提示 API Key？**
到「模型配置」填写对应供应商的 Key，并点「测试连接」确认。

**Q：Windows 原生启动报错？**
确认已安装 ffmpeg 并加入 PATH；Python 版本 ≥ 3.10。其余环境问题建议直接使用 Docker 方式。

**Q：会消耗多少 API 费用？**
一次笔记生成约调用 N+1 次（N=分段数），自测/复盘各 1 次。DeepSeek 单条 30 分钟视频约几分钱。已生成的笔记不会重复请求。

## 🗺 路线图

- [x] 阶段1 MVP：视频解析、官方字幕、DeepSeek 笔记生成、SQLite、历史查询
- [x] 阶段2 核心：分学科模板（英语/数理/计算机/文科）、思维导图、阶梯自测、时间戳跳转、Markdown/PDF/Anki 导出、错题本
- [x] 阶段3 进阶：AI 薄弱复盘、艾宾浩斯复习计划、Kimi/通义千问/Ollama 支持
- [x] 阶段3 完整：合集批量异步队列、全课程知识图谱 + 考点地图、关键帧板书/公式多模态识别（LaTeX）
- [x] 阶段4 工程化：GitHub Actions CI、CHANGELOG、Docker 健康检查、README 完善
- [x] 阶段5 学习闭环增强：英语听写填空、同类变式题、没懂 AI 换讲、学前诊断、SM-2 动态复习、学习数据仪表盘
- [x] 阶段5 体验优化：三套主题配色、侧边吸顶目录、介绍折叠、功能开关、PWA 手机访问基础
- [ ] 持续优化：播放进度高亮当前知识点、代码高亮、双语对照、移动端深度适配（点选式刷题交互）

## ⚖️ 合规声明

本项目仅用于个人学习研究：不缓存、不传播完整视频，仅处理字幕文本与生成的笔记内容；请勿用于商业用途，请尊重 UP 主与平台的版权。

> 所有 API Key、B站 Cookie 仅保存在本地 SQLite（`backend/data/`，已被 `.gitignore` 排除），不会上传 GitHub 或任何服务器。

## 📄 License

[MIT](LICENSE)
