"""Washing machine camera: says whether one top-loading machine is "in use" or "free".

A lit control panel (display / status LEDs) inside a fixed box means "in use"; a box that
stays dark for FREE_AFTER seconds means "free". While a person stands in front of the panel
(YOLO person detection) the current status is held. Only the status string is ever sent to
the backend; frames never leave this script.

  python cv_machine.py --setup           drag a box around the panel, saves roi_<MACHINE_ID>.json
  python cv_machine.py [--preview] [--demo]
"""
import argparse
import json
import os
import sys
import time
from collections import deque

import cv2
import requests

HERE = os.path.dirname(os.path.abspath(__file__))

CAMERA_INDEX = os.getenv("CAMERA_INDEX", "0")
MACHINE_ID = os.getenv("MACHINE_ID", "m1")
MACHINE_LOCATION = os.getenv("MACHINE_LOCATION", "8th floor boys hostel")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
PANEL_THRESHOLD = float(os.getenv("PANEL_THRESHOLD", "0.25"))
FREE_AFTER = float(os.getenv("FREE_AFTER", "8"))
YOLO_MODEL = os.getenv("YOLO_MODEL", "yolov8x.pt")
YOLO_EVERY = int(os.getenv("YOLO_EVERY", "5"))
PERSON_CHECK = os.getenv("PERSON_CHECK", "1") != "0"  # "0" = no YOLO, never hold the status

ROI_PATH = os.path.join(HERE, f"roi_{MACHINE_ID}.json")
IN_USE, FREE = "in use", "free"
BRIGHT_V = 200        # HSV V value that counts as a lit pixel
WINDOW = 10           # readings kept
IN_USE_MIN = 6        # lit readings out of WINDOW needed for "in use"
DARK_MAX = 2          # at most this many lit readings while counting down to "free"
HEARTBEAT = 60
PERIOD = 1.0          # seconds per loop


def open_camera():
    if CAMERA_INDEX.isdigit():
        cap = cv2.VideoCapture(int(CAMERA_INDEX), cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY)
    else:
        cap = cv2.VideoCapture(CAMERA_INDEX)  # URL or video file
    if not cap.isOpened():
        sys.exit(f"Could not open camera CAMERA_INDEX={CAMERA_INDEX!r}. Check the index, URL or file path.")
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # keep frames fresh at 1 fps
    return cap


def read_frame(cap):
    for _ in range(5):
        ok, frame = cap.read()
        if ok:
            return frame
        time.sleep(0.2)
    return None


def setup_roi():
    cap = open_camera()
    frame = read_frame(cap)
    cap.release()
    if frame is None:
        sys.exit(f"Camera CAMERA_INDEX={CAMERA_INDEX!r} opened but gave no frame.")
    x, y, w, h = cv2.selectROI("Drag a box around the panel, then press ENTER", frame, showCrosshair=True)
    cv2.destroyAllWindows()
    if w == 0 or h == 0:
        sys.exit("No box selected, nothing saved.")
    with open(ROI_PATH, "w") as f:
        json.dump({"x": int(x), "y": int(y), "w": int(w), "h": int(h)}, f)
    print(f"Saved ROI {x},{y},{w},{h} to {ROI_PATH}")


def load_roi():
    if not os.path.exists(ROI_PATH):
        sys.exit(f"No ROI file at {ROI_PATH}. Run: python cv_machine.py --setup")
    with open(ROI_PATH) as f:
        r = json.load(f)
    return r["x"], r["y"], r["w"], r["h"]


def lit_score(frame, roi):
    x, y, w, h = roi
    crop = frame[y:y + h, x:x + w]
    if crop.size == 0:
        sys.exit(f"ROI {roi} is outside the camera frame. Run --setup again.")
    v = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)[:, :, 2]
    return float((v > BRIGHT_V).sum()) / v.size


def load_yolo():
    from ultralytics import YOLO  # imported here so --setup starts fast
    local = os.path.join(HERE, YOLO_MODEL)
    return YOLO(local if os.path.exists(local) else YOLO_MODEL)


def person_near(model, frame, roi):
    x, y, w, h = roi
    result = model(frame, classes=[0], conf=0.4, verbose=False)[0]
    for x1, y1, x2, y2 in result.boxes.xyxy.tolist():
        if x1 < x + w and x < x2 and y1 < y + h and y < y2:
            return True
    return False


