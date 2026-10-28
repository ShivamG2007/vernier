<<<<<<< HEAD
# Vernier: setup on a brand-new Windows laptop

Vernier is a campus assistant on WhatsApp. It handles lost & found (with a shelf camera), events
and club alerts, room booking (with optional Outlook), washing-machine status from a camera, and
buy/sell. A companion web dashboard shows everything live.

This guide starts from a laptop with **nothing installed** and ends with the whole system running
on that one laptop. It takes about 45 minutes, most of it downloads.

> **How to use the commands:** open **PowerShell** (Start menu → type `PowerShell`) and paste
> **one line at a time**, pressing Enter after each. Don't use `&&`. If a path has spaces, keep
> the quotes.

---

## What runs where

```
 WhatsApp phone ──► WhatsApp bridge (Node.js)  ─┐
                    god-backend\bridge          │
                                                ▼
 Laundry camera ──► cv\cv_machine.py ──► Vernier backend (Python)  ◄──► Ollama (AI model, qwen3:4b)
                                         god-backend\app.py
 Shelf "camera" ──► shelf.db (placeholder) ──►  │  vernier.db (main database)
                                                ▼
                                    Companion dashboard (React)
                                    app\  → http://localhost:5173
 Optional: Outlook calendar  ◄──── room bookings (Microsoft Graph)
```

