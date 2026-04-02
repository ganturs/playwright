import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import random
import os

def test_chatgpt_with_profile():
    options = uc.ChromeOptions()
    
    # 1. ЧУХАЛ: Headless-ыг False болгов (Cloudflare-ыг давахын тулд)
    # Хэрэв сервер дээр бол Xvfb ашиглах шаардлагатай
    options.add_argument("--headless=new") 
    
    # 2. Profile хавтас зааж өгөх (Нэвтэрсэн сессийг хадгалахын тулд)
    curr_dir = os.getcwd()
    profile_dir = os.path.join(curr_dir, "chatgpt_profile")
    options.add_argument(f"--user-data-dir={profile_dir}")
    
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,1000")
    
    # Драйвер нээхэд гардаг automation flags-ыг унтраах
    options.add_argument("--disable-blink-features=AutomationControlled")

    print(f"[test] Chrome нээж байна... Profile: {profile_dir}")
    
    try:
        driver = uc.Chrome(options=options, version_main=146)
        wait = WebDriverWait(driver, 60) # Cloudflare-ийг хүлээх хугацааг уртасгав

        print("[test] ChatGPT рүү орж байна...")
        driver.get("https://chatgpt.com")
        
        print("💡 ЗӨВЛӨГӨӨ: Хэрэв Cloudflare шалгалт гарч ирвэл ГАРААРАА 'Verify' дээр дарна уу.")
        
        # 3. Input талбарыг илүү удаан хүлээх
        input_selectors = [
            "div#prompt-textarea",
            "textarea[data-id='prompt-textarea']",
            "div[contenteditable='true']"
        ]
        
        input_box = None
        for _ in range(3): # 3 удаа дахин оролдох
            for selector in input_selectors:
                try:
                    input_box = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                    if input_box: break
                except: continue
            if input_box: break
            print("[test] Олдохгүй байна, дахин шалгаж байна...")
            time.sleep(5)

        if not input_box:
            driver.save_screenshot("cloudflare_stuck.png")
            print("❌ Алдаа: Input талбар олдсонгүй. Гараараа нэвтрэх шаардлагатай байж магадгүй.")
            input("Браузерыг хаахгүй байхын тулд Enter дарна уу (Гараараа шалгахын тулд)...")
            return

        # 4. Текст бичих
        test_prompt = "Сайн уу? Энэ бол тест мессеж."
        print(f"[test] Бичиж байна: {test_prompt}")
        
        for char in test_prompt:
            input_box.send_keys(char)
            time.sleep(random.uniform(0.05, 0.15))
        
        input_box.send_keys(Keys.ENTER)
        print("[test] Илгээгдлээ. 10 секунд хүлээгээд хариултыг харна.")
        time.sleep(10)
        
        # Хариулт авах
        responses = driver.find_elements(By.CSS_SELECTOR, "div[data-message-author-role='assistant']")
        if responses:
            print(f"\n✅ ХАРИУЛТ: {responses[-1].text[:100]}...\n")
        else:
            print("❌ Хариултын текст олдсонгүй.")

    except Exception as e:
        print(f"❌ Алдаа: {e}")
    
    finally:
        if 'driver' in locals():
            # Хэрэв та сессийг хадгалахыг хүсвэл driver.quit() хийхээс өмнө 
            # хэсэг хугацаанд браузерыг нээлттэй байлгаж болно.
            time.sleep(5)
            driver.quit()
            print("[test] Браузер хаагдлаа.")

if __name__ == "__main__":
    test_chatgpt_with_profile()