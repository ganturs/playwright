"""
extend_sessions.py — Auth state cookies-ийн expires-г 1 жилээр нэмнэ.

Ажиллуулах:
    python extend_sessions.py
"""
import json
import os
import time
from src.config import CHROME_PROFILE_DIR, WORKER_COUNT

ONE_YEAR = 365 * 24 * 60 * 60  # секундэд
now = int(time.time())

for i in range(WORKER_COUNT):
    path = os.path.join(CHROME_PROFILE_DIR, f"auth_state_worker{i}.json")
    if not os.path.exists(path):
        print(f"[worker-{i}] Файл олдсонгүй — алгасав.")
        continue

    with open(path, "r", encoding="utf-8") as f:
        state = json.load(f)

    updated = 0
    for cookie in state.get("cookies", []):
        if isinstance(cookie.get("expires"), (int, float)) and cookie["expires"] > 0:
            cookie["expires"] = int(cookie["expires"]) + ONE_YEAR
            updated += 1

    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    print(f"[worker-{i}] {updated} cookie expires нэмэгдлээ ✓")

print("\nДууслаа.")
