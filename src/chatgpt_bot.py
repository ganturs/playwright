"""
chatgpt_bot.py — nodriver + Chrome (Camoufox-оос хөнгөн)
API ашиглахгүй, Chrome browser automation ашиглана.

Суулгах:
    pip install nodriver
"""

import asyncio
import os
import json
import nodriver as uc
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
        self._loop = asyncio.new_event_loop()

    def _current_proxy(self) -> str | None:
        if not self._proxy_list:
            return None
        return self._proxy_list[self._proxy_index % len(self._proxy_list)]

    def start(self):
        self.proxy = self._current_proxy()
        self._loop.run_until_complete(self._start())

    def ask(self, prompt: str) -> str:
        return self._loop.run_until_complete(self._ask_prompt(prompt))

    def close(self):
        self._loop.run_until_complete(self._teardown())
        self._loop.close()

    def _restart_with_new_proxy(self):
        tag = f"[bot-{self.worker_id}]"
        self._proxy_index += 1
        self.proxy = self._current_proxy()
        print(f"{tag} Proxy солиж байна → {self.proxy.split('@')[-1] if self.proxy else 'None'}")
        self._loop.run_until_complete(self._teardown())
        self._loop.run_until_complete(self._start())
        print(f"{tag} Шинэ proxy-тай браузер бэлэн ✓")

    async def _start(self):
        tag = f"[bot-{self.worker_id}]"
        print(f"{tag} nodriver Chrome эхэлж байна...")

        # Cookie файл
        auth_file = os.path.join(CHROME_PROFILE_DIR, f"auth_state_worker{self.worker_id}.json")
        self._auth_file = auth_file

        # Proxy тохиргоо
        proxy_arg = None
        if self.proxy:
            proxy_arg = self.proxy
            print(f"{tag} Proxy: {self.proxy.split('@')[-1]}")

        kwargs = dict(
            headless=HEADLESS,
            browser_args=[
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
            ],
        )
        if proxy_arg:
            kwargs["browser_args"].append(f"--proxy-server={proxy_arg.split('://')[-1].split('@')[-1]}")

        self._browser = await uc.start(**kwargs)
        self._page = await self._browser.get(CHATGPT_URL)
        await asyncio.sleep(3)

        # Cookie load
        if os.path.exists(auth_file):
            try:
                cookies = json.load(open(auth_file)).get("cookies", [])
                for c in cookies:
                    await self._page.send(
                        "Network.setCookie",
                        name=c["name"],
                        value=c["value"],
                        domain=c.get("domain", ".chatgpt.com"),
                        path=c.get("path", "/"),
                        httpOnly=c.get("httpOnly", False),
                        secure=c.get("secure", False),
                    )
                await self._page.get(CHATGPT_URL)
                await asyncio.sleep(2)
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
                # Input талбар олох
                input_box = await self._page.find(SELECTORS["input"], timeout=10)
                if not input_box:
                    raise RuntimeError("Input талбар олдсонгүй.")

                # Prompt оруулах
                await input_box.clear_input()
                await input_box.send_keys(prompt)
                await asyncio.sleep(0.3)

                # Send товч
                send_btn = await self._page.find(SELECTORS["send_btn"], timeout=5)
                if send_btn:
                    await send_btn.click()
                else:
                    await input_box.send_keys("\n")

                print(f"  [bot] Промпт илгээлээ: {prompt[:50]}...")

                # Stop button гарах хүртэл хүлээх
                stop_appeared = False
                for _ in range(30):
                    stop = await self._page.find(SELECTORS["stop_btn"], timeout=1)
                    if stop:
                        stop_appeared = True
                        break
                    await asyncio.sleep(1)

                # Stop button алга болох хүртэл хүлээх
                if stop_appeared:
                    for _ in range(180):
                        stop = await self._page.find(SELECTORS["stop_btn"], timeout=1)
                        if not stop:
                            break
                        await asyncio.sleep(1)
                else:
                    await asyncio.sleep(20)

                # Хариулт унших
                for _ in range(5):
                    elements = await self._page.query_selector_all(SELECTORS["response"])
                    if elements:
                        text = await elements[-1].get_html(strip=True)
                        if text and len(text.strip()) > 10:
                            # HTML tag хасах
                            import re
                            text = re.sub(r"<[^>]+>", "", text).strip()
                            return text
                    await asyncio.sleep(2)

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
                self._browser.stop()
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
