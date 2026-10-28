# Vernier — master plan

**Consolidated 27 October 2026 from the project information file, three teammate context files, and six setup guides in this folder.** This is a planning and handoff document, not a claim that the implementation was inspected or that the live demo has passed. The three teammate context files describe the later, integrated hackathon build; the PDF guides contain setup procedures, some written for an earlier starter version. Check the actual private `vernier` repository before changing code or relying on a stated current behavior.

## 1. Executive brief

Vernier (“precision for campus life”) is a campus assistant for the Code Youth Hackathon at Chandigarh University, Open Innovation track. Its primary student interface is WhatsApp. It turns relevant campus messages and selected camera observations into structured records, answers questions, and sends requested alerts. A mobile companion dashboard is part of the later demo plan, while WhatsApp remains the core interface.

The 24-hour build has four product areas:

1. **Lost and found:** ingest lost/found chat reports and shelf-camera observations, match them, notify the person who reported a loss, and check ownership before handover.
2. **Events and clubs:** store event, audition, recruitment, and gathering posts by category and significance; notify students according to their interests and alert level.
3. **Rooms and facilities:** answer room availability and support a basic booking flow from a local bookings table; report whether a particular washing machine is free or in use from a camera. Outlook/Microsoft Graph integration is a stretch goal.
4. **Buy and sell:** store sale listings and buying requests, match relevant items, and seek seller consent before sharing contact details.

**Demo outcome:** a judge sees a group lost-item post become a private acknowledgement, a matching found report or shelf observation trigger an alert, an event alert reach an interested student, a live machine-status answer, the companion dashboard update, and a refusal to reveal a student's location or camera footage.

## 2. Source status and decision rules

The later teammate context files describe a concrete implementation and task split. They supersede earlier setup guides where those guides describe starter code. The project information file records earlier team decisions and proposals; preserve its open questions instead of silently treating them as implemented. In particular:

| Topic | Working baseline in later context | Decision or verification still needed |
|---|---|---|
| Student interface | WhatsApp bot plus a React/Vite companion dashboard for the demo | Whether the dashboard survives beyond the demo; WhatsApp is still the primary interface. |
| WhatsApp account | `whatsapp-web.js` on one bot-host laptop, linked to a dedicated WhatsApp Business account | The earlier note proposed a spare account from Shivam's parents; later guides describe a dedicated SIM. Confirm the actual number/account, ownership, and recovery plan. |
| Group permission | Group admin opt-in is described; group posts are filtered for relevant keywords or a tag | Earlier project notes propose individual `START`/`STOP` consent before any group content reaches AI or storage. That gate is **not described in the later API/database implementation**. Resolve and implement it before using real student groups. |
| Lost/found storage | SQLite `lost_found` table shared by chat and shelf inputs | Earlier spreadsheet idea is obsolete for the described build; confirm the live repository. |
| Room booking | Local `bookings` table with today-only booking and clash check | Outlook read/create/cancel and permission to expose `booked_by` are unresolved. |
| AI | Local Ollama, Qwen3 4B on Shivam's laptop; prompts and JSON schema | Real fine-tuning is future work. Test model availability and extraction quality. |
| Claims | `claim <id>` currently marks `claim_pending` | Real ownership verification and handover workflow remain work to do. |

The sample response in Hitarth's context is a seeded example dated 26 October 2026. It is test data, not evidence of current production records. Pitch numbers and commercial prices in the context files are illustrative and need sources/validation before public use.

## 3. Team, ownership, and work rules

| Person | Ownership | Hackathon laptop role | Priority work |
|---|---|---|---|
| **Avik** | `bot/index.js`, `backend/main.py` | Runs the only active WhatsApp bot | Keep messaging stable; implement claim verification, buyer/seller contact flow, dedupe/alert behavior, and backend coordination. |
| **Shivam** | `cv/`, private GitHub repository; assists backend | Runs Ollama and CV cameras | Keep model and camera feeds available; send shelf/machine observations; provide network IP; coordinate backup host. |
| **Arushi** | `backend/llm.py`, `backend/db.py`, `backend/samples.txt`, `backend/try_llm.py` | Hosts FastAPI backend and SQLite database | Improve extraction on real anonymized samples, event quality/dedupe, booking dates, concise grounded replies, and schema care. |
| **Hitarth** | `app/` | Runs phone-sized React/Vite companion dashboard | Preferences, live cards, loading/empty/error states, deck-aligned visual design. |

