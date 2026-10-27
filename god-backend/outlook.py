"""Book real campus rooms in Outlook (Microsoft Graph) with the signed-in college account.

Setup and commands: see OUTLOOK_SETUP.md
    python outlook.py login        sign in once with the college Microsoft account
    python outlook.py status       who is signed in and which rooms are configured
    python outlook.py check MR-2 2026-10-29 15:00 16:00
    python outlook.py book  MR-2 2026-10-29 15:00 16:00
    python outlook.py upcoming     Vernier bookings in the next 30 days
    python outlook.py cancel 1     cancel booking number 1 from "upcoming"
"""

import json
import os
import re
import sys
import threading
import time
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib import error, request
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
CONFIG_FILE = Path(os.environ.get("VERNIER_OUTLOOK_CONFIG", HERE / "outlook_config.json"))
TOKEN_FILE = Path(os.environ.get("VERNIER_OUTLOOK_TOKEN_FILE", HERE / "outlook_token.json"))
GRAPH = "https://graph.microsoft.com/v1.0"
SCOPES = ["Calendars.ReadWrite", "User.Read"]
_lock = threading.Lock()
_cached = {"key": None, "app": None, "cache": None}


class OutlookError(Exception):
    pass


def config():
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        raise OutlookError(f"{CONFIG_FILE.name} is not valid JSON: {exc}") from None
    data.setdefault("tenant", "organizations")
    data.setdefault("timezone", "India Standard Time")
    data.setdefault("subject", "Room booking (via Vernier)")
    data.setdefault("max_hours", 3)
    data.setdefault("max_days_ahead", 30)
    data.setdefault("allowed_numbers", [])
    data.setdefault("rooms", [])
    return data


def _manual_token():
    return os.environ.get("VERNIER_OUTLOOK_TOKEN", "").strip()


def status():
    try:
        cfg = config()
    except OutlookError:
        return "config error"
    if not cfg.get("rooms"):
        return "off"
    if any("PASTE" in str(r.get("email", "")) for r in cfg["rooms"]):
        return "room emails not filled in"
    if _manual_token():
        return "ready (manual token)"
    if not cfg.get("client_id") or "PASTE" in cfg["client_id"]:
        return "missing client_id"
    if not TOKEN_FILE.exists():
        return "not signed in"
    return "ready"


def ready():
    return status().startswith("ready")


def _app():
    try:
        import msal
    except ImportError:
        raise OutlookError("msal is not installed. Run: pip install msal") from None
    cfg = config()
    if not cfg.get("client_id"):
        raise OutlookError(f"Put your app's client_id in {CONFIG_FILE.name}")
    key = (cfg["client_id"], cfg["tenant"], TOKEN_FILE.stat().st_mtime if TOKEN_FILE.exists() else None)
    if _cached["key"] == key:
        return _cached["app"], _cached["cache"]
    cache = msal.SerializableTokenCache()
    if TOKEN_FILE.exists():
        cache.deserialize(TOKEN_FILE.read_text(encoding="utf-8"))
    try:
        app = msal.PublicClientApplication(
            cfg["client_id"], authority=f"https://login.microsoftonline.com/{cfg['tenant']}",
            token_cache=cache)
    except Exception as exc:
        raise OutlookError(f"Can't reach Microsoft sign-in ({type(exc).__name__}). Check the internet.") from None
    _cached.update(key=key, app=app, cache=cache)
    return app, cache


def _save(cache):
    if cache.has_state_changed:
        TOKEN_FILE.write_text(cache.serialize(), encoding="utf-8")
        cache.has_state_changed = False
        if _cached["cache"] is cache:
            _cached["key"] = _cached["key"][:2] + (TOKEN_FILE.stat().st_mtime,)


def access_token():
    manual = _manual_token()
    if manual:
        return manual
    with _lock:
        app, cache = _app()
        accounts = app.get_accounts()
        if not accounts:
            raise OutlookError("Not signed in to Outlook. Run: python outlook.py login")
        try:
            result = app.acquire_token_silent(SCOPES, account=accounts[0])
        except Exception as exc:
            raise OutlookError(f"Can't reach Microsoft sign-in ({type(exc).__name__}). Check the internet.") from None
        _save(cache)
    if not result or "access_token" not in result:
        raise OutlookError("Outlook sign-in expired. Run: python outlook.py login")
    return result["access_token"]


def login():
    app, cache = _app()
    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        raise OutlookError(flow.get("error_description", "Could not start sign-in"))
    print(flow["message"])
    result = app.acquire_token_by_device_flow(flow)
    _save(cache)
    if "access_token" not in result:
        raise OutlookError(result.get("error_description", "Sign-in failed"))
    return result.get("id_token_claims", {}).get("preferred_username", "your account")


