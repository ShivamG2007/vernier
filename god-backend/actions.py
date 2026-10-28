"""Validate model proposals and dispatch only known backend actions."""

import os
import re
from datetime import date, timedelta
from urllib.parse import urlparse

import memory
import model
import outlook
import store

GROUPS_ENABLED = os.environ.get("VERNIER_ENABLE_GROUPS", "0") == "1"
MESSAGE_TIMEOUT_SECONDS = 25
TIMEOUT_REPLY = (
    "Hmm, I'm taking longer than I should for this. Please try rephrasing your "
    "question. I may not be able to help with it yet."
)
KEYWORDS = re.compile(
    r"lost|found|missing|kho|mila|mile|charger|bottle|wallet|earbud|earphone|airpod|bag|jacket|"
    r"sell|selling|buy|khareed|price|₹|event|audition|recruit|register|fest|match|tournament|"
    r"workshop|club|room|book|washing|machine|laundry", re.I)
PERSON_RULE = re.compile(
    r"\b(?:track\s+(?:him|her|someone|my friend)|live location|"
    r"location of\s+(?:him|her|someone|my friend)|"
    r"where is\s+(?:he|she|my friend))\b", re.I)
PERSON_NAME_RULE = re.compile(r"\bwhere is\s+[A-Z][a-z]{1,30}\b")
CAMERA_RULE = re.compile(
    r"\b(camera|cctv|footage|feed)\b.{0,35}\b(show|see|send|watch|view|photo|video)\b|"
    r"\b(show|send|watch|view|see)\b.{0,35}\b(camera|cctv|footage|feed)\b", re.I)
UNRESOLVED_LOST_RULE = re.compile(
    r"\b(?:lost|missing)\b.{0,50}\b(?:not found|still missing|unresolved|not recovered)\b|"
    r"\b(?:not found|still missing|unresolved|not recovered)\b.{0,50}\b(?:lost|missing)\b", re.I)
BUY_RULE = re.compile(
    r"\b(?:any ?(?:one|body)|koi|kisi)\b[^.?!]{0,25}\b(?:sell|selling|bech\w*)\b|"
    r"\b(?:want|need|looking) to buy\b|\bkhareed|"
    # "buying a calculator" / "buy cycle": mentions buying and never selling.
    r"^(?!.*\b(?:sell|selling|bech\w*)\b).*\bbuy(?:ing)?\b", re.I | re.S)
LISTINGS_RULE = re.compile(
    r"\b(?:what|which|any|kya|koi)\b[^.!]{0,40}\bfor sale\b|\blisted\b[^.!]{0,30}\bfor sale\b|"
    r"\bwhat'?s\s+(?:for sale|available)\b|\bdala hai kya\b|\b(?:show|list)\b[^.!]{0,15}\blistings?\b", re.I)
LOST_RULE = re.compile(r"\b(?:kho|gir)\s*(?:gaya|gayi|gya|gyi|gai|gaye)\b|\blost my\b", re.I)
FOUND_RULE = re.compile(
    r"\bkisi\s+ka\b[^?]{0,60}\b(?:mila|mili|mile)\b|"
    r"\b(?:mila|mili|mile)\s+(?:hai|h|he|hain)\b[^?]{0,30}\bkisi\s+ka\b|"
    r"^\s*(?:i\s+)?found\s+(?:a|an|some|this|these|someone'?s)\b", re.I)
