import logging
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
LEVEL, SUBJECT, YEAR = range(3)
ADMIN_ACTION, ADMIN_LEVEL, ADMIN_SUBJECT, ADMIN_YEAR, ADMIN_FILE = range(5, 10)
DELETE_LEVEL, DELETE_SUBJECT, DELETE_YEAR = range(10, 13)

# Add your admin Telegram user IDs here (get your ID from @userinfobot)
ADMIN_IDS = [7576725871]  # Replace with actual admin user IDs

# Database setup
def init_db():
    """Initialize the database."""
    conn = sqlite3.connect('pyq_papers.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS papers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level TEXT NOT NULL,
            subject TEXT NOT NULL,
            year TEXT NOT NULL,
            file_id TEXT NOT NULL,
            file_name TEXT,
            uploaded_by INTEGER,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(level, subject, year)
        )
    ''')
    conn.commit()
    conn.close()

def get_subjects(level):
    """Get all unique subjects for a level from database."""
    conn = sqlite3.connect('pyq_papers.db')
    c = conn.cursor()
    c.execute('SELECT DISTINCT subject FROM papers WHERE level = ? ORDER BY subject', (level,))
    subjects = [row[0] for row in c.fetchall()]
    conn.close()
    return subjects

def get_years(level, subject):
    """Get all available years for a level and subject."""
    conn = sqlite3.connect('pyq_papers.db')
    c = conn.cursor()
    c.execute('SELECT DISTINCT year FROM papers WHERE level = ? AND subject = ? ORDER BY year DESC', 
              (level, subject))
    years = [row[0] for row in c.fetchall()]
    conn.close()
    return years

def get_paper(level, subject, year):
    """Get paper file_id for given criteria."""
    conn = sqlite3.connect('pyq_papers.db')
    c = conn.cursor()
    c.execute('SELECT file_id, file_name FROM papers WHERE level = ? AND subject = ? AND year = ?', 
              (level, subject, year))
    result = c.fetchone()
    conn.close()
    return result

def add_paper(level, subject, year, file_id, file_name, user_id):
    """Add a new paper to database."""
    conn = sqlite3.connect('pyq_papers.db')
    c = conn.cursor()
    try:
        c.execute('''
            INSERT OR REPLACE INTO papers (level, subject, year, file_id, file_name, uploaded_by)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (level, subject, year, file_id, file_name, user_id))
        conn.commit()
        success = True
    except Exception as e:
        logger.error(f"Error adding paper: {e}")
        success = False
    conn.close()
    return success

def delete_paper(level, subject, year):
    """Delete a paper from database."""
    conn = sqlite3.connect('pyq_papers.db')
    c = conn.cursor()
    c.execute('DELETE FROM papers WHERE level = ? AND subject = ? AND year = ?', 
              (level, subject, year))
    deleted = c.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def is_admin(user_id):
    """Check if user is admin."""
    return user_id in ADMIN_IDS

