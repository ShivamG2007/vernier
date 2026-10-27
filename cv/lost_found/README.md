# Lost & found shelf camera

Owner: Shivam. Only edit files in your own folder.

`cv_shelf.py` watches the lost & found shelf with YOLOv8x and reports items to the backend.
Right now it is a placeholder: it has the settings and empty functions, and the detection
logic comes later.

## Setup (Windows PowerShell)

```powershell
cd "C:\Users\Shivam Ghosh\Documents\Haha i do coding i am cool\Vernier\cv\lost_found"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu132
pip install -r requirements.txt
```

The `torch` line installs the NVIDIA GPU build; skip it on a laptop without an NVIDIA GPU.
If PowerShell blocks `Activate.ps1`, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

## Model

Put `yolov8x.pt` in this folder (`cv\lost_found\yolov8x.pt`). It is never committed.
`MODEL_PATH` can point somewhere else.

## Run

```powershell
python cv_shelf.py
python cv_shelf.py photo1.jpg photo2.jpg
```

The first command uses the camera; the second uses photos instead.

## Settings (environment variables)

`BACKEND_URL` (http://localhost:8000), `MODEL_PATH` (yolov8x.pt in this folder),
`CAMERA_INDEX` (0), `SHELF_NAME` (Lost & found shelf), `MIN_CONF` (0.4), `IMG_SIZE` (640),
`MOTION_LEVEL` (4), `SETTLE_SECONDS` (1.5), `DRY_RUN` (0).

## Backend endpoints

- `POST /camera/item` with `{"item": ..., "colour": ..., "location": ...}`. It returns `{"id": ..., "matched_lost_id": ...}`.
- `POST /camera/item/{id}/removed`, with no body.
