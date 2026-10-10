# BiliLearn-AI

把 B 站学习视频转成结构化笔记、自测题和可打印复习资料的本地工具。

输入单个视频或合集链接，程序自动提取字幕、调用大模型生成笔记，知识点全部绑定视频时间戳，点击即可跳转到对应片段。同时提供 Chromium 浏览器扩展，可在 B 站页面内以侧边栏直接生成和浏览笔记。

所有数据保存在本地 SQLite，API Key 不上传。

---

## 界面预览

| 主界面 | 合集管理 |
| :---: | :---: |
| ![主界面](docs/images/home.png) | ![合集管理](docs/images/collections.png) |

| 学习数据 | 收藏夹导入 |
| :---: | :---: |
| ![学习数据](docs/images/dashboard.png) | ![收藏夹导入](docs/images/favorites.png) |

| 设置 | 手机访问 |
| :---: | :---: |
| ![设置](docs/images/settings.png) | ![手机端](docs/images/mobile.png) |

---

## 功能

**笔记生成**
- 按「定义 → 推导 → 例题 → 结论」组织，而非字幕原文堆砌
- 内置数理、计算机、英语、文科、通用五套学科模板
- 知识点绑定 `HH:MM:SS` 时间戳，点击跳转视频片段
- LaTeX 公式渲染、Mermaid 思维导图
- 无官方字幕时可用 faster-whisper 本地离线转写
- 需要登录才可见的字幕：在「设置 → B站 Cookie」填入含 `SESSDATA` 的 Cookie 即可（可选，支持一键验证登录状态）

**本地视频**
- 首页可在「B站链接 / 本地视频」之间切换：本地 mp4 / mkv / flv / avi 等直接生成笔记，不需要 B 站链接
- 「选择文件」调用系统文件选择框，原文件原地读取，不复制、不上传；也可把视频拖进页面
- 本地视频用 faster-whisper 离线转写，笔记详情页内置播放器，时间戳点击即可跳到对应画面

**合集处理**
- 解析合集后列出全部分集，可指定起止集数范围
- 后台并发生成，默认 4 路（可在 1–6 之间调整），进度实时可见
- 连续网络失败会自动暂停；恢复网络后可从断点继续，已完成的集数不重复生成
- 单集失败可单独重试
- 合集线路图：按知识模块分组，标注重难点，给出建议学习起点

**复习与自测**
- 合集复习资料：将多集笔记按知识逻辑（而非视频顺序）蒸馏重排，导出可打印 PDF / Word，含目录页码、学习目标、易混辨析、章节测试、答案、术语索引和速记卡
- 自测题支持单选、判断、填空、计算、简答，可手动生成、生成变式题
- 基于笔记上下文的 AI 答疑，支持多轮对话
- 错题自动归集
- 笔记可标记「未学 / 学习中 / 已学完」，合集显示整体进度

**其他**
- 知识点关联图谱（ECharts 力导向图，点击节点跳转笔记）
- 按标题和摘要搜索笔记
- 单篇笔记导出 Markdown / PDF / Word，英语内容可导出 Anki 卡片
- 扩展内一键截取视频画面：按视频分组查看，下载时自动按「视频标题」建子文件夹，记录分 P 与时间点

---

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+（仅在前端未预构建时需要，便携版已内置构建产物）

> 安装 Python 时勾选「Add Python to PATH」。安装完成后在终端执行 `python --version` 和 `node --version`，能显示版本号即可。

### 方式一：便携版（Windows，推荐）

