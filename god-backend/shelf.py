"""Side database for the lost-and-found shelf cameras (shelf.db). PLACEHOLDER until the CV works.

    camera (empty node)  ->  shelf.db  (only the camera side writes here)
    main backend         ->  reads shelf.db  ->  updates vernier.db  (sync_to_main)

The camera never touches vernier.db. The main backend never edits shelf.db.

Commands (run from the Vernier folder):
    python god-backend\\shelf.py list               what the "camera" sees
    python god-backend\\shelf.py add bottle blue "Rack 2"
    python god-backend\\shelf.py remove 3           item 3 was taken off the shelf
    python god-backend\\shelf.py seed 8             add 8 random placeholder items
    python god-backend\\shelf.py clear              empty the shelf database
    python god-backend\\shelf.py sync               push shelf changes into vernier.db now
"""

import os
import random
import sqlite3
import sys
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import store

SHELF_DB = Path(os.environ.get("VERNIER_SHELF_DB", Path(__file__).with_name("shelf.db")))
SHELF_LOCATION = os.environ.get("VERNIER_SHELF_LOCATION", "Lost & found shelf")
SEED_COUNT = int(os.environ.get("VERNIER_SHELF_SEED", "8"))
_sync_lock = threading.Lock()

PLACEHOLDER_ITEMS = [
    ("water bottle", "blue", "steel, sticker on the side"),
    ("earphones case", "white", "boAt, small scratch"),
    ("wallet", "brown", "leather, no ID inside"),
    ("umbrella", "black", "foldable"),
    ("calculator", "grey", "Casio fx-991"),
    ("notebook", "red", "spiral, 200 pages"),
    ("charger", "white", "USB-C, 65W"),
    ("spectacles", "black", "in a blue case"),
    ("keys", "silver", "3 keys on a keychain"),
    ("hoodie", "green", "size M"),
    ("ID card", "blue", "with lanyard"),
    ("headphones", "black", "over-ear"),
    ("pencil pouch", "pink", "zip pouch"),
    ("cap", "white", "plain"),
    ("power bank", "black", "10000 mAh"),
]
SPOTS = ["Rack 1, top", "Rack 1, middle", "Rack 1, bottom", "Rack 2, top", "Rack 2, middle", "Rack 2, bottom"]


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect():
    con = sqlite3.connect(SHELF_DB, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        with con:
            yield con
    finally:
        con.close()


def init_shelf(seed=True):
    SHELF_DB.parent.mkdir(parents=True, exist_ok=True)
    with connect() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS shelf_items (
            id INTEGER PRIMARY KEY,
            item TEXT NOT NULL,
            color TEXT,
            details TEXT,
            spot TEXT,
            camera_id TEXT NOT NULL DEFAULT 'placeholder',
            status TEXT NOT NULL DEFAULT 'on_shelf' CHECK(status IN ('on_shelf','gone')),
            seen_at TEXT NOT NULL,
            gone_at TEXT)""")
        empty = not con.execute("SELECT 1 FROM shelf_items LIMIT 1").fetchone()
    if seed and empty and SEED_COUNT > 0:
        seed_placeholders(SEED_COUNT)


# ---------- Camera side: the ONLY code that writes shelf.db ----------

def camera_feed():
    """EMPTY NODE. The real CV goes here.

    Return a list of what the camera sees on the shelf right now, for example
        [{"item": "water bottle", "color": "blue", "spot": "Rack 1, top"}]
    Return None while there is no camera, and nothing changes.
    """
    return None


def camera_add(item, color=None, details=None, spot=None, camera_id="placeholder"):
    item = (item or "").strip()[:120]
    if not item:
        raise ValueError("Item name is required")
    with connect() as con:
        return con.execute("""INSERT INTO shelf_items(item,color,details,spot,camera_id,seen_at)
            VALUES (?,?,?,?,?,?)""", (item, (color or "").strip()[:60] or None,
                                     (details or "").strip()[:300] or None,
                                     (spot or "").strip()[:80] or None, camera_id, now())).lastrowid


def camera_remove(shelf_id):
    with connect() as con:
        cur = con.execute("UPDATE shelf_items SET status='gone', gone_at=? WHERE id=? AND status='on_shelf'",
                          (now(), int(shelf_id)))
        if not cur.rowcount:
            raise ValueError(f"No item #{shelf_id} on the shelf")


def camera_snapshot(seen, camera_id="placeholder"):
    """Apply one full camera view: new things are added, things no longer seen are marked gone."""
    current = list_shelf(status="on_shelf")
    unmatched = list(current)
    added = []
    for thing in seen:
        key = ((thing.get("item") or "").casefold(), (thing.get("color") or "").casefold())
        match = next((r for r in unmatched if ((r["item"] or "").casefold(), (r["color"] or "").casefold()) == key), None)
        if match:
            unmatched.remove(match)
        else:
            added.append(camera_add(thing.get("item"), thing.get("color"), thing.get("details"),
                                    thing.get("spot"), camera_id))
    for row in unmatched:
        camera_remove(row["id"])
    return {"added": added, "gone": [r["id"] for r in unmatched]}


def run_camera_node():
    """What a camera process would loop on. Does nothing while camera_feed() is empty."""
    seen = camera_feed()
    if seen is not None:
        return camera_snapshot(seen)
    return None


def seed_placeholders(count=8):
    picks = random.sample(PLACEHOLDER_ITEMS, min(count, len(PLACEHOLDER_ITEMS)))
    return [camera_add(item, color, details, random.choice(SPOTS)) for item, color, details in picks]


def clear_shelf():
    with connect() as con:
        con.execute("DELETE FROM shelf_items")


def list_shelf(status=None):
    with connect() as con:
        if status:
            rows = con.execute("SELECT * FROM shelf_items WHERE status=? ORDER BY id", (status,))
        else:
            rows = con.execute("SELECT * FROM shelf_items ORDER BY id")
        return [dict(r) for r in rows]


# ---------- Main side: reads shelf.db, writes only vernier.db ----------

def _init_links():
    with store.connect() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS shelf_links (
            shelf_id INTEGER PRIMARY KEY,
            item_id INTEGER NOT NULL,
            removed_synced INTEGER NOT NULL DEFAULT 0)""")


