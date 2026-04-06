"""
migrate_db.py — responses table-д google_results багана нэмнэ (байхгүй бол)

Ажиллуулах (нэг удаа):
    python migrate_db.py
"""
from src.db import get_connection

conn = get_connection()
cursor = conn.cursor()

# google_results багана байгаа эсэх шалгах
cursor.execute("SHOW COLUMNS FROM responses LIKE 'google_results'")
if not cursor.fetchone():
    cursor.execute("ALTER TABLE responses ADD COLUMN google_results LONGTEXT")
    conn.commit()
    print("✓ google_results багана нэмэгдлээ.")
else:
    print("✓ google_results багана аль хэдийн байна.")

# sheet_row давхардахгүй байхаар UNIQUE index нэмэх (байхгүй бол)
cursor.execute("SHOW INDEX FROM responses WHERE Key_name = 'uq_sheet_row'")
if not cursor.fetchone():
    cursor.execute("ALTER TABLE responses ADD UNIQUE INDEX uq_sheet_row (sheet_row)")
    conn.commit()
    print("✓ UNIQUE index (sheet_row) нэмэгдлээ.")
else:
    print("✓ UNIQUE index аль хэдийн байна.")

cursor.close()
conn.close()
print("Migration дууслаа.")
