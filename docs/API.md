# BiliLearn-AI 接口文档

Base URL：`http://localhost:8000/api`

## 视频解析

### POST /video/parse
解析B站单视频/合集链接，提取字幕（自动缓存）。

```json
// 请求
{ "url": "https://www.bilibili.com/video/BV1GJ411x7h7" }

// 响应
{
  "bvid": "BV1GJ411x7h7",
  "title": "视频标题",
  "uploader": "UP主",
  "pages": [{ "page": 1, "title": "P1 标题" }],
  "subtitle_available": true,
  "subtitle_source": "官方字幕(CC)",
  "subtitle_count": 520,
  "subtitles": [{ "start": 1.5, "end": 4.2, "text": "字幕内容" }],
  "whisper_enabled": false,
  "hint": ""
}
```

## 笔记

### POST /notes/generate
异步生成笔记，立即返回笔记 id（status=processing），前端轮询状态。

```json
{
  "bvid": "BV1GJ411x7h7",
  "page": 1,
  "subject": "general",
  "title": "可选标题"
}
```

### GET /notes?limit=50
历史笔记列表。

### GET /notes/{id}
笔记详情（含 note/markdown/mindmap/quizzes/words/review）。

### GET /notes/{id}/status
生成状态：pending / processing / done / failed（附 error）。

### DELETE /notes/{id}
删除笔记（本地视频笔记只删笔记与缓存的关键帧，不会删除你的原视频文件）。

### GET /notes/{id} 响应补充
`source` 为 `bilibili` 或 `local`；本地视频笔记额外返回 `local_path`/`local_name`/`local_available`。

## 本地视频

### POST /local/pick
弹出系统文件选择框，返回选中的绝对路径（用户取消时 `cancelled=true`）。仅在运行后端的同一台机器上有效。

### POST /local/probe
```json
{ "path": "D:\\courses\\os.mp4" }
// 响应
{ "ok": true, "path": "D:\\courses\\os.mp4", "name": "os.mp4", "size": 734003200, "ext": ".mp4", "duration": 3720.5 }
```

### POST /local/upload
浏览器拖拽进来的文件（multipart `file`）复制到 `backend/data/cache/local_videos/`，返回可直接用于 `/local/generate` 的路径。同机上传，速度接近磁盘拷贝；同名同大小文件自动复用。

```json
{ "ok": true, "reused": false, "path": "...", "name": "...", "size": 734003200 }
```

### POST /local/generate
对本地视频/音频生成笔记（faster-whisper 离线转写 + 大模型整理），异步执行，返回笔记 id。

```json
{ "path": "D:\\courses\\os.mp4", "subject": "cs", "title": "可选标题" }
// 响应
{ "id": 12, "status": "processing", "reused": false, "source": "local" }
```

### GET /local/stream/{note_id}
流式返回该笔记对应的本地视频（支持 HTTP Range，播放器可拖进度、按时间戳跳转）。

### GET /local/uploads
拖拽上传缓存占用：`{ "count": 3, "bytes": 2147483648, "dir": "..." }`。

### POST /local/uploads/cleanup
删除不再被任何笔记引用的缓存副本，返回 `{ "removed": 2, "freed": 123456789 }`。

## 自测

### POST /quiz/generate
基于笔记生成三级阶梯自测题。

```json
{ "note_id": 1 }
// 响应
{ "questions": [
  { "difficulty": "basic", "type": "single", "stem": "...",
    "options": ["A. ...", "B. ..."], "answer": "B. ...",
    "explanation": "...", "knowledge_point": "...", "time_stamp": "00:12:34" }
]}
```

### POST /quiz/submit
提交答题结果，错题自动记入错题本。

```json
{
  "note_id": 1,
  "answers": [
    { "question": "...", "user_answer": "...", "correct_answer": "...",
      "explanation": "...", "difficulty": "basic", "time_stamp": "00:12:34",
      "correct": false }
  ]
}
```

### GET /quiz/{note_id}/wrong
错题列表。

## 复盘

### POST /review/analyze
基于错题生成薄弱点分析与艾宾浩斯复习计划。

```json
{ "note_id": 1 }
// 响应
{
  "weak_points": [
    { "point": "薄弱知识点", "reason": "...", "priority": "high",
      "replay_timestamps": ["00:12:34"], "suggestion": "..." }
  ],
  "summary": "...",
  "plan": [{ "id": 1, "content": "复习章节：...", "due_date": "2025-01-02", "done": false }]
}
```