def sync_to_main():
    """Read shelf.db and bring vernier.db up to date. Safe to call any time."""
    with _sync_lock:
        _init_links()
        with store.connect() as con:
            links = {r["shelf_id"]: dict(r) for r in con.execute("SELECT * FROM shelf_links")}
        added, removed = [], []
        for row in list_shelf():
            link = links.get(row["id"])
            if link and not store.get_item(link["item_id"]):
                with store.connect() as con:
                    con.execute("DELETE FROM shelf_links WHERE shelf_id=?", (row["id"],))
                link = None
            if row["status"] == "on_shelf" and not link:
                place = SHELF_LOCATION + (f", {row['spot']}" if row["spot"] else "")
                item_id = store.add_item(kind="found", item=row["item"], color=row["color"], place=place,
                                         custom_string=row["details"], source="camera")
                with store.connect() as con:
                    con.execute("INSERT INTO shelf_links(shelf_id,item_id) VALUES (?,?)", (row["id"], item_id))
                store.alert_lost_reporters(item_id)
                added.append(item_id)
            elif row["status"] == "gone" and link and not link["removed_synced"]:
                item = store.get_item(link["item_id"])
                if item and item["status"] == "unclaimed":
                    store.set_claim_status(link["item_id"], True)
                with store.connect() as con:
                    con.execute("UPDATE shelf_links SET removed_synced=1 WHERE shelf_id=?", (row["id"],))
                removed.append(link["item_id"])
        return {"added": added, "removed": removed}


def main_id_for(shelf_id):
    _init_links()
    with store.connect() as con:
        row = con.execute("SELECT item_id FROM shelf_links WHERE shelf_id=?", (shelf_id,)).fetchone()
    return row["item_id"] if row else None


def start_sync_loop(every_seconds=None):
    every = float(every_seconds or os.environ.get("VERNIER_SHELF_SYNC_SECONDS", "10"))
    stop = threading.Event()

    def loop():
        while not stop.wait(every):
            try:
                result = sync_to_main()
                if result["added"] or result["removed"]:
                    print(f"Shelf sync: {len(result['added'])} new, {len(result['removed'])} taken")
            except Exception as exc:
                print(f"Shelf sync failed: {type(exc).__name__}: {exc}")

    threading.Thread(target=loop, daemon=True).start()
    return stop


def _cli(args):
    init_shelf(seed=False)
    command = args[0] if args else "list"
    if command == "list":
        rows = list_shelf()
        if not rows:
            print("Shelf database is empty. Try: python god-backend\\shelf.py seed 8")
        for r in rows:
            label = " ".join(v for v in (r["color"], r["item"]) if v)
            print(f"#{r['id']:<3} {r['status']:<9} {label:<24} {r['spot'] or '':<16} {r['details'] or ''}")
    elif command == "add" and len(args) >= 2:
        shelf_id = camera_add(args[1], args[2] if len(args) > 2 else None, None,
                              args[3] if len(args) > 3 else random.choice(SPOTS))
        print(f"Added #{shelf_id} to shelf.db. The backend picks it up within a few seconds.")
    elif command == "remove" and len(args) == 2 and args[1].isdigit():
        camera_remove(int(args[1]))
        print(f"Marked #{args[1]} as taken. The backend marks it claimed within a few seconds.")
    elif command == "seed":
        ids = seed_placeholders(int(args[1]) if len(args) > 1 and args[1].isdigit() else 8)
        print(f"Added {len(ids)} placeholder items.")
    elif command == "clear":
        clear_shelf()
        print("Shelf database emptied. Items already in vernier.db stay there.")
    elif command == "sync":
        store.init_db()
        result = sync_to_main()
        print(f"Synced into vernier.db: {len(result['added'])} new, {len(result['removed'])} taken.")
    else:
        print(__doc__)


if __name__ == "__main__":
    try:
        _cli(sys.argv[1:])
    except ValueError as exc:
        sys.exit(f"Error: {exc}")
