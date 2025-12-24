import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import asyncio
import sqlite3
from datetime import datetime

# Configuration
BOT_TOKEN = "8530628540:AAHPuFjnUbE-qYJEmX_NtkKqzf3KoZbk6kw"
WEB_APP_URL = "https://thriving-speculoos-3b863c.netlify.app/"  # e.g., https://your-app.netlify.app
ADMIN_IDS = [1172284285]  # Replace with actual admin Telegram IDs

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Database initialization
def init_db():
    conn = sqlite3.connect('twa_games.db')
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        telegram_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        phone TEXT,
        language TEXT DEFAULT 'uz',
        is_pro BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Games table
    c.execute('''CREATE TABLE IF NOT EXISTS games (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        creator_id INTEGER,
        game_type TEXT,
        title TEXT,
        share_link TEXT UNIQUE,
        questions TEXT,
        is_pro BOOLEAN DEFAULT 0,
        plays INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (creator_id) REFERENCES users(telegram_id)
    )''')
    
    # Pro requests table
    c.execute('''CREATE TABLE IF NOT EXISTS pro_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        status TEXT DEFAULT 'pending',
        requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        approved_at TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(telegram_id)
    )''')
    
    conn.commit()
    conn.close()

init_db()

# States for registration
class Registration(StatesGroup):
    language = State()
    name = State()
    contact = State()

# Language selection keyboard
def get_language_keyboard():
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🇺🇿 O'zbekcha"), KeyboardButton(text="🇬🇧 English")],
            [KeyboardButton(text="🇷🇺 Русский")]
        ],
        resize_keyboard=True
    )
    return kb

# Main menu keyboard
def get_main_menu(lang='uz'):
    texts = {
        'uz': {'webapp': "🎮 O'yinlar sahifasi", 'support': "📞 Qo'llab-quvvatlash"},
        'en': {'webapp': "🎮 Games Dashboard", 'support': "📞 Support"},
        'ru': {'webapp': "🎮 Панель игр", 'support': "📞 Поддержка"}
    }
    
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=texts[lang]['webapp'], web_app=WebAppInfo(url=WEB_APP_URL))],
            [KeyboardButton(text=texts[lang]['support'])]
        ],
        resize_keyboard=True
    )
    return kb

# Admin menu
def get_admin_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Users", callback_data="admin_users")],
        [InlineKeyboardButton(text="🎮 Games Stats", callback_data="admin_games")],
        [InlineKeyboardButton(text="⭐ Pro Requests", callback_data="admin_requests")]
    ])
    return kb

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    conn = sqlite3.connect('twa_games.db')
    c = conn.cursor()
    c.execute("SELECT telegram_id, language FROM users WHERE telegram_id = ?", (message.from_user.id,))
    user = c.fetchone()
    conn.close()
    
    if user:
        lang = user[1]
        welcome_texts = {
            'uz': f"Xush kelibsiz, {message.from_user.first_name}! 🎮",
            'en': f"Welcome back, {message.from_user.first_name}! 🎮",
            'ru': f"Добро пожаловать, {message.from_user.first_name}! 🎮"
        }
        await message.answer(welcome_texts[lang], reply_markup=get_main_menu(lang))
    else:
        await message.answer(
            "🌍 Tilni tanlang / Choose language / Выберите язык:",
            reply_markup=get_language_keyboard()
        )
        await state.set_state(Registration.language)