| Folder | What it is | Used? |
|---|---|---|
| `god-backend\` | **The backend.** AI, database, all features, Outlook, shelf sync | Yes |
| `god-backend\bridge\` | **The WhatsApp bridge** | Yes |
| `app\` | **The companion dashboard** | Yes |
| `cv\cv_machine.py` | **The laundry camera** (works) | Yes |
| `cv\lost_found\` | Shelf camera (not working yet; a placeholder database stands in) | No |
| `backend\`, `bot\` | Old first version, kept for reference | **No, don't run them** |

---

## 1. Install the tools (once)

You need: **Git, Python, Node.js, Ollama, Google Chrome**.

### Option A: with `winget` (fastest)

```powershell
winget install --id Git.Git -e
winget install --id Python.Python.3.12 -e
winget install --id OpenJS.NodeJS.LTS -e
winget install --id Ollama.Ollama -e
winget install --id Google.Chrome -e
```

Accept any prompts. If `winget` isn't recognised, use Option B.

### Option B: download installers

| Tool | Download | During install |
|---|---|---|
| Git | https://git-scm.com/download/win | Keep every default |
| Python 3.12 | https://www.python.org/downloads/ | **Tick "Add python.exe to PATH"** on the first screen |
| Node.js LTS | https://nodejs.org | Keep defaults |
| Ollama | https://ollama.com/download | Keep defaults; it runs in the system tray |
| Chrome | https://www.google.com/chrome | WhatsApp runs through it |

### Check everything installed

**Close PowerShell and open a new one** (new installs only show up in new windows), then:

```powershell
git --version
python --version
node --version
npm --version
ollama --version
```

Each should print a version number.

- **`python` opens the Microsoft Store or says "not found":** open Settings → Apps → Advanced app
  settings → **App execution aliases**, turn **off** both `python.exe` and `python3.exe`, then
  open a new PowerShell. If it's still missing, reinstall Python with "Add to PATH" ticked.
- **`npm` says "running scripts is disabled":** run the next command.

### Allow PowerShell to run scripts (once)

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Type `Y` and press Enter if asked.

---

## 2. Get the code

The repository is private, so the owner must first add your GitHub account as a collaborator,
and you must accept the invite email. Use a folder **outside OneDrive**:

```powershell
mkdir C:\Projects
cd C:\Projects
git clone https://github.com/ShivamG2007/vernier.git
cd vernier
```

A browser window may open asking you to sign in to GitHub. Do that, and the download continues.
From now on, **"the repo folder" means `C:\Projects\vernier`**.

To get teammates' latest changes later:

```powershell
cd C:\Projects\vernier
git pull
```

---

## 3. Download the AI model (once, about 2.5 GB)

Make sure Ollama is running (its llama icon is in the system tray; if not, open **Ollama** from
the Start menu). Then:

```powershell
ollama pull qwen3:4b
ollama list
```

`qwen3:4b` should appear in the list. To check it works, run `ollama run qwen3:4b "say hi"`.
It should reply. If it ever sits there waiting for more input, press `Ctrl + D`.

---

## 4. Start the backend

Open a **new PowerShell window** (this is the **backend window**; keep it open all the time):

```powershell
cd C:\Projects\vernier
python -m pip install -r god-backend\requirements.txt
$env:VERNIER_ENABLE_GROUPS="1"
python god-backend\app.py
```

- The `pip install` line is only needed the first time. It installs `msal` (Outlook) and
  `openpyxl` (Excel tools). The core backend needs nothing else.
- `VERNIER_ENABLE_GROUPS="1"` lets the bot read WhatsApp **group** messages. Leave that line out to
  answer only private messages.
- `$env:` settings only last for that window. Type them again every time you open a new
  backend window.

You should see:

```
Database cleared (previous run saved to vernier-previous.db)
Shelf database (placeholder cameras): 8 items on the shelf, 8 loaded into the main database. Syncing every 10s.
Group chats: on
Outlook room booking: off
Vernier master backend listening at http://127.0.0.1:8000
```

**Every start clears the main database** (the old one is saved as `vernier-previous.db`), so old
alerts are never re-sent. To keep the data instead, also set `$env:VERNIER_KEEP_DB="1"` before
starting.

### Check it

Open http://127.0.0.1:8000/health in a browser. You want:

```
"backend": "ok", "ollama": "ok", "model_ready": true
```

- `"ollama": "unreachable"`: Ollama isn't running. Open it from the Start menu.
- `"model_ready": false`: the model isn't downloaded. Do step 3 again.

### Test the AI without WhatsApp

In a **second** PowerShell window:

```powershell
cd C:\Projects\vernier
python god-backend\chat.py
```

Try `I lost a blue bottle`, then `list items lost and not found`, then `I found a blue bottle`.
Type `/quit` to exit. The first answer is slow (about 20 seconds) while the model loads; after
that it's faster.

---

## 5. Connect WhatsApp

You need the **Vernier WhatsApp number** on a phone (WhatsApp Business), and the backend running.

> **Only one laptop may run the bridge at a time**, otherwise every message gets answered twice.
> If another laptop was running it, stop it there first.

Open a **new PowerShell window** (this is the **bridge window**):

```powershell
cd C:\Projects\vernier\god-backend\bridge
npm install
$env:VERNIER_AUTH_PATH = (Join-Path (Get-Location).Path ".wwebjs_auth")
node index.js
```

- `npm install` is only needed the first time (and after `git pull` if packages changed).
- A **QR code** appears. On the Vernier phone, open WhatsApp → ⋮ (or Settings) → **Linked devices
  → Link a device**, then scan it.
- Wait for: `Vernier is connected. Backend: http://127.0.0.1:8000. Groups: on`.
- The login is saved in `god-backend\bridge\.wwebjs_auth`, so you won't need to scan next time.
  **Never share or upload that folder.** It *is* the WhatsApp login.
- If Chrome is installed somewhere unusual, set its path before `node index.js`:
  `$env:VERNIER_BROWSER_PATH="C:\path\to\chrome.exe"`.

**Test from your own phone:**

| Send | Expected |
|---|---|
| DM the bot: `hi` | A friendly reply |
| DM: `lost my black earbuds in the library` | "I've recorded your lost earbuds…" |
| DM: `interests: dance, music` | "Saved interests…" |
| In a group, **tag** the bot: `@Vernier is the washing machine free?` | Answer in the group |
| DM: `what's on the lost and found shelf?` | List of shelf items |