def _graph(method, path, body=None, timeout=15):
    tz = config().get("timezone", "India Standard Time")
    req = request.Request(
        path if path.startswith("http") else GRAPH + path,
        data=None if body is None else json.dumps(body).encode("utf-8"),
        method=method,
        headers={"Authorization": f"Bearer {access_token()}",
                 "Content-Type": "application/json",
                 "Prefer": f'outlook.timezone="{tz}"'})
    try:
        with request.urlopen(req, timeout=timeout) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}
    except error.HTTPError as exc:
        try:
            detail = json.loads(exc.read()).get("error", {}).get("message", "")
        except Exception:
            detail = ""
        if exc.code == 401:
            if _manual_token():
                raise OutlookError("The Outlook token expired. Copy a fresh one from Graph Explorer into "
                                   "VERNIER_OUTLOOK_TOKEN and restart the backend.") from None
            raise OutlookError("Outlook sign-in expired. Run: python outlook.py login") from None
        if exc.code == 403:
            raise OutlookError(f"The college account doesn't allow this ({detail or 'access denied'})") from None
        raise OutlookError(f"Outlook returned {exc.code}: {detail}") from None
    except (error.URLError, TimeoutError) as exc:
        raise OutlookError(f"Can't reach Outlook ({getattr(exc, 'reason', exc)}). Check the internet.") from None


def rooms():
    return [r for r in config().get("rooms", []) if r.get("name")]


def is_room_mailbox(room):
    """College rooms have their own email and accept/decline invites; demo rooms are just locations."""
    return bool(room.get("email"))


def room_names():
    return ", ".join(r["name"] for r in rooms())


def _pattern(label):
    parts = re.findall(r"[a-z]+|\d+", label.lower())
    if not parts:
        return None
    return r"(?<![a-z0-9])" + r"[\s\-_.#]*".join(map(re.escape, parts)) + r"(?![a-z0-9])"


def find_room(*texts):
    for text in texts:
        if not text:
            continue
        best = None
        for room in rooms():
            for label in [room["name"], *room.get("aliases", [])]:
                pattern = _pattern(label)
                match = pattern and re.search(pattern, text.lower())
                if match and (best is None or len(match.group()) > best[0]):
                    best = (len(match.group()), room)
        if best:
            return best[1]
    return None


def allowed(author):
    numbers = [re.sub(r"\D", "", str(n))[-10:] for n in config().get("allowed_numbers", [])]
    numbers = [n for n in numbers if n]
    if not numbers:
        return True
    digits = re.sub(r"\D", "", (author or "").split("@")[0])
    return any(digits.endswith(n) for n in numbers)


def check_request(day, start, end):
    cfg = config()
    try:
        start_dt = datetime.fromisoformat(f"{day}T{start}")
        end_dt = datetime.fromisoformat(f"{day}T{end}")
    except (TypeError, ValueError):
        raise ValueError("Use a day like 2026-10-29 and times like 15:00.") from None
    if end_dt <= start_dt:
        raise ValueError("The end time must be after the start time.")
    if start_dt < datetime.now() - timedelta(minutes=5):
        raise ValueError("That time has already passed.")
    if end_dt - start_dt > timedelta(hours=float(cfg["max_hours"])):
        raise ValueError(f"I can book at most {cfg['max_hours']} hours at a time.")
    if start_dt.date() > date.today() + timedelta(days=int(cfg["max_days_ahead"])):
        raise ValueError(f"I can only book up to {cfg['max_days_ahead']} days ahead.")


def _slot(day, clock):
    return {"dateTime": f"{day}T{clock}:00", "timeZone": config()["timezone"]}


def _local_iso(day, clock):
    return datetime.fromisoformat(f"{day}T{clock}").astimezone().isoformat(timespec="seconds")


def _same_place(room, location):
    location = (location or "").lower()
    return any((p := _pattern(label)) and re.search(p, location)
               for label in [room["name"], *room.get("aliases", [])])


def _location_free(room, day, start, end, timeout):
    path = ("/me/calendarView?startDateTime=" + quote(_local_iso(day, start)) +
            "&endDateTime=" + quote(_local_iso(day, end)) +
            "&$select=subject,location,showAs,isCancelled&$top=100")
    for event in _graph("GET", path, timeout=timeout).get("value", []):
        if event.get("isCancelled") or event.get("showAs") == "free":
            continue
        if _same_place(room, event.get("location", {}).get("displayName")):
            return False
    return True


def is_free(room, day, start, end, timeout=15):
    if not is_room_mailbox(room):
        return _location_free(room, day, start, end, timeout)
    data = _graph("POST", "/me/calendar/getSchedule", {
        "schedules": [room["email"]],
        "startTime": _slot(day, start),
        "endTime": _slot(day, end),
        "availabilityViewInterval": 5,
    }, timeout=timeout)
    info = (data.get("value") or [{}])[0]
    if info.get("error"):
        raise OutlookError(f"Can't see {room['name']}'s calendar: {info['error'].get('message', '')}")
    view = info.get("availabilityView", "")
    busy = [i for i in info.get("scheduleItems", []) if i.get("status") not in {"free", "workingElsewhere"}]
    return bool(view) and set(view) <= {"0"} and not busy


