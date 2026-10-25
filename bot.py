"""
Admin Notification Bot
Receives booking notifications via webhook and forwards to admin chat(s).
Deploy to Railway alongside main bot.
"""
import json
import logging
import os
from datetime import datetime

from aiohttp import web
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ─── Configuration ──────────────────────────────────────────────
BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN", "YOUR_ADMIN_BOT_TOKEN")
ADMIN_CHAT_IDS = [
    int(x) for x in os.getenv("ADMIN_CHAT_IDS", "").split(",") if x.strip()
]
PORT = int(os.getenv("PORT", "8080"))

# ─── Handlers ───────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        f"✅ Admin bot active.\n"
        f"Your chat ID: <code>{chat_id}</code>\n\n"
        f"Add this ID to ADMIN_CHAT_IDS env var to receive notifications.",
        parse_mode="HTML",
    )


async def notify(request: web.Request) -> web.Response:
    """Webhook endpoint: POST /notify with JSON payload."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    # Required fields
    event = data.get("event")  # "booking_created" or "booking_cancelled"
    booking = data.get("booking")

    if not event or not booking:
        return web.json_response({"error": "Missing event or booking"}, status=400)

    # Format message
    text = format_notification(event, booking)

    # Send to all admin chats
    results = []
    for chat_id in ADMIN_CHAT_IDS:
        try:
            await request.app["bot"].send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="HTML",
            )
            results.append({"chat_id": chat_id, "status": "sent"})
        except Exception as e:
            results.append({"chat_id": chat_id, "status": "failed", "error": str(e)})

    return web.json_response({"results": results})


def format_notification(event: str, booking: dict) -> str:
    """Format notification like user sees it."""
    service = booking.get("service", "Unknown")
    date = booking.get("date", "")
    time = booking.get("time", "")
    username = booking.get("username", "Unknown")
    booking_id = booking.get("id", "")

    try:
        date_fmt = datetime.strptime(date, "%Y-%m-%d").strftime("%A, %d %B %Y")
    except Exception:
        date_fmt = date

    if event == "booking_created":
        return (
            "🔔 <b>New Booking</b>\n\n"
            f"🆔 Booking ID: <code>{booking_id}</code>\n"
            f"👤 User: @{username}\n"
            f"💇 Service: {service}\n"
            f"📅 Date: {date_fmt}\n"
            f"🕐 Time: {time}"
        )
    elif event == "booking_cancelled":
        return (
            "❌ <b>Booking Cancelled</b>\n\n"
            f"🆔 Booking ID: <code>{booking_id}</code>\n"
            f"👤 User: @{username}\n"
            f"💇 Service: {service}\n"
            f"📅 Date: {date_fmt}\n"
            f"🕐 Time: {time}"
        )
    else:
        return f"⚠️ Unknown event: {event}"


# ─── Main ───────────────────────────────────────────────────────
async def on_startup(app: web.Application) -> None:
    """Initialize bot and set webhook."""
    bot_app = Application.builder().token(BOT_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    await bot_app.initialize()
    await bot_app.start()
    app["bot"] = bot_app.bot
    logging.info("Admin bot started")


async def on_shutdown(app: web.Application) -> None:
    """Cleanup."""
    if "bot" in app:
        await app["bot"].get_updates  # keep reference
    logging.info("Admin bot stopped")


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )

    if BOT_TOKEN == "YOUR_ADMIN_BOT_TOKEN":
        raise RuntimeError("Set ADMIN_BOT_TOKEN env var")

    if not ADMIN_CHAT_IDS:
        logging.warning("ADMIN_CHAT_IDS not set — notifications won't be delivered")

    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    app.router.add_post("/notify", notify)
    app.router.add_get("/health", lambda r: web.json_response({"status": "ok"}))

    logging.info(f"Starting admin bot on port {PORT}")
    web.run_app(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()