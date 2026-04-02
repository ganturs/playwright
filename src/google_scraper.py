"""
google_scraper.py — Camoufox ашиглан Google хайлт хийж үр дүн цуглуулна.

Хэрэглээ:
    scraper = GoogleScraper(max_results=5)
    scraper.start()
    results = scraper.search("Python гэж юу вэ?")
    scraper.close()

results жишээ:
    [
        {"rank": 1, "title": "...", "url": "https://...", "snippet": "..."},
        ...
    ]
"""

import asyncio
import random
from camoufox.async_api import AsyncCamoufox
from playwright.async_api import Page


# ─────────────────────────────────────────────
#  Тохиргоо
# ─────────────────────────────────────────────

GOOGLE_URL = "https://www.google.com"
DEFAULT_MAX_RESULTS = 10

SELECTORS = {
    "search_input": [
        "textarea[name='q']",
        "input[name='q']",
    ],
    "result_item": [
        "div.g",
        "div[data-sokoban-container]",
    ],
    "title": "h3",
    "link": "a[href]",
    "snippet": [
        "div[style*='-webkit-line-clamp']",
        "div.VwiC3b",
        "span.aCOpRe",
        "div[data-sncf='1']",
    ],
    "accept_cookies": [
        "button:has-text('Accept all')",
        "button:has-text('I agree')",
        "button:has-text('Agree')",
        "button:has-text('すべて同意')",
    ],
    "captcha": [
        "form#captcha-form",
        "div#recaptcha",
    ],
}


# ─────────────────────────────────────────────
#  Туслах функцүүд
# ─────────────────────────────────────────────

async def _dismiss_cookies(page: Page):
    """Cookie зөвшөөрлийн цонхыг хаана"""
    for sel in SELECTORS["accept_cookies"]:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=2000):
                await btn.click()
                await asyncio.sleep(0.5)
                return
        except Exception:
            continue


async def _check_captcha(page: Page) -> bool:
    """CAPTCHA гарсан эсэхийг шалгана"""
    for sel in SELECTORS["captcha"]:
        try:
            el = page.locator(sel).first
            if await el.is_visible(timeout=1000):
                return True
        except Exception:
            continue
    return False


async def _search_google(page: Page, query: str, max_results: int) -> list[dict]:
    """Google-д хайлт хийж үр дүн буцаана"""
    await page.goto(GOOGLE_URL, wait_until="domcontentloaded", timeout=30000)
    await _dismiss_cookies(page)

    # Хайлтын талбар олох
    input_box = None
    for sel in SELECTORS["search_input"]:
        try:
            input_box = await page.wait_for_selector(sel, timeout=5000)
            if input_box:
                break
        except Exception:
            continue

    if not input_box:
        raise RuntimeError("Google хайлтын талбар олдсонгүй.")

    # Query бичих (хүний хурдыг дуурайна)
    await input_box.click()
    await asyncio.sleep(random.uniform(0.3, 0.7))
    for char in query:
        await page.keyboard.type(char, delay=random.uniform(30, 90))

    await asyncio.sleep(random.uniform(0.4, 0.9))
    await page.keyboard.press("Enter")

    # CAPTCHA шалгах
    await asyncio.sleep(2)
    if await _check_captcha(page):
        raise RuntimeError("Google CAPTCHA гарлаа. Дараа дахин оролдоно уу.")

    # Үр дүн хүлээх
    result_found = False
    for sel in SELECTORS["result_item"]:
        try:
            await page.wait_for_selector(sel, timeout=12000)
            result_found = True
            break
        except Exception:
            continue

    if not result_found:
        raise RuntimeError("Google хайлтын үр дүн олдсонгүй.")

    await asyncio.sleep(random.uniform(0.5, 1.2))

    # Үр дүн цуглуулах
    results = []
    for result_sel in SELECTORS["result_item"]:
        items = await page.query_selector_all(result_sel)
        if not items:
            continue

        for item in items:
            try:
                title_el = await item.query_selector(SELECTORS["title"])
                link_el = await item.query_selector(SELECTORS["link"])

                if not title_el or not link_el:
                    continue

                title = (await title_el.inner_text()).strip()
                url = await link_el.get_attribute("href")

                if not title or not url or not url.startswith("http"):
                    continue

                # Snippet
                snippet = ""
                for snip_sel in SELECTORS["snippet"]:
                    snip_el = await item.query_selector(snip_sel)
                    if snip_el:
                        snippet = (await snip_el.inner_text()).strip()
                        if snippet:
                            break

                results.append({
                    "rank": len(results) + 1,
                    "title": title,
                    "url": url,
                    "snippet": snippet,
                })

                if len(results) >= max_results:
                    return results

            except Exception:
                continue

        if results:
            break

    return results


