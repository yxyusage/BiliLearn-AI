"""V2 新功能实测：key_url / AI答疑 / 逐题批改 / 新版导出。"""
import httpx

BASE = "http://127.0.0.1:8000/api"
c = httpx.Client(base_url=BASE, timeout=300)

# 1) 配置含 key_url
cfg = c.get("/config").json()
urls = {p["id"]: p.get("key_url", "") for p in cfg["providers"]}
print("key_urls:", urls)

# 2) AI 答疑
r = c.post("/notes/1/chat", json={"message": "电子的轨道是什么？请用一句话解释", "history": []})
print("chat:", r.status_code, str(r.json().get("reply"))[:80])

# 3) 逐题批改
note = c.get("/notes/1").json()
qs = note["quizzes"]["questions"]
single_q = next(q for q in qs if q["type"] == "single" and q["options"])
short_q = next(q for q in qs if q["type"] != "single")

# 3a) 单选题答对
r1 = c.post("/quiz/judge", json={
    "note_id": 1, "stem": single_q["stem"], "qtype": "single",
    "options": single_q["options"], "answer": single_q["answer"],
    "user_answer": single_q["answer"], "explanation": single_q["explanation"],
    "knowledge_point": single_q["knowledge_point"], "time_stamp": single_q["time_stamp"],
})
j1 = r1.json()
print("judge-single-correct:", j1["correct"], "| feedback:", str(j1["feedback"])[:60])

# 3b) 单选题答错（选一个错误选项）
wrong_opt = next(o for o in single_q["options"] if o.strip() != single_q["answer"].strip())
r2 = c.post("/quiz/judge", json={
    "note_id": 1, "stem": single_q["stem"], "qtype": "single",
    "options": single_q["options"], "answer": single_q["answer"],
    "user_answer": wrong_opt, "explanation": single_q["explanation"],
    "knowledge_point": single_q["knowledge_point"], "time_stamp": single_q["time_stamp"],
})
j2 = r2.json()
print("judge-single-wrong:", j2["correct"], "| feedback:", str(j2["feedback"])[:60])

# 3c) 简答题 AI 批改（答错内容）
r3 = c.post("/quiz/judge", json={
    "note_id": 1, "stem": short_q["stem"], "qtype": short_q["type"],
    "options": short_q["options"], "answer": short_q["answer"],
    "user_answer": "随便写的错误答案：电子是固定不动的",
    "explanation": short_q["explanation"], "knowledge_point": short_q["knowledge_point"],
    "time_stamp": short_q["time_stamp"],
})
j3 = r3.json()
print("judge-short:", j3["correct"], "| feedback:", str(j3["feedback"])[:60])

# 4) 错题本含 AI 讲解
wrong = c.get("/quiz/1/wrong").json()
print("wrong-list:", len(wrong), "| has-feedback:", any(w.get("feedback") for w in wrong))

# 5) 新版导出
md = c.get("/export/1/markdown")
print("md:", md.status_code, len(md.content), "| hasTOC:", "目录" in md.text)
pdf = c.get("/export/1/pdf")
print("pdf:", pdf.status_code, len(pdf.content), "isPDF:", pdf.content[:4] == b"%PDF")
apkg = c.get("/export/1/anki")
print("apkg:", apkg.status_code, len(apkg.content), "isZip:", apkg.content[:2] == b"PK")

# 6) 笔记详情含 markdown_file
detail = c.get("/notes/1").json()
print("markdown_file:", detail.get("markdown_file"))
print("mindmap_head:", detail.get("mindmap", "").splitlines()[0] if detail.get("mindmap") else "")
print("V2_FEATURES_OK")
