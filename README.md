# Vernier

Vernier is a prototype campus assistant for WhatsApp, with a companion web dashboard. Students can report lost and found items, discover events and second-hand listings, ask about rooms and laundry machines, and receive relevant alerts. The dashboard shows selected public records from the same backend.

The current implementation runs locally. A lost-and-found match is a suggestion: a person at the desk must verify ownership before an item is handed over.

## How it works

```text
WhatsApp bridge or terminal chat
            |
            v
      Python HTTP backend <----> Ollama (qwen3:4b)
            |
            v
     SQLite records and alert outbox
            |
            +----> WhatsApp notifications
            +----> React dashboard (public fields only)
```

Ollama turns a message into a proposed action. The Python backend validates that action, applies the rules, reads or writes records, and prepares the reply. Lost-and-found matching uses word overlap and colour checks in Python; it is not an AI similarity search.

## What you can try

| Area | Current behavior |
| --- | --- |
| Lost and found | Report or search for items, list open lost reports and unclaimed found items, and queue possible-match alerts. Claims require desk review. |
| Events and marketplace | Post and browse events and second-hand listings; send alerts to interested students. |
| Rooms | Check and create Vernier-local bookings. Microsoft Outlook booking is optional and requires separate configuration. |
| Laundry | Show the latest submitted machine observation. The camera script can submit status updates. |
| Dashboard | Browse selected public records, dates, bookings, and machine status in a React app. |

Messages can be in English, Hindi, or Hinglish, although model interpretation is still imperfect. Group-message processing is off by default.

## Quick start (PowerShell)

Run these commands from the repository root, the folder containing `god-backend` and `app`.

**Prerequisites:** Python 3, [Ollama](https://ollama.com/), and a running Ollama service. Node.js and npm are needed for the dashboard or WhatsApp bridge. The bridge also needs Chrome or Edge and a WhatsApp test account.

1. Download the model:

   ```powershell
   ollama pull qwen3:4b
   ```

2. Start the backend in a PowerShell window:

   ```powershell
   $env:VERNIER_KEEP_DB = "1"
   $env:VERNIER_SHELF_SEED = "0"
   python god-backend\app.py
   ```

   It listens at `http://127.0.0.1:8000`. `VERNIER_KEEP_DB=1` preserves reports across restarts; without it, startup copies the previous main database to `vernier-previous.db` and clears the live one. `VERNIER_SHELF_SEED=0` prevents the placeholder shelf from creating eight sample items on a fresh setup. An existing local shelf database is not cleared by this setting.

3. In a second window, check the service and chat with it:

   ```powershell
   Invoke-RestMethod http://127.0.0.1:8000/health
   python god-backend\chat.py
   ```

   Try `I lost a blue bottle`, `I found a blue bottle`, or `List unclaimed found items`. Type `/quit` to exit. The terminal uses the same message endpoint as WhatsApp.

### Dashboard

With the backend running, use another PowerShell window:

```powershell
cd app
npm ci
Copy-Item .env.example .env.local
npm run dev
```

Open `http://localhost:5173`. The demo sign-in is `person1` / `ABC123`. Set `VERNIER_BACKEND_URL` in `app/.env.local` if the backend is elsewhere. The dashboard's server reads the backend; the browser does not need its admin key. See [app/README.md](app/README.md) for build and deployment details.

### WhatsApp bridge (optional)

Keep Ollama and the backend running. In another PowerShell window:

```powershell
cd god-backend\bridge
npm ci
$env:VERNIER_AUTH_PATH = (Join-Path (Get-Location).Path ".wwebjs_auth")
npm start
```

Scan the QR code with the test phone's **Linked devices** screen. Run only one bridge for that account. The login folder is local and Git-ignored. The bridge uses `http://127.0.0.1:8000` by default; set `BACKEND_URL` if needed. See [README_GODBACKEND.md](README_GODBACKEND.md) for a full Windows walkthrough.

## Project layout

| Path | Purpose |
| --- | --- |
| [`god-backend/`](god-backend/) | Combined Python API, message handling, SQLite store, alert outbox, and optional Outlook integration. Start here for the backend. |
| [`god-backend/bridge/`](god-backend/bridge/) | WhatsApp Web bridge. |
| [`app/`](app/) | React/Vite dashboard and server-side public-record adapter. |
| [`cv/`](cv/) | Camera experiments, including the laundry status reader. Lost-and-found shelf detection is unfinished. |
| [`backend/`](backend/) and [`bot/`](bot/) | Earlier implementations kept for reference. |

## Local data and prototype limits

- SQLite databases and WhatsApp login files stay on the machine and are ignored by Git. The optional team workbook is not imported automatically.
- The dashboard sign-in is a demo screen, not verified user authentication. Its profile preferences are stored in the browser and do not configure delivered WhatsApp alerts; students set those by messaging the bot.
- The backend trusts sender IDs supplied by the local bridge. Keep the default localhost binding for a local demo. A public deployment needs verified identity and a fuller data-deletion process.
- Room availability is based on Vernier's own records unless Outlook is configured. Machine status is only as current as its latest observation. The lost-and-found shelf feed is a placeholder, not live detection.
- `forget my conversation` clears short-term server memory, not saved reports or preferences. Requests for another person's whereabouts or camera footage are refused.

For detailed API behavior and optional integrations, see [god-backend/README.md](god-backend/README.md), [god-backend/OUTLOOK_SETUP.md](god-backend/OUTLOOK_SETUP.md), and [god-backend/FEATURES_AND_TEST_ROUTINE.txt](god-backend/FEATURES_AND_TEST_ROUTINE.txt).
