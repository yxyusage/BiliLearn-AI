"""E2E：自测提交 -> 错题 -> 复盘 -> 导出（针对真实生成的笔记 id=1）。"""
import httpx

BASE = "http://127.0.0.1:8015/api"
c = httpx.Client(base_url=BASE, timeout=300)

# 1) 取笔记与自测题
note = c.get("/notes/1").json()
print("note status:", note["status"], "| subject:", note["subject"])
qs = note["quizzes"]["questions"]
print("quiz count:", len(qs), "| tiers:", sorted(set(q["difficulty"] for q in qs)))

# 2) 构造答案：单选全对，其余答错
answers = []
for q in qs:
    if q["type"] == "single" and q["options"]:
        ok = True
        user = q["answer"]
    else:
        ok = False
        user = "我的答案(测试)"
    answers.append({
        "question": q["stem"], "user_answer": user, "correct_answer": q["answer"],
        "explanation": q["explanation"], "difficulty": q["difficulty"],
        "time_stamp": q["time_stamp"], "correct": ok,
    })
r = c.post("/quiz/submit", json={"note_id": 1, "answers": answers})
print("submit:", r.status_code, r.json())

# 3) 复盘
r2 = c.post("/review/analyze", json={"note_id": 1})
print("review:", r2.status_code)
rev = r2.json()
print("weak_points:", len(rev.get("weak_points") or []), "| plan:", len(rev.get("plan") or []))
for w in (rev.get("weak_points") or [])[:2]:
    print("  -", w.get("point"), "| pri:", w.get("priority"), "| replay:", w.get("replay_timestamps"))
print("summary:", str(rev.get("summary"))[:80])

# 4) 导出
md = c.get("/export/1/markdown")
print("md:", md.status_code, len(md.content), md.headers.get("content-disposition", "")[:60])
pdf = c.get("/export/1/pdf")
print("pdf:", pdf.status_code, len(pdf.content), "isPDF:", pdf.content[:4] == b"%PDF")
apkg = c.get("/export/1/anki")
print("apkg:", apkg.status_code, len(apkg.content), "isZip:", apkg.content[:2] == b"PK")
csv_ = c.get("/export/1/anki.csv")
print("csv:", csv_.status_code, len(csv_.content), "hasBOM:", csv_.content.startswith(b"\xef\xbb\xbf"))
print("E2E_CHAIN_OK")
