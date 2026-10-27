"""
Vernier - lost & found shelf camera (YOLOv8x).

Placeholder: settings and function stubs only. Detection logic is written later.
Run:  python cv_shelf.py               (camera)
      python cv_shelf.py a.jpg b.jpg   (photos)
"""

import os
import sys
import time

import cv2
import numpy as np
import requests
from ultralytics import YOLO

# ---------------------------------------------------------------- settings --

HERE = os.path.dirname(os.path.abspath(__file__))

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
MODEL_PATH = os.getenv("MODEL_PATH", os.path.join(HERE, "yolov8x.pt"))
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))
SHELF_NAME = os.getenv("SHELF_NAME", "Lost & found shelf")
MIN_CONF = float(os.getenv("MIN_CONF", "0.4"))
IMG_SIZE = int(os.getenv("IMG_SIZE", "640"))
MOTION_LEVEL = float(os.getenv("MOTION_LEVEL", "4"))
SETTLE_SECONDS = float(os.getenv("SETTLE_SECONDS", "1.5"))
DRY_RUN = os.getenv("DRY_RUN", "0") == "1"

model = None


# ------------------------------------------------------------------- stubs --

def read_image(path):
    pass


def colour_name(crop):
    pass


def iou(a, b):
    pass


def detect(frame):
    pass


def report_new(item):
    pass


def report_removed(item):
    pass


def run_photos(paths):
    pass


def run_camera():
    pass


# -------------------------------------------------------------------- main --

if __name__ == "__main__":
    if not os.path.isfile(MODEL_PATH):
        sys.exit(f"Model not found: {MODEL_PATH}\nPut yolov8x.pt in cv\\lost_found\\ (see README.md).")
    model = YOLO(MODEL_PATH)
    print("model ready")
    if sys.argv[1:]:
        run_photos(sys.argv[1:])
    else:
        run_camera()
