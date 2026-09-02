"""
Central configuration. Loads everything from environment variables (.env),
so no secrets ever live in source code.
"""
import os
from dotenv import load_dotenv

load_dotenv()

STUDENT_BOT_TOKEN = os.getenv("STUDENT_BOT_TOKEN", "")
ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN", "")

ADMIN_TELEGRAM_IDS = {
    int(x) for x in os.getenv("ADMIN_TELEGRAM_IDS", "").split(",") if x.strip().isdigit()
}

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-5")

DB_PATH = os.getenv("DB_PATH", "./data/study_bot.sqlite3")

BOT_NAME = os.getenv("BOT_NAME", "StudyBuddy Cambodia")

TRACKS = {
    "science": "វិទ្យាសាស្ត្រពិត (Science)",
    "social": "វិទ្យាសាស្ត្រសង្គម (Social Science)",
}

GRADES = ["7", "8", "9", "10", "11", "12"]
