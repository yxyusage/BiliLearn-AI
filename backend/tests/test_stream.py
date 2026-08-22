"""测试流式答疑接口（SSE）。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import httpx

chunks = []
with httpx.stream(
    "POST",
    "http://127.0.0.1:8000/api/notes/1/chat/stream",
    json={"message": "用一句话总结电子轨道", "history": []},
    timeout=120,
) as resp:
    print("STATUS:", resp.status_code)
    for line in resp.iter_lines():
        if not line or not line.startswith("data:"):
            continue
        payload = json.loads(line[5:].strip())
        if payload.get("delta"):
            chunks.append(payload["delta"])
        if payload.get("done"):
            break
print("CHUNK_COUNT:", len(chunks))
print("FULL:", "".join(chunks)[:300])
print("STREAM_OK")
