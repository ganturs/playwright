"""
setup.py — Worker-д ChatGPT нэвтрэх session үүсгэнэ.

Ажиллуулах:
    python setup.py --worker 5
    python setup.py --worker 5 6 7 8 9   # олон worker зэрэг
    python setup.py --all                 # бүх worker (WORKER_COUNT)
"""
import asyncio
import argparse
import os
import json
from camoufox.async_api import AsyncCamoufox
from src.config import CHROME_PROFILE_DIR, CHATGPT_URL, WORKER_COUNT


async def setup_worker(worker_id: int):
    tag = f"[setup-{worker_id}]"
    auth_file = os.path.join(CHROME_PROFILE_DIR, f"auth_state_worker{worker_id}.json")
    os.makedirs(CHROME_PROFILE_DIR, exist_ok=True)

    print(f"{tag} Браузер нээж байна...")
    browser = AsyncCamoufox(headless=False, geoip=False, os="windows")
    context = await browser.__aenter__()
    page = await context.new_page()

    await page.goto(CHATGPT_URL, wait_until="domcontentloaded", timeout=60000)
    print(f"{tag} ChatGPT нээгдлээ. Нэвтэрнэ үү...")
    print(f"{tag} Нэвтэрсний дараа Enter дарна уу...")
    input()

    # Session хадгалах
    state = await page.context.storage_state()
    with open(auth_file, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    print(f"{tag} Session хадгалагдлаа → {auth_file}")

    await browser.__aexit__(None, None, None)


async def main(worker_ids: list[int]):
    for wid in worker_ids:
        await setup_worker(wid)
    print("\nБүх worker бэлэн болов ✓")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", type=int, nargs="+", help="Worker ID-үүд")
    parser.add_argument("--all", action="store_true", help="Бүх worker")
    args = parser.parse_args()

    if args.all:
        ids = list(range(WORKER_COUNT))
    elif args.worker:
        ids = args.worker
    else:
        parser.print_help()
        exit(1)

    print(f"Worker-үүд: {ids}")
    asyncio.run(main(ids))
