import os
import sys

# Ensure backend root is in sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

try:
    import db
except ImportError as e:
    print(f"Error importing db: {e}")
    sys.exit(1)

try:
    import openpyxl
except ImportError:
    print("Error: openpyxl is not installed. Please install it (e.g. pip install openpyxl).")
    sys.exit(1)

TARGET_TABLES = ["lost_found", "events", "listings", "machines", "bookings", "students", "outbox"]


def run_export():
    export_path = os.getenv(
        "VERNIER_EXPORT_XLSX",
        os.path.join(backend_dir, "vernier_export.xlsx")
    )

    original_db_xlsx = os.path.abspath(os.path.join(backend_dir, "Vernier_Database.xlsx"))
    export_abs = os.path.abspath(export_path)

    # Safety check: Never overwrite original Vernier_Database.xlsx
    if export_abs.lower() == original_db_xlsx.lower():
        print(f"ERROR: Cannot overwrite original database template '{original_db_xlsx}'.")
        sys.exit(1)

    # Initialize / connect to DB
    db.init_db()
    con = db.connect()

    wb = openpyxl.Workbook()
    default_sheet = wb.active

    counts = {}

    try:
        for table in TARGET_TABLES:
            pragma = con.execute(f'PRAGMA table_info("{table}")').fetchall()
            if not pragma:
                counts[table] = 0
                continue

            cols = [col["name"] for col in pragma]
            ws = wb.create_sheet(title=table)
            ws.append(cols)

            rows = con.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall()
            for r in rows:
                ws.append([r[c] for c in cols])

            counts[table] = len(rows)

        # Remove the initial blank sheet created by openpyxl
        if default_sheet in wb.worksheets and len(wb.worksheets) > 1:
            wb.remove(default_sheet)

        wb.save(export_path)
    finally:
        con.close()

    print(f"\nExport successful to: {export_path}")
    print("-" * 35)
    for table, count in counts.items():
        print(f"  {table:<15}: {count:>4} rows")
    print("-" * 35)
    print(f"  {'Total':<15}: {sum(counts.values()):>4} rows\n")


if __name__ == "__main__":
    run_export()
