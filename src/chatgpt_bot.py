"""
chatgpt_bot.py — Camoufox + Cloudflare Bypass
VM / GPC headless орчинд ажиллах хувилбар.
API ашиглахгүй, Camoufox browser automation ашиглана.

Суулгах:
    pip install camoufox[geoip]
    python -m camoufox fetch          # Firefox binary татах (нэг удаа)

Хэрэв VM дээр display байхгүй бол:
    sudo apt-get install -y xvfb
    Xvfb :99 -screen 0 1280x800x24 &
    export DISPLAY=:99
"""

import asyncio
import random
import os
from urllib.parse import urlparse
from camoufox.async_api import AsyncCamoufox
from playwright.async_api import Page
from src.config import CHROME_PROFILE_DIR, CHATGPT_URL

# ─────────────────────────────────────────────
#  Тохиргоо
# ─────────────────────────────────────────────

# VM / GPC дээр headless=True тавина
# Локал дээр дебаг хийхдээ headless=False болгоно
HEADLESS = os.environ.get("HEADLESS", "true").lower() == "true"

# Cookies хадгалах файл (нэвтэрсний дараа автоматаар үүснэ)
AUTH_FILE = os.path.join(CHROME_PROFILE_DIR, "auth_state.json")

SELECTORS = {
    "input": [
        "div#prompt-textarea",
        "div#prompt-textarea[contenteditable='true']",
        "#prompt-textarea",
        "textarea[data-id='prompt-textarea']",
    ],
    "send_btn": [
        "button[data-testid='send-button']",
        "button[aria-label='Send prompt']",
        "button[aria-label='Send message']",
        "form button[type='submit']",
    ],
    "stop_btn": [
        "button[data-testid='stop-button']",
        "button[aria-label='Stop streaming']",
    ],
    "response": [
        "div[data-message-author-role='assistant'] .markdown",
        "div[data-message-author-role='assistant']",
    ],
    "cookie_btns": [
        "button:has-text('Accept all')",
        "button:has-text('Stay logged out')",
        "button:has-text('Dismiss')",
        "div[role='dialog'] button",
    ],
    # Cloudflare challenge шалгах
    "cf_challenge_title": "title",
}

# ─────────────────────────────────────────────
#  Нэвтрэх хэрэгсэл
# ─────────────────────────────────────────────

async def save_auth(page: Page):
    """Нэвтэрсний дараа session хадгална (дараа дахин нэвтрэхгүй)"""
    import json
    os.makedirs(CHROME_PROFILE_DIR, exist_ok=True)
    # storage_state() dict буцаана: {"cookies": [...], "origins": [...]}
    state = await page.context.storage_state()
    with open(AUTH_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    cookie_count = len(state.get("cookies", []))
    print(f"[bot] Session хадгаллаа → {AUTH_FILE} ({cookie_count} cookies)")


async def is_logged_in(page: Page) -> bool:
    """Нэвтэрсэн эсэхийг шалгана"""
    try:
        await page.wait_for_selector(SELECTORS["input"][0], timeout=8000)
        return True
    except Exception:
        return False


# ─────────────────────────────────────────────
#  Cloudflare Bypass (Camoufox-д ихэвчлэн автомат)
# ─────────────────────────────────────────────

async def wait_cloudflare_pass(page: Page, timeout: int = 60):
    """
    Camoufox Cloudflare-ийг ихэвчлэн өөрөө давдаг.
    Гэхдээ 'Just a moment' хуудас гарвал хүлээнэ.
    """
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        title = await page.title()
        if "Just a moment" in title or "Checking your browser" in title:
            print("  [bot] Cloudflare шалгаж байна, хүлээж байна...")
            await asyncio.sleep(3)
        else:
            print(f"  [bot] Cloudflare давлаа. Хуудас: {title!r}")
            return
    raise TimeoutError("Cloudflare-ийг 60 сек дотор давж чадсангүй.")


async def clear_modals(page: Page):
    """Cookie, login modal цонхнуудыг хаана"""
    for sel in SELECTORS["cookie_btns"]:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=300):  # 1500 → 300мс
                await btn.click()
                await asyncio.sleep(0.3)  # 0.8 → 0.3с
        except Exception:
            continue

    await page.evaluate("""() => {
        document.querySelectorAll('div[role="dialog"], .fixed.inset-0').forEach(d => {
            if (!d.id?.includes('prompt')) d.remove();
        });
        document.body.style.overflow = 'auto';
    }""")


# ─────────────────────────────────────────────
#  Промпт илгээх
# ─────────────────────────────────────────────

async def human_type(page: Page, selector: str, text: str):
    """Хүний бичих хурдыг дуурайна"""
    await page.click(selector)
    await asyncio.sleep(random.uniform(0.2, 0.5))
    for char in text:
        await page.keyboard.type(char, delay=random.uniform(40, 120))
        if random.random() < 0.02:
            await page.keyboard.press("Backspace")
            await page.keyboard.type(char, delay=random.uniform(50, 100))