Each person edits the files they own. A new intent or field needs Arushi's `llm.py`/schema change and Avik's `main.py` handler; a new table or column also needs Arushi's `db.py` change and coordination with Hitarth's app. Keep endpoint paths, JSON keys, and table columns stable until all consumers agree. The context files are snapshots; a newer version from the live repository wins.

The separate private repository is described as `vernier/` with `bot/`, `backend/`, `cv/`, and `app/`. This `C:\Vernier` folder contains planning documents and guides; it is not itself that Git checkout.

## 4. Product behavior and acceptance criteria

### 4.1 Lost and found

- A student reports a loss by DM or eligible group post. Store item, colour, place, details, contact, source, status, and creation time; treat the report as a request for a match alert.
- Found reports and shelf-camera observations enter the same `lost_found` table. A camera record identifies the shelf location and is marked removed/claimed when the item is taken away.
- The current matching rule in `main.py` uses words from item and colour, requires at least one shared item word, and uses Jaccard similarity of at least 0.4. Synonym/embedding matching is stretch work.
- On a match, alert the loss reporter privately through the outbox. A useful claim flow asks for an item-specific detail, checks it, then gives collection instructions or contacts the finder. Today `claim <id>` only sets `claim_pending`; do not present that as completed verification.
- Acceptance: a loss followed by a found chat report and a shelf observation each produce one appropriate alert; a wrong claimant cannot obtain someone else's item/contact merely by entering an ID.

### 4.2 Events and clubs

- Extract a clear title, category (`sports`, `music`, `dance`, `theatre`, `culture`, `tech`, `academic`, `other`), date, venue, details, and `major` flag from eligible posts.
- Preference level is `all` or `major`. Deliver category alerts accordingly. A proposed major rule: official/fest-level/inter-college events are major; small club meet-ups are minor.
- Add deduplication for the same title and date before notifying, since forwarded posts may repeat across groups. Avoid duplicate alerts to one student.
- Acceptance: a dance announcement reaches a dance follower at the chosen level, while an unrelated student does not receive it; forwarding the same event twice does not generate duplicate alerts.

### 4.3 Rooms and facilities

- The current demo booking flow uses the local `bookings` table, today-only date handling, HH:MM start, default one-hour end, and clash detection. Questions should read from stored records. A `day` extraction field and future-date support need coordinated changes.
- Chandigarh University's Outlook bookings are the intended campus source, but Microsoft Graph/free-busy integration is a stretch goal. Do not imply that demo records are live Outlook availability.
- The machine camera reports `in use` or `free` for an identified machine/location; the answer includes the latest known status and should avoid claiming certainty if the observation is stale or unavailable.
- Acceptance: one booking succeeds and the same timeslot conflicts; a machine-status question reflects a recent camera update; Outlook claims are labelled accurately in the demo.

### 4.4 Buy and sell

- Capture `sell_post` and `buy_request` records with item, price where available, details, contact, status, and time.
- Reuse item matching. A buyer should see useful matching item/price details. For `interested <id>`, request the seller's permission before sharing contact information.
- Acceptance: a sale listing can be found from a buying request; no phone or direct contact is disclosed without seller consent.

### 4.5 Student experience

- In DMs, the bot replies to questions and commands. In groups, it processes relevant posts quietly and replies only if tagged or the message starts with `vernier`; private alerts go through the outbox.
- Students can set interests in a DM (`interests: dance, music [major]`) or through the app. The dashboard's first card shows their lost-item status, followed by interest/event cards, found-item board, buy/sell, laundry, and rooms.
- The dashboard should fit a roughly 390 px phone viewport, use the deck's grayscale palette (`#242424`, `#E9E9E9`, white, `#747474`), and refresh about every five seconds with useful loading, empty, and connection-error states.
- Acceptance: a person who signs up for preferences sees relevant cards and alerts; demo changes appear on the phone without a manual rebuild.

## 5. System architecture and message flow

