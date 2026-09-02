"""
Runs BOTH the student bot and the admin bot inside a single process.
This is the recommended way to deploy on Railway: one service, one volume,
no risk of two separate containers writing to the same SQLite file at once.

Start command (Railway / Procfile): python3 combined_bot.py
"""
import asyncio
import logging
import signal

import db
from main_bot import build_app as build_student_app
from admin_bot import build_app as build_admin_app

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("combined")

async def run_bot(app, name):
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    log.info("%s started polling", name)

async def main():
    db.init_db()

    student_app = build_student_app()
    admin_app = build_admin_app()

    await run_bot(student_app, "student_bot")
    await run_bot(admin_app, "admin_bot")

    stop_event = asyncio.Event()

    def _handle_stop(*_):
        log.info("Shutdown signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_stop)
        except NotImplementedError:
            pass  # Windows doesn't support add_signal_handler

    await stop_event.wait()

    log.info("Shutting down...")
    for app in (student_app, admin_app):
        await app.updater.stop()
        await app.stop()
        await app.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