async def send_prompt(page: Page, prompt: str) -> str:
    """Промпт илгээж, хариулт авна"""
    # Алхам 1: Cloudflare болон modal цэвэрлэх
    await wait_cloudflare_pass(page)
    await clear_modals(page)

    # Алхам 2: Input талбар олох
    input_box = None
    for sel in SELECTORS["input"]:
        try:
            input_box = await page.wait_for_selector(sel, timeout=10000)
            if input_box:
                break
        except Exception:
            continue

    if not input_box:
        await page.screenshot(path="debug_no_input.png")
        raise RuntimeError("Input талбар олдсонгүй. debug_no_input.png-г шалгана уу.")

    # Алхам 3: Текст оруулах — JS injection (хурдан, bot detection-д аюулгүй)
    await input_box.click()
    await page.evaluate(
        "(t) => { const el = document.querySelector('div#prompt-textarea'); "
        "el.innerText = t; el.dispatchEvent(new Event('input', {bubbles:true})); }",
        prompt,
    )
    await asyncio.sleep(random.uniform(0.2, 0.4))  # 0.4-1.0 → 0.2-0.4с

    # Алхам 4: Send товч → байхгүй бол Enter
    sent = False
    for sel in SELECTORS["send_btn"]:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=800):  # 2000 → 800мс
                await btn.click()
                sent = True
                break
        except Exception:
            continue

    if not sent:
        await page.keyboard.press("Enter")

    print(f"  [bot] Промпт илгээлээ: {prompt[:50]}...")

    # Алхам 5: Хариулт дуустал хүлээх
    # 5a: Stop button гарах хүртэл хүлээх (ChatGPT бичиж эхэлснийг илтгэнэ)
    stop_appeared = False
    for stop_sel in SELECTORS["stop_btn"]:
        try:
            await page.wait_for_selector(stop_sel, timeout=30000)
            stop_appeared = True
            # 5b: Stop button алга болох хүртэл хүлээх (бичиж дуусна)
            await page.wait_for_selector(stop_sel, state="hidden", timeout=180000)
            break
        except Exception:
            continue

    if not stop_appeared:
        # Stop button харагдаагүй — хариулт ирсэн эсэхийг хүлээнэ
        await asyncio.sleep(15)

    # Алхам 6: Сүүлийн хариулт авах (retry хийнэ)
    for attempt in range(3):
        for sel in SELECTORS["response"]:
            try:
                items = await page.query_selector_all(sel)
                if items:
                    text = await items[-1].inner_text()
                    if text and text.strip():
                        return text.strip()
            except Exception:
                continue
        await asyncio.sleep(1)  # 3 → 1с

    await page.screenshot(path="debug_chatgpt_empty.png")
    return ""


# ─────────────────────────────────────────────
#  Bot үндсэн класс
# ─────────────────────────────────────────────

