import re
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import db
import llm

app = FastAPI(title="Vernier backend")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

db.init_db()

KEYWORDS = re.compile(
    r"lost|found|missing|kho|mila|mile|charger|bottle|wallet|earbud|earphone|airpod|bag|jacket|id card|keys|"
    r"sell|selling|buy|khareed|price|rs\.?|₹|event|audition|recruit|register|registration|fest|match|tournament|"
    r"workshop|club|room|book|washing|machine|laundry", re.I)

PERSON_REFUSAL = "I can't share where any student is. I only help with items, events, rooms and laundry."
CAMERA_REFUSAL = "I can't share camera views. Cameras only tell me what's on the lost & found shelf and if a machine is free."
BUSY_REPLY = "I'm having trouble thinking right now. Please try again in a minute."
HELP_REPLY = ("Hi! I'm Vernier. Ask me about lost items, events, rooms, laundry or buy/sell. "
              "To get alerts, send: interests: sports, music (add 'major' for big events only).")

BLOCKED = [
    (re.compile(r"live location|track (him|her|someone|my friend)|where is (he|she)\b", re.I), PERSON_REFUSAL),
    (re.compile(r"camera.{0,30}(show|see|dekh|dikha|photo|feed|footage|video)|(show|send).{0,20}(camera|cctv|footage)", re.I),
     CAMERA_REFUSAL),
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
    cands = db.rows("SELECT * FROM lost_found WHERE kind=? AND status='open'", (kind_wanted,))
    scored = [(match_score(row, c), c) for c in cands]
    return [c for s, c in sorted(scored, key=lambda x: -x[0]) if s >= 0.4]


def add_lost_found(kind, data, contact, source):
    row = {"kind": kind, "item": data.get("item", ""), "colour": data.get("colour", ""),
           "place": data.get("place", ""), "details": data.get("details", ""),
           "contact": contact, "source": source}
    row["id"] = db.execute(
        "INSERT INTO lost_found(kind,item,colour,place,details,contact,source,created) VALUES (?,?,?,?,?,?,?,?)",
        (kind, row["item"], row["colour"], row["place"], row["details"], contact, source, db.now()))
    return row


def describe(r):
    return " ".join(x for x in [r.get("colour"), r.get("item")] if x).strip() or "item"


def handle_found(row):
    for lost in find_matches(row, "lost"):
        where = (f"It's on the lost & found shelf ({row['place']})." if row["source"] == "camera"
                 else f"Someone found it near {row['place'] or 'campus'}.")
        db.queue(lost["contact"], f"Good news! Something matching your lost {describe(lost)} turned up: {describe(row)}. {where} "
                                  f"Reply 'claim {row['id']}' and tell me one detail only the owner would know.")
        db.execute("UPDATE lost_found SET status='matched' WHERE id=?", (lost["id"],))
        return lost
    return None


def handle_lost(row):
    matches = find_matches(row, "found")
    if matches:
        f = matches[0]
        where = (f"on the lost & found shelf ({f['place']})" if f["source"] == "camera"
                 else f"reported near {f['place'] or 'campus'}")
        return (f"Possible match: {describe(f)}, {where}. Reply 'claim {f['id']}' and tell me one detail "
                f"only the owner would know (a sticker, scratch, case colour).")
    return f"Noted your lost {describe(row)}. I'll message you the moment something similar turns up."


def notify_interested(event):
    for s in db.rows("SELECT * FROM students"):
        interests = [i.strip().lower() for i in (s["interests"] or "").split(",")]
        if event["category"] in interests and (s["level"] == "all" or event["major"]):
            db.queue(s["contact"], f"New {event['category']} update: {event['title']}"
                                   + (f" on {event['date']}" if event["date"] else "")
                                   + (f" at {event['venue']}" if event["venue"] else ""))


def overlaps(a_start, a_end, b_start, b_end):
    return a_start < b_end and b_start < a_end


def save_interests(contact, interests, level):
    db.execute("INSERT OR REPLACE INTO students(contact, interests, level) VALUES (?,?,?)",
               (contact, ",".join(interests), level))


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
                return {"reply": answer, "intent": "blocked"}

    if not m.is_group and low.startswith("interests:"):
        parts = text.split(":", 1)[1]
        level = "major" if "major" in parts.lower() else "all"
        cleaned = re.sub(r"(?i)level\s*[:=]?\s*(major|all)|major only|major", "", parts)
        interests = [t.strip().lower() for t in re.split(r"[,;/]", cleaned) if t.strip()]
        save_interests(m.author, interests, level)
        return {"reply": f"Saved! You'll get {'only major' if level == 'major' else 'all'} updates for: {', '.join(interests)}.",
                "intent": "set_interests"}

    claim = re.match(r"claim\s+(\d+)", low)
    if claim and not m.is_group:
        db.execute("UPDATE lost_found SET status='claim_pending' WHERE id=?", (int(claim.group(1)),))
        return {"reply": "Thanks! Your claim is noted. Collect it from the lost & found desk with your college ID.",
                "intent": "claim"}

    if m.is_group and not m.mentioned and not KEYWORDS.search(text):
        return {"reply": None, "intent": "skipped"}

    try:
        data = llm.extract(text)
    except Exception as e:
        print("LLM error:", e)
        return {"reply": BUSY_REPLY if should_reply else None, "intent": "llm_error"}

    intent = data["intent"]
    data["details"] = text
    reply = None

    try:
        if intent == "ask_person":
            reply = PERSON_REFUSAL
        elif intent == "lost_report":
            row = add_lost_found("lost", data, m.author, "chat")
            reply = handle_lost(row)
            if m.is_group and not m.mentioned:
                db.queue(m.author, reply)
        elif intent == "found_report":
            row = add_lost_found("found", data, m.author, "chat")
            matched = handle_found(row)
            reply = "Thanks! I've logged it" + (" and pinged someone who lost a similar item." if matched else ".")
        elif intent == "event_post":
            ev = {"title": data.get("title") or text[:80], "category": data.get("category", "other"),
                  "date": data.get("date", ""), "venue": data.get("venue", ""), "major": bool(data.get("major"))}
            db.execute("INSERT INTO events(title,category,date,venue,details,major,source,created) VALUES (?,?,?,?,?,?,?,?)",
                       (ev["title"], ev["category"], ev["date"], ev["venue"], text, int(ev["major"]), m.chat_name, db.now()))
            notify_interested(ev)
            reply = "Event noted. I'll tell students who follow " + ev["category"] + "."
        elif intent in ("sell_post", "buy_request"):
            kind = "sell" if intent == "sell_post" else "buy"
            db.execute("INSERT INTO listings(kind,item,price,details,contact,created) VALUES (?,?,?,?,?,?)",
                       (kind, data.get("item", ""), data.get("price", ""), text, m.author, db.now()))
            other = db.rows("SELECT * FROM listings WHERE kind=? AND status='open'", ("buy" if kind == "sell" else "sell",))
            hits = [o for o in other if tokens(o["item"]) & tokens(data.get("item", ""))]
            if kind == "sell":
                price = f" for {data['price']}" if data.get("price") else ""
                for o in hits:
                    db.queue(o["contact"], f"Someone is selling a {data.get('item')}{price}. Reply here if you want their contact.")
            reply = "Listed!" + (f" Found {len(hits)} possible match(es)." if hits and kind == "buy" else "")
        elif intent == "ask_lost":
            reply = llm.write_reply(text, db.rows(
                "SELECT id,item,colour,place,source,created FROM lost_found WHERE kind='found' AND status='open' ORDER BY id DESC LIMIT 30"))
        elif intent == "ask_events":
            reply = llm.write_reply(text, db.rows(
                "SELECT title,category,date,venue,major FROM events ORDER BY id DESC LIMIT 20"))
        elif intent == "ask_listings":
            reply = llm.write_reply(text, db.rows(
                "SELECT item,price,kind FROM listings WHERE status='open' ORDER BY id DESC LIMIT 20"))
        elif intent in ("ask_room", "book_room"):
            room = (data.get("room") or "").lower()
            day = datetime.now().strftime("%Y-%m-%d")
            booked = db.rows("SELECT room,start,end FROM bookings WHERE day=? AND (?='' OR lower(room)=?)", (day, room, room))
            start, end = data.get("start", ""), data.get("end", "")
            if intent == "book_room" and room and re.match(r"^\d{2}:\d{2}$", start):
                end = end if re.match(r"^\d{2}:\d{2}$", end) else f"{(int(start[:2]) + 1) % 24:02d}:{start[3:5]}"
                if any(overlaps(start, end, r["start"], r["end"]) for r in booked):
                    reply = f"The {room} is already booked between {start} and {end}. Want me to check another time?"
                else:
                    db.execute("INSERT INTO bookings(room,day,start,end,booked_by) VALUES (?,?,?,?,?)",
                               (room, day, start, end, m.author))
                    reply = f"Booked! The {room} is yours today from {start} to {end}."
            else:
                reply = llm.write_reply(text, {"today": day, "bookings": booked})
        elif intent == "ask_laundry":
            reply = llm.write_reply(text, db.rows("SELECT location,status,updated FROM machines"))
        else:
            reply = HELP_REPLY
    except Exception as e:
        print("Handler error:", e)
        reply = BUSY_REPLY

    if m.is_group and not m.mentioned:
        reply = None
    return {"reply": reply if should_reply else None, "intent": intent}


@app.get("/outbox")
def outbox():
    return db.take_outbox()


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
    db.execute("UPDATE lost_found SET status='claimed' WHERE id=?", (item_id,))
    return {"ok": True}


class Machine(BaseModel):
    id: str
    location: str
    status: str


@app.post("/camera/machine")
def camera_machine(mc: Machine):
    db.execute("INSERT OR REPLACE INTO machines(id,location,status,updated) VALUES (?,?,?,?)",
               (mc.id, mc.location, mc.status, db.now()))
    return {"ok": True}


class Preferences(BaseModel):
    phone: str
    interests: list[str]
    level: str = "all"


@app.post("/preferences")
def preferences(p: Preferences):
    digits = re.sub(r"\D", "", p.phone)
    if len(digits) == 10:
        digits = "91" + digits
    contact = f"{digits}@c.us"
    level = "major" if p.level == "major" else "all"
    interests = [i.strip().lower() for i in p.interests if i.strip()]
    save_interests(contact, interests, level)
    return {"ok": True, "contact": contact, "interests": interests, "level": level}


@app.get("/records/{table}")
def records(table: str):
    if table not in db.TABLES:
        return {"error": "unknown table", "tables": sorted(db.TABLES)}
    return db.rows(f"SELECT * FROM {table} ORDER BY rowid DESC LIMIT 200")


@app.get("/health")
def health():
    return {"backend": "ok", "database": db.DB_PATH, "ollama_url": llm.OLLAMA_URL, **llm.status()}


@app.post("/dev/seed")
def seed():
    found = [("bottle", "clear", "Rack C, Basket 3"), ("hoodie", "pink", "Rack B, Hanger 4"),
             ("backpack", "purple", "Rack B, Bottom"), ("gloves", "black", "Rack C, Basket 1"),
             ("lunch bag", "blue", "Rack A, Shelf 1")]
    for item, colour, place in found:
        add_lost_found("found", {"item": item, "colour": colour, "place": place}, "", "camera")
    events = [("Dance Club auditions", "dance", "Friday 5 PM", "Auditorium", 0),
              ("Inter-hostel football final", "sports", "Saturday 4 PM", "Main ground", 1),
              ("Open mic night", "music", "Sunday 7 PM", "Amphitheatre", 0),
              ("Annual tech fest registrations", "tech", "This week", "Block C", 1)]
    for t, c, d, v, mj in events:
        db.execute("INSERT INTO events(title,category,date,venue,details,major,source,created) VALUES (?,?,?,?,?,?,?,?)",
                   (t, c, d, v, t, mj, "seed", db.now()))
    for item, price in [("cycle", "₹2000"), ("study table", "₹800"), ("engineering drawing kit", "₹300")]:
        db.execute("INSERT INTO listings(kind,item,price,details,contact,created) VALUES (?,?,?,?,?,?)",
                   ("sell", item, price, f"selling {item}", "seed", db.now()))
    db.execute("INSERT OR REPLACE INTO machines(id,location,status,updated) VALUES (?,?,?,?)",
               ("b8", "8th floor boys hostel", "in use", db.now()))
    db.execute("INSERT OR REPLACE INTO machines(id,location,status,updated) VALUES (?,?,?,?)",
               ("g3", "3rd floor girls hostel", "free", db.now()))
    return {"ok": True}
