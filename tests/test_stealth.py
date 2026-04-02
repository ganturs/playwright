import asyncio
from playwright.async_api import async_playwright
import random

async def run_test():
    async with async_playwright() as p:
        # 1. Браузер эхлүүлэх
        # Хэрэв Cloudflare гацаад байвал headless=False болгож шалгаарай
        browser = await p.chromium.launch(
            headless=True, 
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox"
            ]
        )
        
        # 2. Контекст үүсгэх (Жинхэнэ мэт харагдуулах тохиргоо)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800},
            device_scale_factor=1,
        )

        page = await context.new_page()

        # 3. ГАР АРГААР STEALTH ХИЙХ (Бот илрүүлэгчдийг хуурах JS)
        # Энэ хэсэг navigator.webdriver болон бусад бот шинжүүдийг устгана
        await page.add_init_script("""
            # 1. Webdriver-ыг нуух
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            
            # 2. Chrome-ын объект дуурайх
            window.chrome = { runtime: {} };
            
            # 3. Plugins болон Languages дуурайх
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            
            # 4. Permissions шалгалт хуурах
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
            );
        """)

        print("[test] ChatGPT рүү орж байна...")
        
        try:
            # ChatGPT- рүү нэвтрэх
            await page.goto("https://chatgpt.com", wait_until="domcontentloaded", timeout=60000)
            
            print("[test] Cloudflare-ийг хүлээж байна (15 сек)...")
            await page.wait_for_timeout(15000)

            # Input талбар гарч ирэхийг хүлээх
            input_selector = "div#prompt-textarea"
            
            # Дэлгэц дээр юу харагдаж байгааг скриншот авах (Debug хийхэд хэрэгтэй)
            await page.screenshot(path="debug_result.png")
            
            if await page.query_selector(input_selector):
                print("✅ АМЖИЛТ: ChatGPT-ийн нүүр хуудас ачааллаа!")
                
                # Хүн шиг шивэх
                prompt = "Сайн уу? Энэ бол тест."
                await page.type(input_selector, prompt, delay=100)
                await page.keyboard.press("Enter")
                
                print("[test] Промпт илгээлээ. Хариултыг хүлээж байна...")
                await page.wait_for_timeout(10000)
                
            else:
                print("❌ Input олдсонгүй. Cloudflare шалгалт дээр гацсан байж магадгүй.")
                print("💡 'debug_result.png' файлыг шалгаж хаана гацсаныг харна уу.")

        except Exception as e:
            print(f"❌ Алдаа гарлаа: {e}")

        finally:
            # Түр нээлттэй байлгах (хэрэв headless=False бол)
            await page.wait_for_timeout(5000)
            await browser.close()
            print("[test] Тест дууслаа.")

if __name__ == "__main__":
    asyncio.run(run_test())