```text
Student WhatsApp <-> Avik: bot/index.js <-> Arushi: FastAPI backend :8000
                       |                         |        |
                       |                         |        +-> SQLite vernier.db
                       |                         +-> Shivam: Ollama :11434
                       +<- GET /outbox alerts            +<- Shivam: CV camera POSTs
                                                 |
                                                 +<-> Hitarth: React/Vite app :5173
```

1. The bot ignores its own messages, status, and channels; identifies group vs DM, author, and mention; then sends `{chat_id, chat_name, is_group, author, text, mentioned}` to `POST /message`.
2. The backend checks safety rules, handles preference and claim commands, filters irrelevant group chatter, asks `llm.extract(text)` for a schema-constrained intent/fields, validates them, and uses deterministic handlers to read or write records.
3. For student questions, the backend fetches permitted rows and asks `llm.write_reply(question, rows)` for a short answer grounded in those rows. The model must not execute shell or arbitrary SQL commands.
4. The bot replies in DMs or when tagged in a group, with a small 1–3 second delay. It checks `GET /outbox` about every five seconds and sends queued private alerts.
5. CV scripts POST shelf-item and machine observations to the backend. The app reads record endpoints and saves preferences.

The earlier consent proposal requires a separate step before item 2: handle `START`/`STOP` in application code; discard content from nonconsenting group senders before model calls, rolling context, persistence, or content logging; then apply keyword/mention filtering. A four-hour eligible-message buffer and persistent structured memory were proposed, not confirmed in the later implementation. Keep this distinction explicit.

### Runtime and network

| Host | Service | Setting | Port |
|---|---|---|---|
| Shivam | Ollama with `qwen3:4b`; CV scripts | `OLLAMA_URL=http://SHIVAM-IP:11434` on backend | 11434 |
| Arushi | FastAPI and `backend/vernier.db` | `VERNIER_MODEL=qwen3:4b`, `VERNIER_DB` optional | 8000 |
| Avik | WhatsApp Web bot | `BACKEND_URL=http://ARUSHI-IP:8000` | outbound |
| Hitarth | React/Vite app | `VITE_BACKEND_URL=http://ARUSHI-IP:8000` in `app/.env.local` | 5173 |

All laptops use one hotspot/private network for the demo; college Wi-Fi may block laptop-to-laptop access. IP addresses can change, so collect them with `ipconfig` on the day and check `http://ARUSHI-IP:8000/health`. Open the relevant local firewall ports. Startup order: Ollama → backend → bot → cameras → app. Keep laptops plugged in and awake. Only one laptop runs the bot at once. If the network fails, move the backend/database to Shivam's machine or use a single laptop; restore from a private database backup and prevent two bots from answering simultaneously.

## 6. Interface contract to protect

The later teammate files describe this FastAPI contract. Verify it against `backend/main.py` before editing or demoing. `GET /records/{table}` currently exposes up to the newest 200 rows and CORS is open with no authentication on the local network; that is a demo limitation requiring explicit access decisions before wider deployment.

| Method and route | Request / response | Consumer |
|---|---|---|
| `POST /message` | `{chat_id, chat_name, is_group, author, text, mentioned}` → `{reply, intent}` | Bot |
| `GET /outbox` | `[{id, to_chat, text}]`; marks returned entries sent | Bot |
| `POST /camera/item` | `{item, colour, location}` → `{id, matched_lost_id}` | Shelf CV |
| `POST /camera/item/{id}/removed` | No body → `{ok}` | Shelf CV |
| `POST /camera/machine` | `{id, location, status: "in use"|"free"}` → `{ok}` | Machine CV |
| `POST /preferences` | `{phone, interests:[...], level:"all"|"major"}` → `{ok, contact, interests, level}` | App |
| `GET /records/{table}` | Newest rows for one allowlisted table | App/testing |
| `GET /health` | Backend, database, Ollama/model status | All hosts |
| `POST /dev/seed` | Inserts demo records | Testing only |

**SQLite tables:**

