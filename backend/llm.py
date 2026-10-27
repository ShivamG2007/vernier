import json
import os
import re
from datetime import datetime

import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
MODEL = os.getenv("VERNIER_MODEL", "qwen3:4b")

INTENTS = ["lost_report", "found_report", "event_post", "sell_post", "buy_request",
           "ask_lost", "ask_events", "ask_room", "book_room", "ask_laundry",
           "ask_listings", "ask_person", "chit_chat", "other"]

CATEGORIES = ["sports", "music", "dance", "theatre", "culture", "tech", "academic", "other"]

SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": INTENTS},
        "item": {"type": "string"},
        "colour": {"type": "string"},
        "place": {"type": "string"},
        "title": {"type": "string"},
        "category": {"type": "string", "enum": CATEGORIES},
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
- sell_post: someone selling their own item ("selling my cycle, 2000 rs")
- buy_request: someone wants to buy an item or asks if anyone is selling one ("anyone selling a cooler?", "kisi ke paas cycle hai bechne ke liye?")
- ask_lost: asking the bot if their lost item was found
- ask_events: asking about events; ask_listings: asking what is for sale
- ask_room: asking if a room is free; book_room: asking to book a room
- ask_laundry: asking if a washing machine is free
- ask_person: asking where a specific person is, their location, room, or whereabouts ("where is Rahul right now", "Priya kaha hai")
- chit_chat / other: anything else
Fill item (short noun, e.g. "earbuds"), colour, place, title, category, date (YYYY-MM-DD, only if the message gives a day or date),
venue, major (true only for big official or fest-level events),
price, room (e.g. "music room"), start and end as HH:MM 24h, machine (e.g. "8th floor boys hostel"). Leave unknown fields empty.
Today is {today}."""

BUY_HINT = re.compile(r"\b(any ?(one|body)|koi|kisi)\b[^.?!]{0,25}\b(sell|selling|bech\w*)\b"
                      r"|\b(want|need|looking) to buy\b|\bkhareed", re.I)

REPLY_PROMPT = ("You are Vernier, a friendly campus WhatsApp assistant. Answer in at most 3 short lines, "
                "using ONLY the records given. If no record answers it, say so and suggest what the student can do. "
                "Never invent items, events, rooms or times. Reply in the same language style as the student.")


def chat(messages, schema=None, timeout=120):
    payload = {"model": MODEL, "messages": messages, "stream": False, "think": False,
               "options": {"temperature": 0}}
    if schema:
        payload["format"] = schema
    r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=timeout)
    r.raise_for_status()
    text = r.json()["message"]["content"]
    # qwen3 can still reason with think=False, and then only writes the closing </think> tag
    return text.rsplit("</think>", 1)[-1].strip()


def extract(text):
    raw = chat([
        {"role": "system", "content": EXTRACT_PROMPT.replace("{today}", datetime.now().strftime("%A %d %B %Y"))},
        {"role": "user", "content": text},
    ], SCHEMA)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"intent": "other"}
    if data.get("intent") not in INTENTS:
        data["intent"] = "other"
    if data["intent"] == "sell_post" and BUY_HINT.search(text):
        data["intent"] = "buy_request"
    return data


def write_reply(question, records):
    return chat([
        {"role": "system", "content": REPLY_PROMPT},
        {"role": "user", "content": f"Student asked: {question}\n\nRecords (JSON):\n{json.dumps(records, ensure_ascii=False)}"},
    ])


def status():
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=4)
        names = [m.get("name", "") for m in r.json().get("models", [])]
        ready = MODEL in names or f"{MODEL}:latest" in names
        return {"ollama": "ok", "model": MODEL, "model_ready": ready, "models_on_server": names}
    except Exception as e:
        return {"ollama": f"unreachable ({type(e).__name__})", "model": MODEL, "model_ready": False}
