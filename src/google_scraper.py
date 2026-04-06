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
from urllib.parse import urlparse
from camoufox.async_api import AsyncCamoufox
from playwright.async_api import Page


# ─────────────────────────────────────────────
#  Тохиргоо
# ─────────────────────────────────────────────

GOOGLE_TLDS = [
    "https://www.google.com",
    "https://www.google.co.uk",
    "https://www.google.co.jp",
    "https://www.google.de",
    "https://www.google.fr",
    "https://www.google.ca",
    "https://www.google.com.au",
    "https://www.google.es",
    "https://www.google.it",
    "https://www.google.nl",
]
DEFAULT_MAX_RESULTS = 10

# Google selector
GOOGLE_SELECTORS = {
    "search_input": ["textarea[name='q']", "input[name='q']"],
    "result_item": ["#rso .g", "#search .g", "div.g", "#rso > div > div", "div[data-hveid]"],
    "title": "h3",
    "link": "a[href]",
    "snippet": ["div[style*='-webkit-line-clamp']", "div.VwiC3b", "span.aCOpRe", "div.IsZvec"],
    "accept_cookies": [
        "button:has-text('Accept all')", "button:has-text('I agree')",
        "button:has-text('すべて同意')", "form[action*='consent'] button",
    ],
    "captcha": ["form#captcha-form", "div#recaptcha", "iframe[src*='recaptcha']"],
    "results_container": "#search",
}

# DuckDuckGo selector
DDG_SELECTORS = {
    "search_input": ["input[name='q']"],
    "result_item": ["article[data-testid='result']", "div.nrn-react-div", "div[data-testid='result']"],
    "title": "h2",
    "link": "a[data-testid='result-title-a'], h2 a",
    "snippet": ["div[data-testid='result-extras-url-icon'] ~ div", "div.OgdwYG", "span.kY2IgmnCmOGjharHErah"],
}

# 後方互換
SELECTORS = GOOGLE_SELECTORS


# ─────────────────────────────────────────────
#  Туслах функцүүд
# ─────────────────────────────────────────────

async def _dismiss_cookies(page: Page):
    """Cookie зөвшөөрлийн цонхыг хаана"""
    for sel in SELECTORS["accept_cookies"]:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=2000):
                await btn.click(force=True, timeout=3000)
                await asyncio.sleep(0.5)
                return
        except Exception:
            continue


async def _check_captcha(page: Page) -> bool:
    """CAPTCHA гарсан эсэхийг шалгана"""
    for sel in GOOGLE_SELECTORS["captcha"]:
        try:
            el = page.locator(sel).first
            if await el.is_visible(timeout=1000):
                return True
        except Exception:
            continue
    return False


async def _search_ddg(page: Page, query: str, max_results: int) -> list[dict]:
    """DuckDuckGo-д хайлт хийж үр дүн буцаана (Google CAPTCHA-н fallback)"""
    await page.goto(DDG_URL, wait_until="domcontentloaded", timeout=30000)

    input_box = None
    for sel in DDG_SELECTORS["search_input"]:
        try:
            input_box = await page.wait_for_selector(sel, timeout=5000)
            if input_box:
                break
        except Exception:
            continue

    if not input_box:
        raise RuntimeError("DuckDuckGo хайлтын талбар олдсонгүй.")

    await input_box.click()
    await asyncio.sleep(random.uniform(0.2, 0.4))
    for char in query:
        await page.keyboard.type(char, delay=random.uniform(30, 70))

    await page.keyboard.press("Enter")
    await asyncio.sleep(random.uniform(1.0, 1.5))

    results = []
    for result_sel in DDG_SELECTORS["result_item"]:
        try:
            await page.wait_for_selector(result_sel, timeout=8000)
            items = await page.query_selector_all(result_sel)
            for item in items:
                try:
                    title_el = await item.query_selector(DDG_SELECTORS["title"])
                    link_el = await item.query_selector(DDG_SELECTORS["link"])
                    if not title_el or not link_el:
                        continue
                    title = (await title_el.inner_text()).strip()
                    url = await link_el.get_attribute("href")
                    if not title or not url or not url.startswith("http"):
                        continue
                    snippet = ""
                    for snip_sel in DDG_SELECTORS["snippet"]:
                        snip_el = await item.query_selector(snip_sel)
                        if snip_el:
                            snippet = (await snip_el.inner_text()).strip()
                            if snippet:
                                break
                    results.append({"rank": len(results) + 1, "title": title, "url": url, "snippet": snippet})
                    if len(results) >= max_results:
                        return results
                except Exception:
                    continue
            if results:
                break
        except Exception:
            continue

    return results


