# Laundry camera (`cv/cv_machine.py`)

## What it does

A camera watches a box (ROI) drawn around one washing machine's panel light.

- **Lit**: when at least 6 of the last 10 readings have more than `PANEL_THRESHOLD` of the box's pixels bright, the status becomes `"in use"`.
- **Dark**: when no more than 2 of the last 10 readings are lit for `FREE_AFTER` seconds, the status becomes `"free"`.
- **Person in the way**: YOLOv8x checks for people every `YOLO_EVERY` frames. While a person overlaps the box, the current status is held. Set `PERSON_CHECK=0` to turn this off.

The script starts as `"free"`. It talks to the backend only over HTTP and imports nothing from `backend/`.

## Contract with the backend

The script sends `POST {BACKEND_URL}/camera/machine`:

- once at startup
- every time the status changes (including `u` / `f` key presses in `--demo`)
- as a heartbeat, 60 s after the last send

Example body:

```json
{ "id": "m1", "location": "8th floor boys hostel", "status": "in use" }
```

`status` is always exactly `"in use"` or `"free"`. The script expects any 2xx response. If the backend is down it prints a warning and keeps running.

The backend upserts the body into `machines(id, location, status, updated)` and sets `updated` itself. The `ask_laundry` intent reads `location, status, updated` from that table to answer on WhatsApp.

### What the backend must keep

- The path `POST /camera/machine`.
- The three fields `id`, `location`, `status`, all strings.
- The two status strings exactly: `"in use"` and `"free"`.

No new endpoint is needed.

The default `MACHINE_ID` is `m1`. `/dev/seed` creates a row `b8` with the same location, so after seeding there are two "8th floor boys hostel" rows. Either run the camera with `MACHINE_ID=b8` or don't seed `machines`.

## Run it (Windows Command Prompt)

```bat
cd cv
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python cv_machine.py --setup
python cv_machine.py --preview --demo
```

`--setup` grabs one frame. Drag a box around the light and press Enter to save it as `roi_<MACHINE_ID>.json` next to the script. Run it again after changing `MACHINE_ID` or moving the camera.

`--preview` opens a local window; press `q` to quit. `--demo` adds keys to force the status: `u` for in use, `f` for free, and `a` to go back to the camera.

Set environment variables before running. These are the defaults:

```bat
set CAMERA_INDEX=0
set MACHINE_ID=m1
set MACHINE_LOCATION=8th floor boys hostel
set BACKEND_URL=http://localhost:8000
set PANEL_THRESHOLD=0.25
set FREE_AFTER=8
set YOLO_MODEL=yolov8x.pt
set YOLO_EVERY=5
set PERSON_CHECK=1
```

`CAMERA_INDEX` can be a webcam number, a stream URL or a video file path. `PERSON_CHECK=0` skips YOLO completely, which also avoids the slow model load.

## Test the backend without a camera

These requests stand in for the camera.

Command Prompt (`curl.exe` comes with Windows 10 and 11):

```bat
curl -X POST http://localhost:8000/camera/machine -H "Content-Type: application/json" -d "{\"id\":\"m1\",\"location\":\"8th floor boys hostel\",\"status\":\"in use\"}"
curl -X POST http://localhost:8000/camera/machine -H "Content-Type: application/json" -d "{\"id\":\"m1\",\"location\":\"8th floor boys hostel\",\"status\":\"free\"}"
curl http://localhost:8000/records/machines
```

PowerShell:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/camera/machine -ContentType "application/json" -Body '{"id":"m1","location":"8th floor boys hostel","status":"in use"}'
Invoke-RestMethod -Method Post -Uri http://localhost:8000/camera/machine -ContentType "application/json" -Body '{"id":"m1","location":"8th floor boys hostel","status":"free"}'
Invoke-RestMethod http://localhost:8000/records/machines
```

Each POST returns `{"ok": true}`. `/records/machines` should show the latest status with a fresh `updated` time.

## Privacy

Camera frames are never saved to disk or sent anywhere. The preview window is shown only on the camera laptop. The only data that leaves the script is the `id`, `location` and `status` JSON above.
