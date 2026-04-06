import mysql.connector
from src.config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD


def get_connection():
    return mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        charset="utf8mb4",
    )


def save_result(prompt: str, chatgpt_response: str, google_results: str, sheet_row: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO responses (prompt, response, google_results, sheet_row, status)
           VALUES (%s, %s, %s, %s, 'done')
           ON DUPLICATE KEY UPDATE
               response = VALUES(response),
               google_results = VALUES(google_results),
               status = 'done'
        """,
        (prompt, chatgpt_response, google_results, sheet_row),
    )
    conn.commit()
    cursor.close()
    conn.close()
    print(f"  [db] Row {sheet_row} хадгалагдлаа.")


def save_error(prompt: str, error_message: str, sheet_row: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO responses (prompt, error_message, sheet_row, status)
           VALUES (%s, %s, %s, 'error')
           ON DUPLICATE KEY UPDATE
               error_message = VALUES(error_message),
               status = 'error'
        """,
        (prompt, error_message, sheet_row),
    )
    conn.commit()
    cursor.close()
    conn.close()


def test_connection():
    try:
        conn = get_connection()
        conn.close()
        print("[db] MySQL холболт амжилттай.")
        return True
    except Exception as e:
        print(f"[db] MySQL холболт амжилтгүй: {e}")
        return False
