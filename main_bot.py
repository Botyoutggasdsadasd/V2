"""
Student-facing bot.
Flow:
  /start -> onboarding (name, age, school, grade, track, choose AI name)
  Send a photo -> bot OCRs it, then shows buttons: Test / Question / Summary / Explain answer
  Send text -> normal AI chat (context-aware, remembers profile + recent history)
  Send voice -> currently requires a speech-to-text step (see NOTE in handle_voice)
"""
import logging
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, filters,
)

import db
import ai_client
from config import STUDENT_BOT_TOKEN, TRACKS, GRADES, BOT_NAME

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("student_bot")

# Onboarding states
NAME, AGE, SCHOOL, GRADE, TRACK, AI_NAME = range(6)

MAIN_MENU = ReplyKeyboardMarkup(
    [["🤖 សួរសំណួរ (Chat)", "📷 ផ្ញើរូបភាព"],
     ["📚 លំហាត់ Bac II", "😂 សើចលេងបន្តិច"],
     ["📊 ព័ត៌មានគណនី", "❓ ជំនួយ"]],
    resize_keyboard=True,
)

PHOTO_ACTIONS = InlineKeyboardMarkup([
    [InlineKeyboardButton("📝 បង្កើតជា Test", callback_data="make_test")],
    [InlineKeyboardButton("❔ បង្កើតជា Question ថ្មី", callback_data="make_question")],
    [InlineKeyboardButton("📌 សង្ខេប", callback_data="summarize")],
    [InlineKeyboardButton("🧮 ពន្យល់ចម្លើយ (Explain/Solve)", callback_data="explain")],
])

BAC_MENU = InlineKeyboardMarkup([
    [InlineKeyboardButton(label, callback_data=f"bac_{key}")]
    for key, label in ai_client.BAC_SUBJECTS.items()
])


# ---------------- Onboarding ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = db.get_user(update.effective_user.id)
    if user and user.get("name"):
        await update.message.reply_text(
            f"សួស្តី {user['name']}! 👋 ត្រលប់មកវិញហើយ។ តើថ្ងៃនេះចង់សិក្សាអ្វី?",
            reply_markup=MAIN_MENU,
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "🎓 សូមស្វាគមន៍មកកាន់ StudyBuddy Cambodia!\n\n"
        "មុននឹងចាប់ផ្តើម សូមប្រាប់ខ្ញុំបន្តិចអំពីអ្នក។\n"
        "សូមវាយឈ្មោះរបស់អ្នក (Name):"
    )
    return NAME

async def get_name(update, context):
    context.user_data["name"] = update.message.text.strip()
    await update.message.reply_text("អាយុប៉ុន្មាន? (Age):")
    return AGE

async def get_age(update, context):
    context.user_data["age"] = update.message.text.strip()
    await update.message.reply_text("សាលារៀនអ្វី? (School):")
    return SCHOOL

async def get_school(update, context):
    context.user_data["school"] = update.message.text.strip()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(g, callback_data=f"grade_{g}")] for g in GRADES])
    await update.message.reply_text("ថ្នាក់ទីប៉ុន្មាន?", reply_markup=kb)
    return GRADE

async def get_grade(update, context):
    q = update.callback_query
    await q.answer()
    grade = q.data.split("_")[1]
    context.user_data["grade"] = grade
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(v, callback_data=f"track_{k}")] for k, v in TRACKS.items()
    ])
    await q.edit_message_text("ជ្រើសរើសជំនាញ:", reply_markup=kb)
    return TRACK

async def get_track(update, context):
    q = update.callback_query
    await q.answer()
    track_key = q.data.split("_")[1]
    context.user_data["track"] = TRACKS[track_key]
    await q.edit_message_text(
        f"ចុងក្រោយ តើអ្នកចង់ដាក់ឈ្មោះ AI ជំនួយការនេះថាអ្វី? (ឬសរសេរ 'skip' ដើម្បីប្រើឈ្មោះលំនាំដើម '{BOT_NAME}')"
    )
    return AI_NAME

