import json
import re
import sqlite3
from datetime import datetime

import requests
from fastapi import FastAPI
from pydantic import BaseModel

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3:4b"
DB_PATH = "vernier.db"

app = FastAPI(title="Vernier backend")


def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with db() as con:
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


init_db()


def now():
    return datetime.now().isoformat(timespec="seconds")


INTENTS = ["lost_report", "found_report", "event_post", "sell_post", "buy_request",
           "ask_lost", "ask_events", "ask_room", "book_room", "ask_laundry",
           "ask_listings", "ask_person", "chit_chat", "other"]

SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": INTENTS},
        "item": {"type": "string"},
        "colour": {"type": "string"},
        "place": {"type": "string"},
        "title": {"type": "string"},
        "category": {"type": "string", "enum": ["sports", "music", "dance", "theatre", "culture", "tech", "academic", "other"]},
        "date": {"type": "string"},
        "venue": {"type": "string"},
        "major": {"type": "boolean"},
        "price": {"type": "string"},
        "room": {"type": "string"},
        "start": {"type": "string"},
        "end": {"type": "string"},
        "machine": {"type": "string"},
    },
    "required": ["intent"],
}

EXTRACT_PROMPT = """You read WhatsApp messages from a college campus in India (English, Hindi or Hinglish).
Return JSON only. Pick the intent:
- lost_report: someone says they lost something ("lost my black bottle in library", "mera charger kho gaya")
- found_report: someone found something ("found a blue jacket in canteen", "ye earphones mile hai")
- event_post: an event, audition, recruitment, match or registration announcement
- sell_post: someone selling an item; buy_request: someone wants to buy an item
- ask_lost: asking the bot if their lost item was found
- ask_events: asking about events; ask_listings: asking what is for sale
- ask_room: asking if a room is free; book_room: asking to book a room
- ask_laundry: asking if a washing machine is free
- ask_person: asking where a specific person is, their location, room, or whereabouts ("where is Rahul right now", "Priya kaha hai")
- chit_chat / other: anything else
Fill item (short noun, e.g. "earbuds"), colour, place, title, category, date, venue, major (true only for big official or fest-level events),
price, room (e.g. "music room"), start and end as HH:MM 24h, machine (e.g. "8th floor boys hostel"). Leave unknown fields empty.
Today is {today}."""


def llm(messages, schema=None):
    payload = {"model": MODEL, "messages": messages, "stream": False, "think": False,
               "options": {"temperature": 0}}
    if schema:
        payload["format"] = schema
    r = requests.post(OLLAMA_URL, json=payload, timeout=120)
    r.raise_for_status()
    text = r.json()["message"]["content"]
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


def extract(text):
    raw = llm([
        {"role": "system", "content": EXTRACT_PROMPT.replace("{today}", datetime.now().strftime("%A %d %B %Y"))},
        {"role": "user", "content": text},
    ], SCHEMA)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"intent": "other"}
    if data.get("intent") not in INTENTS:
        data["intent"] = "other"
    return data


def write_reply(question, records):
    return llm([
        {"role": "system", "content": "You are Vernier, a friendly campus WhatsApp assistant. Answer in at most 3 short lines, "
                                      "using ONLY the records given. If no record answers it, say so and suggest what the student can do. "
                                      "Never invent items, events, rooms or times. Reply in the same language style as the student."},
        {"role": "user", "content": f"Student asked: {question}\n\nRecords (JSON):\n{json.dumps(records, ensure_ascii=False)}"},
    ])


KEYWORDS = re.compile(
    r"lost|found|missing|kho|mila|mile|charger|bottle|wallet|earbud|earphone|airpod|bag|jacket|id card|keys|"
    r"sell|selling|buy|khareed|price|rs\.?|₹|event|audition|recruit|register|registration|fest|match|tournament|"
    r"workshop|club|room|book|washing|machine|laundry", re.I)

PERSON_REFUSAL = "I can't share where any student is. I only help with items, events, rooms and laundry."

BLOCKED = [
    (re.compile(r"live location|track (him|her|someone|my friend)|where is (he|she)\b", re.I), PERSON_REFUSAL),
    (re.compile(r"camera.{0,30}(show|see|dekh|dikha|photo|feed|footage|video)|(show|send).{0,20}(camera|cctv|footage)", re.I),
     "I can't share camera views. Cameras only tell me what's on the lost & found shelf and if a machine is free."),
]


def tokens(s):
    return {w for w in re.findall(r"[a-z0-9]+", (s or "").lower()) if len(w) > 2}


def match_score(a, b):
    ta = tokens(f"{a['item']} {a['colour']}")
    tb = tokens(f"{b['item']} {b['colour']}")
    if not ta or not tb or not (tokens(a["item"]) & tokens(b["item"])):
        return 0.0
    return len(ta & tb) / len(ta | tb)


def find_matches(row, kind_wanted):
    with db() as con:
        cands = [dict(r) for r in con.execute(
            "SELECT * FROM lost_found WHERE kind=? AND status='open'", (kind_wanted,))]
    scored = [(match_score(row, c), c) for c in cands]
    return [c for s, c in sorted(scored, key=lambda x: -x[0]) if s >= 0.4]


