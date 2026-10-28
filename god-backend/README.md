# Vernier master backend

This folder combines Avik's local backend with the team's wider campus features. The original `backend` and `bot` folders remain untouched. Run only one backend and one WhatsApp bridge at a time on the same port/login profile.

## What it does

- Direct-message chat: lost/found reports, search, separate lists for unresolved lost reports and unclaimed found items, claim requests, events, interests, listings, room bookings, and machine-status questions.
- Found-item matching: a new found report searches open lost reports and queues a possible-match alert. Claim requests still require lost-and-found desk verification; they never mark an item collected automatically.
- Event and listing alerts: interest subscribers receive matching event alerts; buyers can be alerted when a matching sale is posted.
- Camera setters: add a found item, mark a camera item removed, and update a machine's status. These accept structured observations; this project does not perform CV inference or expose camera footage.
- Optional group ingestion: keyword/mention filtering, with no public reply to unmentioned group posts. It is off by default in both backend and bridge.
- Spreadsheet tools: preview or import the team's existing Excel data, or export this backend's data. Imports are additive and repeat-safe. Historical outbox rows are marked sent so importing them cannot send stale notifications.

The core Python backend uses the standard library. The optional Excel tool needs `openpyxl` from `requirements.txt`. The bridge uses `whatsapp-web.js` and `qrcode-terminal`.

## Conversation context and privacy

For direct messages, the backend keeps up to eight recent exchanges and six short factual notes per sender in server memory. Idle sessions expire after 24 hours by default (`VERNIER_MEMORY_HOURS` changes this); a server restart also clears them. Group messages never enter this memory, even when group ingestion is enabled. No persistent personal chat profile is created.

The model first chooses a schema-constrained action using the current message and that sender's bounded context. The backend validates the action and retrieves only the relevant records. A separate reply stage writes general chat and some record-backed answers; item lists, write confirmations, claims, and safety refusals use backend-written replies. Record-backed replies receive scoped public fields, not reporter contacts or raw database tables.

Each message has a 25-second Ollama processing limit across action selection and reply generation. If that limit is reached, Vernier sends a short request to rephrase and continues accepting later messages; the server does not shut down.

A direct message of `forget my conversation` (also `clear my chat` or `delete my memory`) clears that sender's short-term context. It does **not** delete item reports, preferences, claim requests, or operational message IDs from SQLite. New message-ID deduplication entries store the action without reply text; older entries from before this change may still contain replies in the local database. The database is ignored by Git.

The HTTP API trusts the sender ID supplied by the local WhatsApp bridge. Keep the backend bound to localhost for the prototype. If exposing it beyond localhost, set the same `VERNIER_ADMIN_KEY` in backend and bridge so remote requests require `X-Vernier-Key`. A public multi-user deployment would need verified sender identity and a fuller data-deletion workflow.

## Run locally

In separate PowerShell windows from `C:\Vernier`:

```powershell
python god-backend\app.py
```

```powershell
python god-backend\chat.py
```

For WhatsApp, stop the old `bot` process before starting this bridge. It reuses that bot's private login folder by path without copying its files:

```powershell
cd C:\Vernier\god-backend\bridge
node index.js
```

If the existing bot's dependencies are unavailable, run `npm install` in `god-backend\bridge` first. The bridge uses `BACKEND_URL` (default `http://127.0.0.1:8000`). To process known demo groups, set `VERNIER_ENABLE_GROUPS=1` in the **backend** window before starting it. The bridge asks the backend and follows its setting, so it needs nothing. Keep it off until the team has agreed on group participation and consent.

The bridge uses an installed Chrome or Edge executable if Puppeteer's own browser is missing. Set `VERNIER_BROWSER_PATH` before `node index.js` only if your browser is installed somewhere else.

The backend binds to `127.0.0.1:8000` by default. `VERNIER_HOST`, `VERNIER_PORT`, `VERNIER_DB`, `OLLAMA_URL`, and `VERNIER_MODEL` are configurable. If you expose it beyond localhost, set `VERNIER_ADMIN_KEY` in both backend and bridge windows. The bridge sends it as `X-Vernier-Key`. `VERNIER_CORS_ORIGINS` is a comma-separated list of allowed browser origins.

The local `god-backend\vernier.db` started as a snapshot of `backend\vernier.db` and now also contains the team's workbook records. It is ignored by Git. Future records go into this master copy; both original sources stay unchanged.

## API contract

`POST /message` accepts the existing bridge shape:

```json
{"message_id":"unique WhatsApp ID","author":"sender@c.us","text":"I lost my blue bottle"}
```

It also accepts `chat_id`, `chat_name`, `is_group`, and `mentioned` for the new bridge. It returns `reply`, `action`, `intent`, and `duplicate`, plus `id` for some writes. The backend checks message IDs before processing repeats. The model proposes a fixed action; `actions.py` validates and dispatches it through `store.py`.

`POST /camera/item` accepts either `{"item":"bottle","colour":"blue","location":"shelf"}` or `{"name":"bottle","color":"blue","foundAt":"shelf"}`. `POST /camera/machine` accepts `id`, `location`, and `status`.

| Read route | Result |
| --- | --- |
| `GET /health` | Backend and Ollama state |
| `GET /items` | Recent items, without reporter contact |
| `GET /items/lost` | Lost reports still marked open |
| `GET /items/unclaimed` | Unclaimed found items |
| `GET /events`, `/listings`, `/machines`, `/bookings` | Feature-specific records |
| `GET /records/{table}` | Raw data for `items`, `events`, `listings`, `machines`, `bookings`, `students`, `claim_requests`, or `outbox`; always requires `VERNIER_ADMIN_KEY` and `X-Vernier-Key` |

`POST /preferences` stores an Indian phone number, interest list, and `all` or `major` level. It is restricted to local/admin access. A student can also DM `interests: sports, music` to update their own preferences.

`GET /outbox` leases queued alerts. After a successful WhatsApp send, the bridge calls `POST /outbox/{id}/ack`; on failure it calls `/retry`. Unacknowledged leases return to the queue after two minutes. The restricted `POST /camera/item/{id}/removed` marks only a camera-sourced found item collected. The local `claims.py` command can mark any found item claimed or unclaimed after desk review:

```powershell
python god-backend\claims.py requests
python god-backend\claims.py list
python god-backend\claims.py claim 12
```

Room availability and bookings reflect only Vernier's local database. They are not connected to an official campus room system. Machine status reflects only the latest submitted observation.

## Team workbook and demo data

The team's `Vernier_Database.xlsx` stays in `C:\vernierCopy\vernier\backend`, so its sample contacts and outbox are not accidentally included when this folder is pushed. The optional tool reads it explicitly:

```powershell
python god-backend\tools\excel.py check --source C:\vernierCopy\vernier\backend\Vernier_Database.xlsx
```

```powershell
python god-backend\tools\excel.py import --source C:\vernierCopy\vernier\backend\Vernier_Database.xlsx
```

The import command above previews counts. Add `--apply` to import rows. Importing does not replace current items or send historical alerts. Imported contacts and reports are inactive for future automatic alerts until those users subscribe or report again through this backend. Export writes `god-backend\vernier_export.xlsx` by default; the file is ignored by Git. The optional fabricated demo seed is `python god-backend\tools\seed_demo.py --apply`. These tools change the master database only when explicitly applied.

`samples_labelled.txt` and `tools\try_llm.py` carry over the team's English, Hindi, and Hinglish prompt examples. Run the prompt check only when you want model verification; it calls Ollama but does not write records.