| Table | Fields used by the plan |
|---|---|
| `lost_found` | `id, kind, item, colour, place, details, contact, source, status, created` |
| `events` | `id, title, category, date, venue, details, major, source, created` |
| `listings` | `id, kind, item, price, details, contact, status, created` |
| `machines` | `id, location, status, updated` |
| `bookings` | `id, room, day, start, end, booked_by` |
| `students` | `contact, interests, level` |
| `outbox` | `id, to_chat, text, sent, created` |

`contact` and `to_chat` may be WhatsApp IDs such as `91...@c.us`; newer accounts may use `@lid`. Hitarth's phone-number-based preferences may therefore fail to join to chat-reported records. Test with the actual demo accounts or add an identity mapping. SQLite `CREATE TABLE IF NOT EXISTS` does not migrate existing columns. Back up the database before changing schema; coordinate all consumers and apply a migration or deliberately recreate *demo* data. Do not delete a database containing real reports.

AI intent set in the later files: `lost_report`, `found_report`, `event_post`, `sell_post`, `buy_request`, `ask_lost`, `ask_events`, `ask_room`, `book_room`, `ask_laundry`, `ask_listings`, `ask_person`, `chit_chat`, `other`. Extracted fields include `item`, `colour`, `place`, `title`, `category`, `date`, `venue`, `major`, `price`, `room`, `start`, `end`, and `machine`. The backend also handles certain direct commands without model extraction. Ollama is called locally through `/api/chat` with nonstreaming schema-constrained JSON, `think: false`, and temperature 0. The source describes `qwen3:1.7b` as a lower-memory local test alternative; the integrated demo target is `qwen3:4b`.

## 7. Build order for the 24-hour event

| Stage | Owner(s) | Deliverable and gate |
|---|---|---|
| **Before integration** | All | Confirm bot account, admin-approved demo groups, source repository revision, current API, laptop IPs, local model, and private backup of bot login. Collect anonymized test messages. |
| **1. Bring up services** | Shivam, Arushi, Avik, Hitarth | Ollama model responds; `/health` reports backend and model ready from another laptop; one bot connects; CV endpoints accept observations; phone can open app. |
| **2. Prove core loop** | Avik, Arushi, Shivam | Lost → found → private alert works from two phones. Event → category alert works. Shelf and machine updates appear in records. A question is answered only from stored data. |
| **3. Improve correctness** | Avik, Arushi | Test 30–50 anonymized English/Hindi/Hinglish campus messages, fix targeted prompt rules, aim for about 90% correct intent classification on the demo model. Add event dedupe and real ownership/consent flows. |
| **4. Finish the phone view** | Hitarth, Avik/Arushi as needed | Preferences save, personal lost status, interest cards, boards, machine/room cards, refreshed data, and connection states work on a phone. |
| **5. Rehearse and protect the demo** | All | Run the scripted sequence twice, include a privacy refusal, copy `vernier.db` privately, record a backup video, and make sure only one bot session is active. |

Do the necessary interface changes early: `day` field for future bookings; event-dedupe helper; claim-detail verifier; optional item photo URL; and any buyer/seller consent state. Each change needs the owning files and API consumers coordinated. Embeddings, Outlook integration, daily digests/quiet hours, and photo cards are stretch items after the core flow is reliable.

## 8. Demo script and checks

1. Start Ollama, backend, bot, cameras, and app in order. Check `/health` from a second laptop and display the dashboard on a phone. Use `POST /dev/seed` only if the demo needs sample records.
2. From one phone, post “lost my black earbuds in library” in an approved demo group. Show the private acknowledgement and the new `lost_found` record.
3. From another phone, post “found black earbuds near library desk,” or put a supported object on the demo shelf. Show the private match alert. Demonstrate the ownership question rather than claiming an unchecked ID is proof.
4. Post a dance club event. Show that a student following dance gets the appropriate alert and that the event appears on the phone dashboard. Repeat the post to check deduplication if implemented.
5. Ask “vernier is the 8th floor machine free?” after the machine CV update. Show the status and timestamp. Optionally demonstrate a local room booking and a conflicting second request, clearly identifying it as a local demo table.
6. Ask “where is Rahul right now?” and “show me the camera footage.” Show refusals. Confirm group replies appear only when tagged and that unrelated group chatter is silent.
7. Keep a recording of the successful flow. If model/network/bot connection fails, use the documented fallback host or recorded demo while stating which part is simulated.

