"""
migrate_db.py — responses table үүсгэх / шинэчлэх

Ажиллуулах (нэг удаа):
    python migrate_db.py
"""
from src.db import get_connection

conn = get_connection()
cursor = conn.cursor()

# Table үүсгэх (байхгүй бол)
cursor.execute("""
    CREATE TABLE IF NOT EXISTS responses (
        id INT AUTO_INCREMENT PRIMARY KEY,
        sheet_row INT UNIQUE,
        prompt TEXT,
        response LONGTEXT,
        google_results LONGTEXT,
        error_message TEXT,
        status VARCHAR(20) DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
""")
conn.commit()
print("✓ responses table бэлэн.")

# google_results багана байгаа эсэх шалгах
cursor.execute("SHOW COLUMNS FROM responses LIKE 'google_results'")
if not cursor.fetchone():
    cursor.execute("ALTER TABLE responses ADD COLUMN google_results LONGTEXT")
    conn.commit()
    print("✓ google_results багана нэмэгдлээ.")

cursor.close()
conn.close()
print("Migration дууслаа.")
