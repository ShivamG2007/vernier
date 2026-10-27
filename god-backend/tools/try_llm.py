"""Optional labelled prompt check; does not write to the database."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import model  # noqa: E402

ALIASES = {
    "lost_report": "report_lost", "found_report": "report_found", "ask_lost": "search_found",
    "chit_chat": "chat", "other": "chat",
}


def main():
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "samples_labelled.txt"
    total = correct = 0
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "|" not in line:
            continue
        expected, message = (part.strip() for part in line.split("|", 1))
        expected = ALIASES.get(expected, expected)
        try:
            got = model.plan_message(message).get("action")
        except Exception as exc:
            got = f"ERROR: {exc}"
        total += 1
        correct += got == expected
        if got != expected:
            print(f"Expected {expected}, got {got}: {message}")
    print(f"Action labels: {correct}/{total}")


if __name__ == "__main__":
    main()
