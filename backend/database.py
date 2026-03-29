import sqlite3
import threading

from config import DATABASE_PATH


DATABASE_LOCK = threading.Lock()


def get_connection():
    connection = sqlite3.connect(DATABASE_PATH, timeout=30, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    connection.execute("PRAGMA journal_mode = WAL;")
    return connection


def fetch_all(query, params=()):
    with get_connection() as connection:
        cursor = connection.execute(query, params)
        rows = cursor.fetchall()
    return [dict(row) for row in rows]


def fetch_one(query, params=()):
    with get_connection() as connection:
        cursor = connection.execute(query, params)
        row = cursor.fetchone()
    return dict(row) if row else None


def execute_write(query, params=()):
    with DATABASE_LOCK:
        with get_connection() as connection:
            cursor = connection.execute(query, params)
            connection.commit()
            return cursor.lastrowid


def execute_many(query, parameter_sets):
    with DATABASE_LOCK:
        with get_connection() as connection:
            connection.executemany(query, parameter_sets)
            connection.commit()