@dp.message(Registration.language)
async def process_language(message: types.Message, state: FSMContext):
    lang_map = {
        "🇺🇿 O'zbekcha": 'uz',
        "🇬🇧 English": 'en',
        "🇷🇺 Русский": 'ru'
    }
    
    lang = lang_map.get(message.text, 'uz')
    await state.update_data(language=lang)
    
    name_texts = {
        'uz': "Ismingizni kiriting:",
        'en': "Enter your name:",
        'ru': "Введите ваше имя:"
    }
    
    await message.answer(name_texts[lang], reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(Registration.name)

@dp.message(Registration.name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    data = await state.get_data()
    lang = data['language']
    
    contact_texts = {
        'uz': "Telefon raqamingizni ulashing:",
        'en': "Share your phone number:",
        'ru': "Поделитесь номером телефона:"
    }
    
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Share Contact", request_contact=True)]],
        resize_keyboard=True
    )
    
    await message.answer(contact_texts[lang], reply_markup=kb)
    await state.set_state(Registration.contact)

@dp.message(Registration.contact, F.contact)
async def process_contact(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data['language']
    
    conn = sqlite3.connect('twa_games.db')
    c = conn.cursor()
    c.execute("""INSERT OR REPLACE INTO users 
                 (telegram_id, username, full_name, phone, language) 
                 VALUES (?, ?, ?, ?, ?)""",
              (message.from_user.id, 
               message.from_user.username or '',
               data['name'],
               message.contact.phone_number,
               lang))
    conn.commit()
    conn.close()
    
    success_texts = {
        'uz': "✅ Ro'yxatdan o'tdingiz! Endi o'yinlar sahifasiga kiring.",
        'en': "✅ Registration complete! Now access the Games Dashboard.",
        'ru': "✅ Регистрация завершена! Теперь войдите в панель игр."
    }
    
    await message.answer(success_texts[lang], reply_markup=get_main_menu(lang))
    await state.clear()

@dp.message(F.text.in_(["📞 Qo'llab-quvvatlash", "📞 Support", "📞 Поддержка"]))
async def support_handler(message: types.Message):
    conn = sqlite3.connect('twa_games.db')
    c = conn.cursor()
    c.execute("SELECT language FROM users WHERE telegram_id = ?", (message.from_user.id,))
    result = c.fetchone()
    conn.close()
    
    lang = result[0] if result else 'uz'
    
    support_texts = {
        'uz': "📞 Qo'llab-quvvatlash:\n\nSavollaringiz bo'lsa @admin ga murojaat qiling.",
        'en': "📞 Support:\n\nFor questions, contact @admin.",
        'ru': "📞 Поддержка:\n\nДля вопросов обращайтесь к @admin."
    }
    
    await message.answer(support_texts[lang])

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Access denied.")
        return
    
    await message.answer(
        "🔐 Admin Panel\n\nSelect an option:",
        reply_markup=get_admin_keyboard()
    )

@dp.callback_query(F.data == "admin_users")
async def admin_users(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Access denied", show_alert=True)
        return
    
    conn = sqlite3.connect('twa_games.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*), SUM(is_pro) FROM users")
    total, pro_count = c.fetchone()
    conn.close()
    
    await callback.message.edit_text(
        f"👥 User Statistics:\n\n"
        f"Total Users: {total}\n"
        f"Pro Users: {pro_count or 0}\n"
        f"Free Users: {total - (pro_count or 0)}",
        reply_markup=get_admin_keyboard()
    )

@dp.callback_query(F.data == "admin_games")
async def admin_games(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Access denied", show_alert=True)
        return
    
    conn = sqlite3.connect('twa_games.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*), SUM(plays) FROM games")
    total_games, total_plays = c.fetchone()
    conn.close()
    
    await callback.message.edit_text(
        f"🎮 Games Statistics:\n\n"
        f"Total Games: {total_games or 0}\n"
        f"Total Plays: {total_plays or 0}",
        reply_markup=get_admin_keyboard()
    )

@dp.callback_query(F.data == "admin_requests")
async def admin_requests(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Access denied", show_alert=True)
        return
    
    conn = sqlite3.connect('twa_games.db')
    c = conn.cursor()
    c.execute("""SELECT pr.id, u.full_name, u.telegram_id, pr.requested_at 
                 FROM pro_requests pr 
                 JOIN users u ON pr.user_id = u.telegram_id 
                 WHERE pr.status = 'pending' 
                 ORDER BY pr.requested_at DESC LIMIT 10""")
    requests = c.fetchall()
    conn.close()
    
    if not requests:
        await callback.message.edit_text(
            "⭐ No pending Pro requests.",
            reply_markup=get_admin_keyboard()
        )
        return
    
    text = "⭐ Pending Pro Requests:\n\n"
    kb_buttons = []
    
    for req in requests:
        req_id, name, user_id, req_at = req
        text += f"• {name} (@{user_id})\n  Requested: {req_at}\n\n"
        kb_buttons.append([
            InlineKeyboardButton(text=f"✅ Approve {name}", callback_data=f"approve_{req_id}"),
            InlineKeyboardButton(text=f"❌ Reject {name}", callback_data=f"reject_{req_id}")
        ])
    
    kb_buttons.append([InlineKeyboardButton(text="« Back", callback_data="admin_back")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    
    await callback.message.edit_text(text, reply_markup=kb)

@dp.callback_query(F.data.startswith("approve_"))
async def approve_request(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Access denied", show_alert=True)
        return
    
    req_id = int(callback.data.split("_")[1])
    
    conn = sqlite3.connect('twa_games.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM pro_requests WHERE id = ?", (req_id,))
    result = c.fetchone()
    
    if result:
        user_id = result[0]
        c.execute("UPDATE users SET is_pro = 1 WHERE telegram_id = ?", (user_id,))
        c.execute("UPDATE pro_requests SET status = 'approved', approved_at = ? WHERE id = ?",
                  (datetime.now(), req_id))
        conn.commit()
        
        # Notify user
        try:
            await bot.send_message(user_id, "🎉 Your Pro access has been approved!")
        except:
            pass
    
    conn.close()
    await callback.answer("✅ Approved!")
    await admin_requests(callback)

@dp.callback_query(F.data.startswith("reject_"))
async def reject_request(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Access denied", show_alert=True)
        return
    
    req_id = int(callback.data.split("_")[1])
    
    conn = sqlite3.connect('twa_games.db')
    c = conn.cursor()
    c.execute("UPDATE pro_requests SET status = 'rejected' WHERE id = ?", (req_id,))
    conn.commit()
    conn.close()
    
    await callback.answer("❌ Rejected")
    await admin_requests(callback)

@dp.callback_query(F.data == "admin_back")
async def admin_back(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🔐 Admin Panel\n\nSelect an option:",
        reply_markup=get_admin_keyboard()
    )

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())