import json
import sys
import time

import llm

path = sys.argv[1] if len(sys.argv) > 1 else "samples.txt"
lines = [l.strip() for l in open(path, encoding="utf-8") if l.strip() and not l.startswith("#")]

print(f"Model: {llm.MODEL} at {llm.OLLAMA_URL}\n")

# Detect if the file is labelled ("intent | message")
labelled_tests = []
for line in lines:
    if "|" in line:
        exp, msg = line.split("|", 1)
        labelled_tests.append((exp.strip(), msg.strip()))

is_labelled = len(labelled_tests) == len(lines) and len(lines) > 0 and any(
    exp in llm.INTENTS for exp, _ in labelled_tests
)

if is_labelled:
    wrongs = []
    for expected, msg in labelled_tests:
        t = time.time()
        try:
            data = llm.extract(msg)
            got = data.get("intent", "?")
        except Exception as e:
            got = f"ERROR ({e})"

        if got != expected:
            wrongs.append((expected, got, msg))
            print(f"[FAIL] Expected: {expected} | Got: {got}  ({time.time() - t:.1f}s)")
            print(f"   <- {msg}\n")

    total = len(labelled_tests)
    correct = total - len(wrongs)
    pct = (correct / total * 100) if total else 0.0
    print(f"Accuracy: {correct}/{total} ({pct:.1f}%)")
    if not wrongs:
        print("All tests passed!\n")
else:
    for line in lines:
        t = time.time()
        try:
            data = llm.extract(line)
        except Exception as e:
            print(f"ERROR {e}\n")
            continue
        intent = data.pop("intent", "?")
        fields = {k: v for k, v in data.items() if v not in ("", None, False)}
        print(f"[{intent}] {json.dumps(fields, ensure_ascii=False)}  ({time.time() - t:.1f}s)")
        print(f"   <- {line}\n")