## 9. Privacy, security, and operational guardrails

- Never expose a student's live location or raw camera views. Aim cameras at objects/machines, not faces. A camera status answer is a narrow observation, not access to footage.
- Store extracted facts instead of raw chats in the intended design. Admin opt-in for demo groups is described; individual opt-in, `STOP`, retention/deletion, quoted messages, and how nonconsenting content is discarded still need an explicit team decision and implementation. Use controlled demo groups until that is resolved.
- Do not build profiles of every group member just because the bot can receive their posts. Only send alerts requested through preferences/consent. Do not share buyer/seller contacts or booking-holder data without an access rule.
- Keep `bot/.wwebjs_auth`, `bot/.wwebjs_cache`, `node_modules`, `.venv`, `.env.local`, model weights, and `*.db` out of Git. The WhatsApp login folder grants access to the bot account; back it up privately. Keep the bot phone charged and its two-step verification available to the team.
- The `whatsapp-web.js` connector is an unofficial prototype path and may break after WhatsApp Web updates. A supported production group-ingestion path and Meta eligibility/limits remain unverified. Do not promise production group access based on the demo.
- The current app-facing record endpoint and open CORS/no-auth backend can expose sensitive rows to anyone on the demo network. Constrain the network and data to demo records, and add authentication/field-level access before a real campus launch.
- Use prewritten, parameterized database functions and validated model output. Do not run model-generated terminal or SQL commands. A model's answer should use authorized rows only.

## 10. Setup and troubleshooting reference

The six PDF guides cover fresh Windows setup. The later role guides assume Git, Node.js, Python, Ollama where needed, the private repository, and local virtual environments have already been installed and solo tests passed. Use the PDFs for a fresh machine; use the live repository and its README for exact current commands. PowerShell commands are run one line at a time; quote paths with spaces. The guide's example checkout is `C:\Projects\vernier` outside OneDrive, not this document folder.

- **Model:** Shivam runs Ollama on port 11434. Use `qwen3:4b` for the demo if available; `qwen3:1.7b` is a smaller local fallback. The first request may be slow while the model loads. If `/health` says `model_ready: false`, compare `VERNIER_MODEL` with the installed model list.
- **Backend:** From `backend/` with its `.venv` active, Arushi runs `uvicorn main:app --host 0.0.0.0 --port 8000` with `OLLAMA_URL` pointing at Shivam's hotspot IP. An unreachable backend makes the bot report a fetch failure; an unreachable Ollama makes replies say it is having trouble thinking.
- **Bot:** From `bot/`, Avik runs `node index.js` with `BACKEND_URL` pointing at Arushi's IP. Link only the bot account with the QR code. If mention detection fails because of `@lid`, start the demo group question with `vernier`. Duplicate replies usually mean two bot processes are running.
- **Cameras:** Shivam sets `BACKEND_URL` and the relevant camera settings (`CAMERA_INDEX`, `SHELF_NAME`, `CHECK_EVERY`; or `MACHINE_ID`, `MACHINE_LOCATION`, `MOTION_THRESHOLD`) and verifies the camera POSTs appear in records.
- **App:** Hitarth sets `VITE_BACKEND_URL` in `app/.env.local`, restarts the dev server after changes, and runs `npm run dev -- --host` so a phone on the hotspot can open port 5173. If lists are empty, check `/records/...` and seed only demo data.
- **Network:** Set the hotspot network to Private, use each host's current IPv4 address rather than `localhost` across laptops, and allow ports 11434, 8000, and 5173 as needed. A failed `/health` from another laptop points first to host binding, IP, firewall, or hotspot isolation.

Older standalone bot/backend guides describe a starter `main.py`, a `ping`/`pong` bot, and an older `/message` request without all later fields. They are useful for installation and initial diagnosis, but the contract in section 6 reflects the later teammate context. The setup guides also contain a suggestion to delete `vernier.db` after a schema change; use that only for disposable demo data after taking a backup.

## 11. Decisions to close

