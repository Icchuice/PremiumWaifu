import os, sqlite3, json, time, random
import imghdr # FIX FOR PYTHON 3.13
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext, CallbackQueryHandler, MessageHandler, Filters

# Python 3.13 fix - imghdr hat gaya hai
if not hasattr(imghdr, 'what'):
    def what(file, h=None):
        return None
    imghdr.what = what

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
GROUP_LINK = "https://t.me/Main_Clutch"
OWNER_LINK = "https://t.me/OwnerSween"

conn = sqlite3.connect('premium_ib.db', check_same_thread=False)
c = conn.cursor()

# Tables
c.execute('''CREATE TABLE IF NOT EXISTS users (telegram_id TEXT PRIMARY KEY, cash INTEGER DEFAULT 0, harem TEXT DEFAULT '[]')''')
c.execute('''CREATE TABLE IF NOT EXISTS waifus (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, anime TEXT, rarity INTEGER, img TEXT, price INTEGER DEFAULT 0, qty INTEGER DEFAULT 0)''')
c.execute('''CREATE TABLE IF NOT EXISTS codes (code TEXT PRIMARY KEY, amount INTEGER, used INTEGER DEFAULT 0)''')
c.execute('''CREATE TABLE IF NOT EXISTS groups (chat_id TEXT PRIMARY KEY, msg_count INTEGER DEFAULT 0, spawn_time INTEGER DEFAULT 15)''')
c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
conn.commit()

RARITY = {
1:"🌟 God Summon",2:"🎀 Only Shop",3:"🔮 Limited",4:"💎 Premium",5:"🎐 Special",
6:"💮 Exclusive",7:"🪽 Celestial",8:"🟡 Legendary",9:"🟠 Rare",10:"🔵 Medium",12:"🟢 Common"
}
DROP_WEIGHTS = {1:1, 3:3, 4:5, 5:8, 6:10, 7:15, 8:20, 9:30, 10:50, 12:100}

def get_setting(key, default=""):
    val = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return val[0] if val else default

def set_setting(key, value):
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, value))
    conn.commit()