Group messages that don't tag the bot are read quietly, and any alerts go privately. The bot
never shares anyone's location or camera images.

---

## 6. Start the companion dashboard

Open a **new PowerShell window** (the **app window**):

```powershell
cd C:\Projects\vernier\app
npm install
copy .env.example .env.local
npm run dev
```

- `npm install` and `copy` are only needed the first time.
- Open **http://localhost:5173**. Demo sign-in: username `person1`, password `ABC123`.
- The dashboard reads from the backend (`VERNIER_BACKEND_URL` in `app\.env.local`, default
  `http://127.0.0.1:8000`).

**Show it on a phone** (same Wi-Fi or hotspot as the laptop):

```powershell
npm run dev -- --host
```

Open the `Network:` address it prints (e.g. `http://192.168.x.x:5173`) on the phone. If it
doesn't load, allow the port once in an **administrator** PowerShell:

```powershell
New-NetFirewallRule -DisplayName "Vernier app" -Direction Inbound -Protocol TCP -LocalPort 5173 -Action Allow -Profile Private
```

Also set the Wi-Fi to **Private**: Settings → Network & internet → Wi-Fi → your network →
Private network.

---

## 7. Lost & found shelf (placeholder camera, nothing to install)

The shelf camera's CV isn't working yet, so a separate database, `god-backend\shelf.db`, stands
in for it:

- On first start it fills itself with **8 random placeholder items** (blue water bottle, brown
  wallet…).
- The **camera side writes only to `shelf.db`**. The empty spot for the real CV is
  `camera_feed()` in `god-backend\shelf.py`.
- The **backend reads `shelf.db` every 10 seconds** and updates the main database. A new shelf
  item becomes a "found" item, and anyone who reported a matching lost item gets a WhatsApp
  alert. An item taken off the shelf becomes "claimed".

Pretend to be the camera, from any PowerShell window in the repo folder:

```powershell
python god-backend\shelf.py list
python god-backend\shelf.py add laptop silver "Rack 2, top"
python god-backend\shelf.py remove 3
python god-backend\shelf.py seed 5
python god-backend\shelf.py clear
```

The backend window shows `Shelf sync: 1 new, 1 taken` within about 10 seconds. Browser view:
http://127.0.0.1:8000/shelf.

**Demo flow:** DM the bot `lost my silver laptop`, then run `shelf.py add laptop silver`. The
phone gets a "Possible match" alert.

---

## 8. Laundry camera (needs a webcam)

The laundry camera watches a washing machine's panel light and tells the backend "in use" or
"free". Full details are in `cv\README_cvcode.md`.

Open a **new PowerShell window** (the **camera window**):