def queue(to_chat, text):
    if not to_chat:
        return
    with db() as con:
        con.execute("INSERT INTO outbox(to_chat, text, created) VALUES (?,?,?)", (to_chat, text, now()))


def add_lost_found(kind, data, contact, source):
    row = {"kind": kind, "item": data.get("item", ""), "colour": data.get("colour", ""),
           "place": data.get("place", ""), "details": data.get("details", ""),
           "contact": contact, "source": source}
    with db() as con:
        cur = con.execute(
            "INSERT INTO lost_found(kind,item,colour,place,details,contact,source,created) VALUES (?,?,?,?,?,?,?,?)",
            (row["kind"], row["item"], row["colour"], row["place"], row["details"], contact, source, now()))
        row["id"] = cur.lastrowid
    return row


def describe(r):
    return " ".join(x for x in [r.get("colour"), r.get("item")] if x).strip() or "item"


def handle_found(row):
    for lost in find_matches(row, "lost"):
        where = f"It's on the lost & found shelf ({row['place']})." if row["source"] == "camera" else f"Someone found it near {row['place'] or 'campus'}."
        queue(lost["contact"], f"Good news! Something matching your lost {describe(lost)} turned up: {describe(row)}. {where} "
                               f"Reply 'claim {row['id']}' and tell me one detail only the owner would know.")
        return lost
    return None


def handle_lost(row):
    matches = find_matches(row, "found")
    if matches:
        f = matches[0]
        where = f"on the lost & found shelf ({f['place']})" if f["source"] == "camera" else f"reported near {f['place'] or 'campus'}"
        return (f"Possible match: {describe(f)}, {where}. Reply 'claim {f['id']}' and tell me one detail "
                f"only the owner would know (a sticker, scratch, case colour).")
    return f"Noted your lost {describe(row)}. I'll message you the moment something similar turns up."


def notify_interested(event):
    with db() as con:
        students = [dict(r) for r in con.execute("SELECT * FROM students")]
    for s in students:
        interests = [i.strip().lower() for i in (s["interests"] or "").split(",")]
        if event["category"] in interests and (s["level"] == "all" or event["major"]):
            queue(s["contact"], f"New {event['category']} update: {event['title']}"
                                + (f" on {event['date']}" if event["date"] else "")
                                + (f" at {event['venue']}" if event["venue"] else ""))


def overlaps(a_start, a_end, b_start, b_end):
    return a_start < b_end and b_start < a_end


class Incoming(BaseModel):
    chat_id: str
    chat_name: str = ""
    is_group: bool = False
    author: str
    text: str
    mentioned: bool = False


