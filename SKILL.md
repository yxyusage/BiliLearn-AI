# BiliLearn-AI Skill

> 本文件让 Claude Code / Cursor / Codex / Hermes 等任何 AI 编程助手可以**一键部署并操作本项目**。
> 直接把下面的「一键部署」提示词复制给你的 AI 即可。


## 常用操作指引

### 启动 / 停止
- 启动：执行一键部署第 5 步命令，或直接运行 start.bat（Windows）/ start.sh（macOS/Linux）
- 停止：Ctrl+C 或关闭运行窗口

### 配置模型
- API 在网页「模型配置」页填写（密钥仅存本地 SQLite：backend/data/bililearn.db）
- 支持的供应商：deepseek / kimi / qwen / ollama（见 backend/app/services/llm/factory.py）

### 核心 API（前缀 /api）
| 接口 | 说明 |
| --- | --- |
| POST /video/parse | 解析 B站链接，返回视频信息+字幕 |
| POST /notes/generate | 异步生成笔记 |
| GET /notes/{id}/status | 生成状态轮询 |
| GET /notes/{id} | 笔记详情 |
| POST /notes/{id}/chat/stream | AI 答疑流式（SSE） |
| POST /notes/{id}/keyframes | 提取章节关键帧截图 |
| POST /notes/{id}/formulas | 视觉模型识别板书公式 |
| POST /quiz/generate | 生成三级自测题 |
| POST /quiz/judge | 逐题 AI 批改 |
| POST /review/analyze | 薄弱复盘 + 复习计划 |
| POST /collections/start | 合集批量生成 |
| POST /collections/{id}/map | 全课程知识图谱 |
| GET /export/{id}/markdown | 导出 Markdown |
| GET /export/{id}/pdf | 导出 PDF |
| GET /export/{id}/docx | 导出 Word |
| GET /export/{id}/xmind | 导出 XMind |
| GET /export/{id}/anki | 导出 Anki 卡片 |

### 学科类型
general / english / math / cs / liberal（对应 backend/app/services/prompts.py 的模板）

## 常见问题排查
| 现象 | 处理 |
| --- | --- |
| 模型调用报 WinError 10061 | 系统代理不可用：清掉 HTTP_PROXY/HTTPS_PROXY 环境变量（代码已自动回退直连） |
| 端口 8000 被占用 | 找到并结束旧的 python 进程 |
| whisper 模型下载慢 | 设置 HF_ENDPOINT=https://hf-mirror.com |
| 数据库结构变更 | 启动时自动迁移补列，无需手动处理 |

## 安全注意事项
1. **绝不提交 backend/data/ 目录**（含用户 API Key 与笔记数据库）
2. 密钥只写入 SQLite settings 表，日志中不打印完整密钥
3. 项目仅用于个人学习，不传播视频本体
4. 视觉模型需供应商支持（qwen-vl-plus / moonshot-vision）