```powershell
cd C:\Projects\vernier\cv
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

The line now starts with `(.venv)`. The `pip install` downloads the camera libraries (a few GB,
because of PyTorch), and is only needed once. Next time, just `cd` to the folder and run the
`Activate.ps1` line.

**Optional, for laptops with an NVIDIA GPU:** make the person-detection faster with the GPU
version of PyTorch. RTX 50-series laptops need CUDA 12.8 or newer.

```powershell
pip uninstall -y torch torchvision
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
python -c "import torch; print(torch.cuda.is_available())"
```

`True` means the GPU is in use. Without a GPU, skip this, because the normal version works on
the CPU.

**Point the camera at the machine, then mark the panel light** (once per camera position):

```powershell
$env:MACHINE_ID="b8"
$env:MACHINE_LOCATION="8th floor boys hostel"
python cv_machine.py --setup
```

Drag a box around the panel light and press Enter. It saves `roi_b8.json`.

**Run it** (backend must be running):

```powershell
$env:MACHINE_ID="b8"
$env:MACHINE_LOCATION="8th floor boys hostel"
python cv_machine.py --preview --demo
```

- The first run downloads `yolov8x.pt` (about 130 MB) to check for people standing in front.
  Set `$env:PERSON_CHECK="0"` to skip it.
- In the preview window: `u` forces "in use", `f` forces "free", `a` goes back to automatic, and
  `q` quits. That's handy for the demo.
- If the wrong camera opens, set `$env:CAMERA_INDEX="1"` (or `2`) before running.

Check: http://127.0.0.1:8000/machines shows the status. Then ask the bot "is the washing machine
free?".

---

## 9. Optional: Outlook room booking

Without this, `book MR-2 tomorrow 3 to 4pm` still works, but bookings are stored only in
Vernier's own table. With it, bookings are created in an Outlook calendar. Full guide:
`god-backend\OUTLOOK_SETUP.md`.

**Demo setup with a personal Outlook account** (college accounts usually need IT approval):

1. **Create the room list.** In the repo folder:
   ```powershell
   notepad god-backend\outlook_config.json
   ```
   Click **Yes** to create it, paste this, and save:
   ```json
   {
     "subject": "Room booking (via Vernier)",
     "timezone": "India Standard Time",
     "max_hours": 3,
     "max_days_ahead": 30,
     "allowed_numbers": [],
     "rooms": [
       {"name": "MR-1", "aliases": ["meeting room 1"]},
       {"name": "MR-2", "aliases": ["meeting room 2"]},
       {"name": "Seminar Hall", "aliases": ["seminar room"]},
       {"name": "Music Room", "aliases": ["jam room"]}
     ]
   }
   ```
   Put WhatsApp numbers in `allowed_numbers` (e.g. `["9876543210"]`) to limit who can book.
   Empty means anyone.
2. **Get a token.** Open https://developer.microsoft.com/graph/graph-explorer and sign in with
   the personal Outlook account.
   - In **Graph Explorer's own address box**, enter `https://graph.microsoft.com/v1.0/me/events`
     and click **Run query**.
   - Open **Modify permissions** and click **Consent** on **Calendars.ReadWrite**.
   - Click **Run query** again. It should return `200 OK`.
   - Open the **Access token** tab and copy the token.
3. **Save it** (no backend restart needed):
   ```powershell
   python god-backend\outlook.py token
   ```
   Paste the token when asked. Then check:
   ```powershell
   python god-backend\outlook.py status
   python god-backend\outlook.py book MR-2 2026-11-05 15:00 16:00
   python god-backend\outlook.py upcoming
   python god-backend\outlook.py cancel 1
   ```

The token **expires after about an hour**. Before a demo, copy a fresh one and run
`python god-backend\outlook.py token` again. `outlook_config.json` and the saved token never go
to GitHub.

---

## 10. Every day: start order

Open these in order, each in its own PowerShell window:

| # | Window | Commands |
|---|---|---|
| 1 | Ollama | Open **Ollama** from the Start menu (it may already be running) |
| 2 | Backend | `cd C:\Projects\vernier` → `$env:VERNIER_ENABLE_GROUPS="1"` → `python god-backend\app.py` |
| 3 | Bridge | `cd C:\Projects\vernier\god-backend\bridge` → `$env:VERNIER_AUTH_PATH = (Join-Path (Get-Location).Path ".wwebjs_auth")` → `node index.js` |
| 4 | App | `cd C:\Projects\vernier\app` → `npm run dev` |
| 5 | Laundry camera | `cd C:\Projects\vernier\cv` → `.\.venv\Scripts\Activate.ps1` → `$env:MACHINE_ID="b8"` → `python cv_machine.py --preview --demo` |
| 6 | Outlook (optional) | `python god-backend\outlook.py token` with a fresh token |

To stop anything, press `Ctrl + C` in its window. If you restart the backend, the bridge, app
and camera reconnect on their own.

---

## 11. Optional: spreading it over several laptops

