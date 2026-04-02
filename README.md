# ChatGPT Crawler — Google Sheets → ChatGPT → MySQL

Google Sheets-с prompt уншиж, браузераар ChatGPT-д илгээж, хариуг MySQL-д хадгалах автомат систем.

---

## Бүтэц

```
chatgpt_crawler/
├── src/
│   ├── sheets_reader.py     # Google Sheets-с prompt унших
│   ├── chatgpt_bot.py       # Selenium-р ChatGPT автоматжуулах
│   ├── db.py                # MySQL холболт ба хадгалах
│   └── config.py            # Тохиргоо (.env-с уншина)
├── sql/
│   └── init.sql             # DB table үүсгэх
├── tests/
│   └── test_sheets.py       # Тест
├── main.py                  # Үндсэн ажиллуулах файл
├── .env.example             # Тохиргооны жишээ
└── requirements.txt
```

---

## Алхам 1 — Суулгах

```bash
pip3 install -r requirements.txt
```

Chrome browser суулгасан байх шаардлагатай.

---

## Алхам 2 — Google Sheets тохиргоо

1. [Google Cloud Console](https://console.cloud.google.com/) нээнэ
2. Шинэ project үүсгэнэ
3. **Google Sheets API** идэвхжүүлнэ
4. **Service Account** үүсгэнэ → JSON key татаж авна
5. JSON файлыг `credentials.json` нэрээр project folder-т хуулна
6. Google Sheet-ийн **Share** дээр дарж service account email-г нэмнэ (viewer эрхтэй)

Google Sheet-ийн бүтэц:

| prompt | status | response |
|--------|--------|----------|
| Монгол улсын нийслэл хаана вэ? | pending | |
| Python гэж юу вэ? | pending | |

---

## Алхам 3 — MySQL тохиргоо

```bash
mysql -u root -p < sql/init.sql
```

---

## Алхам 4 — .env тохиргоо

`.env.example`-г хуулж `.env` үүсгэнэ:

```bash
cp .env.example .env
```

Дараа нь `.env` файлд өөрийн утгуудыг бөглөнө.

---

## Алхам 5 — Ажиллуулах

```bash
python main.py
```

Браузер автоматаар нээгдэнэ. ChatGPT-д нэвтэрсэн байх шаардлагатай.
Хэрэв анх удаа ажиллуулж байгаа бол `HEADLESS=false` байлгаж гараар нэвтэрнэ.

---

## Тэмдэглэл

- ChatGPT-д rate limit байдаг тул prompt бүрийн дараа **5-10 секунд** хүлээнэ
- `status` баганыг `done` болгосон prompt-уудыг дахин илгээхгүй
- Selenium Chrome profile хадгалдаг тул дахин нэвтрэх шаардлагагүй болно
# playwright
