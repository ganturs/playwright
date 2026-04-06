import time

try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    Credentials = None
    build = None
    HttpError = Exception

from src.config import GOOGLE_CREDENTIALS_FILE, SPREADSHEET_ID, SHEET_NAME

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

_service = None


def get_service():
    global _service
    if _service is None:
        creds = Credentials.from_service_account_file(
            GOOGLE_CREDENTIALS_FILE, scopes=SCOPES
        )
        _service = build("sheets", "v4", credentials=creds)
    return _service


def _execute_with_retry(request, max_retries: int = 5):
    """429 гарвал exponential backoff-р retry хийнэ"""
    delay = 5
    for attempt in range(max_retries):
        try:
            return request.execute()
        except HttpError as e:
            if e.resp.status == 429 and attempt < max_retries - 1:
                print(f"[sheets] 429 Rate limit — {delay}с хүлээж байна... ({attempt+1}/{max_retries})")
                time.sleep(delay)
                delay *= 2  # 5 → 10 → 20 → 40с
            else:
                raise


def read_prompts() -> list[dict]:
    service = get_service()
    result = _execute_with_retry(
        service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A:C",
        )
    )
    rows = result.get("values", [])
    if not rows or len(rows) < 2:
        print("Sheet хоосон байна эсвэл header л байна.")
        return []
    pending = []
    for i, row in enumerate(rows[1:], start=2):
        prompt = row[0].strip() if len(row) > 0 else ""
        status = row[1].strip().lower() if len(row) > 1 else "pending"
        if prompt and status == "pending":
            pending.append({"row": i, "prompt": prompt})
    print(f"Google Sheets-с {len(pending)} pending prompt олдлоо.")
    return pending


def mark_row_done(row: int, response: str):
    service = get_service()
    _execute_with_retry(
        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!B{row}:C{row}",
            valueInputOption="RAW",
            body={"values": [["done", response]]},
        )
    )


def mark_row_done_with_google(row: int, chatgpt_response: str, google_results: str):
    """ChatGPT хариулт (C багана) болон Google үр дүн (D багана) хадгалана"""
    service = get_service()
    _execute_with_retry(
        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!B{row}:D{row}",
            valueInputOption="RAW",
            body={"values": [["done", chatgpt_response, google_results]]},
        )
    )


def mark_row_error(row: int, message: str):
    service = get_service()
    _execute_with_retry(
        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!B{row}:C{row}",
            valueInputOption="RAW",
            body={"values": [["error", message]]},
        )
    )
