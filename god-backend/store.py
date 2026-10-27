"""All SQLite access for the combined Vernier backend."""

import json
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

DB_PATH = Path(os.environ.get("VERNIER_DB", Path(__file__).with_name("vernier.db")))
RECORD_TABLES = {"items", "events", "listings", "machines", "bookings", "students", "claim_requests", "outbox"}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect():
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        with con:
            yield con
    finally:
        con.close()


def _create_items(con, name="items"):
    con.execute(f"""CREATE TABLE {name} (
        id INTEGER PRIMARY KEY,
        kind TEXT NOT NULL CHECK(kind IN ('lost','found')),
        item TEXT NOT NULL,
        color TEXT,
        place TEXT,
        desc_using_keywords TEXT,
        custom_string TEXT,
        image_href TEXT,
        please_consult_this_person TEXT,
        source TEXT NOT NULL CHECK(source IN ('chat','camera')),
        reporter TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL,
            alerts_enabled INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    )""")


def init_db():
    """Create feature tables and migrate older local item records without deleting them."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as con:
        exists = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='items'").fetchone()
        if not exists:
            _create_items(con)
        else:
            cols = {r["name"]: r for r in con.execute("PRAGMA table_info(items)")}
            required = {"desc_using_keywords", "custom_string", "image_href", "please_consult_this_person"}
            if not required.issubset(cols) or cols["color"]["notnull"] or cols["place"]["notnull"]:
                _create_items(con, "items_migrated")
                for old_row in con.execute("SELECT * FROM items").fetchall():
                    old = dict(old_row)
                    color = old.get("color") or None
                    status = old["status"]
                    if old["kind"] == "found" and status == "open":
                        status = "unclaimed"
                    con.execute("""INSERT INTO items_migrated
                        (id,kind,item,color,place,desc_using_keywords,custom_string,image_href,
                         please_consult_this_person,source,reporter,status,alerts_enabled,created_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0,?)""",
                        (old["id"], old["kind"], old["item"], color, old.get("place") or None,
                         old.get("desc_using_keywords") or (json.dumps([color]) if color else None),
                         old.get("custom_string"), old.get("image_href"),
                         old.get("please_consult_this_person"), old.get("source", "chat"),
                         old.get("reporter", ""), status, old["created_at"]))
                con.execute("DROP TABLE items")
                con.execute("ALTER TABLE items_migrated RENAME TO items")
        con.executescript("""
            CREATE TABLE IF NOT EXISTS processed_messages (
                message_id TEXT PRIMARY KEY, reply TEXT NOT NULL, action TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS match_notifications (
                lost_id INTEGER NOT NULL, found_id INTEGER NOT NULL,
                PRIMARY KEY(lost_id, found_id));
            CREATE TABLE IF NOT EXISTS claim_requests (
                id INTEGER PRIMARY KEY, item_id INTEGER NOT NULL, contact TEXT NOT NULL,
                details TEXT, status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL,
                UNIQUE(item_id, contact));
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY, title TEXT NOT NULL, category TEXT NOT NULL,
                date TEXT, venue TEXT, details TEXT, major INTEGER NOT NULL DEFAULT 0,
                source TEXT, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS listings (
                id INTEGER PRIMARY KEY, kind TEXT NOT NULL CHECK(kind IN ('buy','sell')),
                item TEXT NOT NULL, price TEXT, details TEXT, contact TEXT,
                status TEXT NOT NULL DEFAULT 'open', alerts_enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS machines (
                id TEXT PRIMARY KEY, location TEXT NOT NULL, status TEXT NOT NULL,
                updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY, room TEXT NOT NULL, day TEXT NOT NULL,
                start TEXT NOT NULL, end TEXT NOT NULL, booked_by TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'booked', created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS students (
                contact TEXT PRIMARY KEY, interests TEXT NOT NULL, level TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS outbox (
                id INTEGER PRIMARY KEY, to_chat TEXT NOT NULL, text TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL, leased_at TEXT, sent_at TEXT);
            CREATE TABLE IF NOT EXISTS legacy_imports (
                source_name TEXT NOT NULL, table_name TEXT NOT NULL, source_key TEXT NOT NULL,
                local_id TEXT NOT NULL, PRIMARY KEY(source_name,table_name,source_key));
            CREATE INDEX IF NOT EXISTS idx_items_lookup ON items(kind,status,id);
            CREATE INDEX IF NOT EXISTS idx_outbox_state ON outbox(state,id);
            CREATE INDEX IF NOT EXISTS idx_bookings_slot ON bookings(room,day,start,end);
        """)
        # Existing records predate explicit alert consent. Preserve them but keep
        # them out of automatic notifications until the sender subscribes again.
        for table, column in (("items", "alerts_enabled"),
                              ("listings", "alerts_enabled"), ("students", "active")):
            cols = {r["name"] for r in con.execute(f"PRAGMA table_info({table})")}
            if column not in cols:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {column} INTEGER NOT NULL DEFAULT 1")
                con.execute(f"UPDATE {table} SET {column}=0")


def _text(value, limit, *, required=False):
    if value is None and not required:
        return None
    if not isinstance(value, str):
        raise ValueError("Expected text")
    value = value.strip()
    if required and not value:
        raise ValueError("Required text is empty")
    return value[:limit] or None


def _words(value):
    return {w.casefold() for w in re.findall(r"\w+", value or "") if len(w) > 2}


def _whatsapp_contact(value):
    return isinstance(value, str) and bool(re.search(r"@(?:c\.us|lid)$", value))


def add_item(*, kind, item, color=None, place=None, source="chat", reporter="",
             desc_using_keywords=None, custom_string=None, image_href=None,
             please_consult_this_person=None, created_at=None):
    if kind not in {"lost", "found"} or source not in {"chat", "camera"}:
        raise ValueError("Invalid item kind or source")
    item = _text(item, 120, required=True)
    color, place = _text(color, 60), _text(place, 120)
    if desc_using_keywords is not None and (not isinstance(desc_using_keywords, list) or
                                            not all(isinstance(w, str) for w in desc_using_keywords)):
        raise ValueError("Description keywords must be a list of text")
    keywords = list(dict.fromkeys(w.strip()[:40] for w in (desc_using_keywords or []) if w.strip()))[:20]
    if color and color not in keywords:
        keywords.insert(0, color)
    image_href = _text(image_href, 500)
    if image_href and urlparse(image_href).scheme not in {"http", "https"}:
        raise ValueError("Image href must be an HTTP or HTTPS URL")
    with connect() as con:
        cur = con.execute("""INSERT INTO items
            (kind,item,color,place,desc_using_keywords,custom_string,image_href,
             please_consult_this_person,source,reporter,status,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (kind, item, color, place, json.dumps(keywords, ensure_ascii=False) if keywords else None,
             _text(custom_string, 500), image_href, _text(please_consult_this_person, 120),
             source, _text(reporter, 200) or "", "unclaimed" if kind == "found" else "open",
             created_at or now()))
        return cur.lastrowid


def _public_item(row):
    d = dict(row)
    keywords = json.loads(d["desc_using_keywords"]) if d["desc_using_keywords"] else None
    return {"id": d["id"], "kind": d["kind"], "name": d["item"],
            "item": d["item"], "color": d["color"], "place": d["place"],
            "descUsingKeywords": keywords, "dateTime": d["created_at"],
            "created_at": d["created_at"],
            "foundAt": d["place"] if d["kind"] == "found" else None,
            "customString": d["custom_string"], "imageHref": d["image_href"],
            "pleaseConsultThisPerson": d["please_consult_this_person"],
            "source": d["source"], "status": d["status"]}


def get_item(item_id):
    with connect() as con:
        row = con.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
    return dict(row) if row else None


def list_items(limit=50, *, kind=None, status=None):
    if kind and kind not in {"lost", "found"}:
        raise ValueError("Invalid kind")
    query, args = "SELECT * FROM items WHERE 1=1", []
    if kind:
        query += " AND kind=?"
        args.append(kind)
    if status:
        query += " AND status=?"
        args.append(status)
    query += " ORDER BY id DESC LIMIT ?"
    args.append(min(max(int(limit), 1), 200))
    with connect() as con:
        return [_public_item(r) for r in con.execute(query, args)]


def list_unclaimed_found():
    with connect() as con:
        return [_public_item(r) for r in con.execute(
            "SELECT * FROM items WHERE kind='found' AND status='unclaimed' ORDER BY id DESC")]


def list_open_lost():
    with connect() as con:
        return [_public_item(r) for r in con.execute(
            "SELECT * FROM items WHERE kind='lost' AND status='open' ORDER BY id DESC")]


def list_found_items():
    with connect() as con:
        return [_public_item(r) for r in con.execute(
            "SELECT * FROM items WHERE kind='found' ORDER BY id DESC")]


def find_items(*, kind, item, limit=10):
    wanted = _words(item)
    if not wanted:
        return []
    status = "unclaimed" if kind == "found" else "open"
    rows = list_items(200, kind=kind, status=status)
    return [r for r in rows if wanted & _words(r["item"])][:limit]


def find_matches(item_id, *, limit=5):
    source = get_item(item_id)
    if not source:
        raise ValueError("Unknown item ID")
    opposite = "found" if source["kind"] == "lost" else "lost"
    target_status = "unclaimed" if opposite == "found" else "open"
    with connect() as con:
        rows = [dict(r) for r in con.execute(
            "SELECT * FROM items WHERE kind=? AND status=? AND id<>? ORDER BY id DESC LIMIT 200",
            (opposite, target_status, item_id))]
    source_words = _words(source["item"])
    ranked = []
    for row in rows:
        words = _words(row["item"])
        if not source_words & words:
            continue
        score = len(source_words & words) / len(source_words | words)
        if source["color"] and row["color"]:
            score += 0.25 if source["color"].casefold() == row["color"].casefold() else -0.25
        if score >= 0.5:
            ranked.append((score, row))
    ranked.sort(key=lambda pair: (-pair[0], -pair[1]["id"]))
    return [row for _, row in ranked[:limit]]


def queue(to_chat, message):
    to_chat = _text(to_chat, 200)
    message = _text(message, 2000)
    if not to_chat or not message or not _whatsapp_contact(to_chat):
        return None
    with connect() as con:
        return con.execute("INSERT INTO outbox(to_chat,text,created_at) VALUES (?,?,?)",
                           (to_chat, message, now())).lastrowid


def alert_lost_reporters(found_id):
    found = get_item(found_id)
    if not found or found["kind"] != "found":
        return []
    matches = find_matches(found_id)
    queued = []
    with connect() as con:
        for lost in matches:
            if not lost["alerts_enabled"] or not _whatsapp_contact(lost["reporter"]):
                continue
            cur = con.execute("INSERT OR IGNORE INTO match_notifications(lost_id,found_id) VALUES (?,?)",
                              (lost["id"], found_id))
            if cur.rowcount:
                description = " ".join(v for v in (found["color"], found["item"]) if v)
                place = f" at {found['place']}" if found["place"] else ""
                con.execute("INSERT INTO outbox(to_chat,text,created_at) VALUES (?,?,?)",
                            (lost["reporter"], f"Possible match for your lost item: {description}{place} (#{found_id}). Ask the lost-and-found desk to verify ownership.", now()))
                queued.append(lost["id"])
    return queued


def request_claim(item_id, contact, details=None):
    item = get_item(item_id)
    if not item or item["kind"] != "found" or item["status"] != "unclaimed":
        raise ValueError("That found item is not available to claim")
    contact = _text(contact, 200, required=True)
    details = _text(details, 500)
    with connect() as con:
        con.execute("""INSERT INTO claim_requests(item_id,contact,details,created_at)
            VALUES (?,?,?,?) ON CONFLICT(item_id,contact) DO UPDATE SET details=excluded.details""",
            (item_id, contact, details, now()))


def set_claim_status(item_id, claimed):
    if not isinstance(item_id, int) or item_id <= 0 or not isinstance(claimed, bool):
        raise ValueError("A found item ID and claimed state are required")
    with connect() as con:
        cur = con.execute("UPDATE items SET status=? WHERE id=? AND kind='found'",
                          ("claimed" if claimed else "unclaimed", item_id))
        if not cur.rowcount:
            raise ValueError("Found item ID does not exist")


def get_processed(message_id):
    if not message_id:
        return None
    with connect() as con:
        row = con.execute("SELECT reply,action FROM processed_messages WHERE message_id=?", (message_id,)).fetchone()
    return dict(row) if row else None


def save_processed(message_id, reply, action):
    if message_id:
        with connect() as con:
            con.execute("INSERT OR IGNORE INTO processed_messages(message_id,reply,action) VALUES (?,?,?)",
                        (message_id, reply or "", action))


def save_interests(contact, interests, level):
    contact = _text(contact, 200, required=True)
    if level not in {"all", "major"}:
        raise ValueError("Level must be all or major")
    if not isinstance(interests, list):
        raise ValueError("Interests must be a list")
    values = list(dict.fromkeys(_text(v, 40, required=True).casefold() for v in interests))[:20]
    with connect() as con:
        con.execute("""INSERT INTO students(contact,interests,level,active) VALUES (?,?,?,1)
            ON CONFLICT(contact) DO UPDATE SET interests=excluded.interests,level=excluded.level,active=1""",
            (contact, json.dumps(values), level))
    return values


def add_event(*, title, category="other", date=None, venue=None, details=None, major=False, source=None):
    title = _text(title, 160, required=True)
    category = _text(category, 40) or "other"
    with connect() as con:
        cur = con.execute("""INSERT INTO events(title,category,date,venue,details,major,source,created_at)
            VALUES (?,?,?,?,?,?,?,?)""",
            (title, category, _text(date, 100), _text(venue, 120), _text(details, 4000),
             int(bool(major)), _text(source, 200), now()))
        event_id = cur.lastrowid
        for student in con.execute("SELECT * FROM students WHERE active=1"):
            interests = json.loads(student["interests"])
            if _whatsapp_contact(student["contact"]) and category.casefold() in interests and (
                    student["level"] == "all" or major):
                summary = f"New {category} update: {title}"
                if date:
                    summary += f" on {date}"
                if venue:
                    summary += f" at {venue}"
                con.execute("INSERT INTO outbox(to_chat,text,created_at) VALUES (?,?,?)",
                            (student["contact"], summary[:2000], now()))
    return event_id


def list_events(limit=20):
    with connect() as con:
        return [dict(r) for r in con.execute(
            "SELECT id,title,category,date,venue,major,created_at FROM events ORDER BY id DESC LIMIT ?",
            (min(limit, 200),))]


def add_listing(*, kind, item, price=None, details=None, contact=None):
    if kind not in {"buy", "sell"}:
        raise ValueError("Invalid listing kind")
    item = _text(item, 120, required=True)
    with connect() as con:
        cur = con.execute("""INSERT INTO listings(kind,item,price,details,contact,created_at)
            VALUES (?,?,?,?,?,?)""",
            (kind, item, _text(price, 80), _text(details, 4000), _text(contact, 200), now()))
        listing_id = cur.lastrowid
        opposite = "buy" if kind == "sell" else "sell"
        matches = [dict(r) for r in con.execute(
            "SELECT * FROM listings WHERE kind=? AND status='open' AND id<>?", (opposite, listing_id))
            if _words(item) & _words(r["item"])]
        if kind == "sell":
            for match in matches:
                if match["alerts_enabled"] and _whatsapp_contact(match["contact"]):
                    con.execute("INSERT INTO outbox(to_chat,text,created_at) VALUES (?,?,?)",
                                (match["contact"], f"Someone listed a {item} for sale. Ask Vernier about current listings.", now()))
    return listing_id, len(matches)


def list_listings(limit=20):
    with connect() as con:
        return [dict(r) for r in con.execute(
            "SELECT id,kind,item,price,details,created_at FROM listings WHERE status='open' ORDER BY id DESC LIMIT ?",
            (min(limit, 200),))]


def book_room(room, day, start, end, booked_by):
    room = _text(room, 120, required=True)
    try:
        datetime.strptime(day, "%Y-%m-%d")
        start_time = datetime.strptime(start, "%H:%M").time()
        end_time = datetime.strptime(end, "%H:%M").time()
    except (TypeError, ValueError):
        raise ValueError("Use YYYY-MM-DD for day and HH:MM for times") from None
    if start_time >= end_time:
        raise ValueError("End time must be after start time")
    with connect() as con:
        con.execute("BEGIN IMMEDIATE")
        overlap = con.execute("""SELECT 1 FROM bookings WHERE lower(room)=lower(?) AND day=?
            AND status='booked' AND start<? AND end>? LIMIT 1""", (room, day, end, start)).fetchone()
        if overlap:
            return None
        return con.execute("""INSERT INTO bookings(room,day,start,end,booked_by,created_at)
            VALUES (?,?,?,?,?,?)""", (room, day, start, end, _text(booked_by, 200) or "", now())).lastrowid


def list_bookings(day=None, room=None):
    day = day or datetime.now().date().isoformat()
    with connect() as con:
        return [dict(r) for r in con.execute("""SELECT id,room,day,start,end,status FROM bookings
            WHERE day=? AND (? IS NULL OR lower(room)=lower(?)) ORDER BY start""", (day, room, room))]


def set_machine(machine_id, location, status):
    machine_id = _text(machine_id, 80, required=True)
    location = _text(location, 160, required=True)
    status = _text(status, 80, required=True)
    with connect() as con:
        con.execute("""INSERT INTO machines(id,location,status,updated_at) VALUES (?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET location=excluded.location,status=excluded.status,
            updated_at=excluded.updated_at""", (machine_id, location, status, now()))


def list_machines():
    with connect() as con:
        return [dict(r) for r in con.execute("SELECT id,location,status,updated_at FROM machines ORDER BY location")]


def lease_outbox(limit=20):
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat(timespec="seconds")
    with connect() as con:
        con.execute("BEGIN IMMEDIATE")
        rows = [dict(r) for r in con.execute("""SELECT id,to_chat,text FROM outbox
            WHERE state='pending' OR (state='leased' AND leased_at<?)
            ORDER BY id LIMIT ?""", (cutoff, min(limit, 100)))]
        for row in rows:
            con.execute("UPDATE outbox SET state='leased',leased_at=?,attempts=attempts+1 WHERE id=?",
                        (now(), row["id"]))
    return rows


def finish_outbox(outbox_id, sent):
    with connect() as con:
        cur = con.execute("UPDATE outbox SET state=?,sent_at=?,leased_at=NULL WHERE id=? AND state='leased'",
                          ("sent" if sent else "pending", now() if sent else None, outbox_id))
        if not cur.rowcount:
            raise ValueError("Unknown or inactive outbox message")


def records(table, limit=200):
    if table not in RECORD_TABLES:
        raise ValueError("Unknown table")
    with connect() as con:
        return [dict(r) for r in con.execute(f"SELECT * FROM {table} ORDER BY rowid DESC LIMIT ?", (min(limit, 200),))]
