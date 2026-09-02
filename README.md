# StudyBuddy Cambodia — Telegram Study Bot (MVP)

Two bots:
- **main_bot.py** — student-facing bot: onboarding, AI chat, photo → OCR + Test/Question/Summary/Explain buttons.
- **admin_bot.py** — separate bot, admin-only, for stats / user list / broadcast.

## 1. Setup

```bash
python3 -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:
- Create **two** Telegram bots via [@BotFather](https://t.me/BotFather) → paste their tokens into
  `STUDENT_BOT_TOKEN` and `ADMIN_BOT_TOKEN`.
- Get your own numeric Telegram ID (e.g. via [@userinfobot](https://t.me/userinfobot)) → put it in
  `ADMIN_TELEGRAM_IDS`.
- **Rotate the API key** you shared earlier (it's no longer private) and put the *new* key in
  `ANTHROPIC_API_KEY`. Confirm with your router provider (`clauderouter.app`) which base URL / model
  name they actually support — `ANTHROPIC_BASE_URL` and `ANTHROPIC_MODEL` are both overridable in `.env`
  without touching code.

## 2. Run locally

Two separate terminals (two separate processes, one per bot):

```bash
python3 main_bot.py
python3 admin_bot.py
```

Both share the same SQLite database (`data/study_bot.sqlite3`), created automatically on first run.

## 2b. Deploying on Railway (fixes "npm: command not found")

That error means Railway thinks this is a **Node.js** project and is trying to run `npm start` instead
of your Python code. Fix it like this:

1. **Use ONE Railway service, not two.** Deploy `combined_bot.py`, which runs both the student bot and
   the admin bot inside the same process. This avoids two containers writing to the same SQLite file at
   once (which causes `database is locked` errors).
2. This repo now includes `Procfile`, `nixpacks.toml`, and `railway.json` — all three tell Railway/Nixpacks
   explicitly: *this is Python, install `requirements.txt`, start with `python3 combined_bot.py`*. Push all
   of them along with your code.
3. In the Railway dashboard, open your service → **Settings → Deploy → Start Command**, and make sure it's
   **empty** or set to `python3 combined_bot.py` — not `npm start`. A leftover custom Start Command in the
   dashboard overrides all the config files above.
4. Set all the same environment variables from `.env` in Railway's **Variables** tab (Railway does not read
   your local `.env` file).
5. Attach a **Volume** mounted at e.g. `/app/data` and set `DB_PATH=/app/data/study_bot.sqlite3` in
   Variables, so your SQLite data survives redeploys (the "Mounting volume on..." log line in your output
   means you already have a volume — just make sure `DB_PATH` points inside it).
6. Since this is a long-running polling bot with no HTTP server, make sure the Railway service type is a
   **Worker**, not a **Web Service** expecting a `$PORT` — worker services don't need to bind a port.

## 3. What's already working

- `/start` onboarding: name, age, school, grade (7–12), track (Science / Social Science), custom AI name.
- Free-text chat with memory of the last ~12 messages + student's profile (grade/track shape the answers).
- Send a photo of a test/textbook page → bot OCRs it via Claude vision, then lets the student pick:
  - 📝 Turn into a Test (multiple-choice + short answer, answer key at the end)
  - ❔ Generate new practice Questions on the same topic
  - 📌 Summarize into bullet points
  - 🧮 Explain / solve step-by-step with final answer
- Admin bot: `/stats`, `/users`, `/broadcast <message>`.

## 4. What you still need to wire up (deliberately left as extension points)

- **Voice messages**: Claude doesn't accept raw audio. `handle_voice()` in `main_bot.py` is a stub —
  plug in a speech-to-text call (OpenAI Whisper API, or self-hosted `faster-whisper`), then feed the
  transcript into `ai_client.chat()` exactly like text messages.
- **Rate limiting / cost control**: add a per-user daily message cap in `db.py` if you're worried about
  API cost from a free public bot.
- **Payments / premium tier**: not included — ask if you want a Telegram Payments or bank-QR flow added.
- **Hosting**: for 24/7 uptime, deploy both bots on a small VPS (e.g. `systemd` services or Docker) or a
  platform like Railway/Fly.io — polling mode (used here) doesn't need a public URL; if you later want
  webhooks for lower latency at scale, that's a small change to `run_polling()` → `run_webhook()`.

## 5. Security reminders

- Never commit `.env` to git. `.env.example` has placeholders only.
- The API key you originally pasted in chat should be treated as compromised — generate a new one.
- Consider adding basic abuse protection (e.g. block non-admins from `admin_bot.py`, already done via
  `ADMIN_TELEGRAM_IDS`).