@app.post("/message")
def message(m: Incoming):
    text = m.text.strip()
    if not text:
        return {"reply": None}
    should_reply = (not m.is_group) or m.mentioned
    low = text.lower()

    if should_reply:
        for pattern, answer in BLOCKED:
            if pattern.search(text):
                return {"reply": answer}

    if not m.is_group and low.startswith("interests:"):
        parts = text.split(":", 1)[1]
        level = "major" if "major" in parts.lower() else "all"
        interests = re.sub(r"(?i)level\s*[:=]?\s*(major|all)|major only|major", "", parts)
        interests = ",".join(t.strip().lower() for t in re.split(r"[,;/]", interests) if t.strip())
        with db() as con:
            con.execute("INSERT OR REPLACE INTO students(contact, interests, level) VALUES (?,?,?)",
                        (m.author, interests, level))
        return {"reply": f"Saved! You'll get {'only major' if level == 'major' else 'all'} updates for: {interests}."}

    claim = re.match(r"claim\s+(\d+)\s*(.*)", low)
    if claim and not m.is_group:
        with db() as con:
            con.execute("UPDATE lost_found SET status='claim_pending' WHERE id=?", (int(claim.group(1)),))
        return {"reply": "Thanks! Your claim is noted. Collect it from the lost & found desk with your college ID."}

    if m.is_group and not m.mentioned and not KEYWORDS.search(text):
        return {"reply": None}

    data = extract(text)
    intent = data["intent"]
    data["details"] = text
    reply = None

    if intent == "ask_person":
        return {"reply": PERSON_REFUSAL if should_reply else None, "intent": intent}

    if intent == "lost_report":
        row = add_lost_found("lost", data, m.author, "chat")
        reply = handle_lost(row)
        if m.is_group and not m.mentioned:
            queue(m.author, reply)
            reply = None
    elif intent == "found_report":
        row = add_lost_found("found", data, m.author, "chat")
        matched = handle_found(row)
        reply = "Thanks! I've logged it" + (" and pinged someone who lost a similar item." if matched else ".")
    elif intent == "event_post":
        ev = {"title": data.get("title") or text[:80], "category": data.get("category", "other"),
              "date": data.get("date", ""), "venue": data.get("venue", ""), "major": bool(data.get("major"))}
        with db() as con:
            con.execute("INSERT INTO events(title,category,date,venue,details,major,source,created) VALUES (?,?,?,?,?,?,?,?)",
                        (ev["title"], ev["category"], ev["date"], ev["venue"], text, int(ev["major"]), m.chat_name, now()))
        notify_interested(ev)
        reply = "Event noted. I'll tell students who follow " + ev["category"] + "."
    elif intent in ("sell_post", "buy_request"):
        kind = "sell" if intent == "sell_post" else "buy"
        with db() as con:
            con.execute("INSERT INTO listings(kind,item,price,details,contact,created) VALUES (?,?,?,?,?,?)",
                        (kind, data.get("item", ""), data.get("price", ""), text, m.author, now()))
            other = [dict(r) for r in con.execute(
                "SELECT * FROM listings WHERE kind=? AND status='open'", ("buy" if kind == "sell" else "sell",))]
        hits = [o for o in other if tokens(o["item"]) & tokens(data.get("item", ""))]
        for o in hits:
            if kind == "sell":
                queue(o["contact"], f"Someone is selling a {data.get('item')} {('for ' + data['price']) if data.get('price') else ''}. Want their contact?")
        reply = "Listed!" + (f" Found {len(hits)} possible match(es)." if hits and kind == "buy" else "")
    elif intent == "ask_lost":
        with db() as con:
            rows = [dict(r) for r in con.execute(
                "SELECT id,item,colour,place,source,created FROM lost_found WHERE kind='found' AND status='open' ORDER BY id DESC LIMIT 30")]
        reply = write_reply(text, rows)
    elif intent == "ask_events":
        with db() as con:
            rows = [dict(r) for r in con.execute(
                "SELECT title,category,date,venue,major FROM events ORDER BY id DESC LIMIT 20")]
        reply = write_reply(text, rows)
    elif intent == "ask_listings":
        with db() as con:
            rows = [dict(r) for r in con.execute(
                "SELECT item,price,kind FROM listings WHERE status='open' ORDER BY id DESC LIMIT 20")]
        reply = write_reply(text, rows)
    elif intent in ("ask_room", "book_room"):
        room = (data.get("room") or "").lower()
        day = datetime.now().strftime("%Y-%m-%d")
        with db() as con:
            rows = [dict(r) for r in con.execute(
                "SELECT room,start,end FROM bookings WHERE day=? AND (?='' OR lower(room)=?)", (day, room, room))]
        start, end = data.get("start", ""), data.get("end", "")
        if intent == "book_room" and room and start:
            end = end or f"{(int(start[:2]) + 1) % 24:02d}:{start[3:5]}"
            if any(overlaps(start, end, r["start"], r["end"]) for r in rows):
                reply = f"The {room} is already booked between {start} and {end}. Want me to check another time?"
            else:
                with db() as con:
                    con.execute("INSERT INTO bookings(room,day,start,end,booked_by) VALUES (?,?,?,?,?)",
                                (room, day, start, end, m.author))
                reply = f"Booked! The {room} is yours today from {start} to {end}."
        else:
            reply = write_reply(text, {"today": day, "bookings": rows})
    elif intent == "ask_laundry":
        with db() as con:
            rows = [dict(r) for r in con.execute("SELECT location,status,updated FROM machines")]
        reply = write_reply(text, rows)
    elif should_reply:
        reply = ("Hi! I'm Vernier. Ask me about lost items, events, rooms, laundry or buy/sell. "
                 "To get alerts, send: interests: sports, music (add 'major' for big events only).")

    return {"reply": reply if should_reply else None, "intent": intent}


@app.get("/outbox")
def outbox():
    with db() as con:
        rows = [dict(r) for r in con.execute("SELECT id,to_chat,text FROM outbox WHERE sent=0 ORDER BY id LIMIT 20")]
        con.executemany("UPDATE outbox SET sent=1 WHERE id=?", [(r["id"],) for r in rows])
    return rows


class CameraItem(BaseModel):
    item: str
    colour: str = ""
    location: str = "Lost & found shelf"


@app.post("/camera/item")
def camera_item(c: CameraItem):
    row = add_lost_found("found", {"item": c.item, "colour": c.colour, "place": c.location}, "", "camera")
    matched = handle_found(row)
    return {"id": row["id"], "matched_lost_id": matched["id"] if matched else None}


@app.post("/camera/item/{item_id}/removed")
def camera_item_removed(item_id: int):
    with db() as con:
        con.execute("UPDATE lost_found SET status='claimed' WHERE id=?", (item_id,))
    return {"ok": True}


class Machine(BaseModel):
    id: str
    location: str
    status: str


@app.post("/camera/machine")
def camera_machine(mc: Machine):
    with db() as con:
        con.execute("INSERT OR REPLACE INTO machines(id,location,status,updated) VALUES (?,?,?,?)",
                    (mc.id, mc.location, mc.status, now()))
    return {"ok": True}


TABLES = {"lost_found", "events", "listings", "machines", "bookings", "students", "outbox"}


@app.get("/records/{table}")
def records(table: str):
    if table not in TABLES:
        return {"error": "unknown table"}
    with db() as con:
        return [dict(r) for r in con.execute(f"SELECT * FROM {table} ORDER BY rowid DESC LIMIT 200")]
