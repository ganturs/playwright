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
            if await btn.is_visible(timeout=1500):
                await btn.click()
                await asyncio.sleep(0.8)
        except Exception:
            continue

    # Хэрэв modal хаагдаагүй бол JS-ээр устгана
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

    # Алхам 3: Текст оруулах
    await input_box.click()
    if len(prompt) > 200:
        # Урт текстийг JS-ээр оруулна (хурдан)
        await page.evaluate(
            "(t) => { const el = document.querySelector('div#prompt-textarea'); "
            "el.innerText = t; el.dispatchEvent(new Event('input', {bubbles:true})); }",
            prompt,
        )
        await asyncio.sleep(0.3)
    else:
        await human_type(page, "div#prompt-textarea", prompt)

    await asyncio.sleep(random.uniform(0.4, 1.0))

    # Алхам 4: Send товч → байхгүй бол Enter
    sent = False
    for sel in SELECTORS["send_btn"]:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=2000):
                await btn.click()
                sent = True
                break
        except Exception:
            continue

    if not sent:
        await page.keyboard.press("Enter")

    print(f"  [bot] Промпт илгээлээ: {prompt[:50]}...")

    # Алхам 5: Хариулт дуустал хүлээх (stop button алга болох)
    try:
        await page.wait_for_selector(SELECTORS["stop_btn"][0], timeout=12000)
        await page.wait_for_selector(
            SELECTORS["stop_btn"][0], state="hidden", timeout=120000
        )
    except Exception:
        # Stop button харагдаагүй ч хариулт ирсэн байж болно
        await asyncio.sleep(6)

    # Алхам 6: Сүүлийн хариулт авах
    for sel in SELECTORS["response"]:
        try:
            items = await page.query_selector_all(sel)
            if items:
                return await items[-1].inner_text()
        except Exception:
            continue

    return ""


# ─────────────────────────────────────────────
#  Bot үндсэн класс
# ─────────────────────────────────────────────

class ChatGPTBot:
    """
    Camoufox ашиглан ChatGPT-тэй харилцах bot.

    Хэрэглээ:
        bot = ChatGPTBot()
        bot.start()          # нэг удаа эхлүүлнэ
        answer = bot.ask("Сайн уу?")
        bot.close()

    Эхний удаа нэвтрэх:
        HEADLESS=false python -c "from chatgpt_bot import ChatGPTBot; b=ChatGPTBot(); b.start()"
        # Гараар нэвтэрсний дараа Ctrl+C дарна — session хадгалагдана.
        # Дараа нь HEADLESS=true байдлаар ажиллана.
    """

    def __init__(self):
        self._browser = None   # AsyncCamoufox context manager
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
        print("[bot] Camoufox эхэлж байна...")

        # Storage state файл байвал ашиглана (хурдан нэвтэрнэ)
        storage = AUTH_FILE if os.path.exists(AUTH_FILE) else None
        if storage:
            print(f"[bot] Хадгалсан session ашиглаж байна: {storage}")
        else:
            print("[bot] Шинэ session — нэвтрэх шаардлагатай.")

        # Camoufox — fingerprint, timezone, locale автоматаар тохируулна
        # storage_state нь launch()-д биш, new_context()-д ордог тул тусад нь өгнө
        self._browser = AsyncCamoufox(
            headless=True,
            geoip=True,         # IP-д тохирсон гео мэдээлэл
            os="windows",       # OS fingerprint (linux нь bot гэж таньдаг)
            block_images=False, # Зураг блоклоход зарим сайт bot гэж таньдаг
        )

        self._context = await self._browser.__aenter__()

        # Session байвал шинэ context-д load хийнэ
        if storage:
            try:
                await self._context.add_cookies(
                    __import__("json").load(open(storage)).get("cookies", [])
                )
                print("[bot] Cookies амжилттай load хийлээ.")
            except Exception as e:
                print(f"[bot] Cookies load алдаа (шинэ session эхэлнэ): {e}")

        self._page = await self._context.new_page()

        print(f"[bot] {CHATGPT_URL} руу очиж байна...")
        await self._page.goto(CHATGPT_URL, wait_until="domcontentloaded", timeout=60000)

        # Cloudflare давах
        await wait_cloudflare_pass(self._page, timeout=90)
        await clear_modals(self._page)

        # Нэвтрэлт шалгах
        if not await is_logged_in(self._page):
            if HEADLESS:
                raise RuntimeError(
                    "Нэвтрээгүй байна! Эхлээд HEADLESS=false горимд нэвтэрч session хадгална уу.\n"
                    "  HEADLESS=false python -c \"from chatgpt_bot import ChatGPTBot; b=ChatGPTBot(); b.start()\""
                )
            else:
                print("[bot] Гараар нэвтэрнэ үү. Нэвтэрсний дараа Enter дарна уу...")
                input("  [Enter дарна уу] ")
                await save_auth(self._page)

        await self._page.screenshot(path="debug_ready.png")
        print("[bot] Бэлэн болоо ✓")

    async def _ask_prompt(self, prompt: str) -> str:
        for attempt in range(3):
            try:
                return await send_prompt(self._page, prompt)
            except Exception as e:
                print(f"  [bot] {attempt+1}-р оролдлого амжилтгүй: {e}")
                if attempt < 2:
                    await self._page.reload(wait_until="domcontentloaded")
                    await asyncio.sleep(8)
        return ""

    async def _teardown(self):
        try:
            # Session шинэчилж хадгална
            if self._page:
                await save_auth(self._page)
            if self._browser:
                await self._browser.__aexit__(None, None, None)
        except Exception as e:
            print(f"[bot] Хаах үед алдаа: {e}")


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