async def get_ai_name(update, context):
    text = update.message.text.strip()
    ai_name = BOT_NAME if text.lower() == "skip" else text
    d = context.user_data
    db.upsert_user(
        update.effective_user.id,
        name=d["name"], age=d.get("age"), school=d.get("school"),
        grade=d.get("grade"), track=d.get("track"), ai_name=ai_name, state="idle",
    )
    await update.message.reply_text(
        f"✅ រួចរាល់! ជំនួយការរបស់អ្នកឥឡូវឈ្មោះ '{ai_name}'។\n\n"
        "ឥឡូវផ្ញើសំណួរជាអក្សរ ឬផ្ញើរូបភាពលំហាត់/តេស្តមកខ្ញុំបានហើយ! 🚀\n"
        "ចង់អនុវត្តន៍ម៉ូតប្រឡងជាតិ? ចុច '📚 លំហាត់ Bac II'។\n"
        "ចង់សម្រាកខួរក្បាល? ចុច '😂 សើចលេងបន្តិច' 😄",
        reply_markup=MAIN_MENU,
    )
    return ConversationHandler.END

async def cancel(update, context):
    await update.message.reply_text("បោះបង់។ វាយ /start ម្តងទៀតនៅពេលត្រៀមខ្លួន។")
    return ConversationHandler.END


# ---------------- Photo handling ----------------

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = db.get_user(uid)
    if not user:
        await update.message.reply_text("សូមវាយ /start មុនសិន 🙂")
        return

    msg = await update.message.reply_text("🔍 កំពុងអានរូបភាព... (Reading image...)")
    photo_file = await update.message.photo[-1].get_file()
    image_bytes = bytes(await photo_file.download_as_bytearray())

    extracted = ai_client.read_image_and_answer(user, image_bytes, "image/jpeg", ai_client.INSTR_EXTRACT)
    db.save_ocr(uid, extracted)

    preview = extracted if len(extracted) < 600 else extracted[:600] + "…"
    await msg.edit_text(f"✅ អានរួច! នេះជាខ្លឹមសារដែលបានអាន:\n\n{preview}\n\nចង់ឲ្យខ្ញុំធ្វើអ្វីជាមួយវា?")
    await update.message.reply_text("ជ្រើសរើសសកម្មភាព:", reply_markup=PHOTO_ACTIONS)


async def handle_photo_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    user = db.get_user(uid)
    extracted = db.get_ocr(uid)
    if not extracted:
        await q.edit_message_text("មិនមានរូបភាពថ្មីៗទេ សូមផ្ញើរូបភាពម្តងទៀត។")
        return

    action_map = {
        "make_test": ai_client.INSTR_MAKE_TEST,
        "make_question": ai_client.INSTR_MAKE_QUESTION,
        "summarize": ai_client.INSTR_SUMMARIZE,
        "explain": ai_client.INSTR_EXPLAIN_ANSWER,
    }
    instruction = action_map[q.data]
    await q.edit_message_text("✍️ កំពុងរៀបចំចម្លើយ...")

    prompt = f"{instruction}\n\n--- ខ្លឹមសារ ---\n{extracted}"
    result = ai_client.chat(user, [], prompt)

    db.save_message(uid, "user", f"[Photo action: {q.data}]")
    db.save_message(uid, "assistant", result)

    for i in range(0, len(result), 3800):
        await context.bot.send_message(chat_id=uid, text=result[i:i+3800])


# ---------------- Bac II practice ----------------

async def show_bac_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📚 ជ្រើសរើសមុខវិជ្ជាដែលចង់អនុវត្តន៍ម៉ូតប្រឡងជាតិ (Bac II):",
        reply_markup=BAC_MENU,
    )

async def handle_bac_subject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    user = db.get_user(uid)
    if not user:
        await q.edit_message_text("សូមវាយ /start មុនសិន 🙂")
        return
    subject_key = q.data.split("_", 1)[1]
    subject_label = ai_client.BAC_SUBJECTS.get(subject_key, subject_key)
    await q.edit_message_text(f"✍️ កំពុងរៀបចំលំហាត់ម៉ូត Bac II មុខវិជ្ជា{subject_label}...")

    instruction = ai_client.bac_practice_instruction(subject_label, user.get("grade") or "12")
    result = ai_client.chat(user, [], instruction)
    db.track_subject_mention(uid, subject_key)
    db.save_message(uid, "user", f"[Bac practice: {subject_label}]")
    db.save_message(uid, "assistant", result)

    for i in range(0, len(result), 3800):
        await context.bot.send_message(chat_id=uid, text=result[i:i+3800])


