import asyncio
import logging
import os
import requests
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
BOT_TOKEN    = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")   # Optional – raises rate limit 60→5000 req/hr

# Scheduled time (UTC)
SCHEDULE_HOUR   = 21   # 9 PM UTC  ≈  best global reach (Asia evening / Europe night / US afternoon)
SCHEDULE_MINUTE = 0

# Keywords to search on GitHub
SEARCH_QUERIES = [
    "AI mobile",
    "AI assistant mobile",
    "LLM mobile Android",
    "on-device AI",
    "edge AI mobile",
    "local LLM Android",
    "AI tools open source",
    "AI agent",
    "mobile AI app",
    "generative AI mobile",
]

# ── State  (in-memory; survives restarts if you add a file/db later) ──────────
scheduled_chats: set[int] = set()

# ── GitHub helpers ────────────────────────────────────────────────────────────

def _gh_headers() -> dict:
    h = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"token {GITHUB_TOKEN}"
    return h


def search_github(query: str, days_back: int = 1, per_page: int = 5) -> list:
    """Return repos updated in the last `days_back` days matching `query`."""
    since = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    params = {
        "q":        f"{query} pushed:>{since}",
        "sort":     "updated",
        "order":    "desc",
        "per_page": per_page,
    }
    try:
        r = requests.get(
            "https://api.github.com/search/repositories",
            headers=_gh_headers(),
            params=params,
            timeout=12,
        )
        r.raise_for_status()
        return r.json().get("items", [])
    except Exception as e:
        logger.error(f"GitHub search error for '{query}': {e}")
        return []


def format_repo(repo: dict) -> str:
    name   = repo.get("full_name", "Unknown")
    desc   = repo.get("description") or "No description"
    stars  = repo.get("stargazers_count", 0)
    forks  = repo.get("forks_count", 0)
    lang   = repo.get("language") or "—"
    url    = repo.get("html_url", "")
    updated = repo.get("updated_at", "")[:10]
    topics  = repo.get("topics", [])[:4]

    tag_line = ("🏷 " + "  ".join(f"`{t}`" for t in topics) + "\n") if topics else ""
    desc_cut  = desc[:120] + ("…" if len(desc) > 120 else "")

    return (
        f"🤖 *{name}*\n"
        f"⭐ {stars:,} stars  🍴 {forks:,} forks  💻 {lang}\n"
        f"📅 Updated: {updated}\n"
        f"📝 {desc_cut}\n"
        f"{tag_line}"
        f"🔗 {url}\n"
    )


# ── Core search logic ─────────────────────────────────────────────────────────

async def do_search(bot, chat_id: int, is_scheduled: bool = False):
    label  = "🕘 *Scheduled Daily AI Report*" if is_scheduled else "🔍 *Manual Search Triggered*"
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    await bot.send_message(
        chat_id=chat_id,
        text=f"{label}\n📆 {now_str}\n\n⏳ Scanning GitHub… please wait.",
        parse_mode="Markdown",
    )

    # Collect unique repos across all queries
    seen:      set[int] = set()
    all_repos: list     = []

    for q in SEARCH_QUERIES:
        for repo in search_github(q):
            rid = repo.get("id")
            if rid and rid not in seen:
                seen.add(rid)
                all_repos.append(repo)

    if not all_repos:
        await bot.send_message(
            chat_id=chat_id,
            text="😔 No new AI repos found today. Try again later or use /search.",
        )
        return

    # Sort by stars descending, take top 10
    all_repos.sort(key=lambda x: x.get("stargazers_count", 0), reverse=True)
    top = all_repos[:10]

    await bot.send_message(
        chat_id=chat_id,
        text=f"✅ Found *{len(all_repos)}* repos! Here are the top *{len(top)}*:",
        parse_mode="Markdown",
    )

    for repo in top:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=format_repo(repo),
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
            await asyncio.sleep(0.3)   # stay within Telegram rate limits
        except Exception as e:
            logger.error(f"Message send error: {e}")

    await bot.send_message(
        chat_id=chat_id,
        text=(
            "━━━━━━━━━━━━━━━━━━━\n"
            "✅ Done!  Use /search to run again manually.\n"
            "🕘 Next auto-report: 9:00 PM UTC (if /schedule on)"
        ),
    )


# ── Scheduled job (APScheduler calls this) ────────────────────────────────────

async def scheduled_job(application: Application):
    logger.info(f"Scheduled job firing – {len(scheduled_chats)} subscriber(s)")
    for chat_id in list(scheduled_chats):
        try:
            await do_search(application.bot, chat_id, is_scheduled=True)
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Scheduled job failed for chat {chat_id}: {e}")


# ── Command handlers ──────────────────────────────────────────────────────────

HELP_TEXT = (
    "👾 *AI GitHub Tracker Bot*\n"
    "━━━━━━━━━━━━━━━━━━━\n"
    "I search GitHub every day for the freshest AI projects!\n\n"
    "📋 *Commands*\n"
    "/search       — Search GitHub *right now*\n"
    "/schedule on  — Enable daily auto-search at 9 PM UTC\n"
    "/schedule off — Disable daily auto-search\n"
    "/status       — Show your current settings\n"
    "/help         — Show this message\n\n"
    "🔍 *I track keywords like:*\n"
    "AI mobile · LLM · on-device AI · edge AI · AI agent · and more"
)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await do_search(context.bot, update.effective_chat.id, is_scheduled=False)


async def cmd_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    args    = context.args

    if not args or args[0].lower() not in ("on", "off"):
        await update.message.reply_text(
            "Usage:\n/schedule on  — enable daily 9 PM alert\n/schedule off — disable it"
        )
        return

    if args[0].lower() == "on":
        scheduled_chats.add(chat_id)
        await update.message.reply_text(
            "✅ *Daily schedule ON!*\n"
            "🕘 You'll get a report every day at *9:00 PM UTC*.\n\n"
            "Use /schedule off to stop.",
            parse_mode="Markdown",
        )
    else:
        scheduled_chats.discard(chat_id)
        await update.message.reply_text(
            "❌ Daily schedule *OFF*.\nUse /schedule on to re-enable.",
            parse_mode="Markdown",
        )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id  = update.effective_chat.id
    sched    = "✅ ON — 9:00 PM UTC daily" if chat_id in scheduled_chats else "❌ OFF"
    keywords = "AI mobile · LLM · on-device AI · edge AI · AI agent · …"

    await update.message.reply_text(
        f"📊 *Your Settings*\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🕘 Schedule : {sched}\n"
        f"🔍 Keywords : {keywords}\n"
        f"📦 Results  : Top 10 repos per search\n",
        parse_mode="Markdown",
    )


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("help",     cmd_help))
    app.add_handler(CommandHandler("search",   cmd_search))
    app.add_handler(CommandHandler("schedule", cmd_schedule))
    app.add_handler(CommandHandler("status",   cmd_status))

    # APScheduler — fires daily at 21:00 UTC (9 PM)
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        lambda: asyncio.ensure_future(scheduled_job(app)),
        CronTrigger(hour=SCHEDULE_HOUR, minute=SCHEDULE_MINUTE, timezone="UTC"),
        id="daily_ai_search",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(f"Scheduler started — daily job at {SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d} UTC")

    logger.info("Bot is running…  Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