def book(room, day, start, end, timeout=15):
    cfg = config()
    place = {"displayName": room["name"], "locationType": "conferenceRoom"}
    if is_room_mailbox(room):
        place["locationEmailAddress"] = room["email"]
    body = {
        "subject": cfg["subject"],
        "body": {"contentType": "text", "content": "Booked from WhatsApp through Vernier."},
        "start": _slot(day, start),
        "end": _slot(day, end),
        "location": place,
        "locations": [place],
        "showAs": "busy",
        "transactionId": str(uuid.uuid4()),
    }
    if is_room_mailbox(room):
        body["attendees"] = [{"emailAddress": {"address": room["email"], "name": room["name"]},
                              "type": "resource"}]
        body["allowNewTimeProposals"] = False
    return _graph("POST", "/me/events", body, timeout=timeout)


def cancel(event_id):
    _graph("DELETE", f"/me/events/{quote(event_id, safe='')}")


def room_response(event_id, room):
    data = _graph("GET", f"/me/events/{quote(event_id, safe='')}?$select=attendees")
    for attendee in data.get("attendees", []):
        if attendee.get("emailAddress", {}).get("address", "").lower() == room["email"].lower():
            return attendee.get("status", {}).get("response", "none")
    return "none"


def watch(event_id, room, on_result, wait_seconds=90):
    """Wait in the background for the room to accept or decline, then call on_result(response)."""
    def run():
        deadline = time.monotonic() + wait_seconds
        while time.monotonic() < deadline:
            time.sleep(6)
            try:
                response = room_response(event_id, room)
            except OutlookError as exc:
                print(f"Outlook check failed: {exc}")
                continue
            if response in {"accepted", "declined", "tentativelyAccepted"}:
                if response == "declined":
                    try:
                        cancel(event_id)
                    except OutlookError as exc:
                        print(f"Could not remove declined booking: {exc}")
                on_result(response)
                return
        on_result("pending")
    threading.Thread(target=run, daemon=True).start()


def upcoming(days=30):
    cfg = config()
    start = datetime.now().astimezone()
    end = start + timedelta(days=days)
    path = ("/me/calendarView?startDateTime=" + quote(start.isoformat(timespec="seconds")) +
            "&endDateTime=" + quote(end.isoformat(timespec="seconds")) +
            "&$select=id,subject,start,end,location&$orderby=start/dateTime&$top=100")
    events = _graph("GET", path).get("value", [])
    return [e for e in events if e.get("subject") == cfg["subject"]]


def _cli(args):
    command = args[0] if args else "status"
    if command == "login":
        print(f"Signed in as {login()}. Vernier can now book rooms.")
    elif command == "status":
        print(f"Outlook: {status()}")
        if ready():
            me = _graph("GET", "/me?$select=displayName,mail,userPrincipalName")
            print(f"Signed in as: {me.get('displayName')} <{me.get('mail') or me.get('userPrincipalName')}>")
        for room in rooms():
            aliases = ", ".join(room.get("aliases", []))
            print(f"  {room['name']:<14} {room.get('email') or '(location only)'}" + (f"   (also: {aliases})" if aliases else ""))
    elif command in {"check", "book"} and len(args) == 5:
        room = find_room(args[1])
        if not room:
            sys.exit(f"Unknown room '{args[1]}'. Configured rooms: {room_names()}")
        day, start, end = args[2], args[3], args[4]
        check_request(day, start, end)
        free = is_free(room, day, start, end)
        print(f"{room['name']} on {day} {start}-{end}: {'FREE' if free else 'BUSY'}")
        if command == "book" and free:
            event = book(room, day, start, end)
            if not is_room_mailbox(room):
                print(f"Booked in Outlook: {room['name']} on {day} {start}-{end}")
                return
            print(f"Booking sent. Waiting for {room['name']} to answer...")
            for _ in range(15):
                time.sleep(6)
                response = room_response(event["id"], room)
                if response not in {"none", "notResponded"}:
                    break
            print(f"Room answered: {response}")
            if response == "declined":
                cancel(event["id"])
                print("Removed the declined booking from your calendar.")
    elif command == "upcoming":
        events = upcoming()
        if not events:
            print("No Vernier bookings in the next 30 days.")
        for n, e in enumerate(events, 1):
            print(f"{n}. {e['location'].get('displayName', '?')}  "
                  f"{e['start']['dateTime'][:16].replace('T', ' ')} - {e['end']['dateTime'][11:16]}")
    elif command == "cancel" and len(args) == 2 and args[1].isdigit():
        events = upcoming()
        n = int(args[1])
        if not 1 <= n <= len(events):
            sys.exit("No booking with that number. Run: python outlook.py upcoming")
        cancel(events[n - 1]["id"])
        print(f"Cancelled booking {n}.")
    else:
        print(__doc__)


if __name__ == "__main__":
    try:
        _cli(sys.argv[1:])
    except (OutlookError, ValueError) as exc:
        sys.exit(f"Error: {exc}")