| Decision | Why it matters | Owner / next action |
|---|---|---|
| Actual bot number/account and who controls recovery | Pairing, session backup, demo continuity | Avik and Shivam confirm before the event. |
| Individual group consent and `START`/`STOP` behavior | Current group filtering is not the earlier consent proposal | Team decides; Avik/Arushi implement and test before real groups. |
| Who may see room `booked_by`, student contacts, raw listing details | Current record endpoint exposes rows broadly | Team defines allowed fields; Avik enforces. |
| Ownership verification and collection handoff | Current `claim_pending` is not proof | Avik defines and tests the check with Arushi. |
| Identity mapping between phone numbers and `@lid` IDs | App preference joins may miss WhatsApp records | Avik/Arushi/Hitarth choose demo IDs and longer-term mapping. |
| Booking scope | Local demo table vs real Outlook read/write | Team chooses demo claim; Outlook permissions are stretch. |
| Data retention, deletion, logging, backup | Personal/group data needs a lifecycle | Team sets policy and adds code before campus rollout. |
| Event dedupe and alert repeat rules | Prevent spam from forwards | Arushi adds helper; Avik calls it. |

## 12. Pitch and business framing

The deck's concise story is that useful campus information already exists but is buried across groups and systems. Vernier gives students one WhatsApp contact for questions, personal alerts, and selected real-world status checks. The proposed differentiators are no required new student app, one conversational entry point, proactive interest alerts, narrow camera observations, and a local open-source model with explicit privacy limits. The companion dashboard is a visual addition for the demo; keep the “no required new app” claim precise.

The source context proposes a **pitch-only, unvalidated** business model: free for students; colleges pay per student per year (illustrative Core ₹49 for bot/chat and Campus ₹99 for cameras, room booking, and an admin dashboard); camera hardware at cost plus annual maintenance; optional club event boosts and featured listings only for opted-in students; no sale of student data. Neither pricing nor institutional demand has been validated in these files.

The context files also contain promotional statistics about WhatsApp use, group membership, event awareness, lost-property recovery, room no-shows, and laundry demand. They have no supporting citations in this folder. Verify each statistic and its geography/date before putting it on a judge-facing slide, or present the problem with observed campus examples instead.

## 13. Source register

This document consolidates the following files without copying large code snapshots or seeded JSON fixtures. Keep the source files for exact historical instructions and example payloads.

- [`VERNIER_PROJECT_INFO.md`](VERNIER_PROJECT_INFO.md) — original concept, agreed capabilities, architecture direction, and explicitly open proposals.
- [`Vernier_AI_Context_Avik.txt`](Guides%20and%20Plans/Vernier_AI_Context_Avik.txt) — later integrated architecture, API, database, bot/backend snapshot, and Avik's priorities.
- [`Vernier_AI_Context_Arushi.txt`](Guides%20and%20Plans/Vernier_AI_Context_Arushi.txt) — later AI/database snapshot, sample-message testing, and Arushi's priorities.
- [`Vernier_AI_Context_Hitarth.txt`](Guides%20and%20Plans/Vernier_AI_Context_Hitarth.txt) — later app plan, sample API responses, and Hitarth's priorities.
- [`Vernier_Bot_Setup_Guide.pdf`](Guides%20and%20Plans/Vernier_Bot_Setup_Guide.pdf) — initial bot installation, pairing, and troubleshooting.
- [`Vernier_Ollama_Setup_Guide.pdf`](Guides%20and%20Plans/Vernier_Ollama_Setup_Guide.pdf) — model installation and local testing.
- [`Vernier_Backend_Connection_Guide.pdf`](Guides%20and%20Plans/Vernier_Backend_Connection_Guide.pdf) — initial backend/bot/CV connection guide.
- [`Vernier_Setup_Avik.pdf`](Guides%20and%20Plans/Vernier_Setup_Avik.pdf), [`Vernier_Setup_Arushi.pdf`](Guides%20and%20Plans/Vernier_Setup_Arushi.pdf), and [`Vernier_Setup_Hitarth.pdf`](Guides%20and%20Plans/Vernier_Setup_Hitarth.pdf) — individual laptop setup and role-specific handoffs.

The code appendices in the three teammate context files are historical snapshots. The working `bot/index.js`, `backend/*.py`, and `app/src/App.jsx` in the private repository are the implementation source of truth.
