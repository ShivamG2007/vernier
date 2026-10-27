# Vernier companion dashboard

React 19/Vite 7 frontend for Vernier. The WhatsApp bridge remains the primary way to submit reports, request claims, post events and listings, book rooms, and set delivered alert preferences. The dashboard reads public records from the newer `god-backend` API. It also accepts the older FastAPI read contract when a public route returns 404.

## Local development on a Mac

From the repository root, start the chosen backend separately. For the newer service, `python3 god-backend/app.py` starts its local HTTP server on `127.0.0.1:8000` and creates/updates its SQLite database. Start Ollama separately if you need WhatsApp conversational features. Do not run the older backend on the same port at the same time.

Then in a second terminal:

```sh
cd /Users/hitarthnijhara/Projects/vernier/app
npm ci
cp .env.example .env.local
npm run dev
```

The browser opens `http://localhost:5173`. Set `VERNIER_BACKEND_URL` in `app/.env.local` if the API is elsewhere. This is read by the Vite server; the browser calls same-origin `/api/records/...`. If the backend is on a separate host, configure its `VERNIER_ADMIN_KEY` and put the same value in the app server's `VERNIER_ADMIN_KEY` environment variable. Never use a `VITE_` prefix for a secret. Keep both services on a private network during the demo.

The original `VITE_BACKEND_URL` remains a non-secret compatibility fallback for local setups. `VERNIER_BACKEND_URL` takes precedence. No `VITE_API_BASE_URL` is needed because the browser does not contact the backend directly.

## Build and serve

```sh
npm test
npm run build
VERNIER_BACKEND_URL=http://127.0.0.1:8000 npm start
```

`npm run build` writes `app/dist/`. `npm start` runs the app-owned Node server on `PORT` (default 4173) and `HOST` (default `127.0.0.1`; set `0.0.0.0` in a hosted container). Unlike Vite, this production command reads shell environment variables rather than `.env.local`. It serves the built app, supports client-side refreshes, and applies the same safe record adapter as Vite development and preview. Deploy the Node server and built assets together; a static-only host cannot run the `/api/records` adapter. Set `VERNIER_BACKEND_URL` and, if required, `VERNIER_ADMIN_KEY` as server-side deployment environment variables. Do not put them in a client-side `VITE_` variable. The production host also needs to reach the backend over its network.

## Read contract and privacy

The adapter requests `GET /items`, `/items/lost`, `/items/unclaimed`, `/events`, `/listings`, `/machines`, and `/bookings` from `god-backend`. Those routes return objects with corresponding arrays. The dedicated item lists back the open-lost and unclaimed-found filters; the dashboard's recent preview uses `/items`. The adapter maps records to existing public field names and discards reporter contacts, listing contacts/details, booking holders, original messages, claim requests, and raw camera fields. The older backend's `GET /records/{table}` is used only when a public route returns 404. Errors and malformed responses remain errors; no demo rows are substituted.

Lost/found filters include open lost and unclaimed found records. Claims remain desk-reviewed. Event calendar dots come only from parseable record dates. Machine counts use observations no more than five minutes old; older observations are labelled accordingly. The dashboard requests today's `/bookings`; the Campus view lets students choose a day through the backend's supported `day=YYYY-MM-DD` query. These are Vernier's local records, not official campus availability.

The `person1` / `ABC123` sign-in is a local demo gate. It is not backend authentication or authorization. “Remember me” stores only the demo username. Profile interests and alert level remain browser-local and are **not** submitted as delivered alert preferences, because the backend has no verified browser identity. Students can set actual WhatsApp alerts through their own DM. Do not use this demo gate to protect private records.

The generic “Chat now” button opens WhatsApp Web because no approved Vernier chat link/number is configured. A dedicated link requires the team's verified WhatsApp destination. No phone number is fabricated.
