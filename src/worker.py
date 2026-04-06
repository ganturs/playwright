"""
worker.py — Нэг worker = нэг ChatGPT session + нэг Google session + proxy rotation

Google Semaphore:
    Олон worker зэрэг Google-д хандахад CAPTCHA гардаг.
    google_semaphore ашиглан нэгэн зэрэг хандах тоог хязгаарлана.
    (жишээ: 5 worker, 2 semaphore → Google-д зэрэг 2 хүсэлт л явна)

Proxy Rotation:
    proxy_list = [proxy_A, proxy_B, ...] гэж дамжуулбал rotate_every хүсэлт
    тутам дараагийн proxy руу шилжинэ. GoogleScraper-ийг дахин эхлүүлнэ.
    ChatGPT үргэлж шууд холболт ашиглана (proxy=None).
"""

import time
import threading
from concurrent.futures import ThreadPoolExecutor
from src.chatgpt_bot import ChatGPTBot
from src.google_scraper import GoogleScraper
from src.config import DELAY_BETWEEN_PROMPTS


class Worker:
    def __init__(
        self,
        worker_id: int,
        proxy_list: list = None,
        google_semaphore: threading.Semaphore = None,
        chatgpt_semaphore: threading.Semaphore = None,
        rotate_every: int = 5,
    ):
        self.worker_id = worker_id
        self._proxy_list = proxy_list or []
        self._semaphore = google_semaphore
        self._chatgpt_semaphore = chatgpt_semaphore
        self._rotate_every = rotate_every
        self._proxy_index = 0
        self._request_count = 0

        self._bot = ChatGPTBot(
            worker_id=worker_id,
            proxy_list=self._proxy_list,
            rotate_every=rotate_every,
        )
        self._google = GoogleScraper(max_results=10, proxy=self._current_proxy())
        self._executor = ThreadPoolExecutor(max_workers=2)
        import os
        self.google_enabled = os.environ.get("GOOGLE_ENABLED", "true").lower() == "true"

    def _current_proxy(self) -> str | None:
        if not self._proxy_list:
            return None
        return self._proxy_list[self._proxy_index % len(self._proxy_list)]

    def start(self):
        tag = f"[worker-{self.worker_id}]"
        proxy = self._current_proxy()
        print(f"{tag} Эхэлж байна..." + (f" proxy={proxy.split('@')[-1]}" if proxy else " proxy=None"))
        if self.google_enabled:
            self._google.start()
        self._bot.start()
        print(f"{tag} Бэлэн ✓")

    def _rotate_proxy(self):
        """Google-ийн proxy-г дараагийн рүү солиод scraper-ийг дахин эхлүүлнэ"""
        tag = f"[worker-{self.worker_id}]"
        self._proxy_index += 1
        new_proxy = self._current_proxy()
        print(f"{tag} Proxy солиж байна → {new_proxy.split('@')[-1] if new_proxy else 'None'}")
        try:
            self._google.close()
        except Exception:
            pass
        self._google = GoogleScraper(max_results=10, proxy=new_proxy)
        self._google.start()
        print(f"{tag} Шинэ proxy тохируулагдлаа ✓")

    def _google_search_safe(self, prompt: str) -> str:
        """Semaphore ашиглан Google хайлтыг хязгаарлана"""
        if self._semaphore:
            with self._semaphore:
                return self._google.search_as_text(prompt)
        return self._google.search_as_text(prompt)

    def _chatgpt_ask_safe(self, prompt: str) -> str:
        """Semaphore ашиглан ChatGPT зэрэг хандалтыг хязгаарлана"""
        if self._chatgpt_semaphore:
            with self._chatgpt_semaphore:
                return self._bot.ask(prompt)
        return self._bot.ask(prompt)

    def process(self, prompt: str) -> tuple[str, str]:
        """
        Google + ChatGPT зэрэг ажиллуулж хариулт буцаана.
        Google нь semaphore-р хязгаарлагдана (CAPTCHA-гүй).
        rotate_every хүсэлт тутам proxy солино.
        Returns: (chatgpt_response, google_text)
        """
        # Proxy rotation шалгах (process эхлэхээс өмнө)
        if self._proxy_list and self._rotate_every > 0:
            if self._request_count > 0 and self._request_count % self._rotate_every == 0:
                self._rotate_proxy()

        self._request_count += 1

        # Prompt хооронд throttle — CPU spike багасгана
        if self._request_count > 1 and DELAY_BETWEEN_PROMPTS > 0:
            time.sleep(DELAY_BETWEEN_PROMPTS)

        if self.google_enabled:
            g_future = self._executor.submit(self._google_search_safe, prompt)
        c_future = self._executor.submit(self._chatgpt_ask_safe, prompt)
        google_text = g_future.result() if self.google_enabled else ""
        chatgpt_response = c_future.result()
        return chatgpt_response, google_text

    def close(self):
        if self.google_enabled:
            try:
                self._google.close()
            except Exception as e:
                print(f"[worker-{self.worker_id}] Google хаах алдаа: {e}")
        try:
            self._bot.close()
        except Exception as e:
            print(f"[worker-{self.worker_id}] ChatGPT хаах алдаа: {e}")
        self._executor.shutdown(wait=False)
