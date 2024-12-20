import sqlite3
import os
from datetime import datetime

# Определяем путь к базе данных
DB_PATH = os.path.expandvars(os.path.join(os.environ.get("CONFIG_DIR", "/config"), "directories.db"))

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Создаем таблицу directories с колонкой logs, если она еще не существует
    c.execute('''CREATE TABLE IF NOT EXISTS directories
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  path TEXT UNIQUE,
                  status TEXT,
                  last_update TEXT,
                  logs TEXT)''')
    # Проверяем, существует ли колонка logs, если нет — добавляем
    c.execute("PRAGMA table_info(directories)")
    columns = [info[1] for info in c.fetchall()]
    if 'logs' not in columns:
        c.execute("ALTER TABLE directories ADD COLUMN logs TEXT")
    conn.commit()
    conn.close()

def update_directory_status(path, status, logs=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Вставляем новую запись, если ее нет
    c.execute("INSERT OR IGNORE INTO directories (path, status, last_update, logs) VALUES (?, ?, ?, ?)",
              (path, status, datetime.now().isoformat(), logs if logs else ""))
    # Обновляем статус и логи
    if logs is not None:
        c.execute("UPDATE directories SET status=?, last_update=?, logs=? WHERE path=?",
                  (status, datetime.now().isoformat(), logs, path))
    else:
        c.execute("UPDATE directories SET status=?, last_update=? WHERE path=?",
                  (status, datetime.now().isoformat(), path))
    conn.commit()
    conn.close()

def get_directory_status(path):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT status, last_update, logs FROM directories WHERE path=?", (path,))
    row = c.fetchone()
    conn.close()
    if row:
        return row[0], row[1], row[2]
    return None, None, None

def get_all_directories():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT path, status, last_update, logs FROM directories")
    rows = c.fetchall()
    conn.close()
    return rows
