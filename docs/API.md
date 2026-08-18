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
删除笔记。

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

### GET /config 响应（节选）
```json
{
  "provider": "deepseek",
  "api_keys": { "deepseek_api_key": "sk-3a****dbbe" },
  "models": { "deepseek": "deepseek-chat", "kimi": "moonshot-v1-32k" },
  "ollama_base_url": "http://localhost:11434",
  "enable_whisper": true,
  "whisper_model": "base",
  "whisper_language": ""
}
```

### POST /config/test
测试模型连接，返回模型回复前 50 字。

## 导出

- `GET /export/{note_id}/markdown` — Markdown 文件
- `GET /export/{note_id}/pdf` — PDF 文件（中文字体内置）
- `GET /export/{note_id}/anki` — Anki .apkg 生词卡（英语专项）
- `GET /export/{note_id}/anki.csv` — Anki 导入用 CSV（带 BOM）

## 通用

- `GET /api/health` — 健康检查
