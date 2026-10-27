import os
import sqlite3
from datetime import datetime

DB_PATH = os.getenv("VERNIER_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "vernier.db"))

TABLES = {"lost_found", "events", "listings", "machines", "bookings", "students", "outbox"}


def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with connect() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS lost_found(
            id INTEGER PRIMARY KEY, kind TEXT, item TEXT, colour TEXT, place TEXT,
            details TEXT, contact TEXT, source TEXT, status TEXT DEFAULT 'open', created TEXT);
        CREATE TABLE IF NOT EXISTS events(
            id INTEGER PRIMARY KEY, title TEXT, category TEXT, date TEXT, venue TEXT,
            details TEXT, major INTEGER, source TEXT, created TEXT);
        CREATE TABLE IF NOT EXISTS listings(
            id INTEGER PRIMARY KEY, kind TEXT, item TEXT, price TEXT, details TEXT,
            contact TEXT, status TEXT DEFAULT 'open', created TEXT);
        CREATE TABLE IF NOT EXISTS machines(
            id TEXT PRIMARY KEY, location TEXT, status TEXT, updated TEXT);
        CREATE TABLE IF NOT EXISTS bookings(
            id INTEGER PRIMARY KEY, room TEXT, day TEXT, start TEXT, end TEXT, booked_by TEXT);
        CREATE TABLE IF NOT EXISTS students(
            contact TEXT PRIMARY KEY, interests TEXT, level TEXT);
        CREATE TABLE IF NOT EXISTS outbox(
            id INTEGER PRIMARY KEY, to_chat TEXT, text TEXT, sent INTEGER DEFAULT 0, created TEXT);
        """)


def now():
    return datetime.now().isoformat(timespec="seconds")


def rows(sql, params=()):
    with connect() as con:
        return [dict(r) for r in con.execute(sql, params)]


def execute(sql, params=()):
    with connect() as con:
        return con.execute(sql, params).lastrowid


def queue(to_chat, text):
    if to_chat:
        execute("INSERT INTO outbox(to_chat, text, created) VALUES (?,?,?)", (to_chat, text, now()))


def take_outbox(limit=20):
    with connect() as con:
        items = [dict(r) for r in con.execute(
            "SELECT id,to_chat,text FROM outbox WHERE sent=0 ORDER BY id LIMIT ?", (limit,))]
        con.executemany("UPDATE outbox SET sent=1 WHERE id=?", [(r["id"],) for r in items])
    return items