BOOK_RULE = re.compile(r"^\s*(?:please\s+|pls\s+|can you\s+)?book\b", re.I)
ROOM_RULE = re.compile(r"\b(?:room|hall|lab|auditorium)\b", re.I)
LAUNDRY_RULE = re.compile(r"\b(?:wash\w*|machine|laundry|dryer)\b", re.I)
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
CATEGORY_WORDS = [
    ("sports", r"football|cricket|basketball|volleyball|badminton|kabaddi|athletics|sports?|tournament|match"),
    ("dance", r"dance|dancing"),
    ("music", r"music|singing|band|open mic|concert"),
    ("theatre", r"drama|theatre|theater|nukkad|natak"),
    ("tech", r"hackathon|coding|tech|robotics|programming"),
    ("academic", r"seminar|lecture|quiz|exam|workshop"),
    ("culture", r"fest|cultural|garba|diwali|holi"),
]
TIME_RANGE = re.compile(
    r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*(?:to|-|till|until)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", re.I)
ONE_TIME = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b|\bat\s+(\d{1,2})(?::(\d{2}))?\b", re.I)

TEAM_ACTIONS = {
    "lost_report": "report_lost", "found_report": "report_found", "ask_lost": "search_found",
    "chit_chat": "chat", "other": "chat",
}


def _explicit_text(value, message, limit):
    if not isinstance(value, str):
        return None
    value = value.strip()[:limit]
    if not value or not re.search(r"(?<!\w)" + re.escape(value) + r"(?!\w)", message, re.I):
        return None
    return value


def _explicit_keywords(values, message):
    if not isinstance(values, list):
        return None
    found = []
    for value in values[:20]:
        word = _explicit_text(value, message, 40)
        if word and word.casefold() not in {w.casefold() for w in found}:
            found.append(word)
    return found or None


def _field(value, limit):
    return value.strip()[:limit] if isinstance(value, str) else ""


def _record_reply(question, records, scope, fallback):
    try:
        return _field(model.write_reply(question, records, scope=scope), 1000) or fallback
    except TimeoutError:
        raise
    except Exception as exc:
        print(f"Reply generation failed: {type(exc).__name__}: {exc}")
        return fallback


def _summary(row):
    name = row.get("item") or row.get("name") or "item"
    place = row.get("place") or row.get("foundAt")
    label = store.item_label(row.get("color"), name)
    return f"#{row['id']} {label}" + (f" at {place}" if place else "")


def _result(action, reply, message_id, *, group=False, extra=None):
    # The bridge ignores duplicate replies; keep only the action for deduplication.
    store.save_processed(message_id, None, action)
    result = {"reply": None if group else reply, "action": action,
              "intent": action, "duplicate": False}
    if extra:
        result.update(extra)
    return result


def _day(value, text):
    value = _field(value, 10)
    if value:
        try:
            date.fromisoformat(value)
            return value
        except ValueError:
            return None
    if re.search(r"\btomorrow\b|\bkal\b", text, re.I):
        return (date.today() + timedelta(days=1)).isoformat()
    if re.search(r"\btoday\b|\baaj\b", text, re.I):
        return date.today().isoformat()
    return None


def _text_day(text):
    # Day words in the message beat the model's date, which is often just today's date.
    day = _day(None, text)
    if day:
        return day
    if re.search(r"\btonight\b", text, re.I):
        return date.today().isoformat()
    for i, name in enumerate(WEEKDAYS):
        if re.search(rf"\b{name}\b", text, re.I):
            return (date.today() + timedelta(days=(i - date.today().weekday()) % 7)).isoformat()
    return None


def _event_date(value, text):
    return _text_day(text) or _explicit_text(value, text, 100)


def _with_weekday(value):
    try:
        return f"{value} ({date.fromisoformat(value):%A})"
    except (TypeError, ValueError):
        return value


def _category(value, text):
    if value in model.CATEGORIES and value != "other":
        return value
    for category, words in CATEGORY_WORDS:
        if re.search(rf"\b(?:{words})\b", text, re.I):
            return category
    return "other"


def _clock(hour, minute, half):
    hour, minute = int(hour), int(minute or 0)
    if half:
        hour = hour % 12 + (12 if half.casefold() == "pm" else 0)
    elif hour < 8:
        hour += 12  # "at 5" for a campus room means 5 PM
    return f"{hour:02d}:{minute:02d}" if hour < 24 and minute < 60 else None


def _times(text):
    # The model often leaves start/end empty, so read times like "3 to 4pm" or "at 5pm" directly.
    match = TIME_RANGE.search(text)
    if match:
        h1, m1, a1, h2, m2, a2 = match.groups()
        start, end = _clock(h1, m1, a1 or a2), _clock(h2, m2, a2)
        if start and end:
            return start, end
    match = ONE_TIME.search(text)
    if match:
        start = _clock(*match.groups()[:3]) if match.group(1) else _clock(match.group(4), match.group(5), None)
        if start:
            return start, f"{(int(start[:2]) + 1) % 24:02d}{start[2:]}"
    return None, None


def _outlook_room(room_text, text, day, start, end):
    room = outlook.find_room(room_text, text)
    if not room:
        return None, f"Which room? I can check: {outlook.room_names()}."
    if not (day and start and end):
        return None, f"Tell me the day and time for {room['name']}, e.g. \"{room['name']} tomorrow 3 to 4pm\"."
    try:
        outlook.check_request(day, start, end)
    except ValueError as exc:
        return None, str(exc)
    return room, None


def _book_in_outlook(room_text, text, day, start, end, author, direct):
    room, problem = _outlook_room(room_text, text, day, start, end)
    if problem:
        return problem, None
    if not direct:
        return "Tag me or message me directly to book a room.", None
    if not outlook.allowed(author):
        return "Outlook room booking is limited to approved numbers right now.", None
    when = f"{room['name']} on {_with_weekday(day)}, {start}-{end}"
    try:
        if not outlook.is_free(room, day, start, end, timeout=model.remaining_timeout(15)):
            return f"{when} is already booked in Outlook. Try another time or room.", None
        event = outlook.book(room, day, start, end, timeout=model.remaining_timeout(15))
    except outlook.OutlookError as exc:
        print(f"Outlook booking failed: {exc}")
        return f"I couldn't book {room['name']} in Outlook right now ({exc}).", None
    mailbox = outlook.is_room_mailbox(room)
    booking_id = store.log_outlook_booking(event["id"], room["name"], day, start, end, author,
                                           "requested" if mailbox else "booked")
    if not mailbox:
        return f"Booked in Outlook: {when}.", {"id": booking_id, "outlook": "booked"}

    def on_result(response):
        if response == "accepted":
            message = f"Confirmed in Outlook: {when}."
            store.set_outlook_booking_status(event["id"], "booked")
        elif response == "tentativelyAccepted":
            message = f"{when} is tentatively accepted and waiting for approval in Outlook."
            store.set_outlook_booking_status(event["id"], "tentative")
        elif response == "declined":
            message = f"The room declined {when}, so I removed the booking. Try another time or room."
            store.set_outlook_booking_status(event["id"], "declined")
        else:
            message = f"{room['name']} hasn't answered yet for {when}. It may need approval; check Outlook."
        if author:
            store.queue(author, message)

    outlook.watch(event["id"], room, on_result)
    return (f"Booking request sent to Outlook: {when}. I'll message you when the room confirms.",
            {"id": booking_id, "outlook": "requested"})


def _handle_message(payload, planner=None):
    if not isinstance(payload, dict) or not isinstance(payload.get("text"), str):
        raise ValueError("Message text is required")
    planner = model.plan_message if planner is None else planner
    text = payload["text"].strip()
    if not 1 <= len(text) <= 4000:
        raise ValueError("Message text must contain 1 to 4000 characters")
    author = _field(payload.get("author"), 200)
    message_id = _field(payload.get("message_id"), 200)
    is_group = payload.get("is_group", False)
    mentioned = payload.get("mentioned", False)
    if not isinstance(is_group, bool) or not isinstance(mentioned, bool):
        raise ValueError("is_group and mentioned must be booleans")
    previous = store.get_processed(message_id)
    if previous:
        return {"reply": None, "action": previous["action"],
                "intent": previous["action"], "duplicate": True}

    context = memory.context_for(author) if author and not is_group else None

    def finish(action, reply, *, group=False, extra=None, remember=True, fact=None):
        result = _result(action, reply, message_id, group=group, extra=extra)
        if remember and author and not is_group and result["reply"]:
            memory.remember(author, text, result["reply"], fact=fact)
        return result

    if is_group and not GROUPS_ENABLED:
        return finish("ignored_group", None, group=True, remember=False)
    if is_group and not mentioned and not KEYWORDS.search(text):
        return finish("skipped", None, group=True, remember=False)

    if not is_group and re.fullmatch(r"(?:forget|clear|delete)\s+(?:my\s+)?(?:chat|conversation|memory)", text, re.I):
        memory.forget(author)
        return finish("forget_context", "I cleared this chat's short-term context. Saved reports, preferences, and operational message records remain.", remember=False)

    if PERSON_RULE.search(text) or PERSON_NAME_RULE.search(text):
        return finish("blocked", "I can't share anyone's location.",
                      group=is_group and not mentioned, remember=False)
    if CAMERA_RULE.search(text):
        return finish("blocked", "I can't share camera footage or images.",
                      group=is_group and not mentioned, remember=False)

    if not is_group and text.casefold().startswith("interests:"):
        rest = text.split(":", 1)[1]
        level = "major" if re.search(r"\bmajor\b", rest, re.I) else "all"
        rest = re.sub(r"(?i)\blevel\s*[:=]?\s*(major|all)\b|\bmajor(?: only)?\b", "", rest)
        interests = [v.strip().casefold() for v in re.split(r"[,;/]", rest) if v.strip()]
        if not author or not interests:
            return finish("set_interests", "Include at least one interest and a sender ID.", remember=False)
        saved = store.save_interests(author, interests, level)
        return finish("set_interests", f"Saved interests: {', '.join(saved)} ({level}).", remember=False)

    claim = re.fullmatch(r"claim\s+#?(\d+)(?:\s+(.+))?", text, re.I | re.S)
    if claim and not is_group:
        if not author:
            return finish("claim_request", "I need your sender ID to record a claim request.", remember=False)
        try:
            store.request_claim(int(claim.group(1)), author, claim.group(2))
        except ValueError as exc:
            return finish("claim_request", str(exc), remember=False)
        return finish("claim_request", "Your claim request is recorded. The lost-and-found desk must verify ownership before collection.", remember=False)

    proposal = planner(text, context=context) if planner is model.plan_message else planner(text)
    model.remaining_timeout(MESSAGE_TIMEOUT_SECONDS)
    if not isinstance(proposal, dict):
        raise ValueError("Model returned an invalid action")
    action = proposal.get("action") or TEAM_ACTIONS.get(proposal.get("intent"), proposal.get("intent"))
    action = TEAM_ACTIONS.get(action, action)
    if action not in model.ACTIONS:
        action = "chat"
    if action == "list_unclaimed_found" and UNRESOLVED_LOST_RULE.search(text):
        action = "list_open_lost"
    if action == "sell_post" and BUY_RULE.search(text):
        action = "buy_request"
    if action in {"sell_post", "buy_request", "chat"} and LISTINGS_RULE.search(text):
        action = "ask_listings"
    if action in {"search_found", "list_unclaimed_found", "ask_room", "chat"} and LOST_RULE.search(text):
        action = "report_lost"
    elif action in {"search_found", "list_unclaimed_found", "chat"} and FOUND_RULE.search(text):
        action = "report_found"
    if action == "ask_laundry" and ROOM_RULE.search(text) and not LAUNDRY_RULE.search(text):
        action = "ask_room"
    if action == "ask_room" and BOOK_RULE.search(text):
        action = "book_room"

    item = _field(proposal.get("item"), 120)
    color = _explicit_text(proposal.get("color", proposal.get("colour")), text, 60)
    place = _explicit_text(proposal.get("place"), text, 120)
    keywords = _explicit_keywords(proposal.get("descUsingKeywords"), text)
    custom_string = _explicit_text(proposal.get("customString"), text, 500)
    image_href = _explicit_text(proposal.get("imageHref"), text, 500)
    if image_href and urlparse(image_href).scheme not in {"http", "https"}:
        image_href = None
    consult = _explicit_text(proposal.get("pleaseConsultThisPerson"), text, 120)
    reply, extra, fact = None, None, None

    if action in {"report_lost", "report_found"}:
        if not item:
            reply = "Tell me which item was lost or found."
        else:
            kind = "lost" if action == "report_lost" else "found"
            item_id = store.add_item(kind=kind, item=item, color=color, place=place,
                desc_using_keywords=keywords, custom_string=custom_string,
                image_href=image_href, please_consult_this_person=consult,
                source="chat", reporter=author)
            extra = {"id": item_id}
            fact = f"Earlier reported {kind} {store.item_label(color, item)} as item #{item_id}"
            if kind == "found":
                matches = store.find_matches(item_id)
                alerted = store.alert_lost_reporters(item_id)
                reply = f"Thanks, I've recorded the {_summary({'id': item_id, 'item': item, 'color': color, 'place': place})}."
                if matches:
                    reply += " A possible lost-item match was found."
                if alerted:
                    reply += " I queued an alert about a possible match."
            else:
                matches = store.find_matches(item_id)
                reply = f"I've recorded your lost {item}."
                if matches:
                    reply += f" Possible match: {_summary(matches[0])}. Ask the lost-and-found desk to verify ownership."
                else:
                    reply += " I'll alert you if a similar found item is reported."
                if is_group and not mentioned and author:
                    store.queue(author, reply)
    elif action == "search_found":
        matches = store.find_items(kind="found", item=item) if item else []
        reply = ("Possible matches: " + "; ".join(_summary(row) for row in matches[:3]) +
                 ". Ask the lost-and-found desk to verify ownership.") if matches else f"I don't have an unclaimed {item or 'matching item'} recorded."
        if item:
            fact = f"Earlier asked whether {item} was found"
    elif action == "list_unclaimed_found":
        rows = store.list_unclaimed_found()
        reply = ("Unclaimed found items:\n" + "\n".join(_summary(r) for r in rows[:30]) +
                 (f"\n…and {len(rows)-30} more." if len(rows) > 30 else "")) if rows else "There are no unclaimed found items recorded."
    elif action == "list_open_lost":
        rows = store.list_open_lost()
        if rows:
            lines = []
            for row in rows[:30]:
                label = store.item_label(row["color"], row["item"])
                place = f" (last reported near {row['place']})" if row["place"] else ""
                lines.append(f"#{row['id']} {label}{place}")
            reply = "Items reported lost and still open:\n" + "\n".join(lines)
            if len(rows) > 30:
                reply += f"\n…and {len(rows) - 30} more."
        else:
            reply = "There are no unresolved lost-item reports recorded."
    elif action == "event_post":
        # The model usually puts the event name in "item" and leaves category empty.
        title = (_explicit_text(proposal.get("title"), text, 160) or
                 _explicit_text(proposal.get("item"), text, 160) or text[:160])
        category = _category(proposal.get("category"), text)
        event_id = store.add_event(title=title, category=category,
            date=_event_date(proposal.get("date"), text),
            venue=_explicit_text(proposal.get("venue"), text, 120),
            details=text, major=proposal.get("major") is True,
            source=_field(payload.get("chat_name"), 200) if is_group else author)
        extra = {"id": event_id}
        reply = f"Event recorded under {category}. Interested students will receive an alert."
    elif action == "ask_events":
        events = store.list_events()
        public_events = [{k: _with_weekday(row[k]) if k == "date" else row[k]
                          for k in ("id", "title", "category", "date", "venue", "major")}
                         for row in events]
        fallback = "Recorded events: " + "; ".join(row["title"] for row in events[:5]) + "." if events else "I don't have any events recorded yet."
        # The model can't work out weekdays itself, so give it today's date and each event's weekday.
        records = {"today": _with_weekday(date.today().isoformat()), "events": public_events}
        reply = _record_reply(text, records, "recorded events", fallback) if events else fallback
    elif action in {"sell_post", "buy_request"}:
        if not item:
            reply = "Tell me which item you're buying or selling."
        else:
            kind = "sell" if action == "sell_post" else "buy"
            listing_id, matches = store.add_listing(kind=kind, item=item,
                price=_explicit_text(proposal.get("price"), text, 80),
                details=text, contact=author)
            extra = {"id": listing_id}
            if kind == "buy" and matches:
                reply = f"Buy request recorded for {item}. Already for sale: " + "; ".join(
                    m["item"] + (f" ({m['price']})" if m["price"] else "") for m in matches[:5]) + "."
            elif kind == "buy":
                reply = f"Buy request recorded for {item}. Nothing matching is for sale yet; I'll message you when someone lists one."
            else:
                reply = f"Listed {item} for sale." + (
                    f" {len(matches)} buyer(s) are looking for this and will be told." if matches else "")
    elif action == "ask_listings":
        listings = store.list_listings()
        public_listings = [{"id": row["id"], "item": row["item"],
                            "type": "for sale" if row["kind"] == "sell" else "wanted by a buyer",
                            "price": f"₹{row['price']}" if (row["price"] or "").isdigit() else row["price"]}
                           for row in listings]
        fallback = "Open listings: " + "; ".join(
            f"{row['kind']} {row['item']}" for row in listings[:5]) + "." if listings else "I don't have any open listings recorded yet."
        reply = _record_reply(text, public_listings, "open buy and sell listings", fallback) if listings else fallback
    elif action == "ask_room":
        day = (_text_day(text) or _day(proposal.get("day") or proposal.get("date"), text)
               or date.today().isoformat())
        room = _field(proposal.get("room"), 120) or _field(proposal.get("item"), 120) or None
        bookings = store.list_bookings(day, room)
        start, end = _times(text)
        outlook_room = outlook.find_room(room, text) if outlook.ready() and start else None
        if outlook_room:
            try:
                outlook.check_request(day, start, end)
                free = outlook.is_free(outlook_room, day, start, end, timeout=model.remaining_timeout(15))
            except (ValueError, outlook.OutlookError) as exc:
                reply = f"I couldn't check Outlook right now ({exc})."
            else:
                when = f"{outlook_room['name']} on {_with_weekday(day)}, {start}-{end}"
                reply = (f"{when} is free in Outlook. Say \"book {outlook_room['name']} ...\" to book it."
                         if free else f"{when} is already booked in Outlook.")
        elif bookings:
            reply = "Vernier bookings: " + "; ".join(
                f"{b['room']} {b['start']}-{b['end']}" for b in bookings[:10]) + "."
        else:
            reply = "No booking is recorded in Vernier for that room and day. Confirm availability with campus staff."
    elif action == "book_room":
        # The model usually puts the room in "item" and the day in "date".
        room = _field(proposal.get("room"), 120) or _field(proposal.get("item"), 120)
        day = _text_day(text) or _day(proposal.get("day") or proposal.get("date"), text)
        start, end = _times(text)
        if not (start and end):
            start, end = _field(proposal.get("start"), 5), _field(proposal.get("end"), 5)
        if outlook.ready():
            reply, extra = _book_in_outlook(room, text, day, start, end, author,
                                            direct=not is_group or mentioned)
        elif not (room and day and start and end):
            reply = "Please give a room, day, start time and end time to book it."
        else:
            try:
                booking_id = store.book_room(room, day, start, end, author)
            except ValueError as exc:
                reply = str(exc)
            else:
                if booking_id:
                    extra = {"id": booking_id}
                    reply = f"Booked in Vernier: {room} on {day}, {start}-{end}. Confirm with campus staff."
                else:
                    reply = f"Vernier already has a booking for {room} in that time slot."
    elif action == "ask_laundry":
        machines = store.list_machines()
        fallback = "Machine observations: " + "; ".join(
            f"{row['location']}: {row['status']}" for row in machines[:5]) + "." if machines else "I don't have any machine status recorded yet."
        reply = _record_reply(text, machines, "latest submitted washing-machine observations", fallback) if machines else fallback
    elif action == "ask_person":
        action, reply = "blocked", "I can't share anyone's location."
    else:
        if planner is model.plan_message:
            try:
                reply = (model.chat_reply(text, context)
                         or "Ask me about lost items, events, listings, rooms or laundry.")
            except TimeoutError:
                raise
            except Exception as exc:
                print(f"Chat reply failed: {type(exc).__name__}: {exc}")
                reply = "Ask me about lost items, events, listings, rooms or laundry."
        else:
            reply = _field(proposal.get("reply"), 1000) or "Ask me about lost items, events, listings, rooms or laundry."

    return finish(action, reply, group=is_group and not mentioned, extra=extra,
                  remember=action != "blocked", fact=fact)


def handle_message(payload, planner=None):
    with model.message_deadline(MESSAGE_TIMEOUT_SECONDS):
        try:
            return _handle_message(payload, planner)
        except TimeoutError:
            # Return a normal reply; the server stays available for the next message.
            message_id = _field(payload.get("message_id"), 200) if isinstance(payload, dict) else ""
            group = (payload.get("is_group") is True and payload.get("mentioned") is not True
                     if isinstance(payload, dict) else False)
            return _result("timeout", TIMEOUT_REPLY, message_id, group=group)
