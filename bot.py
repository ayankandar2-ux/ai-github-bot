import os
import re
import json
import time
import requests
import logging
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# ─────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Environment Variables
# ─────────────────────────────────────────────────────────────

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ─────────────────────────────────────────────────────────────
# Settings
# ─────────────────────────────────────────────────────────────

SCHEDULE_HOUR = 21
SCHEDULE_MINUTE = 0

DATA_FILE = "scheduled_chats.json"

SEARCH_QUERIES = [
    "AI mobile",
    "LLM mobile Android",
    "on-device AI",
    "edge AI mobile",
    "local LLM Android",
    "AI agent open source",
    "mobile AI app",
    "generative AI mobile",
    "AI tools open source",
]

# ─────────────────────────────────────────────────────────────
# Global Variables
# ─────────────────────────────────────────────────────────────

offset = 0
scheduled_chats = set()

# ─────────────────────────────────────────────────────────────
# Load / Save Schedule Data
# ─────────────────────────────────────────────────────────────

def load_scheduled_chats():
    global scheduled_chats

    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                scheduled_chats = set(json.load(f))
            logger.info(f"Loaded {len(scheduled_chats)} scheduled chats")
        except Exception as e:
            logger.error(f"Failed loading scheduled chats: {e}")

def save_scheduled_chats():
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(list(scheduled_chats), f)
    except Exception as e:
        logger.error(f"Failed saving scheduled chats: {e}")

# ─────────────────────────────────────────────────────────────
# Markdown Escape
# ─────────────────────────────────────────────────────────────

def escape_md(text):
    if not text:
        return ""
    return re.sub(r'([_*[\]()~`>#+\-=|{}.!])', r'\\\1', str(text))

# ─────────────────────────────────────────────────────────────
# Telegram Helpers
# ─────────────────────────────────────────────────────────────

def tg_send(chat_id, text):
    try:
        r = requests.post(
            f"{API}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "MarkdownV2",
                "disable_web_page_preview": True
            },
            timeout=15
        )

        if not r.ok:
            logger.error(f"Telegram API Error: {r.text}")

    except Exception as e:
        logger.error(f"Telegram send error: {e}")

def tg_get_updates(offset_val):
    try:
        r = requests.get(
            f"{API}/getUpdates",
            params={
                "offset": offset_val,
                "timeout": 30
            },
            timeout=35
        )

        if r.ok:
            return r.json().get("result", [])

        logger.error(f"getUpdates failed: {r.text}")
        return []

    except Exception as e:
        logger.error(f"getUpdates error: {e}")
        return []

# ─────────────────────────────────────────────────────────────
# GitHub Search
# ─────────────────────────────────────────────────────────────

def search_github(query):
    since = (
        datetime.now(timezone.utc) - timedelta(days=1)
    ).strftime("%Y-%m-%d")

    headers = {
        "Accept": "application/vnd.github.v3+json"
    }

    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    try:
        r = requests.get(
            "https://api.github.com/search/repositories",
            headers=headers,
            params={
                "q": f"{query} pushed:>{since}",
                "sort": "updated",
                "order": "desc",
                "per_page": 5
            },
            timeout=15
        )

        if r.ok:
            return r.json().get("items", [])

        logger.error(f"GitHub API error: {r.text}")
        return []

    except Exception as e:
        logger.error(f"GitHub request error: {e}")
        return []

# ─────────────────────────────────────────────────────────────
# Repo Formatting
# ─────────────────────────────────────────────────────────────

def format_repo(repo):
    name = escape_md(repo.get("full_name", "Unknown"))
    desc = escape_md(
        (repo.get("description") or "No description")[:120]
    )

    stars = repo.get("stargazers_count", 0)
    forks = repo.get("forks_count", 0)
    lang = escape_md(repo.get("language") or "Unknown")
    url = repo.get("html_url", "")
    updated = repo.get("updated_at", "")[:10]

    return (
        f"🤖 *{name}*\n"
        f"⭐ {stars:,} stars   🍴 {forks:,} forks\n"
        f"💻 {lang}\n"
        f"📅 Updated: {updated}\n"
        f"📝 {desc}\n"
        f"🔗 {url}\n"
    )

# ─────────────────────────────────────────────────────────────
# Search Runner
# ─────────────────────────────────────────────────────────────

