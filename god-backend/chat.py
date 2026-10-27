"""Terminal client for the master backend."""

import json
import os
from urllib import error, request

BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")


def main():
    print(f"Vernier chat -> {BACKEND_URL}. Type /quit to exit.")
    while True:
        try:
            text = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if text.lower() in {"/quit", "/exit"}:
            break
        if not text:
            continue
        body = json.dumps({"author": "terminal-demo", "text": text}).encode("utf-8")
        req = request.Request(f"{BACKEND_URL}/message", data=body,
                              headers={"Content-Type": "application/json"}, method="POST")
        try:
            with request.urlopen(req, timeout=120) as response:
                answer = json.load(response)
            print("Vernier:", answer.get("reply"))
            print("Action:", answer.get("action"))
        except error.HTTPError as exc:
            print(f"Backend error {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
        except error.URLError:
            print("Backend is unreachable. Start it with: python god-backend\\app.py")


if __name__ == "__main__":
    main()