Running everything on one laptop is simplest and is what this guide assumes. To split it, put
all laptops on the same **phone hotspot** (college Wi-Fi often blocks laptop-to-laptop traffic)
and set each network to **Private**. Run `ipconfig` on each laptop to find its IPv4 address.

- **Ollama on another laptop.** On the Ollama laptop:
  1. Run `setx OLLAMA_HOST 0.0.0.0`.
  2. Quit Ollama from the tray and open it again.
  3. Allow port 11434 in an administrator PowerShell:
     `New-NetFirewallRule -DisplayName "Ollama" -Direction Inbound -Protocol TCP -LocalPort 11434 -Action Allow -Profile Private`.

  In the backend window, set `$env:OLLAMA_URL="http://OLLAMA-LAPTOP-IP:11434"` before starting.
- **Backend reachable from other laptops.** In the backend window, set:
  ```powershell
  $env:VERNIER_HOST="0.0.0.0"
  $env:VERNIER_ADMIN_KEY="pick-a-long-secret"
  ```
  Allow port 8000 the same way. Then:
  - **Bridge laptop:** set `$env:BACKEND_URL="http://BACKEND-IP:8000"` and the same
    `$env:VERNIER_ADMIN_KEY`.
  - **App laptop:** put `VERNIER_BACKEND_URL=http://BACKEND-IP:8000` and
    `VERNIER_ADMIN_KEY=...` in `app\.env.local`.
- **Keep the laundry camera on the backend laptop.** `cv_machine.py` doesn't send the admin key,
  so a remote backend would reject its updates.

---

## 12. Settings reference

Set these with `$env:NAME="value"` in the window **before** starting that program.

| Setting | Where | Default | What it does |
|---|---|---|---|
| `VERNIER_ENABLE_GROUPS` | backend | `0` | `1` = read WhatsApp groups |
| `VERNIER_KEEP_DB` | backend | `0` | `1` = don't clear the database on start |
| `VERNIER_MODEL` | backend | `qwen3:4b` | Ollama model name |
| `OLLAMA_URL` | backend | `http://127.0.0.1:11434` | Where Ollama is |
| `VERNIER_HOST` / `VERNIER_PORT` | backend | `127.0.0.1` / `8000` | Backend address |
| `VERNIER_ADMIN_KEY` | backend, bridge, app | none | Needed when the backend is reachable from other laptops |
| `VERNIER_SHELF_SYNC_SECONDS` | backend | `10` | How often the shelf database is read |
| `VERNIER_SHELF_SEED` | backend | `8` | Placeholder items added to an empty shelf |
| `VERNIER_MEMORY_HOURS` | backend | `24` | How long the bot remembers a DM conversation |
| `BACKEND_URL` | bridge, camera, chat.py | `http://127.0.0.1:8000` | Where the backend is |
| `VERNIER_AUTH_PATH` | bridge | `bot\.wwebjs_auth` | Where the WhatsApp login is saved |
| `VERNIER_BROWSER_PATH` | bridge | auto | Chrome/Edge location |
| `MACHINE_ID` / `MACHINE_LOCATION` | camera | `m1` / `8th floor boys hostel` | Which machine the camera watches |
| `CAMERA_INDEX` | camera | `0` | Which webcam (or a video URL/file) |
| `PERSON_CHECK` | camera | `1` | `0` = skip YOLO person detection |

---

## 13. Problems and fixes

