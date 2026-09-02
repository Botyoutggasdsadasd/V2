"""
Admin-only bot. Run this as a SEPARATE process/token from main_bot.py.
Commands:
  /stats            -> total users
  /users            -> list recent users
  /broadcast <text> -> send a message to every registered student
"""
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

import db
from config import ADMIN_BOT_TOKEN, ADMIN_TELEGRAM_IDS

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("admin_bot")

def is_admin(update: Update) -> bool:
    return update.effective_user.id in ADMIN_TELEGRAM_IDS

async def guard(update: Update) -> bool:
    if not is_admin(update):
        await update.message.reply_text("⛔ អ្នកមិនមានសិទ្ធិប្រើប្រាស់ bot នេះទេ។")
        return False
    return True

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard(update):
        return
    await update.message.reply_text(f"👥 សរុបសិស្សដែលបានចុះឈ្មោះ: {db.user_count()}")

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard(update):
        return
    users = db.all_users()[:30]
    if not users:
        await update.message.reply_text("មិនទាន់មានសិស្សចុះឈ្មោះនៅឡើយទេ។")
        return
    lines = [
        f"• {u['name']} | ថ្នាក់{u['grade']} | {u['track']} | id={u['telegram_id']}"
        for u in users
    ]
    await update.message.reply_text("\n".join(lines))

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard(update):
        return
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("សូមប្រើ: /broadcast <message>")
        return
    users = db.all_users()
    sent = 0
    for u in users:
        try:
            await context.bot.send_message(chat_id=u["telegram_id"], text=f"📢 {text}")
            sent += 1
        except Exception as e:
            log.warning("Failed to message %s: %s", u["telegram_id"], e)
    await update.message.reply_text(f"✅ ផ្ញើទៅសិស្សចំនួន {sent}/{len(users)} នាក់។")

def build_app():
    app = Application.builder().token(ADMIN_BOT_TOKEN).build()
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("users", list_users))
    app.add_handler(CommandHandler("broadcast", broadcast))
    return app

if __name__ == "__main__":
    db.init_db()
    application = build_app()
    log.info("Admin bot starting...")
    application.run_polling()
