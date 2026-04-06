from dotenv import load_dotenv
import os

load_dotenv()

# Google Sheets
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "")
SHEET_NAME = os.getenv("SHEET_NAME", "Sheet1")

# MySQL
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_NAME = os.getenv("DB_NAME", "chatgpt_crawler")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# Browser
HEADLESS = True
CHROME_PROFILE_DIR = os.getenv("CHROME_PROFILE_DIR", "./chrome_profile")
CHATGPT_URL = os.getenv("CHATGPT_URL", "https://chatgpt.com")

# Crawl
DELAY_BETWEEN_PROMPTS = int(os.getenv("DELAY_BETWEEN_PROMPTS", "5"))

# Worker / Proxy
WORKER_COUNT = int(os.getenv("WORKER_COUNT", "1"))
PROXIES_FILE = os.getenv("PROXIES_FILE", "proxies.txt")

# Google зэрэг хандалтын хязгаар (CAPTCHA-гүй байхын тулд 2 хэтрүүлэхгүй)
GOOGLE_CONCURRENT = int(os.getenv("GOOGLE_CONCURRENT", "2"))
CHATGPT_CONCURRENT = int(os.getenv("CHATGPT_CONCURRENT", "3"))


def load_proxies() -> list[str]:
    """
    proxies.txt-с proxy жагсаалт уншина.
    Буцаах утга: ["http://user:pass@host:port", ...]
    Файл байхгүй эсвэл хоосон бол [] буцаана (proxy-гүй ажиллана).
    """
    if not os.path.exists(PROXIES_FILE):
        return []
    proxies = []
    with open(PROXIES_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                proxies.append(line)
    return proxies