# ---------------- Text chat ----------------

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = db.get_user(uid)
    if not user:
        await update.message.reply_text("សូមវាយ /start មុនសិន 🙂")
        return

    text = update.message.text

    if text == "📚 លំហាត់ Bac II":
        await show_bac_menu(update, context)
        return
    if text == "😂 សើចលេងបន្តិច":
        await update.message.reply_text(ai_client.random_joke())
        return
    if text == "📊 ព័ត៌មានគណនី":
        streak = user.get("streak") or 0
        top_subjects = db.get_top_subjects(uid, 3)
        subj_text = ", ".join(ai_client.BAC_SUBJECTS.get(k, k) for k, _ in top_subjects) or "មិនទាន់មានទិន្នន័យ"
        await update.message.reply_text(
            f"👤 ឈ្មោះ: {user['name']}\n🎂 អាយុ: {user['age']}\n🏫 សាលា: {user['school']}\n"
            f"📚 ថ្នាក់: {user['grade']}\n🧭 ជំនាញ: {user['track']}\n🤖 ជំនួយការ: {user['ai_name']}\n"
            f"🔥 រៀនជាប់គ្នា: {streak} ថ្ងៃ\n📈 មុខវិជ្ជាសិក្សាញឹកញាប់: {subj_text}"
        )
        return
    if text == "❓ ជំនួយ":
        await update.message.reply_text(
            "📖 របៀបប្រើ:\n"
            "• សរសេរសំណួរអ្វីក៏បាន ខ្ញុំឆ្លើយបាន\n"
            "• ផ្ញើរូបភាពលំហាត់/តេស្ត ខ្ញុំអានឲ្យ ហើយអាចប្រែជា Test/Question/សង្ខេប/ដោះស្រាយ\n"
            "• ចុច '📚 លំហាត់ Bac II' ដើម្បីអនុវត្តន៍ម៉ូតប្រឡងជាតិតាមមុខវិជ្ជា\n"
            "• ចុច '😂 សើចលេងបន្តិច' ពេលចង់សម្រាកខួរក្បាល\n"
            "• ផ្ញើសារជាសំឡេងក៏បានដែរ"
        )
        return
    if text == "🤖 សួរសំណួរ (Chat)":
        await update.message.reply_text("បាទ/ចាស សូមសរសេរសំណួររបស់អ្នកមក! 😊")
        return

    # --- memory: streak + subject interest tracking (the "understands you" part) ---
    db.record_activity_and_streak(uid)
    subject = ai_client.detect_subject(text)
    if subject:
        db.track_subject_mention(uid, subject)

    stressed = ai_client.detect_stress(text)
    if stressed:
        db.set_mood(uid, "stressed")
        await update.message.reply_text(ai_client.CALMING_INTRO)
    else:
        db.set_mood(uid, "neutral")

    history = db.get_recent_history(uid, limit=12)
    reply = ai_client.chat(user, history, text)

    db.save_message(uid, "user", text)
    db.save_message(uid, "assistant", reply)

    for i in range(0, len(reply), 3800):
        await update.message.reply_text(reply[i:i+3800])


# ---------------- Voice ----------------

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # NOTE: Claude does not accept raw audio input. To support voice messages you need a
    # speech-to-text step first (e.g. OpenAI Whisper API, or a self-hosted whisper.cpp / faster-whisper).
    # Wire that transcription call in here, then pass the resulting text into ai_client.chat(),
    # the same as handle_text() does.
    await update.message.reply_text(
        "🎤 ខ្ញុំទទួលបានសារជាសំឡេងហើយ! ប៉ុន្តែមុខងារបំប្លែងសំឡេងទៅជាអក្សរ (speech-to-text) "
        "នៅមិនទាន់ភ្ជាប់នៅឡើយទេ។ សូមអ្នកអភិវឌ្ឍន៍ភ្ជាប់សេវា Whisper API ក្នុងឯកសារ main_bot.py "
        "(មើល handle_voice) ។ ជាបណ្តោះអាសន្ន សូមសរសេរជាអក្សរវិញ 🙏"
    )


# ---------------- App wiring ----------------

def build_app():
    app = Application.builder().token(STUDENT_BOT_TOKEN).build()

    onboarding = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
            SCHOOL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_school)],
            GRADE: [CallbackQueryHandler(get_grade, pattern="^grade_")],
            TRACK: [CallbackQueryHandler(get_track, pattern="^track_")],
            AI_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_ai_name)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(onboarding)
    app.add_handler(CallbackQueryHandler(handle_photo_action, pattern="^(make_test|make_question|summarize|explain)$"))
    app.add_handler(CallbackQueryHandler(handle_bac_subject, pattern="^bac_"))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    return app

if __name__ == "__main__":
    db.init_db()
    application = build_app()
    log.info("Student bot starting...")
    application.run_polling()