从 [Release 页面](https://github.com/yxyusage/BiliLearn-AI/releases/latest) 下载 `BiliLearn-AI-v1.8.5-portable.zip`，解压后双击根目录的 `BiliLearn-AI-Launcher.exe`，点击「启动服务」。

启动器会自动完成虚拟环境创建、依赖安装和前端检查，之后启动只需数秒。完成后浏览器自动打开。

> 首次安装依赖时，启动器会**先并发探测各个 PyPI 镜像、挑最快的那个**，再并发下载 wheel 后本地安装。镜像之间差别很大——实测同一台机器上华为云 732 KB/s、阿里云只有 46 KB/s（差 16 倍），这也是"以前首启特别慢"的主要原因。
> 进度条上是**真实的百分比、下载速度和预计剩余时间**；即使回退到普通 pip，也是逐行实时输出，不会"看起来卡死"。

启动器还支持：API Key / 模型 / 端口配置、实时日志、数据目录打开、版本检查，以及关闭窗口后最小化到系统托盘。

### 方式二：命令行脚本

适合 macOS / Linux，或不想用图形启动器的用户。

下载源码（`Code → Download ZIP`，或 `git clone`）后，在项目根目录执行：

```bash
# Windows
start.bat

# macOS / Linux
chmod +x start.sh
./start.sh
```

脚本会自动创建虚拟环境、安装依赖、构建前端并启动服务，成功后访问 http://localhost:8000。

> 若通过 `Download ZIP` 获取源码后又想使用图形界面，可单独下载 `BiliLearn-AI-Launcher.exe` 并放到项目根目录（与 `backend/`、`frontend/` 同级），否则启动器找不到后端文件。

### 配置 API Key

1. 打开页面，点击右上角「设置」
2. 选择模型供应商，填入 API Key
3. 点击「测试连接」确认可用后保存

API Key 仅保存在本地数据库中。

### 生成第一篇笔记

1. 首页粘贴 B 站视频链接，点击「解析」
2. 点击「生成笔记」，等待完成（时长取决于视频长度）
3. 生成后自动进入笔记详情页

---

## 浏览器扩展

扩展可在 B 站页面内以侧边栏完成笔记生成与浏览，无需切换标签页。

![侧边栏演示](docs/images/sidepanel.gif)

> 完整录屏：[docs/images/sidepanel.mp4](docs/images/sidepanel.mp4)

1. 打开 Chrome 或 Edge，地址栏输入 `chrome://extensions/`（Edge 为 `edge://extensions/`）
2. 打开右上角「开发者模式」（Edge 为左下角「开发人员模式」）
3. 如果是升级：在扩展卡片上点一次「🔄 重新加载」，否则会继续跑旧版本的插件代码
4. 点击「加载已解压的扩展程序」，选择项目下的 `extension/` 目录

使用前确保后端服务已启动。侧边栏包含笔记、答疑、题目、合集和截图五个面板。

> **Edge 用户**：需在扩展详情页的「站点访问权限」中，开启对 `https://*.bilibili.com/*` 和 `http://127.0.0.1:8000/*` 的访问权限。扩展与 Web 端共用同一份本地数据库。
>
> Edge 的侧边栏与 Chrome 略有差异（拿不到"当前活动标签页"），v1.8.4 起已做多级兜底（活跃标签页 → 最近聚焦窗口 → 按 URL 查找 B 站视频页 → 上次记住的标签页），并在内容脚本缺失时自动补注入。若仍识别不到，把 B 站视频页切到前台，点侧边栏右上角 🔄 重试即可；提示信息会明确告诉你是"没找到标签页"还是"读不到视频信息"。

---

## 手机访问

电脑启动服务后，手机与电脑连接同一 WiFi（或电脑热点），浏览器访问 `http://电脑IP:8000`。

Windows 下在终端执行 `ipconfig`，找到对应网卡的 IPv4 地址；若无法连接，检查电脑防火墙是否放行 8000 端口。

---

## 工作原理

### 整体架构

```
┌─────────────────────────────────────────────────────┐
│  Web 前端 (Vue 3 + Element Plus + Vite + Pinia)       │
│  播放器联动 · 笔记渲染 · 自测交互 · 复习与图谱         │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP / REST API
┌──────────────────────▼──────────────────────────────┐
│  后端 (FastAPI)                                       │
│                                                       │
│   视频解析        笔记生成         自测 / 复习 / 导出    │
│  (bilibili)     (note_gen)       (quiz/review/export) │
│   yt-dlp         map-reduce                           │
│       └───────────────┬───────────────────────────┘   │
│                       ▼                                │
│              LLM 统一封装层                             │
│              DeepSeek / Kimi / Qwen / OpenAI / Ollama   │
│                       │                                │
│                       ▼                                │
│              SQLite（笔记 / 字幕 / 错题 / 配置）         │
└───────────────────────────────────────────────────────┘
                       ▲
                       │ 消息通信
┌──────────────────────┴──────────────────────────────┐
│  浏览器扩展 (Chromium MV3)                            │
│  content script · background · side panel            │
│  获取视频信息 · 控制播放器 · 侧边栏浏览               │
└──────────────────────────────────────────────────────┘
```

### 笔记生成流程

```
视频 / 合集链接
      │
      ▼
yt-dlp 解析视频信息并提取字幕
      │
      ├─ 优先使用 B 站官方 CC 字幕
      └─ 无字幕时可选 faster-whisper 离线转写
      ▼
字幕按 6000 字符切分（map 阶段）
      ▼
每块独立调用大模型生成小节笔记（套用学科模板）
      ▼
全局汇总（reduce 阶段）：合并重复知识点、生成章节结构与思维导图
      ▼
写入 SQLite，由前端 / 扩展展示
```

字幕分块采用 map-reduce：完整字幕按 6000 字符切成多块，每块独立生成小节笔记，全部完成后再调用一次大模型做全局汇总。这样可以在模型上下文窗口有限的情况下处理长视频，分块大小可在 `backend/app/config.py` 的 `subtitle_chunk_chars` 调整。

---

## 目录结构

```
BiliLearn-AI/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口
│   │   ├── config.py            # 配置（分块大小、转写开关等）
│   │   ├── database.py          # SQLite 连接与迁移
│   │   ├── models.py            # 数据模型
│   │   ├── routers/             # API 路由
│   │   │   ├── notes.py         # 笔记 CRUD 与生成
│   │   │   ├── collections.py   # 合集批量任务
│   │   │   ├── roadmap.py       # 合集线路图
│   │   │   ├── local.py         # 本地视频：转写、流式播放、缓存清理
│   │   │   ├── favorites.py     # 收藏夹导入
│   │   │   ├── review_material.py
│   │   │   ├── quiz.py
│   │   │   ├── export.py
│   │   │   └── config.py        # 网页设置
│   │   └── services/
│   │       ├── bilibili.py      # 视频解析与字幕提取
│   │       ├── note_generator.py
│   │       ├── review_material.py
│   │       ├── quiz_generator.py
│   │       ├── prompts.py       # 学科 Prompt 模板
│   │       └── llm/             # 大模型封装（factory / openai_compat / ollama）
│   ├── data/                    # 旧版数据目录（v1.8 起自动迁移到 ~/BiliLearn-AI）
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── views/
│       ├── components/
│       └── utils/theme.js       # 配色主题
├── extension/                   # Chromium 扩展
│   ├── manifest.json
│   ├── background.js
│   ├── content/
│   ├── sidepanel/
│   └── icons/
├── launcher/                    # 图形启动器（main.py + 打包脚本）
├── start.bat / start.sh         # 一键启动脚本
└── README.md
```

---

## 模型支持

| 供应商 | Key 申请 | 默认模型 | 说明 |
| --- | --- | --- | --- |
| DeepSeek | platform.deepseek.com | deepseek-chat | 综合成本低，推荐 |
| Kimi | platform.moonshot.cn | kimi-k2.6 | 上下文窗口大，适合长视频 |
| 通义千问 | 阿里云百炼 | qwen-plus | 视觉用 qwen-vl-max |
| OpenAI | platform.openai.com | gpt-4o-mini | 视觉用 gpt-4o，模型质量稳定 |
| Ollama | 本地运行，无需 Key | qwen2.5:7b | 完全离线 |

接口地址与模型名均可在设置中覆盖，因此也兼容任何 OpenAI 协议格式的第三方中转服务。

---

## 常见问题

**浏览器没有自动打开？**
手动访问 http://localhost:8000。

**提示「未检测到官方字幕」？**
两种可能：

1. 该视频确实没有 CC 字幕 → 在设置中开启离线语音转写（faster-whisper）；
2. 该视频的字幕只有**登录后**才可见 → 在「设置 → B站 Cookie」里粘贴你登录后的 Cookie。

**B站 Cookie 怎么填才有用？**
必须包含 `SESSDATA`（B站的登录凭证）。取法：登录 bilibili.com → F12 → **应用(Application) → Cookie → https://www.bilibili.com** → 整段复制。填完点「验证登录状态」，显示「已登录：你的昵称」才算生效；如果提示「没有 SESSDATA」，说明你复制的是游客 Cookie，等于没配。Cookie 只保存在本地，只用于拉取字幕与受限视频。

**长视频笔记不完整？**
可调小 `backend/app/config.py` 中的 `subtitle_chunk_chars`，或换用更大上下文窗口的模型。

**本地视频生成失败？**
本地视频靠 faster-whisper 离线转写，请确认视频有音轨（纯画面无声的视频无法转写）。若提示「文件已被移动」，重新选择一次文件即可。

**第一次转写卡在「正在下载语音识别模型」，过一会儿报连接超时（WinError 10060）？**
语音识别模型托管在 `huggingface.co`，国内网络直连经常连不上，表现就是 **TCP 连接超时**（报错里会带 `An error happened while trying to locate the files on the Hub`）。任选一种方式解决：

1. 网页「**设置 → 模型下载源**」选 **国内镜像 hf-mirror.com**（推荐，改完下次转写立即生效）；
2. 或设置环境变量后**重启程序**：
   - Windows（PowerShell）：`[Environment]::SetEnvironmentVariable('HF_ENDPOINT','https://hf-mirror.com','User')`
   - macOS / Linux：`export HF_ENDPOINT=https://hf-mirror.com`
   - `start.bat` / `start.sh` / 图形启动器**已经默认帮你设好镜像**，只有手动跑 `uvicorn` 的才需要自己设；
3. 或给本机挂一个可用的代理。

> 临时办法：改用**有官方字幕**的视频——有字幕就不会走本地转写，也就不需要下模型。
> 想确认是哪个域名不通，可以对比 `Test-NetConnection huggingface.co -Port 443` 与 `Test-NetConnection hf-mirror.com -Port 443`。

**模型下载到哪了？想重下怎么办？**
默认在 `~/.cache/huggingface/hub`（Windows 为 `C:\Users\你的用户名\.cache\huggingface\hub`），`base` 约 150MB。删掉 `models--Systran--faster-whisper-*` 目录即可重新下载。

**解析视频报 `HTTP Error 412: Precondition Failed`？**
这不是本项目的问题，是 **B站的风控**（同一链接换网络/IP 就好了，很典型）。常见触发原因是出口 IP 被标记（代理/VPN/机房或共享 NAT）或请求过于频繁。可尝试：

- 换一个网络（手机热点通常没问题）；
- 关掉代理/VPN 后重试，或换一个干净的出口节点；
- 在「设置 → B站 Cookie」里填一份**含 SESSDATA** 的登录 Cookie（登录态能显著降低被风控的概率，这也是该设置的主要用途之一），并点「验证登录状态」确认；
- 升到最新版 yt-dlp：`.venv/bin/pip install -U yt-dlp`（Windows：`.venv\Scripts\pip install -U yt-dlp`）。

**端口 8000 被占用？**
关闭占用该端口的旧实例，或在启动器设置中改用其他端口。

**扩展提示「无法获取视频信息」？**
刷新 B 站页面、等待完全加载后再打开扩展；Edge 用户检查站点访问权限是否已开启。

**Edge 侧边栏显示「当前视频暂无笔记」，但网页版里明明有这篇笔记？**
这是 v1.8.3 及更早版本的问题：Edge 侧边栏下拿不到"当前活动标签页"，插件就把"没识别到视频"错报成了"没有笔记"（生成笔记、截图也一并失效）。
升级到 **v1.8.4** 后：

1. 打开 `edge://extensions/`，在插件卡片上点一次 **🔄 重新加载**（插件版本升到 2.2.0，必须重载才会生效）；
2. 回到 B 站视频页，把该页切到前台，再点侧边栏右上角 **🔄** 刷新。
   若提示"未检测到 B 站视频标签页"，说明当前确实没有打开的 B 站视频页；若提示"已找到视频页，但读不到视频信息"，说明是内容脚本没注入——v1.8.4 会自动补注入一次，仍失败就刷新 B 站页面。

**数据保存在哪里？**
默认在用户主目录下的 `BiliLearn-AI` 文件夹（Windows 即 `C:\Users\你的用户名\BiliLearn-AI`），与程序目录分离——**升级或重新下载新版本都不会丢笔记**。里面包含：

| 内容 | 路径 |
| --- | --- |
| 数据库（笔记 / 错题 / 复习计划 / 配置） | `BiliLearn-AI/bililearn.db` |
| 每篇笔记的 Markdown | `BiliLearn-AI/notes/` |
| 关键帧与公式截图 | `BiliLearn-AI/notes/<笔记id>_keyframes`、`_formulas` |

在网页「设置 → 笔记数据与学习存档」里可以直接看到路径、打开目录、导出/导入存档；也可以用环境变量 `BILI_DATA_DIR` 指定到别处（如 NAS 或移动硬盘）。

**换电脑 / 重装后怎么把笔记搬过来？**
在旧机器「设置 → 导出学习存档」得到一个 zip，在新机器把它（或任意一个 `bililearn.db`）拖到「导入 / 合并存档」区域即可：同一个视频（同 BV + 同分 P）会自动跳过，只补充新内容，不会覆盖你本机的密钥与设置。

> 从 v1.7 及更早版本升级时，程序首次启动会自动把原来的 `backend/data` 搬到新目录，并在旧目录留下一个说明文件。

---

## 合规声明

本项目仅供个人学习研究使用，不缓存、不传播完整视频，仅处理字幕文本与生成的笔记内容。请尊重 UP 主与平台版权，勿用于商业用途。

## License

MIT