# User flow functions
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the conversation and ask for program level."""
    keyboard = [
        [InlineKeyboardButton("Foundation", callback_data="foundation")],
        [InlineKeyboardButton("Diploma", callback_data="diploma")],
        [InlineKeyboardButton("Degree", callback_data="degree")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = "🎓 Welcome to IIT Madras BS Degree PYQ Bot!\n\nSelect your program level:"
    
    if is_admin(update.effective_user.id):
        message_text += "\n\n👑 Admin: Use /admin to manage papers"
    
    await update.message.reply_text(message_text, reply_markup=reply_markup)
    return LEVEL

async def select_level(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store selected level and ask for subject."""
    query = update.callback_query
    await query.answer()
    
    context.user_data["level"] = query.data
    
    subjects = get_subjects(query.data)
    
    if not subjects:
        await query.edit_message_text(
            f"❌ No papers available for {query.data.capitalize()} level yet.\n\n"
            "Use /start to try another level."
        )
        return ConversationHandler.END
    
    keyboard = [[InlineKeyboardButton(subject, callback_data=subject)] for subject in subjects]
    keyboard.append([InlineKeyboardButton("« Back", callback_data="back_to_level")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"📚 Level: {query.data.capitalize()}\n\n"
        "Select a subject:",
        reply_markup=reply_markup
    )
    return SUBJECT

async def select_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store selected subject and ask for year."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "back_to_level":
        keyboard = [
            [InlineKeyboardButton("Foundation", callback_data="foundation")],
            [InlineKeyboardButton("Diploma", callback_data="diploma")],
            [InlineKeyboardButton("Degree", callback_data="degree")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🎓 Welcome to IIT Madras BS Degree PYQ Bot!\n\n"
            "Select your program level:",
            reply_markup=reply_markup
        )
        return LEVEL
    
    context.user_data["subject"] = query.data
    
    years = get_years(context.user_data["level"], query.data)
    
    keyboard = [[InlineKeyboardButton(year, callback_data=year)] for year in years]
    keyboard.append([InlineKeyboardButton("« Back", callback_data="back_to_subject")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"📚 Level: {context.user_data['level'].capitalize()}\n"
        f"📖 Subject: {query.data}\n\n"
        "Select the year:",
        reply_markup=reply_markup
    )
    return YEAR

async def select_year(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Provide the question paper based on selections."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "back_to_subject":
        level = context.user_data.get("level")
        subjects = get_subjects(level)
        keyboard = [[InlineKeyboardButton(subject, callback_data=subject)] for subject in subjects]
        keyboard.append([InlineKeyboardButton("« Back", callback_data="back_to_level")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"📚 Level: {level.capitalize()}\n\n"
            "Select a subject:",
            reply_markup=reply_markup
        )
        return SUBJECT
    
    year = query.data
    level = context.user_data.get("level")
    subject = context.user_data.get("subject")
    
    paper = get_paper(level, subject, year)
    
    if paper:
        file_id, file_name = paper
        await query.edit_message_text(
            f"✅ Question Paper Found!\n\n"
            f"📚 Level: {level.capitalize()}\n"
            f"📖 Subject: {subject}\n"
            f"📅 Year: {year}\n\n"
            f"📄 Sending file..."
        )
        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=file_id,
            caption=f"📝 {subject} - {year}\n\nUse /start to search for another paper."
        )
    else:
        await query.edit_message_text(
            f"❌ Sorry, question paper not available.\n\n"
            f"📚 Level: {level.capitalize()}\n"
            f"📖 Subject: {subject}\n"
            f"📅 Year: {year}\n\n"
            f"Use /start to search for another paper."
        )
    
    return ConversationHandler.END

# Admin functions
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show admin panel."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ You are not authorized to use admin commands.")
        return ConversationHandler.END
    
    keyboard = [
        [InlineKeyboardButton("📤 Upload Paper", callback_data="admin_upload")],
        [InlineKeyboardButton("🗑️ Delete Paper", callback_data="admin_delete")],
        [InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👑 Admin Panel\n\nWhat would you like to do?",
        reply_markup=reply_markup
    )
    return ADMIN_ACTION

async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle admin action selection."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "admin_cancel":
        await query.edit_message_text("❌ Admin panel closed. Use /admin to open again.")
        return ConversationHandler.END
    
    context.user_data["admin_action"] = query.data
    
    if query.data == "admin_upload":
        keyboard = [
            [InlineKeyboardButton("Foundation", callback_data="foundation")],
            [InlineKeyboardButton("Diploma", callback_data="diploma")],
            [InlineKeyboardButton("Degree", callback_data="degree")],
            [InlineKeyboardButton("« Cancel", callback_data="admin_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📤 Upload New Paper\n\nSelect program level:",
            reply_markup=reply_markup
        )
        return ADMIN_LEVEL
    
    elif query.data == "admin_delete":
        keyboard = [
            [InlineKeyboardButton("Foundation", callback_data="foundation")],
            [InlineKeyboardButton("Diploma", callback_data="diploma")],
            [InlineKeyboardButton("Degree", callback_data="degree")],
            [InlineKeyboardButton("« Cancel", callback_data="admin_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🗑️ Delete Paper\n\nSelect program level:",
            reply_markup=reply_markup
        )
        return DELETE_LEVEL

async def admin_select_level(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Admin selects level for upload."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "admin_cancel":
        await query.edit_message_text("❌ Operation cancelled.")
        return ConversationHandler.END
    
    context.user_data["admin_level"] = query.data
    
    await query.edit_message_text(
        f"📚 Level: {query.data.capitalize()}\n\n"
        "Now send the subject name (e.g., 'Mathematics I'):"
    )
    return ADMIN_SUBJECT

async def admin_get_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Admin provides subject name."""
    subject = update.message.text.strip()
    context.user_data["admin_subject"] = subject
    
    await update.message.reply_text(
        f"📚 Level: {context.user_data['admin_level'].capitalize()}\n"
        f"📖 Subject: {subject}\n\n"
        "Now send the year (e.g., '2024'):"
    )
    return ADMIN_YEAR

async def admin_get_year(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Admin provides year."""
    year = update.message.text.strip()
    context.user_data["admin_year"] = year
    
    await update.message.reply_text(
        f"📚 Level: {context.user_data['admin_level'].capitalize()}\n"
        f"📖 Subject: {context.user_data['admin_subject']}\n"
        f"📅 Year: {year}\n\n"
        "Now send the PDF file:"
    )
    return ADMIN_FILE

async def admin_get_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Admin uploads the file."""
    if not update.message.document:
        await update.message.reply_text("❌ Please send a document file. Use /cancel to abort.")
        return ADMIN_FILE
    
    file = update.message.document
    level = context.user_data["admin_level"]
    subject = context.user_data["admin_subject"]
    year = context.user_data["admin_year"]
    
    success = add_paper(level, subject, year, file.file_id, file.file_name, update.effective_user.id)
    
    if success:
        await update.message.reply_text(
            f"✅ Paper uploaded successfully!\n\n"
            f"📚 Level: {level.capitalize()}\n"
            f"📖 Subject: {subject}\n"
            f"📅 Year: {year}\n"
            f"📄 File: {file.file_name}\n\n"
            "Use /admin to upload more papers."
        )
    else:
        await update.message.reply_text(
            "❌ Error uploading paper. Please try again.\n\n"
            "Use /admin to try again."
        )
    
    return ConversationHandler.END

# Delete flow
async def delete_select_level(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Admin selects level for deletion."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "admin_cancel":
        await query.edit_message_text("❌ Operation cancelled.")
        return ConversationHandler.END
    
    context.user_data["delete_level"] = query.data
    subjects = get_subjects(query.data)
    
    if not subjects:
        await query.edit_message_text(
            f"❌ No papers found for {query.data.capitalize()} level.\n\n"
            "Use /admin to try again."
        )
        return ConversationHandler.END
    
    keyboard = [[InlineKeyboardButton(subject, callback_data=subject)] for subject in subjects]
    keyboard.append([InlineKeyboardButton("« Cancel", callback_data="admin_cancel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"📚 Level: {query.data.capitalize()}\n\n"
        "Select subject to delete:",
        reply_markup=reply_markup
    )
    return DELETE_SUBJECT

async def delete_select_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Admin selects subject for deletion."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "admin_cancel":
        await query.edit_message_text("❌ Operation cancelled.")
        return ConversationHandler.END
    
    context.user_data["delete_subject"] = query.data
    years = get_years(context.user_data["delete_level"], query.data)
    
    keyboard = [[InlineKeyboardButton(year, callback_data=year)] for year in years]
    keyboard.append([InlineKeyboardButton("« Cancel", callback_data="admin_cancel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"📚 Level: {context.user_data['delete_level'].capitalize()}\n"
        f"📖 Subject: {query.data}\n\n"
        "Select year to delete:",
        reply_markup=reply_markup
    )
    return DELETE_YEAR

async def delete_select_year(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Admin confirms deletion."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "admin_cancel":
        await query.edit_message_text("❌ Operation cancelled.")
        return ConversationHandler.END
    
    year = query.data
    level = context.user_data["delete_level"]
    subject = context.user_data["delete_subject"]
    
    deleted = delete_paper(level, subject, year)
    
    if deleted:
        await query.edit_message_text(
            f"✅ Paper deleted successfully!\n\n"
            f"📚 Level: {level.capitalize()}\n"
            f"📖 Subject: {subject}\n"
            f"📅 Year: {year}\n\n"
            "Use /admin to manage more papers."
        )
    else:
        await query.edit_message_text(
            "❌ Error deleting paper.\n\n"
            "Use /admin to try again."
        )
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation."""
    await update.message.reply_text(
        "❌ Operation cancelled. Use /start to begin again."
    )
    return ConversationHandler.END

def main() -> None:
    """Run the bot."""
    # Initialize database
    init_db()
    
    # Replace 'YOUR_BOT_TOKEN' with your actual bot token from @BotFather
    application = Application.builder().token("8531233411:AAG1kju85IYyrzeuL0xXUyddvIGcC5qfEZ0").build()

    # User conversation handler
    user_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LEVEL: [CallbackQueryHandler(select_level)],
            SUBJECT: [CallbackQueryHandler(select_subject)],
            YEAR: [CallbackQueryHandler(select_year)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Admin conversation handler for upload
    admin_upload_handler = ConversationHandler(
        entry_points=[CommandHandler("admin", admin_panel)],
        states={
            ADMIN_ACTION: [CallbackQueryHandler(admin_action)],
            ADMIN_LEVEL: [CallbackQueryHandler(admin_select_level)],
            ADMIN_SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_get_subject)],
            ADMIN_YEAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_get_year)],
            ADMIN_FILE: [MessageHandler(filters.Document.PDF | filters.Document.ALL, admin_get_file)],
            DELETE_LEVEL: [CallbackQueryHandler(delete_select_level)],
            DELETE_SUBJECT: [CallbackQueryHandler(delete_select_subject)],
            DELETE_YEAR: [CallbackQueryHandler(delete_select_year)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(user_conv_handler)
    application.add_handler(admin_upload_handler)

    # Start the bot
    logger.info("Bot started!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()