| What you see | Fix |
|---|---|
| `python` / `node` / `ollama` not recognised | Close and reopen PowerShell. Python: tick "Add to PATH", and turn off the App execution aliases (step 1) |
| `running scripts is disabled` / `Activate.ps1 cannot be loaded` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `'vite' is not recognized` | Run `npm install` in `app\` first |
| `Cannot find module ...index.js` | Wrong folder. The bridge is `god-backend\bridge` |
| Backend: `Address already in use` / port 8000 busy | Another backend is running. Close it (`Ctrl + C`) and don't run the old `backend\` |
| Bot replies "Model or backend unavailable" | Look in the backend window for the line starting `POST failed:`; it names the problem. Check http://127.0.0.1:8000/health |
| `/health` shows `"ollama": "unreachable"` | Open Ollama from the Start menu |
| Bridge: `Outbox polling failed: fetch failed` | The backend isn't running (or was restarting). Start it; the message stops |
| Bridge: `Groups: off` | Stop the backend, set `$env:VERNIER_ENABLE_GROUPS="1"`, start it again |
| Group tag gets no reply | Tag the bot with @ from the member list, or send a DM |
| QR code every time / `Auth failure` | `Ctrl + C`, delete `god-backend\bridge\.wwebjs_auth`, run again and rescan |
| Every message answered twice | Two laptops run the bridge. Stop one |
| First AI reply very slow | Normal: the model loads on first use (about 20 s) |
| Laundry: `No ROI file` | Run `python cv_machine.py --setup` with the same `MACHINE_ID` |
| Laundry: `Could not open camera` | Try `$env:CAMERA_INDEX="1"`; close other apps using the webcam |
| Outlook: `token expired` | Copy a fresh token from Graph Explorer → `python god-backend\outlook.py token` |
| Outlook: `room emails not filled in` | Remove the `email` lines from `outlook_config.json` (personal-account mode) |
| `git push` rejected | `git pull` first, then push again. Never use `--force` |

---

## 14. Never upload these to GitHub

They're already in `.gitignore`. Don't force-add them:

- `god-backend\bridge\.wwebjs_auth\`: the WhatsApp login
- `*.db` (`vernier.db`, `shelf.db`): local data with phone numbers
- `god-backend\outlook_config.json`, `outlook_token.json`, `outlook_manual_token.txt`: Outlook
  access
- `app\.env.local`, `.venv\`, `node_modules\`, `*.pt` (model files)

Git routine for the team: **pull → edit only your own files → commit → pull → push.**
=======
<h1 align="center">Vernier</h1>

<p align="center"><strong>A campus companion for WhatsApp and the web</strong></p>

<p align="center">Report lost items, find events and second-hand listings, check rooms and laundry machines, and get useful alerts in one place.</p>

<p align="center"><a href="#what-you-can-do">Explore features</a> · <a href="#quick-start">Get started</a> · <a href="#dashboard">Open the dashboard</a> · <a href="#project-layout">Browse the project</a></p>

> **Prototype status:** Vernier currently runs locally. Lost-and-found matches are suggestions; a person at the desk must verify ownership before handing over an item.

## Demo sign-in

After starting the dashboard, sign in with these demo credentials:

| Username | Password |
| :--- | :--- |
| `person1` | `ABC123` |

The sign-in is a local demo gate, not a verified campus account or backend authentication.

## What you can do

| Feature | Try it |
| :--- | :--- |
| **Lost and found** | Report or search for items, browse open lost reports and unclaimed finds, and get possible-match alerts. Claims require desk review. |
| **Events and marketplace** | Post and browse campus events and second-hand listings; alert interested students. |
| **Rooms** | Check and create Vernier-local bookings. Outlook booking is available with separate configuration. |
| **Laundry** | View the latest submitted machine observation; the camera script can send status updates. |
| **Dashboard** | Browse selected public records, dates, bookings, and machine status. |

Messages can be in English, Hindi, or Hinglish, though model interpretation is still imperfect. Group-message processing is off by default.

## How Vernier works

```text
WhatsApp bridge or terminal chat
              │
              ▼
       Python HTTP backend ◀────▶ Ollama (qwen3:4b)
              │
              ▼
      SQLite records + alert outbox
              ├────────▶ WhatsApp notifications
              └────────▶ React dashboard (public fields only)