def send(status):
    try:
        requests.post(f"{BACKEND_URL}/camera/machine", timeout=5,
                      json={"id": MACHINE_ID, "location": MACHINE_LOCATION, "status": status}).raise_for_status()
        return True
    except requests.RequestException as e:
        print(f"WARNING: could not reach backend at {BACKEND_URL}: {e}")
        return False


def set_status(status, why=""):
    sent = send(status)
    print(f"STATUS -> {status} ({'sent' if sent else 'NOT sent'}){why}")
    return time.time()


def draw(frame, roi, score, person, status, forced):
    x, y, w, h = roi
    colour = (0, 0, 255) if status == IN_USE else (0, 200, 0)
    cv2.rectangle(frame, (x, y), (x + w, y + h), colour, 2)
    cv2.putText(frame, status.upper() + (" (forced)" if forced else ""), (20, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 1.8, colour, 4)
    info = f"lit {score:.3f}" if score is not None else "lit -"
    cv2.putText(frame, f"{info}  person {'yes' if person else 'no'}", (20, 110),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
    cv2.imshow(f"Vernier machine {MACHINE_ID} (local only, q quits)", frame)


def run(preview, demo):
    roi = load_roi()
    cap = open_camera()
    model = None
    if PERSON_CHECK:
        print(f"Loading {YOLO_MODEL} ...")
        model = load_yolo()
    else:
        print("PERSON_CHECK=0: person check off, status is never held.")
    print(f"Machine {MACHINE_ID} ({MACHINE_LOCATION}), ROI {roi}, backend {BACKEND_URL}")

    readings = deque(maxlen=WINDOW)
    status, forced, person = FREE, False, False
    dark_since = None
    last_sent = set_status(status, " at startup")
    frame_no = 0

    while True:
        start = time.time()
        frame = read_frame(cap)
        if frame is None:
            print(f"Camera CAMERA_INDEX={CAMERA_INDEX!r} stopped giving frames, exiting.")
            break

        if PERSON_CHECK and frame_no % YOLO_EVERY == 0:
            person = person_near(model, frame, roi)
        frame_no += 1

        score = None
        if person:
            dark_since = None  # someone at the panel: hold status, restart the free countdown
        else:
            score = lit_score(frame, roi)
            readings.append(score > PANEL_THRESHOLD)
            lit = sum(readings)
            if lit <= DARK_MAX:
                dark_since = dark_since or time.time()
            else:
                dark_since = None
            if not forced:
                if status == FREE and lit >= IN_USE_MIN:
                    status = IN_USE
                    last_sent = set_status(status)
                elif status == IN_USE and dark_since and time.time() - dark_since >= FREE_AFTER:
                    status = FREE
                    last_sent = set_status(status)

        if time.time() - last_sent >= HEARTBEAT:
            send(status)
            last_sent = time.time()

        shown = f"{score:.3f}" if score is not None else "  -  "
        print(f"{time.strftime('%H:%M:%S')}  lit {shown}  person {'yes' if person else 'no '}  status {status}"
              + ("  (forced)" if forced else ""))

        wait = max(0.01, PERIOD - (time.time() - start))
        if preview:
            draw(frame, roi, score, person, status, forced)
            key = cv2.waitKey(40) & 0xFF
            if key == ord("q"):
                break
            if demo and key in (ord("u"), ord("f")):
                forced, status = True, IN_USE if key == ord("u") else FREE
                last_sent = set_status(status, " [demo key]")
            elif demo and key == ord("a") and forced:
                forced = False
                print("Demo override off, back to camera.")
        else:
            time.sleep(wait)

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Washing machine in use / free from a camera.")
    p.add_argument("--setup", action="store_true", help="select the panel box and save it")
    p.add_argument("--preview", action="store_true", help="show a local window (never saved or sent)")
    p.add_argument("--demo", action="store_true", help="u / f force the status, a returns to auto (needs --preview)")
    args = p.parse_args()
    if args.setup:
        setup_roi()
    else:
        if args.demo and not args.preview:
            print("--demo needs the preview window, turning on --preview.")
        try:
            run(args.preview or args.demo, args.demo)
        except KeyboardInterrupt:
            print("Stopped.")
