"""Local HTTP API for WhatsApp, the companion app, and camera observations."""

import hmac
import json
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import actions
import model
import outlook
import store

HOST = os.environ.get("VERNIER_HOST", "127.0.0.1")
PORT = int(os.environ.get("VERNIER_PORT", "8000"))
ADMIN_KEY = os.environ.get("VERNIER_ADMIN_KEY", "")
CORS_ORIGINS = {s.strip() for s in os.environ.get(
    "VERNIER_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if s.strip()}


class Handler(BaseHTTPRequestHandler):
    def log_request(self, code="-", size="-"):
        # The bridge polls every five seconds; keep normal request logging useful.
        if self.command == "GET" and urlsplit(self.path).path == "/outbox" and code == 200:
            return
        super().log_request(code, size)

    def send_json(self, status, data):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        origin = self.headers.get("Origin")
        if origin in CORS_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Vernier-Key")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Vary", "Origin")
        self.end_headers()
        if raw:
            self.wfile.write(raw)

    def do_OPTIONS(self):
        self.send_json(204, {})

    def read_json(self):
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
            raise ValueError("Content-Type must be application/json")
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 < length <= 16000:
            raise ValueError("JSON body must be 1 to 16000 bytes")
        data = json.loads(self.rfile.read(length))
        if not isinstance(data, dict):
            raise ValueError("Expected a JSON object")
        return data

    def privileged(self):
        if ADMIN_KEY:
            return hmac.compare_digest(self.headers.get("X-Vernier-Key", ""), ADMIN_KEY)
        return self.client_address[0] in {"127.0.0.1", "::1"}

    def require_privileged(self):
        if self.privileged():
            return True
        self.send_json(403, {"error": "Local access or X-Vernier-Key is required"})
        return False

    def do_GET(self):
        path = urlsplit(self.path)
        query = parse_qs(path.query)
        try:
            if self.client_address[0] not in {"127.0.0.1", "::1"} and not self.require_privileged():
                return
            if path.path == "/":
                self.send_json(200, {"service": "Vernier master backend", "routes": [
                    "GET /health", "GET /items", "GET /items/lost", "GET /items/unclaimed", "GET /events",
                    "GET /listings", "GET /machines", "GET /bookings", "GET /outbox",
                    "GET /records/{table}", "POST /message", "POST /camera/item",
                    "POST /camera/item/{id}/removed", "POST /camera/machine",
                    "POST /preferences", "POST /outbox/{id}/ack", "POST /outbox/{id}/retry"]})
            elif path.path == "/health":
                self.send_json(200, {"backend": "ok", "groups_enabled": actions.GROUPS_ENABLED,
                                     "outlook": outlook.status(), **model.status()})
            elif path.path == "/items":
                self.send_json(200, {"items": store.list_items()})
            elif path.path == "/items/lost":
                self.send_json(200, {"items": store.list_open_lost()})
            elif path.path == "/items/unclaimed":
                self.send_json(200, {"items": store.list_unclaimed_found()})
            elif path.path == "/events":
                self.send_json(200, {"events": store.list_events()})
            elif path.path == "/listings":
                self.send_json(200, {"listings": store.list_listings()})
            elif path.path == "/machines":
                self.send_json(200, {"machines": store.list_machines()})
            elif path.path == "/bookings":
                self.send_json(200, {"bookings": store.list_bookings(
                    (query.get("day") or [None])[0], (query.get("room") or [None])[0])})
            elif path.path == "/outbox":
                if self.require_privileged():
                    self.send_json(200, {"messages": store.lease_outbox()})
            elif path.path.startswith("/records/"):
                if not ADMIN_KEY or not hmac.compare_digest(self.headers.get("X-Vernier-Key", ""), ADMIN_KEY):
                    self.send_json(403, {"error": "Set VERNIER_ADMIN_KEY and send X-Vernier-Key for raw records"})
                else:
                    self.send_json(200, {"records": store.records(path.path.split("/", 2)[2])})
            else:
                self.send_json(404, {"error": "Unknown route"})
        except (ValueError, TypeError) as exc:
            self.send_json(400, {"error": str(exc)})
        except Exception as exc:
            print(f"GET failed: {type(exc).__name__}: {exc}")
            self.send_json(503, {"error": "Backend unavailable"})

    def do_POST(self):
        path = urlsplit(self.path).path
        try:
            if self.client_address[0] not in {"127.0.0.1", "::1"} and not self.require_privileged():
                return
            if path == "/message":
                self.send_json(200, actions.handle_message(self.read_json()))
            elif path == "/camera/item":
                if not self.require_privileged():
                    return
                data = self.read_json()
                item_id = store.add_item(kind="found", item=data.get("name", data.get("item")),
                    color=data.get("color", data.get("colour")),
                    place=data.get("foundAt", data.get("place", data.get("location"))),
                    desc_using_keywords=data.get("descUsingKeywords"),
                    custom_string=data.get("customString"), image_href=data.get("imageHref"),
                    please_consult_this_person=data.get("pleaseConsultThisPerson"), source="camera")
                matches = store.find_matches(item_id)
                alerted = store.alert_lost_reporters(item_id)
                self.send_json(201, {"id": item_id,
                                     "matched_lost_ids": [m["id"] for m in matches],
                                     "matched_lost_id": matches[0]["id"] if matches else None,
                                     "alerted_lost_ids": alerted})
            elif re.fullmatch(r"/camera/item/\d+/removed", path):
                if not self.require_privileged():
                    return
                item_id = int(path.split("/")[3])
                item = store.get_item(item_id)
                if not item or item["kind"] != "found" or item["source"] != "camera":
                    raise ValueError("Camera-found item ID does not exist")
                store.set_claim_status(item_id, True)
                self.send_json(200, {"ok": True})
            elif path == "/camera/machine":
                if not self.require_privileged():
                    return
                data = self.read_json()
                store.set_machine(data.get("id"), data.get("location"), data.get("status"))
                self.send_json(200, {"ok": True})
            elif path == "/preferences":
                if not self.require_privileged():
                    return
                data = self.read_json()
                phone = data.get("phone")
                if not isinstance(phone, str):
                    raise ValueError("Phone must be text")
                digits = re.sub(r"\D", "", phone)
                if len(digits) == 10:
                    digits = "91" + digits
                if len(digits) != 12 or not digits.startswith("91"):
                    raise ValueError("Use a 10-digit Indian phone number")
                level = data.get("level", "all")
                contact = f"{digits}@c.us"
                interests = store.save_interests(contact, data.get("interests"), level)
                self.send_json(200, {"ok": True, "contact": contact,
                                     "interests": interests, "level": level})
            elif re.fullmatch(r"/outbox/\d+/(ack|retry)", path):
                if not self.require_privileged():
                    return
                outbox_id, operation = int(path.split("/")[2]), path.split("/")[3]
                store.finish_outbox(outbox_id, sent=operation == "ack")
                self.send_json(200, {"ok": True})
            else:
                self.send_json(404, {"error": "Unknown route"})
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self.send_json(400, {"error": str(exc)})
        except Exception as exc:
            print(f"POST failed: {type(exc).__name__}: {exc}")
            self.send_json(503, {"error": "Model or backend unavailable; check Ollama and try again"})


def sync_outlook(every=60):
    """Keep the bookings table in step with Outlook so the app shows every room booking."""
    last_error = None
    while True:
        if outlook.ready():
            try:
                store.sync_outlook_bookings(*outlook.room_events())
                if last_error:
                    print("Outlook sync working again.")
                last_error = None
            except Exception as exc:
                if str(exc) != last_error:
                    print(f"Outlook sync failed: {exc}")
                last_error = str(exc)
        time.sleep(every)


if __name__ == "__main__":
    if HOST not in {"127.0.0.1", "::1", "localhost"} and not ADMIN_KEY:
        raise RuntimeError("Set VERNIER_ADMIN_KEY before binding outside localhost")
    store.init_db()
    print(f"Outlook room booking: {outlook.status()}")
    if outlook.ready() and not outlook.config().get("allowed_numbers"):
        print("  Warning: allowed_numbers is empty, so anyone who messages the bot can book rooms.")
    threading.Thread(target=sync_outlook, daemon=True).start()
    print(f"Vernier master backend listening at http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