class ChatGPTBot:
    """
    Camoufox ашиглан ChatGPT-тэй харилцах bot.

    Хэрэглээ:
        bot = ChatGPTBot(worker_id=0, proxy="http://user:pass@host:port")
        bot.start()
        answer = bot.ask("Сайн уу?")
        bot.close()
    """

    def __init__(self, worker_id: int = 0, proxy: str = None):
        self.worker_id = worker_id
        self.proxy = proxy
        self._browser = None
        self._context = None
        self._page = None
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

    # ── Нийтийн интерфэйс ──────────────────────

    def start(self):
        self._loop.run_until_complete(self._start())

    def ask(self, prompt: str) -> str:
        return self._loop.run_until_complete(self._ask_prompt(prompt))

    def close(self):
        self._loop.run_until_complete(self._teardown())
        self._loop.close()

    # ── Дотоод async методууд ──────────────────

    async def _start(self):
        tag = f"[bot-{self.worker_id}]"
        print(f"{tag} Camoufox эхэлж байна...")

        # Worker бүр өөрийн session файлтай
        auth_file = os.path.join(CHROME_PROFILE_DIR, f"auth_state_worker{self.worker_id}.json")
        storage = auth_file if os.path.exists(auth_file) else None
        if storage:
            print(f"{tag} Хадгалсан session ашиглаж байна: {storage}")
        else:
            print(f"{tag} Шинэ session — нэвтрэх шаардлагатай.")

        # Proxy тохиргоо (credentials задлах)
        proxy_config = None
        if self.proxy:
            parsed = urlparse(self.proxy)
            proxy_config = {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"}
            if parsed.username:
                proxy_config["username"] = parsed.username
            if parsed.password:
                proxy_config["password"] = parsed.password
            print(f"{tag} Proxy: {parsed.hostname}:{parsed.port}")

        self._browser = AsyncCamoufox(
            headless=True,
            geoip=False,
            os="windows",
            block_images=False,
            **({"proxy": proxy_config} if proxy_config else {}),
        )

        self._browser_obj = await self._browser.__aenter__()

        # AsyncCamoufox нь Browser буцаана — BrowserContext тусад нь үүсгэнэ
        if hasattr(self._browser_obj, 'new_context'):
            self._context = await self._browser_obj.new_context()
        else:
            self._context = self._browser_obj

        if storage:
            try:
                cookies = __import__("json").load(open(storage)).get("cookies", [])
                await self._context.add_cookies(cookies)
                print(f"{tag} Cookies амжилттай load хийлээ.")
            except Exception as e:
                print(f"{tag} Cookies load алдаа (шинэ session эхэлнэ): {e}")

        self._page = await self._context.new_page()
        self._auth_file = auth_file

        print(f"{tag} {CHATGPT_URL} руу очиж байна...")
        await self._page.goto(CHATGPT_URL, wait_until="domcontentloaded", timeout=60000)

        await wait_cloudflare_pass(self._page, timeout=90)
        await clear_modals(self._page)

        if not await is_logged_in(self._page):
            if HEADLESS:
                raise RuntimeError(
                    f"{tag} Нэвтрээгүй байна! Эхлээд setup.py ажиллуулж worker {self.worker_id}-д нэвтэрнэ үү."
                )
            else:
                print(f"{tag} Гараар нэвтэрнэ үү. Нэвтэрсний дараа Enter дарна уу...")
                input("  [Enter дарна уу] ")
                await self._save_auth()

        await self._page.screenshot(path=f"debug_ready_worker{self.worker_id}.png")
        print(f"{tag} Бэлэн болоо ✓")

    async def _recover_session(self) -> bool:
        """
        IP солигдсоны дараа session алдагдвал cookies-р дахин нэвтрэх оролдлого.
        True = амжилттай, False = амжилтгүй.
        """
        tag = f"[bot-{self.worker_id}]"
        print(f"{tag} Session алдагдлаа — сэргээж байна...")
        try:
            await self._page.goto(CHATGPT_URL, wait_until="domcontentloaded", timeout=60000)
            await wait_cloudflare_pass(self._page, timeout=60)
            await clear_modals(self._page)
            if await is_logged_in(self._page):
                print(f"{tag} Session сэргэлээ ✓")
                return True
            # Cookies дахин load хийх
            if hasattr(self, "_auth_file") and __import__("os").path.exists(self._auth_file):
                cookies = __import__("json").load(open(self._auth_file)).get("cookies", [])
                await self._context.add_cookies(cookies)
                await self._page.reload(wait_until="domcontentloaded")
                await asyncio.sleep(3)
                if await is_logged_in(self._page):
                    print(f"{tag} Cookies-р session сэргэлээ ✓")
                    return True
        except Exception as e:
            print(f"{tag} Session сэргээхэд алдаа: {e}")
        print(f"{tag} Session сэргээж чадсангүй.")
        return False

    async def _ask_prompt(self, prompt: str) -> str:
        for attempt in range(3):
            try:
                # Промпт илгээхээс өмнө нэвтэрсэн эсэхийг шалгана
                if not await is_logged_in(self._page):
                    recovered = await self._recover_session()
                    if not recovered:
                        raise RuntimeError("Session сэргээж чадсангүй.")
                response = await send_prompt(self._page, prompt)
                if "Something went wrong" in response or "If this issue persists" in response:
                    raise RuntimeError(f"ChatGPT алдаа хуудас буцаалаа: {response[:80]}")
                return response
            except Exception as e:
                print(f"  [bot-{self.worker_id}] {attempt+1}-р оролдлого амжилтгүй: {e}")
                if attempt < 2:
                    await asyncio.sleep(10)
                    # Шинэ chat нээж алдааг цэвэрлэнэ
                    try:
                        await self._page.goto(CHATGPT_URL, wait_until="domcontentloaded", timeout=30000)
                        await wait_cloudflare_pass(self._page, timeout=30)
                        await clear_modals(self._page)
                    except Exception:
                        pass
        return ""

    async def _save_auth(self):
        import json
        os.makedirs(CHROME_PROFILE_DIR, exist_ok=True)
        state = await self._page.context.storage_state()
        with open(self._auth_file, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        print(f"[bot-{self.worker_id}] Session хадгаллаа → {self._auth_file}")

    async def _teardown(self):
        try:
            if self._page:
                await self._save_auth()
            if self._browser:
                await self._browser.__aexit__(None, None, None)
        except Exception as e:
            print(f"[bot-{self.worker_id}] Хаах үед алдаа: {e}")


# ─────────────────────────────────────────────
#  Шууд ажиллуулах
# ─────────────────────────────────────────────

if __name__ == "__main__":
    bot = ChatGPTBot()
    try:
        bot.start()
        while True:
            q = input("\nАсуулт (гарах: q): ").strip()
            if q.lower() == "q":
                break
            answer = bot.ask(q)
            print(f"\n[ChatGPT] {answer}\n")
    finally:
        bot.close()