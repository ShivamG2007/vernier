"""
Vernier - laundry machine camera.

Placeholder: settings and function stubs only. Detection logic is written later.
Run:  python cv_machine.py
"""

import os
import time

import cv2
import numpy as np
import requests

# ---------------------------------------------------------------- settings --

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))
MACHINE_ID = os.getenv("MACHINE_ID", "b8")
MACHINE_LOCATION = os.getenv("MACHINE_LOCATION", "8th floor boys hostel")


# ------------------------------------------------------------------- stubs --

def report_status(status):
    pass


def run_camera():
    pass


# -------------------------------------------------------------------- main --

if __name__ == "__main__":
    run_camera()
