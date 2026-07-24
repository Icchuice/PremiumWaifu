import os, sqlite3, types
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters

# PYTHON 3.13 FIX
try: import imghdr
except ModuleNotFoundError: imghdr = types.ModuleType('imghdr'); imghdr.what = lambda f,h=None: None

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
GROUP_LINK = "https://t.me/Main_Clutch"
OWNER_LINK = "https://t.me/OwnerSween"
DB_FILE = "database.db"

MSG_COUNT = {}

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, cash INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS waifus (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, anime TEXT, rarity INTEGER, img_url TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_waifus (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, waifu_id INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS shop (id INTEGER PRIMARY KEY, waifu_id INTEGER, price INTEGER, qty INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS codes (code TEXT PRIMARY KEY, amount INTEGER, used_by TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS config (id INTEGER PRIMARY KEY, qr_file_id TEXT, caption TEXT, photo_file_id TEXT, video_file_id TEXT, spawn_time INTEGER)''')
    c.execute("INSERT OR IGNORE INTO config (id, caption, spawn_time) VALUES (1, 'Welcome to Waifu Bot!\nUse /help to see commands', 15)")
    conn.commit(); conn.close()

def get_rarity_name(r):
    return {1:"🌟 God",2:"✨ Mythic",3:"🔮 Legendary",4:"💎 Epic",5:"🏆 Rare",6:"🎯 Uncommon",7:"📦 Common",8:"📦 Common",9:"📦 Common",10:"📦 Common",11:"📦 Common",12:"📦 Common"}.get(r, "📦 Common")

def get_cash(user_id):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor(); c.execute("SELECT cash FROM users WHERE user_id=?", (user_id,)); r = c.fetchone(); conn.close()
    return r[0] if r else 0

def add_cash(user_id, amount):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor(); c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,)); c.execute("UPDATE users SET cash=cash+? WHERE user_id=?", (amount, user_id)); conn.commit(); conn.close()

# SPAWN
def spawn_waifu(update, context):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor(); c.execute("SELECT * FROM waifus ORDER BY RANDOM() LIMIT 1"); waifu = c.fetchone(); conn.close()
    if not waifu: return
    waifu_id, name, anime, rarity, img_url = waifu
    caption = f"✨ A wild waifu appeared! ✨\n\n**ID:** `{waifu_id}`\n**Name:** {name}\n**Anime:** {anime}\n**Rarity:** {get_rarity_name(rarity)}\n\nType `/clutch {name}` to claim her!"
    context.bot.send_photo(chat_id=update.effective_chat.id, photo=img_url, caption=caption, parse_mode='Markdown')

def handle_message(update: Update, context: CallbackContext):
    if update.effective_chat.type not in ["group", "supergroup"]: return
    chat_id = update.effective_chat.id
    if chat_id not in MSG_COUNT: MSG_COUNT[chat_id] = 0
    MSG_COUNT[chat_id] += 1

    conn = sqlite3.connect(DB_FILE); c = conn.cursor(); c.execute("SELECT spawn_time FROM config WHERE id=1"); res = c.fetchone(); spawn_time = res[0] if res else 15; conn.close()

    if MSG_COUNT[chat_id] >= spawn_time:
        MSG_COUNT[chat_id] = 0
        spawn_waifu(update, context)

# USER
def start(update: Update, context: CallbackContext):
    keyboard = [[InlineKeyboardButton("📢 Group", url=GROUP_LINK), InlineKeyboardButton("👑 Owner", url=OWNER_LINK)]]
    conn = sqlite3.connect(DB_FILE); c = conn.cursor(); c.execute("SELECT caption, photo_file_id, video_file_id FROM config WHERE id=1"); res = c.fetchone(); conn.close()

    caption = res[0] if res and res[0] else "Welcome to Waifu Bot!"
    photo = res[1] if res else None
    video = res[2] if res else None

    if video:
        update.message.reply_video(video=video, caption=caption, reply_markup=InlineKeyboardMarkup(keyboard))
    elif photo:
        update.message.reply_photo(photo=photo, caption=caption, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        update.message.reply_text(caption, reply_markup=InlineKeyboardMarkup(keyboard))

def help_cmd(update: Update, context: CallbackContext):
    text = """**Available Commands:**
`/gallery` - View your harem
`/clutch <name>` - Claim spawned waifu
`/search <name>` - Search waifu by name
`/check <id>` - Check waifu by ID
`/cash` - Check balance"""
    update.message.reply_text(text, parse_mode='Markdown')

def gallery(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    conn = sqlite3.connect(DB_FILE); c = conn.cursor(); c.execute("SELECT w.id, w.name FROM user_waifus uw JOIN waifus w ON uw.waifu_id=w.id WHERE uw.user_id=?", (user_id,)); res = c.fetchall(); conn.close()
    if not res: update.message.reply_text("Your harem is empty."); return
    text = "**Your Harem:**\n" + "\n".join([f"ID: `{r[0]}` | {r[1]}" for r in res])
    update.message.reply_text(text, parse_mode='Markdown')

def clutch(update: Update, context: CallbackContext):
    if not context.args: return
    name = " ".join(context.args)
    user_id = update.effective_user.id
    conn = sqlite3.connect(DB_FILE); c = conn.cursor(); c.execute("SELECT * FROM waifus WHERE name LIKE?", (f"%{name}%",)); waifu = c.fetchone()
    if not waifu: update.message.reply_text("Waifu not found."); conn.close(); return
    waifu_id, w_name, _, rarity, _ = waifu
    cost = 49 if rarity <= 4 else 0
    if get_cash(user_id) < cost: update.message.reply_text(f"You need {cost} cash."); conn.close(); return
    add_cash(user_id, -cost)
    c.execute("INSERT INTO user_waifus (user_id, waifu_id) VALUES (?,?)", (user_id, waifu_id))
    conn.commit(); conn.close()
    update.message.reply_text(f"🎉 You claimed {w_name}!")

def cash(update: Update, context: CallbackContext):
    update.message.reply_text(f"Your balance: {get_cash(update.effective_user.id)} Cash")

def search(update: Update, context: CallbackContext):
    if not context.args: update.message.reply_text("Use: /search <name>"); return
    name = "%" + " ".join(context.args) + "%"
    conn = sqlite3.connect(DB_FILE); c = conn.cursor(); c.execute("SELECT id, name, anime, rarity FROM waifus WHERE name LIKE? LIMIT 10", (name,)); res = c.fetchall(); conn.close()
    if not res: update.message.reply_text("No waifu found"); return
    text = "**Search Results:**\n\n" + "\n".join([f"**ID:** `{r[0]}` | **{r[1]}** | {r[2]} | {get_rarity_name(r[3])}" for r in res])
    update.message.reply_text(text, parse_mode='Markdown')

def check(update: Update, context: CallbackContext):
    if not context.args: update.message.reply_text("Use: /check <waifu_id>"); return
    try: waifu_id = int(context.args[0])
    except: update.message.reply_text("ID must be a number"); return
    conn = sqlite3.connect(DB_FILE); c = conn.cursor(); c.execute("SELECT * FROM waifus WHERE id=?", (waifu_id,)); waifu = c.fetchone(); conn.close()
    if not waifu: update.message.reply_text(f"No waifu found with ID: {waifu_id}"); return
    _, name, anime, rarity, img_url = waifu
    caption = f"**WAIFU INFO**\n\n**ID:** `{waifu_id}`\n**Name:** {name}\n**Anime:** {anime}\n**Rarity:** {get_rarity_name(rarity)}"
    context.bot.send_photo(chat_id=update.effective_chat.id, photo=img_url, caption=caption, parse_mode='Markdown')

# ADMIN
def upload(update: Update, context: CallbackContext):
    if update.effective_user.id!= ADMIN_ID: return
    if len(context.args) < 3: update.message.reply_text("Use: /upload <name> <anime> <rarity>"); return
    name, anime, rarity = context.args[0], context.args[1], context.args[2]
    conn = sqlite3.connect(DB_FILE); c = conn.cursor(); c.execute("INSERT INTO waifus (name, anime, rarity, img_url) VALUES (?,?,?,?)", (name, anime, rarity, "https://via.placeholder.com/500")); conn.commit(); conn.close()
    update.message.reply_text(f"Added {name}")

def stime(update: Update, context: CallbackContext):
    if update.effective_user.id!= ADMIN_ID or not context.args: return
    t = int(context.args[0])
    conn = sqlite3.connect(DB_FILE); c = conn.cursor(); c.execute("UPDATE config SET spawn_time=? WHERE id=1", (t,)); conn.commit(); conn.close()
    update.message.reply_text(f"Spawn time set to {t} messages")

def setvid(update: Update, context: CallbackContext):
    if update.effective_user.id!= ADMIN_ID: return
    if not update.message.reply_to_message or not update.message.reply_to_message.video:
        update.message.reply_text("Reply to a video with /setvid")
        return
    file_id = update.message.reply_to_message.video.file_id
    conn = sqlite3.connect(DB_FILE); c = conn.cursor(); c.execute("UPDATE config SET video_file_id=?, photo_file_id=NULL WHERE id=1", (file_id,)); conn.commit(); conn.close()
    update.message.reply_text("✅ Welcome video set!")

def setphoto(update: Update, context: CallbackContext):
    if update.effective_user.id!= ADMIN_ID: return
    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        update.message.reply_text("Reply to a photo with /setphoto")
        return
    file_id = update.message.reply_to_message.photo[-1].file_id
    conn = sqlite3.connect(DB_FILE); c = conn.cursor(); c.execute("UPDATE config SET photo_file_id=?, video_file_id=NULL WHERE id=1", (file_id,)); conn.commit(); conn.close()
    update.message.reply_text("✅ Welcome photo set!")

def setcaption(update: Update, context: CallbackContext):
    if update.effective_user.id!= ADMIN_ID: return
    if not update.message.reply_to_message or not update.message.reply_to_message.text:
        update.message.reply_text("Reply to text with /setcaption")
        return
    caption = update.message.reply_to_message.text
    conn = sqlite3.connect(DB_FILE); c = conn.cursor(); c.execute("UPDATE config SET caption=? WHERE id=1", (caption,)); conn.commit(); conn.close()
    update.message.reply_text("✅ Welcome caption updated!")

def refresh(update: Update, context: CallbackContext):
    if update.effective_user.id!= ADMIN_ID: return
    conn = sqlite3.connect(DB_FILE); c = conn.cursor(); c.execute("UPDATE config SET photo_file_id=NULL, video_file_id=NULL WHERE id=1"); conn.commit(); conn.close()
    update.message.reply_text("✅ Welcome media deleted")

def main():
    init_db()
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_cmd))
    dp.add_handler(CommandHandler("gallery", gallery))
    dp.add_handler(CommandHandler("clutch", clutch))
    dp.add_handler(CommandHandler("cash", cash))
    dp.add_handler(CommandHandler("search", search))
    dp.add_handler(CommandHandler("check", check))
    dp.add_handler(CommandHandler("upload", upload))
    dp.add_handler(CommandHandler("stime", stime))
    dp.add_handler(CommandHandler("setvid", setvid))
    dp.add_handler(CommandHandler("setphoto", setphoto))
    dp.add_handler(CommandHandler("setcaption", setcaption))
    dp.add_handler(CommandHandler("refresh", refresh))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