```

Ollama proposes an action from each message. The Python backend validates it, applies the rules, reads or writes records, and prepares the reply. Lost-and-found matching uses word overlap and colour checks in Python.

## Quick start

These commands use **PowerShell** and start from the repository root (the folder containing `god-backend` and `app`).

**You need:** Python 3, [Ollama](https://ollama.com/), and a running Ollama service. The dashboard and WhatsApp bridge also need Node.js and npm. The bridge additionally needs Chrome or Edge and a WhatsApp test account.

### 1. Download the model

```powershell
ollama pull qwen3:4b
```

### 2. Start the backend

In a PowerShell window:

```powershell
$env:VERNIER_KEEP_DB = "1"
$env:VERNIER_SHELF_SEED = "0"
python god-backend\app.py
```

The API listens at `http://127.0.0.1:8000`. `VERNIER_KEEP_DB=1` preserves reports across restarts. Without it, startup copies the previous main database to `vernier-previous.db` and clears the live one. `VERNIER_SHELF_SEED=0` prevents eight sample shelf items from appearing on a fresh setup; it does not clear an existing local shelf database.

### 3. Check the service and try a chat

In a second PowerShell window:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
python god-backend\chat.py
```

Try `I lost a blue bottle`, `I found a blue bottle`, or `List unclaimed found items`. Type `/quit` to exit. The terminal uses the same message endpoint as WhatsApp.

### Dashboard

With the backend running, open another PowerShell window:

```powershell
cd app
npm ci
Copy-Item .env.example .env.local
npm run dev
```

Open **http://localhost:5173** and use the [demo sign-in](#demo-sign-in). If the backend is elsewhere, set `VERNIER_BACKEND_URL` in `app/.env.local`. The dashboard server reads the backend; the browser does not need its admin key. See [dashboard setup and deployment](app/README.md) for details.

### WhatsApp bridge (optional)

Keep Ollama and the backend running. In another PowerShell window:

```powershell
cd god-backend\bridge
npm ci
$env:VERNIER_AUTH_PATH = (Join-Path (Get-Location).Path ".wwebjs_auth")
npm start
```

Scan the QR code from the test phone's **Linked devices** screen. Run only one bridge for that account. Its local login folder is ignored by Git. The bridge uses `http://127.0.0.1:8000` by default; set `BACKEND_URL` if needed. For a full Windows walkthrough, see [README_GODBACKEND.md](README_GODBACKEND.md).

## Project layout

| Directory | What is there |
| :--- | :--- |
| [`god-backend/`](god-backend/) | Python API, message handling, SQLite store, alert outbox, and optional Outlook integration. |
| [`god-backend/bridge/`](god-backend/bridge/) | WhatsApp Web bridge. |
| [`app/`](app/) | React/Vite dashboard and server-side public-record adapter. |
| [`cv/`](cv/) | Camera experiments, including the laundry status reader. Shelf detection is unfinished. |
| [`backend/`](backend/) and [`bot/`](bot/) | Earlier implementations kept for reference. |

## Local data and prototype limits

- SQLite databases and WhatsApp login files stay on the machine and are ignored by Git. The optional team workbook is not imported automatically.
- Dashboard profile preferences stay in the browser and do not configure delivered WhatsApp alerts. Students set those by messaging the bot.
- The backend trusts sender IDs supplied by the local bridge. Keep the default localhost binding for a local demo. A public deployment needs verified identity and a fuller data-deletion process.
- Room availability uses Vernier's own records unless Outlook is configured. Machine status is only as current as its latest observation. The lost-and-found shelf feed is a placeholder, not live detection.
- `forget my conversation` clears short-term server memory, not saved reports or preferences. Requests for another person's whereabouts or camera footage are refused.

For detailed API behavior and optional integrations, see the [backend README](god-backend/README.md), [Outlook setup](god-backend/OUTLOOK_SETUP.md), and [features and test routine](god-backend/FEATURES_AND_TEST_ROUTINE.txt).
>>>>>>> 520da25d639a7ebbf200ec8dce1cb63894b9bbcb
