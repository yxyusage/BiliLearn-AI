"""独立转写验证：只处理单个分P。"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.services.whisper import transcribe

t0 = time.time()
subs = transcribe("BV1Gf4y1y7wc", 1, "base", "en")
elapsed = time.time() - t0
print("SEGMENTS=", len(subs), "ELAPSED=", round(elapsed, 1))
for s in subs[:6]:
    print(" ", round(s["start"], 1), "-", round(s["end"], 1), s["text"])
print("LAST:", subs[-1]["text"] if subs else "")
