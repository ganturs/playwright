"""
main.py — Google Sheets → Google Search + ChatGPT → MySQL

Ажиллуулах:
    python main.py

Flow:
    1. Google Sheets-с pending prompt унших
    2. Prompt бүрт Google хайлт хийж үр дүн цуглуулах
    3. Prompt-г ChatGPT-д илгээж хариулт авах
    4. Хоёр үр дүнг Google Sheets-д хадгалах (C=ChatGPT, D=Google)
"""

import time
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.config import DELAY_BETWEEN_PROMPTS
from src.sheets_reader import read_prompts, mark_row_done_with_google, mark_row_error
from src.chatgpt_bot import ChatGPTBot
from src.google_scraper import GoogleScraper


def main():
    print("=" * 60)
    print("ChatGPT + Google Crawler эхэлж байна")
    print("=" * 60)

    # 1. Google Sheets-с prompt унших
    print("\n[1/4] Google Sheets-с prompt уншиж байна...")
    try:
        prompts = read_prompts()
    except Exception as e:
        print(f"Google Sheets унших амжилтгүй: {e}")
        print("credentials.json болон SPREADSHEET_ID-г шалгана уу.")
        sys.exit(1)

    if not prompts:
        print("Pending prompt олдсонгүй. Дуусав.")
        return

    print(f"\nНийт {len(prompts)} prompt боловсруулна.\n")

    # 2. Google Scraper эхлүүлэх
    print("[2/4] Google Scraper нээж байна...")
    google = GoogleScraper(max_results=10)
    try:
        google.start()
    except Exception as e:
        print(f"Google Scraper нээхэд алдаа: {e}")
        sys.exit(1)

    # 3. ChatGPT браузер нээх
    print("\n[3/4] ChatGPT нээж байна...")
    bot = ChatGPTBot()
    try:
        bot.start()
    except Exception as e:
        print(f"Браузер нээхэд алдаа: {e}")
        google.close()
        sys.exit(1)

    # 4. Prompt бүрийг боловсруулах
    print(f"\n[4/4] {len(prompts)} prompt боловсруулж байна...\n")
    success_count = 0
    error_count = 0

    for i, item in enumerate(prompts, start=1):
        row = item["row"]
        prompt = item["prompt"]

        print(f"[{i}/{len(prompts)}] Row {row}: {prompt[:70]}...")

        try:
            # Google + ChatGPT зэрэг ажиллуулах
            print(f"  → Google + ChatGPT зэрэг ажиллаж байна...")
            with ThreadPoolExecutor(max_workers=2) as executor:
                google_future = executor.submit(google.search_as_text, prompt)
                chatgpt_future = executor.submit(bot.ask, prompt)
                google_text = google_future.result()
                chatgpt_response = chatgpt_future.result()

            if not chatgpt_response:
                raise ValueError("ChatGPT-с хоосон хариу ирлээ")

            # Sheets-д хадгалах (C=ChatGPT, D=Google)
            mark_row_done_with_google(row, chatgpt_response, google_text)
            success_count += 1

            print(f"  [ok] ChatGPT: {chatgpt_response[:80]}...")
            print(f"  [ok] Google:  {google_text.splitlines()[0][:80]}..." if google_text else "  [ok] Google: үр дүн алга")

        except Exception as e:
            error_msg = str(e)
            print(f"  [error] {error_msg}")
            mark_row_error(row, error_msg)
            error_count += 1

        # Rate limit-с зайлсхийх хүлээлт
        if i < len(prompts):
            print(f"  {DELAY_BETWEEN_PROMPTS} секунд хүлээж байна...\n")
            time.sleep(DELAY_BETWEEN_PROMPTS)

    # Хаах
    google.close()
    bot.close()

    print("\n" + "=" * 60)
    print(f"Дууслаа! Амжилттай: {success_count} | Алдаа: {error_count}")
    print("=" * 60)


if __name__ == "__main__":
    main()
