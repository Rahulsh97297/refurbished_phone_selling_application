import sqlite3

DB_NAME = "phones.db"

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS phones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand TEXT,
            model TEXT,
            price REAL,
            condition TEXT
        )
    """)
    # Add default admin if not exists
    user = conn.execute("SELECT * FROM users WHERE username=?", ("admin",)).fetchone()
    if not user:
        conn.execute("INSERT INTO users (username, password) VALUES (?, ?)", ("admin", "admin123"))
    conn.commit()
    conn.close()
