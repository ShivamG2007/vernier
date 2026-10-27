# Run Vernier god-backend on a Windows laptop

These steps run the backend locally on **your** laptop. You do not need Avik's database, WhatsApp login files, the old Python `backend`, or the old `bot` to test the core service. Commands below are for **PowerShell**; run each line separately.

## 1. Install and check prerequisites

Install Python 3, Ollama, and (only for WhatsApp) Node.js 18+ and Chrome or Edge. Then open PowerShell:

```powershell
python --version
ollama --version
node --version
npm --version
```

If you are only testing with the terminal chat, Node.js and the browser are optional. If a command is not recognized, install that program and reopen PowerShell.

## 2. Get the latest repository

For a fresh copy, open PowerShell in the directory where you want the project:

```powershell
git clone https://github.com/ShivamG2007/vernier.git
cd vernier
```

If you already have the repository, open PowerShell in its folder instead:

```powershell
git pull
```

The following commands assume PowerShell is at the repository root, with `god-backend` visible when you run `ls`.

## 3. Get the model ready

Start the Ollama Windows app, then run:

```powershell
ollama pull qwen3:4b
ollama list
```

You should see `qwen3:4b` in the list. Leave Ollama running. If `ollama list` cannot connect, start the Ollama app and try again. If you run Ollama manually with `ollama serve`, keep that PowerShell window open.

## 4. Start the backend

Open a **new** PowerShell window at the repository root:

```powershell
python god-backend\app.py
```

Leave it open. It should say it is listening at `http://127.0.0.1:8000`. A fresh `god-backend\vernier.db` is created automatically; do not copy someone else's database.

In another PowerShell window, check its health:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health | ConvertTo-Json
```

Look for `"backend": "ok"`, `"ollama": "ok"`, and `"model_ready": true`.

## 5. Test without WhatsApp

In that second PowerShell window, from the repository root:

```powershell
python god-backend\chat.py
```

Type one message at a time. For example: `I lost a blue bottle`, then `List items lost and not found`, then `I found a blue bottle`. Type `/quit` to exit. This uses the same `/message` backend route as WhatsApp, without needing a phone or Node.js.

If a model response takes longer than 25 seconds, Vernier asks you to rephrase. The backend stays running for the next message. Some model action choices are still imperfect; check the returned `Action:` line when testing.

## 6. Optional: connect WhatsApp

Do this only with a test account and known participants. Run **one** Vernier bridge at a time so messages are not handled twice. The backend and Ollama must already be running.

Open another PowerShell window at the repository root:

```powershell
cd god-backend\bridge
npm install
$env:VERNIER_AUTH_PATH = (Join-Path (Get-Location).Path ".wwebjs_auth")
node index.js
```

Scan the displayed QR code on the WhatsApp phone under **Linked devices**. The login stays in your own `god-backend\bridge\.wwebjs_auth` folder, which Git ignores. Never send that folder to anyone. The bridge ignores groups by default.

The bridge looks for normal Chrome or Edge installations on Windows. If your browser is somewhere else, set its full executable path **before** `node index.js`:

```powershell
$env:VERNIER_BROWSER_PATH = "C:\path\to\chrome.exe"
```

If port 8000 is already occupied, stop the other backend rather than starting two copies. Press `Ctrl+C` in a window to stop its process.

## 7. Optional: sample data and spreadsheet tools

The service starts with an empty database. To add fabricated demo records, run this from the repository root in another PowerShell window:

```powershell
python god-backend\tools\seed_demo.py --apply
```

The core backend needs no pip packages. Only the Excel check/import/export tool needs `openpyxl`:

```powershell
python -m pip install -r god-backend\requirements.txt
python god-backend\tools\excel.py check --source backend\Vernier_Database.xlsx
```

The team workbook is optional and is **not** imported automatically. Do not use `--apply` unless you intentionally want its rows added to your local database. Historical imported alerts are marked sent.

## What is local to each laptop?

- Ollama model download, Python/Node packages, and Chrome or Edge installation.
- SQLite database and WhatsApp QR login. Neither needs to be pushed to GitHub.
- The bridge's `npm install` creates its own `node_modules`; that directory is ignored by Git.

Room bookings are Vernier's own records, not the campus's official booking system. Camera endpoints accept observations but do not run computer vision or provide footage.