def do_search(chat_id, scheduled=False):

    title = (
        "🕘 *Scheduled Daily AI Report*"
        if scheduled else
        "🔍 *Searching GitHub AI Repositories*"
    )

    tg_send(
        chat_id,
        f"{title}\n⏳ Please wait\\.\\.\\."
    )

    seen = set()
    all_repos = []

    for query in SEARCH_QUERIES:
        repos = search_github(query)

        for repo in repos:
            repo_id = repo.get("id")

            if repo_id and repo_id not in seen:
                seen.add(repo_id)
                all_repos.append(repo)

    if not all_repos:
        tg_send(
            chat_id,
            "😔 No new AI repositories found today\\."
        )
        return

    # Sort by stars
    all_repos.sort(
        key=lambda x: x.get("stargazers_count", 0),
        reverse=True
    )

    top = all_repos[:10]

    header = (
        f"✅ Found *{len(all_repos)}* repositories\\!\n"
        f"📦 Showing Top *{len(top)}* Results:\n\n"
    )

    repo_text = ""

    for repo in top:
        repo_text += format_repo(repo)
        repo_text += "\n━━━━━━━━━━━━━━\n\n"

    footer = (
        "✅ Done\\!\n"
        "Use /search to run again\n"
        "🕘 Auto report: 9 PM UTC"
    )

    final_message = header + repo_text + footer

    # Telegram limit
    MAX_LEN = 4000

    for i in range(0, len(final_message), MAX_LEN):
        tg_send(chat_id, final_message[i:i+MAX_LEN])
        time.sleep(1)

# ─────────────────────────────────────────────────────────────
# Help Message
# ─────────────────────────────────────────────────────────────

HELP = (
    "👾 *AI GitHub Tracker Bot*\n"
    "━━━━━━━━━━━━━━━━━━\n\n"
    "/search \\- Search GitHub now\n"
    "/schedule on \\- Enable daily report\n"
    "/schedule off \\- Disable daily report\n"
    "/status \\- Show your settings\n"
    "/help \\- Show help menu\n\n"
    "🕘 Daily Report Time: 9:00 PM UTC"
)

# ─────────────────────────────────────────────────────────────
# Command Handler
# ─────────────────────────────────────────────────────────────

def handle_update(update):
    global scheduled_chats

    msg = update.get("message", {})

    if not msg:
        return

    chat_id = msg["chat"]["id"]
    text = msg.get("text", "").strip()

    logger.info(f"Message from {chat_id}: {text}")

    # /start /help
    if text.startswith("/start") or text.startswith("/help"):
        tg_send(chat_id, HELP)

    # /search
    elif text.startswith("/search"):
        do_search(chat_id)

    # /schedule on
    elif text.startswith("/schedule on"):

        scheduled_chats.add(chat_id)
        save_scheduled_chats()

        tg_send(
            chat_id,
            "✅ *Daily Schedule Enabled\\!*\n\n"
            "🕘 You will receive AI repo reports every day at 9:00 PM UTC\\."
        )

    # /schedule off
    elif text.startswith("/schedule off"):

        scheduled_chats.discard(chat_id)
        save_scheduled_chats()

        tg_send(
            chat_id,
            "❌ *Daily Schedule Disabled*"
        )

    # /status
    elif text.startswith("/status"):

        status = (
            "✅ ON \\(9:00 PM UTC\\)"
            if chat_id in scheduled_chats
            else
            "❌ OFF"
        )

        tg_send(
            chat_id,
            f"📊 *Your Settings*\n\n"
            f"🕘 Schedule: {status}\n"
            f"📦 Results: Top 10 repositories"
        )

# ─────────────────────────────────────────────────────────────
# Scheduled Job
# ─────────────────────────────────────────────────────────────

def scheduled_job():

    logger.info(
        f"Running scheduled search for "
        f"{len(scheduled_chats)} chats"
    )

    for chat_id in list(scheduled_chats):

        try:
            do_search(chat_id, scheduled=True)
            time.sleep(2)

        except Exception as e:
            logger.error(
                f"Scheduled job failed for {chat_id}: {e}"
            )

# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

def main():

    global offset

    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is missing!")
        return

    if not GITHUB_TOKEN:
        logger.warning(
            "GITHUB_TOKEN not set "
            "(GitHub rate limits may occur)"
        )

    # Load saved users
    load_scheduled_chats()

    # Scheduler
    scheduler = BackgroundScheduler(timezone="UTC")

    scheduler.add_job(
        scheduled_job,
        CronTrigger(
            hour=SCHEDULE_HOUR,
            minute=SCHEDULE_MINUTE
        )
    )

    scheduler.start()

    logger.info(
        f"Scheduler started "
        f"({SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d} UTC)"
    )

    logger.info("Bot is running...")

    # Main polling loop
    while True:

        try:
            updates = tg_get_updates(offset)

            for update in updates:

                offset = update["update_id"] + 1

                try:
                    handle_update(update)

                except Exception as e:
                    logger.error(f"Update handling error: {e}")

        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
            break

        except Exception as e:
            logger.error(f"Main loop error: {e}")
            time.sleep(5)

# ─────────────────────────────────────────────────────────────
# Start
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    main()