async def _search_google(page: Page, query: str, max_results: int, google_url: str = None) -> list[dict]:
    """Google-д хайлт хийж үр дүн буцаана"""
    await page.goto(google_url or GOOGLE_TLDS[0], wait_until="domcontentloaded", timeout=30000)
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

    # CAPTCHA / sorry шалгах
    await asyncio.sleep(2)
    current_url = page.url
    if "/sorry/" in current_url or "sorry/index" in current_url:
        raise RuntimeError(f"Google IP блоклов (sorry/index). Proxy солих шаардлагатай.")
    if await _check_captcha(page):
        raise RuntimeError("Google CAPTCHA гарлаа.")

    # Consent/redirect хуудас шалгах (Google зарим бүс нутагт redirect хийдэг)
    current_url = page.url
    if "consent.google" in current_url or "accounts.google" in current_url:
        await page.screenshot(path="debug_google_consent.png")
        # Consent хуудсыг давах
        for sel in SELECTORS["accept_cookies"]:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=2000):
                    await btn.click()
                    await asyncio.sleep(1)
                    break
            except Exception:
                continue

    # Үр дүн хүлээх
    result_found = False

    # Эхлээд #search container хүлээнэ
    try:
        await page.wait_for_selector(SELECTORS["results_container"], timeout=10000)
    except Exception:
        pass

    for sel in SELECTORS["result_item"]:
        try:
            await page.wait_for_selector(sel, timeout=8000)
            result_found = True
            break
        except Exception:
            continue

    if not result_found:
        await page.screenshot(path="debug_google_no_results.png")
        title = await page.title()
        url = page.url
        raise RuntimeError(f"Google үр дүн олдсонгүй. Хуудас: '{title}' | URL: {url} | debug_google_no_results.png шалгана уу.")

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
        scraper = GoogleScraper(max_results=5, proxy="http://user:pass@host:port")
        scraper.start()
        results = scraper.search("Python гэж юу вэ?")
        text = scraper.search_as_text("Python гэж юу вэ?")
        scraper.close()
    """

    def __init__(self, max_results: int = DEFAULT_MAX_RESULTS, proxy: str = None):
        self.max_results = max_results
        self.proxy = proxy
        self._browser = None
        self._context = None
        self._page = None
        self._loop = asyncio.new_event_loop()
        self._tld_index = random.randint(0, len(GOOGLE_TLDS) - 1)  # worker тус бүр өөр TLD-с эхэлнэ
        self._search_count = 0

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

    @staticmethod
    def _build_proxy_config(proxy_url: str) -> dict:
        """
        "http://user:pass@host:port" → {"server": "http://host:port", "username": "user", "password": "pass"}
        Playwright/Camoufox нь URL-с credentials автоматаар задлахгүй тул тусад нь дамжуулна.
        """
        parsed = urlparse(proxy_url)
        config = {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"}
        if parsed.username:
            config["username"] = parsed.username
        if parsed.password:
            config["password"] = parsed.password
        return config

    async def _start(self):
        proxy_config = self._build_proxy_config(self.proxy) if self.proxy else None
        print(f"[google] Camoufox эхэлж байна... proxy={proxy_config['server'] if proxy_config else 'None'}")
        self._browser = AsyncCamoufox(
            headless=True,
            geoip=True,
            os="windows",
            block_images=False,  # True байвал Google CAPTCHA өдөөдөг
            **({"proxy": proxy_config} if proxy_config else {}),
        )
        self._context = await self._browser.__aenter__()
        self._page = await self._context.new_page()
        print("[google] Бэлэн болоо ✓")

    async def _do_search(self, query: str) -> list[dict]:
        # Хайлт хооронд random delay (Google rate limit-аас зугтах)
        if self._search_count > 0:
            await asyncio.sleep(random.uniform(3.0, 6.0))

        # TLD rotation: хайлт бүрт дараагийн TLD ашиглана
        google_url = GOOGLE_TLDS[self._tld_index % len(GOOGLE_TLDS)]
        self._tld_index += 1
        self._search_count += 1

        print(f"  [google] {google_url} → {query[:40]}...")
        try:
            results = await _search_google(self._page, query, self.max_results, google_url)
        except RuntimeError as e:
            if "IP блоклов" in str(e):
                # Блоклогдвол дараагийн TLD-р дахин оролдоно
                google_url = GOOGLE_TLDS[self._tld_index % len(GOOGLE_TLDS)]
                self._tld_index += 1
                print(f"  [google] Retry → {google_url}")
                await asyncio.sleep(random.uniform(2.0, 4.0))
                results = await _search_google(self._page, query, self.max_results, google_url)
            else:
                raise

        if results:
            print(f"  [google] {len(results)} үр дүн олдлоо.")
        else:
            print(f"  [google] Үр дүн олдсонгүй.")
        return results

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
