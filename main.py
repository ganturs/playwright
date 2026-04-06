"""
main.py — Google Sheets → [Worker Pool] → Google Search + ChatGPT → Sheets

Ажиллуулах:
    python main.py

Worker тоо тохируулах (.env):
    WORKER_COUNT=5

Proxy тохируулах (proxies.txt):
    http://user1:pass1@host:port
    http://user2:pass2@host:port
    ...
"""

import sys
import queue
import threading
from src.config import WORKER_COUNT, GOOGLE_CONCURRENT, CHATGPT_CONCURRENT, load_proxies, DELAY_BETWEEN_PROMPTS
from src.sheets_reader import read_prompts
from src.db import save_result, save_error, test_connection
from src.worker import Worker


# ─────────────────────────────────────────────
#  Worker thread функц
# ─────────────────────────────────────────────

def run_worker(worker: Worker, task_queue: queue.Queue, lock: threading.Lock, counters: dict):
    """Worker thread: queue-с prompt авч боловсруулна"""
    try:
        worker.start()
    except Exception as e:
        print(f"[worker-{worker.worker_id}] Эхлүүлэхэд алдаа: {e}")
        return

    while True:
        try:
            item = task_queue.get(timeout=10)
        except queue.Empty:
            break

        row, prompt = item["row"], item["prompt"]
        wid = worker.worker_id

        try:
            print(f"  [worker-{wid}] Row {row}: {prompt[:60]}...")
            chatgpt_response, google_text = worker.process(prompt)

            if not chatgpt_response:
                raise ValueError("ChatGPT-с хоосон хариу ирлээ")

            save_result(prompt, chatgpt_response, google_text, row)
            with lock:
                counters["success"] += 1
                total = counters["success"] + counters["error"]
                print(f"  [worker-{wid}] ✓ Row {row} хадгалагдлаа. ({total}/{counters['total']})")

        except Exception as e:
            save_error(prompt, str(e), row)
            with lock:
                counters["error"] += 1
                print(f"  [worker-{wid}] ✗ Row {row} алдаа: {e}")

        finally:
            task_queue.task_done()

    worker.close()
    print(f"[worker-{worker.worker_id}] Дууслаа.")


# ─────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────

def main():
    print("=" * 60)
    print("ChatGPT + Google Crawler (Worker Pool)")
    print("=" * 60)

    # 0. DB холболт шалгах
    if not test_connection():
        sys.exit(1)

    # 1. Proxy унших + rotation тохируулах
    proxies = load_proxies()

    # Proxy rotation тохиргоо:
    #   10 proxy → 2 batch (5+5), 5 worker
    #   worker i → [proxies[i], proxies[i+5]] гэж 2 proxy авна
    #   5 хүсэлт тутам proxy солино
    ROTATE_EVERY = 5
    BATCH_SIZE = 5  # нэг batch дахь proxy тоо

    if len(proxies) >= BATCH_SIZE * 2:
        worker_count = BATCH_SIZE
        worker_proxy_lists = [
            [proxies[i], proxies[i + BATCH_SIZE]]
            for i in range(BATCH_SIZE)
        ]
        print(f"\n[Proxy Rotation] {len(proxies)} proxy → {BATCH_SIZE} worker × 2 batch")
        print(f"  {ROTATE_EVERY} хүсэлт тутам proxy солино.")
        for i, pl in enumerate(worker_proxy_lists):
            print(f"  Worker {i}: {pl[0].split('@')[-1]} → {pl[1].split('@')[-1]}")
    elif proxies:
        worker_count = WORKER_COUNT
        # Proxy байгаа ч 2 batch хүрэхгүй — worker тус бүрт 1 proxy
        worker_proxy_lists = [[proxies[i % len(proxies)]] for i in range(worker_count)]
        print(f"\n[Тохиргоо] Worker: {worker_count} | Proxy: {len(proxies)} (rotation байхгүй)")
        for i, p in enumerate(proxies):
            print(f"  Proxy {i+1}: {p.split('@')[-1]}")
    else:
        worker_count = WORKER_COUNT
        worker_proxy_lists = [[] for _ in range(worker_count)]
        print(f"\n[Тохиргоо] Worker: {worker_count} | Proxy байхгүй — proxy-гүй ажиллана.")

    # Semaphore — зэрэг хандалтыг хязгаарлана
    google_semaphore = threading.Semaphore(GOOGLE_CONCURRENT)
    chatgpt_semaphore = threading.Semaphore(CHATGPT_CONCURRENT)
    print(f"  Google зэрэг хандалт: {GOOGLE_CONCURRENT} | ChatGPT зэрэг хандалт: {CHATGPT_CONCURRENT}")

    # 2. Google Sheets-с prompt унших
    print("\n[1/3] Google Sheets-с prompt уншиж байна...")
    try:
        prompts = read_prompts()
    except Exception as e:
        print(f"Google Sheets унших амжилтгүй: {e}")
        sys.exit(1)

    if not prompts:
        print("Pending prompt олдсонгүй. Дуусав.")
        return

    print(f"Нийт {len(prompts)} prompt боловсруулна.")

    # 3. Worker-уудыг үүсгэх
    print(f"\n[2/3] {worker_count} worker үүсгэж байна...")
    workers = []
    for i in range(worker_count):
        workers.append(Worker(
            worker_id=i,
            proxy_list=worker_proxy_lists[i],
            google_semaphore=google_semaphore,
            chatgpt_semaphore=chatgpt_semaphore,
            rotate_every=ROTATE_EVERY,
        ))

    # 4. Queue + Thread ажиллуулах
    print(f"\n[3/3] Боловсруулж байна...\n")

    task_queue = queue.Queue()
    for item in prompts:
        task_queue.put(item)

    lock = threading.Lock()
    counters = {"success": 0, "error": 0, "total": len(prompts)}

    threads = []
    for worker in workers:
        t = threading.Thread(
            target=run_worker,
            args=(worker, task_queue, lock, counters),
            daemon=True,
        )
        threads.append(t)
        t.start()

    # Бүх thread дуусахыг хүлээх
    for t in threads:
        t.join()

    print("\n" + "=" * 60)
    print(f"Дууслаа! Амжилттай: {counters['success']} | Алдаа: {counters['error']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
