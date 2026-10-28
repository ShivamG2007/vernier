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