# /start
def start(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    c.execute("INSERT OR IGNORE INTO users (telegram_id) VALUES (?)", (user_id,))
    conn.commit()

    caption = get_setting("welcome_caption", "Welcome to **Premium IB** ❤️\n\nUse /help to see all commands")
    photo = get_setting("welcome_photo", "")
    keyboard = [[InlineKeyboardButton("GROUP", url=GROUP_LINK), InlineKeyboardButton("OWNER", url=OWNER_LINK)]]

    if photo and os.path.exists(photo):
        update.message.reply_photo(photo=open(photo,'rb'), caption=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else:
        update.message.reply_text(caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

def help(update: Update, context: CallbackContext):
    text = """**PREMIUM IB COMMANDS**

**USER**
/gallery - View your harem
/clutch <name> - Claim a waifu
/shop - Buy waifus from shop
/redeem <code> - Use redeem code
/phone - Open waifu phone
/cash - Check balance
/addbal - Add balance via QR
/verification <amount> <utr> - Verify payment

**ADMIN**
/upload <name> <anime> <rarity> - Add waifu
/rup <id> - Remove waifu
/adds <id> <price> <qty> - Add to shop
/rsp <id> - Remove from shop
/createdcode <amount> <code> - Create code
/broadcast - Reply to msg and broadcast
/setqr - Reply to QR and set
/stime <number> - Set spawn time
/setcaption - Reply to text to set welcome
/setphoto - Reply to photo to set welcome
/refresh - Delete old welcome photo"""
    update.message.reply_text(text, parse_mode='Markdown')

def gallery(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    harem = json.loads(c.execute("SELECT harem FROM users WHERE telegram_id=?", (user_id,)).fetchone()[0])
    if not harem: return update.message.reply_text("Your harem is empty. Catch spawned waifus!")
    text = "🎀 **YOUR HAREM** 🎀\n\n"
    for wid in harem:
        w = c.execute("SELECT name,anime,rarity FROM waifus WHERE id=?", (wid,)).fetchone()
        if w: text += f"ID:`{wid}` | {w[0]} | {w[1]} | {RARITY.get(w[2])}\n"
    update.message.reply_text(text, parse_mode='Markdown')

def clutch(update: Update, context: CallbackContext):
    if not context.args: return update.message.reply_text("Usage: /clutch <waifu_name>")
    name = "_".join(context.args)
    w = c.execute("SELECT id, rarity FROM waifus WHERE name=?", (name,)).fetchone()
    if not w: return update.message.reply_text("Waifu not found or not spawned.")
    user_id = str(update.effective_user.id)

    if w[1] == 4: # Premium
        user_cash = c.execute("SELECT cash FROM users WHERE telegram_id=?", (user_id,)).fetchone()[0]
        if user_cash < 49: return update.message.reply_text(f"You have {user_cash} balance to Clutch This waifu\nUse /addbal")
        c.execute("UPDATE users SET cash=cash-49 WHERE telegram_id=?", (user_id,))

    harem = json.loads(c.execute("SELECT harem FROM users WHERE telegram_id=?", (user_id,)).fetchone()[0])
    if w[0] in harem: return update.message.reply_text("Already in your harem.")
    harem.append(w[0])
    c.execute("UPDATE users SET harem=? WHERE telegram_id=?", (json.dumps(harem), user_id))
    conn.commit()
    msg = f"✅ You successfully claimed **{name.replace('_',' ')}**! 💕"
    if w[1] == 4: msg += "\n-49 Cash deducted"
    update.message.reply_text(msg, parse_mode='Markdown')

def shop(update: Update, context: CallbackContext, page=0, edit=False):
    data = c.execute("SELECT id,name,anime,rarity,price,qty FROM waifus WHERE qty>0").fetchall()
    if not data:
        if edit: update.callback_query.edit_message_text("Shop is empty.")
        else: update.message.reply_text("Shop is empty.")
        return
    items_per_page = 5
    total_pages = (len(data) - 1) // items_per_page + 1
    page = max(0, min(page, total_pages-1))
    page_data = data[page*items_per_page:(page+1)*items_per_page]

    text = f"🏪 **PREMIUM SHOP** 🏪\nPage {page+1}/{total_pages}\n*<BUYING>*\n\n"
    keyboard = []
    for w in page_data:
        text += f"ID:`{w[0]}` | {w[1]} | {RARITY.get(w[3])}\n💰 Price: {w[4]} | Stock: {w[5]}\n\n"
        keyboard.append([InlineKeyboardButton(f"Buy {w[1]} - {w[4]} Cash", callback_data=f"buy_{w[0]}")])

    nav = []
    nav.append(InlineKeyboardButton("⬅️", callback_data=f"shop_page_{page-1}" if page>0 else "null"))
    nav.append(InlineKeyboardButton("BUYING", callback_data="buying"))
    nav.append(InlineKeyboardButton("➡️", callback_data=f"shop_page_{page+1}" if page<total_pages-1 else "null"))
    keyboard.append(nav)

    if edit: update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else: update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

def redeem(update: Update, context: CallbackContext):
    if not context.args: return update.message.reply_text("Usage: /redeem CODE001")
    code = context.args[0]
    data = c.execute("SELECT amount,used FROM codes WHERE code=?", (code,)).fetchone()
    if not data or data[1]==1: return update.message.reply_text("Invalid or already used code.")
    user_id = str(update.effective_user.id)
    c.execute("UPDATE users SET cash=cash+? WHERE telegram_id=?", (data[0], user_id))
    c.execute("UPDATE codes SET used=1 WHERE code=?", (code,))
    conn.commit()
    update.message.reply_text(f"✅ Redeemed! +{data[0]} Cash added.")

def phone(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    harem = json.loads(c.execute("SELECT harem FROM users WHERE telegram_id=?", (user_id,)).fetchone()[0])
    if not harem: return update.message.reply_text("Claim a waifu first with /clutch")
    wid = harem[0]
    w = c.execute("SELECT name,img FROM waifus WHERE id=?", (wid,)).fetchone()
    keyboard = [[InlineKeyboardButton("📸 Instagram", callback_data='ig'), InlineKeyboardButton("📘 Facebook", callback_data='fb')], [InlineKeyboardButton("💬 WhatsApp", callback_data='wa'), InlineKeyboardButton("🖼️ Photos", callback_data='photos')], [InlineKeyboardButton("🌆 Set Wallpaper", callback_data=f"wall_{wid}"), InlineKeyboardButton("📞 Call", callback_data='call')], [InlineKeyboardButton("🔋 Battery 100%", callback_data='battery'), InlineKeyboardButton("🔴 Power Off", callback_data='off')]]
    caption = f"📱 **{w[0]}'s Phone**\nTime: {time.strftime('%H:%M')}\nSelect an app:"
    if w[1] and os.path.exists(w[1]): update.message.reply_photo(photo=open(w[1],'rb'), caption=caption, reply_markup=InlineKeyboardMarkup(keyboard))
    else: update.message.reply_text(caption, reply_markup=InlineKeyboardMarkup(keyboard))

def cash(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    cash = c.execute("SELECT cash FROM users WHERE telegram_id=?", (user_id,)).fetchone()[0]
    update.message.reply_text(f"💰 **Your Balance: {cash} Cash**\n\nAdd cash: /addbal", parse_mode='Markdown')

def addbal(update: Update, context: CallbackContext):
    try: update.message.reply_photo(photo=open('qr.jpg','rb'), caption="Scan Here for adding Balance\nAfter payment use /verification <amount> <UTR_ID>")
    except: update.message.reply_text("❌ QR not set. Admin use /setqr to upload QR first")

def verification(update: Update, context: CallbackContext):
    if len(context.args)<2: return update.message.reply_text("Enter Amounts UTR ID to verify your payment\nUsage: /verification <amount> <UTR_ID>")
    amount, utr = context.args[0], context.args[1]
    context.bot.send_message(ADMIN_ID, f"⚠️ **New Payment Request**\nUser: {update.effective_user.id}\nAmount: {amount}\nUTR: {utr}")
    update.message.reply_text("Payment request sent to admin. Wait for approval.")

# WELCOME SETTINGS
def setcaption(update: Update, context: CallbackContext):
    if update.effective_user.id!=ADMIN_ID: return
    if not update.message.reply_to_message or not update.message.reply_to_message.text: return update.message.reply_text("Reply to a text message with /setcaption")
    set_setting("welcome_caption", update.message.reply_to_message.text)
    update.message.reply_text("✅ Welcome caption saved!")

def setphoto(update: Update, context: CallbackContext):
    if update.effective_user.id!=ADMIN_ID: return
    if not update.message.reply_to_message or not update.message.reply_to_message.photo: return update.message.reply_text("Reply to a photo with /setphoto")
    file = update.message.reply_to_message.photo[-1].get_file()
    file.download('welcome.jpg')
    set_setting("welcome_photo", 'welcome.jpg')
    update.message.reply_text("✅ Welcome photo saved!")

def refresh(update: Update, context: CallbackContext):
    if update.effective_user.id!=ADMIN_ID: return
    if os.path.exists('welcome.jpg'): os.remove('welcome.jpg')
    set_setting("welcome_photo", "")
    update.message.reply_text("✅ Old welcome photo deleted.")

def stime(update: Update, context: CallbackContext):
    if update.effective_chat.type == 'private': return update.message.reply_text("Use this in groups only")
    if not context.args: return update.message.reply_text("Usage: /stime 15")
    c.execute("INSERT OR REPLACE INTO groups (chat_id, spawn_time) VALUES (?,?)", (str(update.effective_chat.id), int(context.args[0])))
    conn.commit()
    update.message.reply_text(f"✅ Spawn time set to every **{context.args[0]} messages**")

def handle_message(update: Update, context: CallbackContext):
    if not update.message or update.message.from_user.is_bot: return
    chat_id = str(update.effective_chat.id)
    c.execute("INSERT OR IGNORE INTO groups (chat_id) VALUES (?)", (chat_id,))
    c.execute("UPDATE groups SET msg_count = msg_count + 1 WHERE chat_id=?", (chat_id,))
    data = c.execute("SELECT msg_count, spawn_time FROM groups WHERE chat_id=?", (chat_id,)).fetchone()
    if data[0] >= data[1]:
        spawn_waifu(update, context, chat_id)
        c.execute("UPDATE groups SET msg_count = 0 WHERE chat_id=?", (chat_id,))
        conn.commit()

def spawn_waifu(update: Update, context: CallbackContext, chat_id):
    waifus = c.execute("SELECT id, name, anime, rarity FROM waifus WHERE rarity!= 2").fetchall()
    if not waifus: return
    pool = []
    for w in waifus:
        weight = DROP_WEIGHTS.get(w[3], 5)
        if w[3] == 1: weight = 1
        pool.extend([w] * weight)
    waifu = random.choice(pool)
    if waifu[3] == 1 and random.randint(1, 100000)!= 1: return

    rarity_name = RARITY.get(waifu[3])
    rarity_emoji = rarity_name.split(" ")[0]
    if waifu[3] == 4:
        caption = f"*A New 49₹ {rarity_name.split(' ',1)[1]} SealWaifu💫 Appeared...*\n\n/Clutch {waifu[1]} and add in Your Sealwaifu Collection 👾"
    else:
        caption = f"*A New {rarity_emoji} {rarity_name.split(' ',1)[1]} SealWaifu💫 Appeared...*\n\n/Clutch {waifu[1]} and add in Your Sealwaifu Collection 👾"

    keyboard = [[InlineKeyboardButton("Clutch", callback_data=f"clutch_btn_{waifu[0]}")]]
    context.bot.send_message(chat_id, caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

def setqr(update: Update, context: CallbackContext):
    if update.effective_user.id!= ADMIN_ID: return
    if not update.message.reply_to_message or not update.message.reply_to_message.photo: return update.message.reply_text("Usage: Reply to QR image with /setqr")
    update.message.reply_to_message.photo[-1].get_file().download('qr.jpg')
    update.message.reply_text("✅ QR Image Set Successfully!")

# ADMIN
def upload(update: Update, context: CallbackContext):
    if update.effective_user.id!=ADMIN_ID: return
    name, anime, rarity = context.args[0], context.args[1], int(context.args[2])
    c.execute("INSERT INTO waifus (name, anime, rarity, img) VALUES (?,?,?,?)", (name, anime, rarity, ""))
    conn.commit()
    update.message.reply_text(f"✅ Waifu Uploaded. ID: {c.lastrowid}")

def rup(update: Update, context: CallbackContext):
    if update.effective_user.id!=ADMIN_ID: return
    c.execute("DELETE FROM waifus WHERE id=?", (context.args[0],))
    conn.commit()
    update.message.reply_text(f"✅ Waifu ID {context.args[0]} removed.")

def createdcode(update: Update, context: CallbackContext):
    if update.effective_user.id!=ADMIN_ID: return
    c.execute("INSERT INTO codes (code, amount) VALUES (?,?)", (context.args[1], context.args[0]))
    conn.commit()
    update.message.reply_text(f"✅ Code Created: {context.args[1]} = {context.args[0]} Cash")

def adds(update: Update, context: CallbackContext):
    if update.effective_user.id!=ADMIN_ID: return
    c.execute("UPDATE waifus SET price=?, qty=? WHERE id=?", (context.args[1], context.args[2], context.args[0]))
    conn.commit()
    update.message.reply_text(f"✅ Waifu ID {context.args[0]} added to shop.")

def rsp(update: Update, context: CallbackContext):
    if update.effective_user.id!=ADMIN_ID: return
    c.execute("UPDATE waifus SET qty=0 WHERE id=?", (context.args[0],))
    conn.commit()
    update.message.reply_text(f"✅ Waifu ID {context.args[0]} removed from shop.")

def broadcast(update: Update, context: CallbackContext):
    if update.effective_user.id!=ADMIN_ID: return
    if not update.message.reply_to_message: return update.message.reply_text("Reply to a message and use /broadcast")
    users = c.execute("SELECT telegram_id FROM users").fetchall()
    count=0
    for u in users:
        try: context.bot.copy_message(chat_id=u[0], from_chat_id=update.effective_chat.id, message_id=update.message.reply_to_message.message_id); count+=1
        except: pass
    update.message.reply_text(f"✅ Broadcast sent to {count} users.")

def button(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    data = query.data

    if data.startswith('clutch_btn_'):
        wid = int(data.split('_')[2])
        user_id = str(query.from_user.id)
        waifu = c.execute("SELECT name, rarity FROM waifus WHERE id=?", (wid,)).fetchone()
        if waifu[1] == 4:
            user_cash = c.execute("SELECT cash FROM users WHERE telegram_id=?", (user_id,)).fetchone()[0]
            if user_cash < 49: return query.edit_message_text(f"You have {user_cash} balance to Clutch This waifu\nUse /addbal")
            c.execute("UPDATE users SET cash=cash-49 WHERE telegram_id=?", (user_id,))
        harem = json.loads(c.execute("SELECT harem FROM users WHERE telegram_id=?", (user_id,)).fetchone()[0])
        if wid in harem: return query.edit_message_text("Already in your harem.")
        harem.append(wid)
        c.execute("UPDATE users SET harem=? WHERE telegram_id=?", (json.dumps(harem), user_id))
        conn.commit()
        msg = f"✅ You successfully claimed **{waifu[0]}**! 💕"
        if waifu[1] == 4: msg += "\n-49 Cash deducted"
        query.edit_message_text(msg, parse_mode='Markdown')

    elif data.startswith('shop_page_'):
        shop(query, context, int(data.split('_')[2]), edit=True)
    elif data == 'buying': query.answer("You are in Shop 🛒")
    elif data == 'null': query.answer(" ")
    elif data.startswith('buy_'):
        wid = int(data.split('_')[1])
        user_id = str(query.from_user.id)
        w = c.execute("SELECT price,qty FROM waifus WHERE id=?", (wid,)).fetchone()
        if not w or w[1] <= 0: return query.edit_message_text("❌ Out of stock")
        user_cash = c.execute("SELECT cash FROM users WHERE telegram_id=?", (user_id,)).fetchone()[0]
        if user_cash < w[0]: return query.answer("❌ Not enough cash", show_alert=True)
        harem = json.loads(c.execute("SELECT harem FROM users WHERE telegram_id=?", (user_id,)).fetchone()[0])
        harem.append(wid)
        c.execute("UPDATE users SET cash=cash-?, harem=? WHERE telegram_id=?", (w[0], json.dumps(harem), user_id))
        c.execute("UPDATE waifus SET qty=qty-1 WHERE id=?", (wid,))
        conn.commit()
        query.answer(f"✅ Bought! -{w[0]} Cash", show_alert=True)
        shop(query, context, 0, edit=True)

def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help))
    dp.add_handler(CommandHandler("gallery", gallery))
    dp.add_handler(CommandHandler("harem", gallery))
    dp.add_handler(CommandHandler("clutch", clutch))
    dp.add_handler(CommandHandler("shop", shop))
    dp.add_handler(CommandHandler("redeem", redeem))
    dp.add_handler(CommandHandler("phone", phone))
    dp.add_handler(CommandHandler("cash", cash))
    dp.add_handler(CommandHandler("addbal", addbal))
    dp.add_handler(CommandHandler("verification", verification))
    dp.add_handler(CommandHandler("setqr", setqr))
    dp.add_handler(CommandHandler("stime", stime))
    dp.add_handler(CommandHandler("setcaption", setcaption))
    dp.add_handler(CommandHandler("setphoto", setphoto))
    dp.add_handler(CommandHandler("refresh", refresh))
    dp.add_handler(CommandHandler("upload", upload))
    dp.add_handler(CommandHandler("rup", rup))
    dp.add_handler(CommandHandler("createdcode", createdcode))
    dp.add_handler(CommandHandler("adds", adds))
    dp.add_handler(CommandHandler("rsp", rsp))
    dp.add_handler(CommandHandler("broadcast", broadcast))
    dp.add_handler(CallbackQueryHandler(button))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    print("✅ PREMIUM IB BOT LIVE - PYTHON 3.13 FIXED")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
