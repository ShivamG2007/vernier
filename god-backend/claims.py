"""Local command for reviewing claim requests and marking collection status."""

import argparse

import store


def main():
    parser = argparse.ArgumentParser(description="Manage found items locally")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    sub.add_parser("requests")
    sub.add_parser("claim").add_argument("id", type=int)
    sub.add_parser("unclaim").add_argument("id", type=int)
    args = parser.parse_args()
    store.init_db()
    if args.command == "list":
        for row in store.list_found_items():
            print(f"#{row['id']} [{row['status']}] {row['name']}")
    elif args.command == "requests":
        for row in store.records("claim_requests"):
            print(f"Request #{row['id']}: item #{row['item_id']}, {row['contact']}, {row['details'] or ''}")
    else:
        try:
            store.set_claim_status(args.id, args.command == "claim")
        except ValueError as exc:
            parser.error(str(exc))
        print(f"Found item #{args.id} marked {'claimed' if args.command == 'claim' else 'unclaimed'}.")


if __name__ == "__main__":
    main()
