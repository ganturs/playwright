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

# Selenium
# HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"
HEADLESS = True
CHROME_PROFILE_DIR = os.getenv("CHROME_PROFILE_DIR", "./chrome_profile")
CHATGPT_URL = os.getenv("CHATGPT_URL", "https://chatgpt.com")

# Crawl
DELAY_BETWEEN_PROMPTS = int(os.getenv("DELAY_BETWEEN_PROMPTS", "5"))
