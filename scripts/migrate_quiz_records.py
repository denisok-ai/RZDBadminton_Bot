#!/usr/bin/env python3
"""
Однократная миграция: добавить в таблицу quiz_records колонки correct_answer и explanation
(для публикации правильного ответа на квиз в пятницу 21:00).

Запуск из корня проекта:
  python3 scripts/migrate_quiz_records.py

Читает DATABASE_URL из .env (или по умолчанию sqlite+aiosqlite:///./data/badminton_bot.db).
"""
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def main() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass
    url = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./data/badminton_bot.db") or ""
    if not url.startswith("sqlite"):
        print("Миграция только для SQLite. DATABASE_URL:", url[:50] + "...")
        sys.exit(1)
    # sqlite+aiosqlite:///./data/badminton_bot.db -> data/badminton_bot.db
    path = url.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "").strip()
    if path.startswith("./"):
        path = path[2:]
    db_path = ROOT / path
    if not db_path.exists():
        print("Файл БД не найден:", db_path)
        sys.exit(1)
    conn = sqlite3.connect(str(db_path))
    cur = conn.execute("PRAGMA table_info(quiz_records)")
    columns = [row[1] for row in cur.fetchall()]
    if "correct_answer" not in columns:
        conn.execute("ALTER TABLE quiz_records ADD COLUMN correct_answer VARCHAR(500)")
        print("Добавлена колонка quiz_records.correct_answer")
    else:
        print("Колонка correct_answer уже есть")
    if "explanation" not in columns:
        conn.execute("ALTER TABLE quiz_records ADD COLUMN explanation TEXT")
        print("Добавлена колонка quiz_records.explanation")
    else:
        print("Колонка explanation уже есть")
    conn.commit()
    conn.close()
    print("Миграция завершена.")

if __name__ == "__main__":
    main()
