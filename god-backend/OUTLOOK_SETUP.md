# Outlook room booking

Vernier books real rooms by creating an Outlook event with the room as the location, which is
the same thing you do by hand in Outlook. It uses the college Microsoft account of whoever signs in.
It never sees the password: Microsoft gives it a token that can only use the calendar.

When it isn't set up, Vernier falls back to its own bookings table, exactly as before.

## Files (all in `god-backend\`)

| File | What it is | In Git? |
|---|---|---|
| `outlook.py` | Talks to Outlook: sign-in, free/busy check, booking, cancelling | yes |
| `outlook_config.example.json` | Template for the settings | yes |
| `outlook_config.json` | Your real settings (app ID, rooms, allowed numbers) | **no** |
| `outlook_token.json` | Your saved sign-in. Anyone with this file can book as you | **no** |
| `actions.py`, `app.py` | Edited so `book_room` / `ask_room` use Outlook when it's ready | yes |

## 1. Register the app (once, about 5 minutes)

1. Go to https://portal.azure.com and sign in with your **college** account.
   Open **Microsoft Entra ID → App registrations → New registration**.
   - Name: `Vernier`
   - Supported account types: **Accounts in any organizational directory**
   - Redirect URI: leave empty, then click **Register**.
   - If it says you don't have permission, sign in with a personal Microsoft account
     instead and do the same steps. The college sign-in comes later.
2. On the app's **Overview** page, copy the **Application (client) ID**.
3. Go to **Authentication** and turn on **Allow public client flows** (set it to Yes), then click **Save**.
4. Go to **API permissions → Add a permission → Microsoft Graph → Delegated permissions**.
   Tick `Calendars.ReadWrite` and `User.Read`, then click **Add permissions**.

## 2. Fill in the settings

```powershell
cd "C:\Users\Shivam Ghosh\Documents\Haha i do coding i am cool\Vernier\god-backend"
copy outlook_config.example.json outlook_config.json
notepad outlook_config.json
```

- `client_id`: paste the Application (client) ID.
- `rooms`: one entry per bookable room. To get a room's email address, open Outlook,
  create a new event, open **Room Finder** (or click Location), pick the room, then
  open its contact card. The email is usually something like `xyz@plaksha.edu.in`.
  `aliases` are other names students might use ("meeting room 2", "MR2").
- `allowed_numbers`: WhatsApp numbers allowed to book, e.g. `["9876543210"]`.
  **Fill this in.** Every booking is made under your account, and an empty list means
  anyone who messages the bot can book.
- `max_hours` (3) and `max_days_ahead` (30) are safety limits.
- `tenant`: leave it as `organizations`, or put your college domain (`plaksha.edu.in`).

## 3. Install and sign in

```powershell
python -m pip install msal
python outlook.py login
```

It prints a code. Open https://microsoft.com/devicelogin, enter the code and sign in with your
**college** account, then accept the permissions. The sign-in is saved in `outlook_token.json`
and refreshes on its own.

- **"Need admin approval"** means the college blocks third-party apps, and only IT can allow
  it. For the demo, use a temporary token instead (see the end of this file).

## 4. Test from the terminal (no WhatsApp needed)

```powershell
python outlook.py status
python outlook.py check MR-2 2026-10-29 15:00 16:00
python outlook.py book MR-2 2026-10-29 15:00 16:00
python outlook.py upcoming
python outlook.py cancel 1
```

`book` waits for the room to accept or decline. A declined booking is removed automatically.
Use short test bookings and cancel them afterwards: these are real rooms.

## 5. Run Vernier as usual

```powershell
cd "C:\Users\Shivam Ghosh\Documents\Haha i do coding i am cool\Vernier"
python god-backend\app.py
```

The startup output shows `Outlook room booking: ready`, and `/health` shows `"outlook": "ready"`.

On WhatsApp (by DM, or tag the bot in a group):

| Message | What happens |
|---|---|
| `book MR-2 tomorrow 3 to 4pm` | Checks Outlook, books, replies "Booking request sent…"; a few seconds later you get "Confirmed in Outlook…" (or "declined") |
| `is MR-2 free tomorrow 3 to 4pm?` | Live Outlook free/busy answer |
| `book MR-2 tomorrow` | Asks for the time |
| `book room 9 …` | Lists the rooms it knows |

Group messages that don't tag the bot never create bookings.

## Temporary token (if the college blocks app sign-in)

1. Open https://developer.microsoft.com/graph/graph-explorer and sign in with your college account.
2. Run any request, then open the **Access token** tab and copy the token.
3. In the backend window, before starting it:
   ```powershell
   $env:VERNIER_OUTLOOK_TOKEN="paste-token-here"
   python god-backend\app.py
   ```

The token expires after about an hour, so get a fresh one just before the demo.
Graph Explorer must have `Calendars.ReadWrite` consented (Modify permissions tab).
`outlook_config.json` still needs the `rooms` list in this mode.

## Problems

| What you see | Fix |
|---|---|
| `Outlook room booking: off` | No `outlook_config.json`, or `rooms` is empty |
| `missing client_id` / `room emails not filled in` | Edit `outlook_config.json` |
| `not signed in` / "sign-in expired" | `python outlook.py login` |
| "The college account doesn't allow this" | The college blocked access. Use the temporary token, or ask IT |
| "Can't see MR-2's calendar" | Wrong room email, or the room hides its calendar |
| Room always declines | Outside the room's booking hours, or you're not allowed to book that room |
| "hasn't answered yet" | That room needs manual approval by a delegate. Check Outlook later |
