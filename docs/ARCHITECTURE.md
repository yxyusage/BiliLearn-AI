# BiliLearn-AI 架构与规划

## 1. 总体项目规划图

```mermaid
graph TD
  subgraph 前端 Vue3 + Element Plus
    A1[首页 · 视频解析/学科选择]
    A2[笔记详情页]
    A3[历史笔记]
    A4[模型配置 · 四供应商 + Key 网址入口 + 转写参数]
    A2 --> A2a[双布局：左右分栏可拖动 / 视频置顶吸顶]
    A2 --> A2b[结构化笔记 + 各章节内嵌自测]
    A2 --> A2c[箭头脑图 · 节点点击跳转视频]
    A2 --> A2d[AI 答疑抽屉]
    A2 --> A2e[错题本 + 薄弱复盘 + 艾宾浩斯计划]
  end

  subgraph 后端 FastAPI + SQLite
    B1[bilibili.py 视频解析/官方字幕]
    B2[llm/ 统一封装 DeepSeek·Kimi·千问·Ollama]
    B3[note_generator 分段+汇总 map-reduce]
    B4[quiz 生成 + 逐题 AI 批改]
    B5[review 薄弱复盘 + 复习计划]
    B6[export Markdown·PDF·Anki·CSV]
    B7[(SQLite + data/notes/*.md 自动落盘)]
  end

  B站 --> B1
  B1 -->|无字幕| W[faster-whisper 本地转写]
  W --> B3
  B1 --> B3
  B2 --> B3
  B2 --> B4
  B2 --> B5
  B2 --> A2d
  B3 --> B7
  B4 --> B7
  B5 --> B7
  B6 --> B7
  A1 --> B1
  A2 --> B3
  A2 --> B4
  A2 --> B5
  A2 --> B6
```

## 2. 阶段路线图

```mermaid
graph LR
  P1["阶段1 MVP<br/>解析/字幕/笔记/存储"] --> P2["阶段2 核心<br/>学科模板/脑图/自测/导出"]
  P2 --> P3["阶段3 进阶<br/>复盘/复习计划/四供应商"]
  P3 --> P35["阶段3.5 交互升级<br/>双布局/答疑/逐题批改/美化导出"]
  P35 --> P4["阶段4 开源发布"]
  P5["下阶段：合集批量队列 + 全课程知识图谱 + 考点地图"] -.-> P4
  P6["下阶段：多模态板书/公式 OCR 识别"] -.-> P4
```

## 3. 核心运行流程图（视频 → 学习闭环）

```mermaid
sequenceDiagram
  participant U as 用户
  participant F as 前端
  participant B as 后端
  participant Y as yt-dlp/B站
  participant W as faster-whisper
  participant L as 大模型

  U->>F: 粘贴链接 + 选学科
  F->>B: POST /video/parse
  B->>Y: 解析视频 + 抓官方字幕
  Y-->>B: 字幕（无则空）
  B-->>F: 视频信息 + 字幕预览

  U->>F: 点击生成笔记
  F->>B: POST /notes/generate（异步）
  B->>B: 读取字幕缓存
  alt 无官方字幕且已开启转写
    B->>W: 下载音频 + 本地转写（结果入缓存）
    W-->>B: 转写字幕
  end
  B->>L: map：分段生成小节笔记
  L-->>B: 各段小节
  B->>L: reduce：全局汇总 + 箭头脑图（节点带时间戳）
  L-->>B: 结构化笔记 JSON
  B->>B: 落库 + 自动保存 .md 文件
  F->>B: 轮询状态
  B-->>F: done

  U->>F: 看笔记（分栏/置顶布局，视频吸顶）
  U->>F: 点时间戳 / 点脑图节点 → 播放器跳转
  U->>F: AI 答疑（基于笔记上下文）
  F->>B: POST /notes/{id}/chat
  B->>L: 上下文 + 历史对话
  L-->>F: 解答

  U->>F: 做各章节自测题
  F->>B: POST /quiz/judge（逐题）
  B->>L: 判对错 + 讲解
  L-->>F: 批改反馈（错题入错题本）
  U->>F: 生成复盘
  F->>B: POST /review/analyze
  B->>L: 错题 + 笔记 → 薄弱点 + 复习片段
  L-->>F: 复盘 + 艾宾浩斯计划
  U->>F: 导出 Markdown / PDF / Anki / CSV
```

## 4. 进一步优化方向

### 已交付（v1.1）
- ✅ 合集批量异步队列（后台逐集生成、进度实时展示、已完成集复用缓存）
- ✅ 全课程知识图谱（箭头 graph TD、节点 p页码_HHMMSS 点击跨集跳转）+ 考点地图（必考/掌握/了解分级）
- ✅ 多模态公式/板书识别（PyAV 关键帧提取无需 ffmpeg + qwen-vl-plus/kimi-vision 转 LaTeX）
- ✅ 深浅主题一键切换、AI 答疑图示化回答、逐题 AI 批改、分栏独立滚动、分隔条拖动、代理不可用自动直连
- ✅ GitHub Actions CI、CHANGELOG、Docker 健康检查

### 功能层
| 优先级 | 优化项 | 说明 |
| --- | --- | --- |
| 中 | 播放进度联动 | 监听播放器播放进度，自动高亮正在讲解的知识点（postMessage + 时间区间匹配） |
| 中 | 笔记 LaTeX 实时渲染 | 前端引入 KaTeX，把 $...$ 与 $$...$$ 渲染为公式（数理专项体验关键） |
| 中 | 代码高亮 | cs 专项代码块前端语法高亮 + 一键复制 |
| 中 | 双语对照 | 英语专项提供「原文 + 逐句翻译」并行对照视图 |
| 低 | 任务管理面板 | 失败重试、任务队列可视化、API 成本统计 |
| 低 | 字幕后处理 | 转写字幕时间戳纠偏、重复句合并、VAD 静音过滤加速转写 |
| 低 | 合集精简模式 | 仅生成总框架 + 重点章节，降低大批量成本 |

### 工程层
| 优化项 | 说明 |
| --- | --- |
| 前端体积优化 | mermaid 等大依赖按需加载 / manualChunks 拆分（当前单 chunk 1MB+） |
| GPU 转写支持 | whisper device 配置化（当前固定 CPU，兼容性优先） |
| 移动端适配 | 分栏布局在窄屏自动降级为视频置顶模式 |
| CI + 打包 | GitHub Actions：单元测试 + 构建镜像；Release 发布 |
| 鉴权（可选） | 本地单用户定位下暂不需要，如需公网部署可加简单访问口令 |

## 5. 数据与合规边界

- 所有数据仅存本地：SQLite（backend/data/bililearn.db）+ Markdown（backend/data/notes/）
- 模型密钥仅存本地数据库，API 调用只发送字幕文本与笔记内容
- 不缓存、不传播视频本体，仅处理字幕与学习产物，仅限个人学习使用