def format_results_for_sheet(results: list[dict]) -> str:
    """
    Хайлтын үр дүнг Google Sheets-д хадгалахад тохиромжтой текст болгоно.

    Жишээ:
        1. Python гэж юу вэ? | https://... | Python бол ...
        2. ...
    """
    if not results:
        return "Үр дүн олдсонгүй"
    lines = []
    for r in results:
        snippet = r["snippet"].replace("\n", " ")[:200]
        lines.append(f"{r['rank']}. {r['title']} | {r['url']} | {snippet}")
    return "\n".join(lines)


# ─────────────────────────────────────────────
#  GoogleScraper класс
# ─────────────────────────────────────────────

class GoogleScraper:
    """
    Camoufox ашиглан Google хайлт хийх scraper.

    Хэрэглээ:
        scraper = GoogleScraper(max_results=5)
        scraper.start()
        results = scraper.search("Python гэж юу вэ?")
        # [{"rank":1, "title":"...", "url":"...", "snippet":"..."}, ...]
        text = scraper.search_as_text("Python гэж юу вэ?")
        # "1. Python... | https://... | ..."
        scraper.close()
    """

    def __init__(self, max_results: int = DEFAULT_MAX_RESULTS):
        self.max_results = max_results
        self._browser = None
        self._context = None
        self._page = None
        self._loop = asyncio.new_event_loop()

    # ── Нийтийн интерфэйс ──────────────────────

    def start(self):
        self._loop.run_until_complete(self._start())

    def search(self, query: str) -> list[dict]:
        """Хайлт хийж dict жагсаалт буцаана"""
        return self._loop.run_until_complete(self._do_search(query))

    def search_as_text(self, query: str) -> str:
        """Хайлт хийж Sheet-д тохиромжтой текст буцаана"""
        results = self.search(query)
        return format_results_for_sheet(results)

    def close(self):
        self._loop.run_until_complete(self._teardown())
        self._loop.close()

    # ── Дотоод async методууд ──────────────────

    async def _start(self):
        print("[google] Camoufox эхэлж байна...")
        self._browser = AsyncCamoufox(
            headless=True,
            geoip=True,
            os="windows",
            block_images=True,  # Хурдасгахын тулд зураг блоклоно
        )
        self._context = await self._browser.__aenter__()
        self._page = await self._context.new_page()
        print("[google] Бэлэн болоо ✓")

    async def _do_search(self, query: str) -> list[dict]:
        for attempt in range(3):
            try:
                results = await _search_google(self._page, query, self.max_results)
                print(f"  [google] {len(results)} үр дүн олдлоо.")
                return results
            except RuntimeError as e:
                # CAPTCHA эсвэл хайлт олдсонгүй → дахин оролдохгүй
                print(f"  [google] Алдаа: {e}")
                return []
            except Exception as e:
                print(f"  [google] {attempt + 1}-р оролдлого амжилтгүй: {e}")
                if attempt < 2:
                    await asyncio.sleep(5)
        return []

    async def _teardown(self):
        try:
            if self._browser:
                await self._browser.__aexit__(None, None, None)
        except Exception as e:
            print(f"[google] Хаах үед алдаа: {e}")


# ─────────────────────────────────────────────
#  Шууд ажиллуулах
# ─────────────────────────────────────────────

if __name__ == "__main__":
    scraper = GoogleScraper(max_results=5)
    try:
        scraper.start()
        while True:
            q = input("\nХайх (гарах: q): ").strip()
            if q.lower() == "q":
                break
            results = scraper.search(q)
            for r in results:
                print(f"\n{r['rank']}. {r['title']}")
                print(f"   {r['url']}")
                print(f"   {r['snippet'][:120]}")
    finally:
        scraper.close()
