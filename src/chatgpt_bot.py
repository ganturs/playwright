import asyncio
import os
import json
import nest_asyncio
nest_asyncio.apply()
import zendriver as uc
from src.config import CHROME_PROFILE_DIR, CHATGPT_URL

HEADLESS = os.environ.get("HEADLESS", "true").lower() == "true"

SELECTORS = {
    "input": "div#prompt-textarea",
    "send_btn": "button[data-testid='send-button']",
    "stop_btn": "button[data-testid='stop-button'], button[aria-label='Stop streaming'], button.stop-button",
    "response": "div[data-message-author-role='assistant']",
}


class ChatGPTBot:
    def __init__(self, worker_id: int = 0, proxy: str = None,
                 proxy_list: list = None, rotate_every: int = 5):
        self.worker_id = worker_id
        self.proxy = proxy
        self._proxy_list = proxy_list or ([proxy] if proxy else [])
        self._rotate_every = rotate_every
        self._proxy_index = 0
        self._request_count = 0
        self._browser = None
        self._page = None
        self._loop = None

    def _get_loop(self):
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        return self._loop

    def _current_proxy(self) -> str | None:
        if not self._proxy_list:
            return None
        return self._proxy_list[self._proxy_index % len(self._proxy_list)]

    def start(self):
        self.proxy = self._current_proxy()
        self._get_loop().run_until_complete(self._start())

    def ask(self, prompt: str) -> str:
        return self._get_loop().run_until_complete(self._ask_prompt(prompt))

    def close(self):
        loop = self._get_loop()
        loop.run_until_complete(self._teardown())
        loop.close()
        self._loop = None

    def _restart_with_new_proxy(self):
        tag = f"[bot-{self.worker_id}]"
        self._proxy_index += 1
        self.proxy = self._current_proxy()
        print(f"{tag} Proxy солиж байна → {self.proxy.split('@')[-1] if self.proxy else 'None'}")
        self._get_loop().run_until_complete(self._teardown())
        self._get_loop().run_until_complete(self._start())
        print(f"{tag} Шинэ proxy-тай браузер бэлэн ✓")

    async def _start(self):
        tag = f"[bot-{self.worker_id}]"
        print(f"{tag} zenDriver Chrome эхэлж байна...")

        # Cookie файл
        auth_file = os.path.join(CHROME_PROFILE_DIR, f"auth_state_worker{self.worker_id}.json")
        self._auth_file = auth_file

        # Proxy тохиргоо
        proxy_arg = None
        if self.proxy:
            proxy_arg = self.proxy
            print(f"{tag} Proxy: {self.proxy.split('@')[-1]}")

        browser_args = [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-extensions",
            "--disable-background-networking",
            "--disable-sync",
            "--disable-translate",
            "--disable-logging",
            "--disable-default-apps",
            "--mute-audio",
            "--no-first-run",
            "--safebrowsing-disable-auto-update",
            "--disable-background-timer-throttling",
            "--disable-renderer-backgrounding",
            "--disable-backgrounding-occluded-windows",
            "--blink-settings=imagesEnabled=false",
            "--js-flags=--max-old-space-size=256",
        ]
        self._browser = await uc.start(
            headless=HEADLESS,
            no_sandbox=True,
            browser_args=browser_args,
        )

        self._page = await self._browser.get(CHATGPT_URL)
        await asyncio.sleep(5)

        # Cookie consent modal dismiss
        for selector in [
            "button[data-testid='accept-button']",
            "button:has-text('Accept all')",
            "button:has-text('Accept')",
            "button:has-text('Reject non-essential')",
            "button:has-text('Got it')",
        ]:
            try:
                btn = await self._page.query_selector(selector)
                if btn:
                    await btn.click()
                    await asyncio.sleep(1)
                    print(f"{tag} Cookie modal dismiss хийлээ ✓")
                    break
            except Exception:
                pass

        # Cookie load — CDP Network.setCookie ашиглан inject хийнэ
        if os.path.exists(auth_file):
            try:
                cookies = json.load(open(auth_file)).get("cookies", [])
                for c in cookies:
                    try:
                        params = {
                            "name": c.get("name", ""),
                            "value": c.get("value", ""),
                            "domain": c.get("domain", ""),
                            "path": c.get("path", "/"),
                            "secure": c.get("secure", False),
                            "httpOnly": c.get("httpOnly", False),
                        }
                        if c.get("expirationDate"):
                            params["expires"] = int(c["expirationDate"])
                        await self._browser.connection.send(
                            "Network.setCookie", **params
                        )
                    except Exception:
                        pass
                await self._page.get(CHATGPT_URL)
                await asyncio.sleep(5)
                login_check = await self._page.query_selector(
                    "button[data-testid='login-button'], a[href='/auth/login'], input[name='email']"
                )
                if login_check:
                    print(f"{tag} Cookies inject хийсэн ч login screen байна.")
                else:
                    print(f"{tag} Cookies load хийлээ ✓")
            except Exception as e:
                print(f"{tag} Cookies load алдаа: {e}")
        else:
            print(f"{tag} Session байхгүй — нэвтрэхгүйгээр ажиллана.")

        print(f"{tag} Бэлэн болоо ✓")

    async def _dismiss_cookie_modal(self):
        for selector in [
            "button[data-testid='accept-button']",
            "button[data-testid='reject-button']",
        ]:
            try:
                btn = await self._page.query_selector(selector)
                if btn:
                    await btn.click()
                    await asyncio.sleep(1)
                    return
            except Exception:
                pass
        # Text-based fallback
        try:
            await self._page.evaluate("""
                const btns = document.querySelectorAll('button');
                for (const b of btns) {
                    if (b.textContent.includes('Accept all') || b.textContent.includes('Reject non-essential')) {
                        b.click(); break;
                    }
                }
            """)
            await asyncio.sleep(1)
        except Exception:
            pass

    async def _is_login_screen(self) -> bool:
        """Input box байхгүй + email input байвал л login screen гэж үзнэ"""
        try:
            input_box = await self._page.query_selector(SELECTORS["input"])
            if input_box:
                return False
            email_input = await self._page.query_selector("input[name='email'], input[type='email']")
            return email_input is not None
        except Exception:
            return False

    async def _restart_with_new_proxy_async(self):
        """Browser дахин эхлүүлнэ — Evomi rotating proxy тул IP автоматаар солигдоно"""
        tag = f"[bot-{self.worker_id}]"
        print(f"{tag} Login screen → browser restart хийж байна (IP автоматаар солигдоно)...")
        await self._teardown()
        await self._start()
        print(f"{tag} Шинэ browser бэлэн ✓")

    async def _ask_prompt(self, prompt: str) -> str:
        tag = f"[bot-{self.worker_id}]"
        self._request_count += 1

        # 2 request тутам browser restart — login redirect гарахаас өмнө
        if self._request_count > 1 and (self._request_count - 1) % 2 == 0:
            print(f"{tag} {self._request_count-1} request болсон — browser restart хийж байна...")
            await self._teardown()
            await self._start()

        for attempt in range(3):
            try:
                # Login screen илрвэл эхлээд "Stay logged out" дарж үзнэ
                if await self._is_login_screen():
                    print(f"{tag} Login screen илрлээ (attempt {attempt+1}) — Stay logged out дарж байна...")
                    dismissed = False
                    for selector in [
                        "button[data-testid='stay-logged-out-button']",
                        "a[data-testid='stay-logged-out']",
                        "button:has-text('Stay logged out')",
                        "//button[contains(text(),'Stay logged out')]",
                        "//a[contains(text(),'Stay logged out')]",
                    ]:
                        try:
                            btn = await self._page.query_selector(selector)
                            if btn:
                                await btn.click()
                                await asyncio.sleep(2)
                                dismissed = True
                                print(f"{tag} Stay logged out дарлаа ✓")
                                break
                        except Exception:
                            pass
                    if not dismissed:
                        print(f"{tag} Stay logged out олдсонгүй — browser restart хийж байна...")
                        await self._restart_with_new_proxy_async()
                        await asyncio.sleep(3)

                # Input талбар олох (30s хүлээх)
                input_box = None
                for _ in range(30):
                    input_box = await self._page.query_selector(SELECTORS["input"])
                    if input_box:
                        break
                    await asyncio.sleep(1)

                if not input_box:
                    await self._page.save_screenshot(f"debug_no_input_worker{self.worker_id}.png")
                    raise RuntimeError("Input талбар олдсонгүй.")

                # Cookie modal байвал dismiss хийнэ
                await self._dismiss_cookie_modal()

                # Prompt оруулах
                await input_box.clear_input()
                await input_box.send_keys(prompt)
                await asyncio.sleep(0.3)

                # Send товч
                send_btn = await self._page.query_selector(SELECTORS["send_btn"])
                if send_btn:
                    await send_btn.click()
                    print(f"  [bot] Send товч дарлаа ✓")
                else:
                    await input_box.send_keys("\n")
                    print(f"  [bot] Enter дарлаа ✓")

                print(f"  [bot] Промпт илгээлээ: {prompt[:50]}...")
                await self._page.save_screenshot(f"debug_sent_worker{self.worker_id}.png")

                # Stop button гарах хүртэл хүлээх
                stop_appeared = False
                for _ in range(15):
                    stop = await self._page.query_selector(SELECTORS["stop_btn"])
                    if stop:
                        stop_appeared = True
                        break
                    # Stop button олдохгүй ч response гарсан бол дуусчихсан
                    els = await self._page.query_selector_all(SELECTORS["response"])
                    if els:
                        stop_appeared = True
                        break
                    await asyncio.sleep(2)

                print(f"  {tag} stop_appeared={stop_appeared}")

                # Stop button алга болох хүртэл хүлээх
                if stop_appeared:
                    for _ in range(90):
                        stop = await self._page.query_selector(SELECTORS["stop_btn"])
                        if not stop:
                            break
                        await asyncio.sleep(3)
                    await asyncio.sleep(5)
                else:
                    await asyncio.sleep(60)

                await self._page.save_screenshot(f"debug_after_wait_worker{self.worker_id}.png")

                # Хариулт унших
                import re
                for i in range(8):
                    elements = await self._page.query_selector_all(SELECTORS["response"])
                    print(f"  {tag} Хариулт хайж байна ({i+1}/8): {len(elements)} элемент олдлоо")
                    if elements:
                        raw = await elements[-1].get_html()
                        print(f"  {tag} raw html урт: {len(raw) if raw else 0}")
                        if raw:
                            text = re.sub(r"<[^>]+>", "", raw).strip()
                            print(f"  {tag} strip хийсний дараа урт: {len(text)}")
                            if len(text) > 10:
                                return text
                    await asyncio.sleep(3)

                await self._page.save_screenshot(f"debug_empty_worker{self.worker_id}.png")
                raise RuntimeError("Хоосон хариу ирлээ.")

            except Exception as e:
                print(f"  {tag} {attempt+1}-р оролдлого амжилтгүй: {e}")
                if attempt < 2:
                    await asyncio.sleep(10)
                    try:
                        await self._page.get(CHATGPT_URL)
                        await asyncio.sleep(3)
                    except Exception:
                        pass

        return ""

    async def _teardown(self):
        try:
            if self._browser:
                try:
                    await self._browser.stop()
                except TypeError:
                    self._browser.stop()
                self._browser = None
                self._page = None
        except Exception as e:
            print(f"[bot-{self.worker_id}] Хаах үед алдаа: {e}")


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
