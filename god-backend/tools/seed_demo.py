"""Optional fabricated demo records. Run only with --apply."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import store  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Add fabricated demo records")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.apply:
        print("No data changed. Add --apply to insert demo records.")
        return
    store.init_db()
    with store.connect() as con:
        if con.execute("SELECT 1 FROM legacy_imports WHERE source_name='demo_seed' LIMIT 1").fetchone():
            print("Demo seed was already applied.")
            return
    for item, color, place in [
        ("bottle", "clear", "Rack C, Basket 3"),
        ("hoodie", "pink", "Rack B, Hanger 4"),
        ("backpack", "purple", "Rack B, Bottom"),
        ("gloves", "black", "Rack C, Basket 1"),
        ("lunch bag", "blue", "Rack A, Shelf 1"),
    ]:
        store.add_item(kind="found", item=item, color=color, place=place, source="camera")
    with store.connect() as con:
        for title, category, when, venue, major in [
            ("Dance Club auditions", "dance", "Friday 5 PM", "Auditorium", False),
            ("Inter-hostel football final", "sports", "Saturday 4 PM", "Main ground", True),
            ("Open mic night", "music", "Sunday 7 PM", "Amphitheatre", False),
            ("Annual tech fest registrations", "tech", "This week", "Block C", True),
        ]:
            con.execute("""INSERT INTO events(title,category,date,venue,major,source,created_at)
                VALUES (?,?,?,?,?,'demo_seed',?)""",
                (title, category, when, venue, int(major), store.now()))
        for item, price in [("cycle", "₹2000"), ("study table", "₹800"),
                            ("engineering drawing kit", "₹300")]:
            con.execute("""INSERT INTO listings(kind,item,price,details,contact,alerts_enabled,created_at)
                VALUES ('sell',?,?,?,'demo_seed',0,?)""",
                (item, price, f"selling {item}", store.now()))
    store.set_machine("b8", "8th floor boys hostel", "in use")
    store.set_machine("g3", "3rd floor girls hostel", "free")
    with store.connect() as con:
        con.execute("""INSERT INTO legacy_imports(source_name,table_name,source_key,local_id)
            VALUES ('demo_seed','all','1','1')""")
    print("Fabricated demo records added.")


if __name__ == "__main__":
    main()
