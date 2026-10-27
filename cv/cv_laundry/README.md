# Laundry machine camera

Owner: laundry teammate. Only edit files in your own folder.

`cv_machine.py` watches a washing machine and tells the backend whether it is in use.
Right now it is a placeholder: it has the settings and empty functions, and the detection
logic comes later.

## Setup (Windows PowerShell)

```powershell
cd cv\laundry
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python cv_machine.py
```

If PowerShell blocks `Activate.ps1`, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

## Settings (environment variables)

`BACKEND_URL` (http://localhost:8000), `CAMERA_INDEX` (0), `MACHINE_ID` (b8),
`MACHINE_LOCATION` (8th floor boys hostel).

## Backend endpoint

- `POST /camera/machine` with `{"id": ..., "location": ..., "status": ...}`.
  `status` is exactly `"in use"` or `"free"`. Send it only when the status changes.
