"""为已有笔记重新生成箭头式脑图（真实 LLM 调用）。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.database import SessionLocal
from backend.app.models import Note
from backend.app.routers.notes import _save_markdown_file
from backend.app.services import export as export_service
from backend.app.services.llm import build_llm
from backend.app.services.prompts import SUBJECTS, mindmap_prompt
from backend.app.services.settings_store import resolve_llm_config

db = SessionLocal()
note = db.query(Note).filter(Note.id == 1).first()
if not note or not note.note_json:
    print("NO_NOTE")
    sys.exit(1)
note_json = json.loads(note.note_json)
cfg = resolve_llm_config(db)
llm = build_llm(cfg["provider"], cfg["api_key"], cfg["model"], cfg["base_url"])
data = llm.chat_json(mindmap_prompt(json.dumps(note_json, ensure_ascii=False)[:8000]))
mindmap = data.get("mindmap") if isinstance(data, dict) else None
if isinstance(mindmap, list):
    mindmap = "\n".join(str(x) for x in mindmap)
mindmap = str(mindmap or "").strip()
if not mindmap:
    print("EMPTY_MINDMAP")
    sys.exit(1)
note_json["mindmap"] = mindmap
words = json.loads(note.words) if note.words else None
markdown = export_service.render_note_markdown(note_json, note.subject, words, meta={
    "bvid": note.bvid, "page": note.page,
    "subject_name": SUBJECTS.get(note.subject, note.subject),
    "created_at": note.created_at.isoformat() if note.created_at else "",
})
note.note_json = json.dumps(note_json, ensure_ascii=False)
note.mindmap = mindmap
note.markdown = markdown
db.commit()
_save_markdown_file(note.id, note.title, markdown)
print("MINDMAP_LINES=", len(mindmap.splitlines()))
print("HEAD=", mindmap.splitlines()[0])
print("HAS_ARROWS=", "-->" in mindmap)
print("NODE_COUNT=", mindmap.count("-->") + 1)
print("SAMPLE=", " | ".join(mindmap.splitlines()[1:4]))
db.close()
