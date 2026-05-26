# 🤖 AI GitHub Tracker Bot

Searches GitHub daily for the latest AI projects (mobile-friendly, no root needed)
and delivers them straight to your Telegram.

---

## ✨ Features

| Feature | Detail |
|---|---|
| 🔍 Manual search | `/search` — runs instantly |
| 🕘 Auto schedule | Every day at **9:00 PM UTC** |
| 📦 Top 10 results | Sorted by stars |
| 🔑 Per-user toggle | `/schedule on/off` |
| ⚡ GitHub API | Optional token for higher rate limits |

---

## 🚀 Deploy in 5 Steps

### Step 1 — Get a Bot Token
1. Open Telegram → search **@BotFather**
2. Send `/newbot`
3. Follow prompts → copy your token (looks like `123456:ABC-DEF…`)

### Step 2 — (Optional) Get a GitHub Token
1. Go to https://github.com/settings/tokens
2. Generate a **classic token** with `public_repo` scope
3. Increases rate limit from 60 → 5,000 requests/hour

### Step 3 — Deploy on Railway (Free)
1. Go to https://railway.app → sign up free
2. Click **New Project → Deploy from GitHub**
3. Fork this repo or upload files
4. Add environment variables:
   - `BOT_TOKEN` = your Telegram bot token
   - `GITHUB_TOKEN` = your GitHub token (optional)
5. Railway auto-detects Python and runs `bot.py`

### Step 4 — Or run locally
```bash
pip install -r requirements.txt
export BOT_TOKEN="your_token_here"
export GITHUB_TOKEN="your_github_token"  # optional
python bot.py
```

### Step 5 — Start the bot
1. Open Telegram → find your bot
2. Send `/start`
3. Send `/schedule on` to enable daily 9 PM reports
4. Send `/search` to test immediately

---

## 📋 Commands

```
/start        — Welcome message
/search       — Search GitHub right now
/schedule on  — Enable daily 9 PM UTC auto-search
/schedule off — Disable daily auto-search
/status       — Show your current settings
/help         — Show help
```

---

## 🔍 Search Keywords

The bot searches GitHub for:
- AI mobile
- AI assistant mobile
- LLM mobile Android
- on-device AI
- edge AI mobile
- local LLM Android
- AI tools open source
- AI agent
- mobile AI app
- generative AI mobile

---

## 🕘 Schedule Time

Default: **9:00 PM UTC**

| Your timezone | Local time |
|---|---|
| UTC+5:30 (India) | 2:30 AM IST |
| UTC+6 (Bangladesh) | 3:00 AM |
| UTC+0 (UK) | 9:00 PM |
| UTC-5 (US East) | 4:00 PM |
| UTC+8 (China/PH) | 5:00 AM |

To change the time, edit `SCHEDULE_HOUR` and `SCHEDULE_MINUTE` in `bot.py`.

---

## 📁 File Structure

```
bot.py            ← Main bot (everything in one file)
requirements.txt  ← Python dependencies
README.md         ← This file
```

---

## ⚠️ Notes

- Scheduled chats are stored **in memory** — restarting the bot clears them.
  Users need to re-run `/schedule on` after a restart.
  (For persistence, a simple SQLite/JSON file can be added.)
- GitHub search API allows 60 requests/hour unauthenticated, 5000 with a token.
