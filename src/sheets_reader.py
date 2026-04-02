try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
except ImportError:
    Credentials = None
    build = None

from src.config import GOOGLE_CREDENTIALS_FILE, SPREADSHEET_ID, SHEET_NAME

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def get_service():
    creds = Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS_FILE, scopes=SCOPES
    )
    return build("sheets", "v4", credentials=creds)


def read_prompts() -> list[dict]:
    service = get_service()
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A:C",
    ).execute()
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
    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!B{row}:C{row}",
        valueInputOption="RAW",
        body={"values": [["done", response]]},
    ).execute()


def mark_row_done_with_google(row: int, chatgpt_response: str, google_results: str):
    """ChatGPT хариулт (C багана) болон Google үр дүн (D багана) хадгалана"""
    service = get_service()
    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!B{row}:D{row}",
        valueInputOption="RAW",
        body={"values": [["done", chatgpt_response, google_results]]},
    ).execute()


def mark_row_error(row: int, message: str):
    service = get_service()
    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!B{row}:C{row}",
        valueInputOption="RAW",
        body={"values": [["error", message]]},
    ).execute()