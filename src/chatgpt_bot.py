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
    "stop_btn": "button[data-testid='stop-button']",
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

        # Cookie load
        if os.path.exists(auth_file):
            try:
                cookies = json.load(open(auth_file)).get("cookies", [])
                for c in cookies:
                    try:
                        await self._page.send(
                            "Network.setCookie",
                            name=c.get("name", ""),
                            value=c.get("value", ""),
                            domain=c.get("domain", ""),
                            path=c.get("path", "/"),
                            secure=c.get("secure", False),
                            httpOnly=c.get("httpOnly", False),
                        )
                    except Exception:
                        pass
                await self._page.get(CHATGPT_URL)
                await asyncio.sleep(3)
                print(f"{tag} Cookies load хийлээ ✓")
            except Exception as e:
                print(f"{tag} Cookies load алдаа: {e}")
        else:
            print(f"{tag} Session байхгүй — нэвтрэхгүйгээр ажиллана.")

        print(f"{tag} Бэлэн болоо ✓")

    async def _ask_prompt(self, prompt: str) -> str:
        tag = f"[bot-{self.worker_id}]"

        # Proxy rotation
        if self._proxy_list and self._rotate_every > 0:
            if self._request_count > 0 and self._request_count % self._rotate_every == 0:
                self._restart_with_new_proxy()
        self._request_count += 1

        for attempt in range(3):
            try:
                # Input талбар олох (30s хүлээх)
                input_box = None
                for _ in range(30):
                    input_box = await self._page.query_selector(SELECTORS["input"])
                    if input_box:
                        break
                    await asyncio.sleep(1)

                if not input_box:
                    # ChatGPT нэвтрэхийг шаардаж байвал "Stay logged out" дарна
                    try:
                        stay_out = await self._page.find("Stay logged out", timeout=3)
                        if stay_out:
                            await stay_out.click()
                            await asyncio.sleep(2)
                            input_box = await self._page.query_selector(SELECTORS["input"])
                    except Exception:
                        pass
                if not input_box:
                    await self._page.save_screenshot(f"debug_no_input_worker{self.worker_id}.png")
                    raise RuntimeError("Input талбар олдсонгүй.")

                # Prompt оруулах
                await input_box.clear_input()
                await input_box.send_keys(prompt)
                await asyncio.sleep(0.3)

                # Send товч
                send_btn = await self._page.query_selector(SELECTORS["send_btn"])
                if send_btn:
                    await send_btn.click()
                else:
                    await input_box.send_keys("\n")

                print(f"  [bot] Промпт илгээлээ: {prompt[:50]}...")

                # Stop button гарах хүртэл хүлээх
                stop_appeared = False
                for _ in range(15):
                    stop = await self._page.query_selector(SELECTORS["stop_btn"])
                    if stop:
                        stop_appeared = True
                        break
                    await asyncio.sleep(2)

                # Stop button алга болох хүртэл хүлээх
                if stop_appeared:
                    for _ in range(90):
                        stop = await self._page.query_selector(SELECTORS["stop_btn"])
                        if not stop:
                            break
                        await asyncio.sleep(3)
                    # ChatGPT render дуусахыг хүлээх
                    await asyncio.sleep(5)
                else:
                    await asyncio.sleep(30)

                # Хариулт унших
                import re
                for _ in range(8):
                    elements = await self._page.query_selector_all(SELECTORS["response"])
                    if elements:
                        text = await elements[-1].get_html()
                        if text:
                            text = re.sub(r"<[^>]+>", "", text).strip()
                            if len(text) > 10:
                                return text
                    await asyncio.sleep(3)

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
