import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from datetime import date

BOT_TOKEN = "os.environ.get("BOT_TOKEN")"

DB_FILE = "expenses_v2.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def save_expense(user_id, amount, category):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO expenses (user_id, amount, category) VALUES (?, ?, ?)",
        (user_id, amount, category)
    )
    conn.commit()
    conn.close()

def get_today_total(user_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        "SELECT COALESCE(SUM(amount),0) FROM expenses WHERE user_id=? AND DATE(created_at)=?",
        (user_id, date.today().isoformat())
    )
    total = cur.fetchone()[0]
    conn.close()
    return total

def get_month_total(user_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        "SELECT COALESCE(SUM(amount),0) FROM expenses WHERE user_id=? AND strftime('%Y-%m',created_at)=strftime('%Y-%m','now')",
        (user_id,)
    )
    total = cur.fetchone()[0]
    conn.close()
    return total

def get_month_breakdown(user_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        "SELECT category, SUM(amount) FROM expenses WHERE user_id=? AND strftime('%Y-%m',created_at)=strftime('%Y-%m','now') GROUP BY category ORDER BY SUM(amount) DESC",
        (user_id,)
    )
    rows = cur.fetchall()
    conn.close()
    return rows

def get_today_list(user_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, amount, category FROM expenses WHERE user_id=? AND DATE(created_at)=? ORDER BY id ASC",
        (user_id, date.today().isoformat())
    )
    rows = cur.fetchall()
    conn.close()
    return rows

def delete_expense(user_id, expense_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM expenses WHERE id=? AND user_id=?",
        (expense_id, user_id)
    )
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    return deleted

def get_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ Add Expense", callback_data="add")],
        [InlineKeyboardButton("📅 Today", callback_data="today"),
         InlineKeyboardButton("📊 This Month", callback_data="month")],
        [InlineKeyboardButton("📝 List", callback_data="list"),
         InlineKeyboardButton("❓ Help", callback_data="help")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to your Expense Tracker Bot!\n\n"
        "Use the buttons below or /help for commands.",
        reply_markup=get_menu_keyboard()
    )

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 Main Menu — Tap a button:",
        reply_markup=get_menu_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 Available Commands:\n\n"
        "/add <amount> <category> — Save an expense\n"
        "/today — Today's total\n"
        "/month — This month's total + breakdown\n"
        "/list — Show today's expenses with ID\n"
        "/delete <id> — Delete an expense\n"
        "/menu — Show buttons"
    )

async def add_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Usage: /add <amount> <category>\nExample: /add 250 lunch")
        return
    try:
        amount = float(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Amount must be a number.")
        return
    if amount <= 0:
        await update.message.reply_text("❌ Amount must be greater than 0.")
        return
    category = " ".join(context.args[1:])
    save_expense(update.effective_user.id, amount, category)
    await update.message.reply_text(f"✅ Saved: ₹{amount:.2f} — {category}")

async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total = get_today_total(update.effective_user.id)
    await update.message.reply_text(f"📅 Today's total: ₹{total:.2f}")

async def month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    total = get_month_total(user_id)
    rows = get_month_breakdown(user_id)
    if not rows:
        await update.message.reply_text("📊 No expenses this month yet.")
        return
    msg = f"📊 This month's total: ₹{total:.2f}\n\nBreakdown:\n"
    for cat, amt in rows:
        msg += f"• {cat}: ₹{amt:.2f}\n"
    await update.message.reply_text(msg)

async def list_expenses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    rows = get_today_list(user_id)
    if not rows:
        await update.message.reply_text("📝 No expenses found for today.")
        return
    msg = "📝 Today's Expenses:\n\n"
    for exp_id, amount, category in rows:
        msg += f"ID: {exp_id} | ₹{amount:.2f} — {category}\n"
    msg += "\n🗑️ To delete, send: /delete <ID>"
    await update.message.reply_text(msg)

async def delete_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /delete <ID>")
        return
    try:
        expense_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID must be a number.")
        return
    deleted = delete_expense(update.effective_user.id, expense_id)
    if deleted > 0:
        await update.message.reply_text(f"✅ Expense ID {expense_id} deleted successfully.")
    else:
        await update.message.reply_text("❌ Expense not found.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "add":
        await query.message.reply_text("➕ To add an expense, send:\n/add <amount> <category>\nExample: /add 250 lunch")
    elif query.data == "today":
        total = get_today_total(query.from_user.id)
        await query.message.reply_text(f"📅 Today's total: ₹{total:.2f}")
    elif query.data == "month":
        user_id = query.from_user.id
        total = get_month_total(user_id)
        rows = get_month_breakdown(user_id)
        if not rows:
            await query.message.reply_text("📊 No expenses this month yet.")
            return
        msg = f"📊 This month's total: ₹{total:.2f}\n\nBreakdown:\n"
        for cat, amt in rows:
            msg += f"• {cat}: ₹{amt:.2f}\n"
        await query.message.reply_text(msg)
    elif query.data == "list":
        user_id = query.from_user.id
        rows = get_today_list(user_id)
        if not rows:
            await query.message.reply_text("📝 No expenses found for today.")
            return
        msg = "📝 Today's Expenses:\n\n"
        for exp_id, amount, category in rows:
            msg += f"ID: {exp_id} | ₹{amount:.2f} — {category}\n"
        msg += "\n🗑️ To delete, send: /delete <ID>"
        await query.message.reply_text(msg)
    elif query.data == "help":
        await query.message.reply_text("📋 Commands:\n/add\n/today\n/month\n/list\n/delete <id>\n/menu\n/start")

# Main App Setup
if __name__ == "__main__":
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("add", add_expense))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("month", month))
    app.add_handler(CommandHandler("list", list_expenses))
    app.add_handler(CommandHandler("delete", delete_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("Bot is running...")
    app.run_polling()