### GET /review/plan?due_only=true
复习计划列表。

### POST /review/plan/{plan_id}/toggle
勾选/取消完成。

## 配置

### GET /config
当前配置（API Key 已脱敏）+ 供应商列表。

### POST /config/set
保存配置项（provider / *_api_key / *_model / ollama_base_url / enable_whisper / whisper_model / whisper_language）。
供应商有 deepseek / kimi / qwen / openai / ollama，各自对应 `<供应商>_api_key` 与 `<供应商>_model`。

### GET /config 响应（节选）
```json
{
  "provider": "deepseek",
  "api_keys": { "deepseek_api_key": "sk-3a****dbbe" },
  "models": { "deepseek": "deepseek-chat", "kimi": "kimi-k2.6", "openai": "gpt-4o-mini" },
  "ollama_base_url": "http://localhost:11434",
  "enable_whisper": true,
  "whisper_model": "base",
  "whisper_language": "",
  "hf_endpoint": "mirror",
  "hf_endpoint_env": ""
}
```

`hf_endpoint` 控制语音识别模型的下载源：`""`（自动：先官方、失败自动切国内镜像）、`"mirror"`、`"official"`，或自定义地址。
未设置时由环境变量 `HF_ENDPOINT` 决定（`start.ps1` / `start.sh` / 图形启动器默认写入 `https://hf-mirror.com`）。

### POST /config/test
测试模型连接，返回模型回复前 50 字。

### POST /config/verify-cookie
校验 B站 Cookie 的登录状态。可传 `{"cookie": "..."}` 先测未保存的 Cookie；不传 body 则用已保存的那份。

```json
{
  "has_cookie": true,
  "has_sessdata": true,
  "logged_in": true,
  "uname": "你的昵称",
  "message": "已登录：你的昵称，可用登录态字幕与受限视频"
}
```

> 只有含 `SESSDATA` 的 Cookie 才是登录态；缺 SESSDATA 时 `logged_in=false`，且消息里会说明怎么重新复制。
> 后端会把它转成 yt-dlp 原生的 cookiefile（`<数据目录>/cache/bili_cookies.txt`）用于字幕、音频与视频流请求；清空该设置时会同步删除这个文件。

## 导出

- `GET /export/{note_id}/markdown` — Markdown 文件
- `GET /export/{note_id}/pdf` — PDF 文件（中文字体内置）
- `GET /export/{note_id}/anki` — Anki .apkg 生词卡（英语专项）
- `GET /export/{note_id}/anki.csv` — Anki 导入用 CSV（带 BOM）

## 数据与存档

数据目录默认是 `~/BiliLearn-AI`（可用环境变量 `BILI_DATA_DIR` 覆盖），与程序目录分离，升级不丢数据。

### GET /data/info
```json
{
  "data_dir": "C:\\Users\\me\\BiliLearn-AI",
  "db_path": "C:\\Users\\me\\BiliLearn-AI\\bililearn.db",
  "db_size": 15306752,
  "notes_dir": "C:\\Users\\me\\BiliLearn-AI\\notes",
  "notes_bytes": 12631195,
  "notes_files": 282,
  "note_count": 219,
  "legacy_dir": "E:\\app\\backend\\data",
  "legacy_present": false,
  "env_override": false
}
```

### POST /data/open
在系统文件管理器中打开数据目录。

### GET /data/export
下载学习存档 zip：数据库一致性快照 + `notes/`（Markdown 与关键帧截图）+ `manifest.json`。

### POST /data/import
上传 `bililearn.db` / `.sqlite` / 本工具导出的 `.zip`（multipart 字段名 `file`），合并进本地数据库。

- 同一个 `bvid + page` 已存在则跳过，只补新内容；
- 一并导入错题、复习计划、没懂打点、合集任务、合集复习资料、线路图与字幕缓存；
- **不导入**设置表，因此不会覆盖本机的 API Key、模型与端口配置；
- 来源库里没跑完的笔记会以「失败」状态导入，避免一直显示生成中。

```json
{ "notes_added": 3, "notes_skipped": 216, "wrong_added": 5, "plans_added": 2,
  "confusions_added": 0, "collections_added": 1, "review_materials_added": 0,
  "roadmaps_added": 0, "subtitles_added": 12, "frames_copied": 6, "warnings": [] }
```

## 通用

- `GET /api/health` — 健康检查
