import sqlite3
import random
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import Updater, CommandHandler, CallbackContext, CallbackQueryHandler, MessageHandler, Filters

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
GROUP_URL = "https://t.me/Main_Clutch"
CHANNEL_URL = "https://t.me/Clutch_Update"
DB_FILE = "clutch_waifu.db"

RARITY_MAP = {
    0: "🍷 Luxurious", 1: "🌟 God Summon", 2: "🎀 Only Shop", 3: "🔮 Limited", 4: "💎 Premium",
    5: "🎐 Special", 6: "💮 Exclusive", 7: "🪽 Celestial", 8: "🟡 Legendary", 9: "🟠 Rare",
    10: "🔵 Medium", 11: "🟢 Common", 12: "💀 Battle"
}
DROP_RARITY = [4,5,6,7,8,9,10,11,12]

active_battles = {}
message_count = {}
last_spawn = {} # chat_id: waifu_dict

def db(q,p=()):
    conn=sqlite3.connect(DB_FILE);c=conn.cursor();c.execute(q,p);conn.commit();conn.close()
def dbf(q,p=()):
    conn=sqlite3.connect(DB_FILE);c=conn.cursor();c.execute(q,p);r=c.fetchall();conn.close();return r

def init_db():
    db("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0)")
    db("CREATE TABLE IF NOT EXISTS waifus (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, anime TEXT, rarity INTEGER, price REAL DEFAULT 0, power INTEGER DEFAULT 0, file_id TEXT)")
    db("CREATE TABLE IF NOT EXISTS harem (user_id INTEGER, waifu_id INTEGER, PRIMARY KEY(user_id, waifu_id))")
    db("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    db("CREATE TABLE IF NOT EXISTS redeem (code TEXT PRIMARY KEY, amount REAL, max_uses INTEGER, used_by TEXT)") # updated
    db("CREATE TABLE IF NOT EXISTS battles (chat_id INTEGER PRIMARY KEY, p1 INTEGER, p2 INTEGER)")

def get_setting(key, default=""):
    res = dbf("SELECT value FROM settings WHERE key=?",(key,))
    return res[0][0] if res else default

def set_setting(key, value):
    db("INSERT OR REPLACE INTO settings VALUES (?,?)",(key,value))

def get_balance(uid):
    res = dbf("SELECT balance FROM users WHERE user_id=?",(uid,))
    return res[0][0] if res else 0

def add_balance(uid, amt):
    bal = get_balance(uid) + amt
    db("INSERT OR REPLACE INTO users VALUES (?,?)",(uid,bal))

def add_to_harem(uid, wid):
    db("INSERT OR IGNORE INTO harem VALUES (?,?)",(uid,wid))

def get_waifus():
    return dbf("SELECT * FROM waifus")

# --- USER COMMANDS ---
def start(update: Update, context: CallbackContext):
    caption = get_setting("welcome", "**WELCOME TO CLUTCH WAIFU BOT**\n\nCollect waifus, build your harem, BATTLE!")
    pic = get_setting("welcome_pic")
    keyboard = [[InlineKeyboardButton("Channel", url=CHANNEL_URL), InlineKeyboardButton("Group", url=GROUP_URL)]]
    if pic:
        context.bot.send_photo(update.effective_chat.id, pic, caption=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else:
        update.message.reply_text(caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

def helpcmd(update: Update, context: CallbackContext):
    update.message.reply_text("/clutch name - claim\n/hunt - find\n/harem - collection\n/battle - reply to user\n/redeem code - use code")

def clutch(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if chat_id not in last_spawn:
        update.message.reply_text("No waifu spawned"); return

    waifu = last_spawn[chat_id]
    guess = ' '.join(context.args).lower().strip()
    if not guess: update.message.reply_text("Format: /clutch name"); return

    # FLEXIBLE CLAIM: name ya anime ka koi bhi part
    name = waifu[1].lower()
    anime = waifu[2].lower()
    if guess in name or guess in anime or name in guess or anime in guess:
        del last_spawn[chat_id]
        add_to_harem(user_id, waifu[0])
        caption = f"🎉 **Claimed!**\n\n**{waifu[1]}** from **{waifu[2]}**\n**Rarity:** {RARITY_MAP[waifu[3]]}"
        context.bot.send_photo(chat_id, waifu[5], caption=caption, parse_mode='Markdown')
    else:
        update.message.reply_text("Wrong name")

def hunt(update: Update, context: CallbackContext):
    waifus = get_waifus()
    if not waifus: return
    w = random.choice(waifus)
    caption = f"🔍 Found: **{w[1]}** | {w[2]}\n{RARITY_MAP[w[3]]}"
    context.bot.send_photo(update.effective_chat.id, w[5], caption=caption, parse_mode='Markdown')

def harem(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    rows = dbf("SELECT w.id,w.name,w.anime,w.rarity FROM harem h JOIN waifus w ON h.waifu_id=w.id WHERE h.user_id=?",(uid,))
    if not rows: update.message.reply_text("Empty"); return
    txt = "**Your Harem:**\n";
    for r in rows: txt += f"`{r[0]}`. {r[1]} | {r[2]} | {RARITY_MAP[r[3]]}\n"
    update.message.reply_text(txt, parse_mode='Markdown')

def bcards(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    rows = dbf("SELECT w.name,w.anime,w.power FROM harem h JOIN waifus w ON h.waifu_id=w.id WHERE h.user_id=? AND w.rarity=12",(uid,))
    if not rows: update.message.reply_text("No battle cards"); return
    txt = "**Battle Cards:**\n";
    for r in rows: txt += f"- {r[0]} | {r[1]} | Power: {r[2]}\n"
    update.message.reply_text(txt)

def balance(update: Update, context: CallbackContext):
    update.message.reply_text(f"Balance: {get_balance(update.effective_user.id)} coins")

def search(update: Update, context: CallbackContext):
    q = ' '.join(context.args).lower()
    rows = dbf("SELECT * FROM waifus WHERE name LIKE? OR anime LIKE?", (f"%{q}%", f"%{q}%"))
    if not rows: update.message.reply_text("Not found"); return
    w = rows[0]
    context.bot.send_photo(update.effective_chat.id, w[5], caption=f"**{w[1]}** | {w[2]}", parse_mode='Markdown')

def redeem(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    if not context.args: update.message.reply_text("Format: /redeem CODE"); return
    code = context.args[0].upper()
    row = dbf("SELECT * FROM redeem WHERE code=?",(code,))
    if not row: update.message.reply_text("Invalid code"); return
    amount, max_uses, used_by = row[0][1], row[0][2], row[0][3]
    used_list = used_by.split(",") if used_by else []
    if str(uid) in used_list: update.message.reply_text("Already used"); return
    if len(used_list) >= max_uses: update.message.reply_text("Limit over"); return
    add_balance(uid, amount)
    used_list.append(str(uid))
    db("UPDATE redeem SET used_by=? WHERE code=?",(",".join(used_list),code))
    update.message.reply_text(f"✅ {amount} coins added! Left: {max_uses - len(used_list)}")

def battle(update: Update, context: CallbackContext):
    chat = update.effective_chat
    if chat.type not in ['group','supergroup']:
        update.message.reply_text("❌ Battle only in group"); return

    if not update.message.reply_to_message:
        update.message.reply_text("Reply to someone with /battle"); return
    p1 = update.effective_user.id
    p2 = update.message.reply_to_message.from_user.id
    if p1==p2: update.message.reply_text("Can't battle yourself"); return

    p1_cards = dbf("SELECT COUNT(*) FROM harem h JOIN waifus w ON h.waifu_id=w.id WHERE h.user_id=? AND w.rarity=12",(p1,))[0][0]
    p2_cards = dbf("SELECT COUNT(*) FROM harem h JOIN waifus w ON h.waifu_id=w.id WHERE h.user_id=? AND w.rarity=12",(p2,))[0][0]
    if p1_cards==0 or p2_cards==0: update.message.reply_text("Both need battle cards"); return

    db("INSERT OR REPLACE INTO battles VALUES (?,?,?)",(chat.id,p1,p2))
    keyboard = [[InlineKeyboardButton("⚔️ Join Battle", callback_data=f"joinbattle_{chat.id}")]]
    update.message.reply_text(f"⚔️ Battle: {update.effective_user.first_name} vs {update.message.reply_to_message.from_user.first_name}", reply_markup=InlineKeyboardMarkup(keyboard))

def joinbattle(update: Update, context: CallbackContext):
    query = update.callback_query; query.answer()
    chat_id = int(query.data.split("_")[1])
    row = dbf("SELECT * FROM battles WHERE chat_id=?",(chat_id,))
    if not row: query.edit_message_text("Expired"); return
    p1,p2 = row[0][1], row[0][2]
    winner = random.choice([p1,p2])
    add_balance(winner, 100)
    query.edit_message_text(f"🏆 Winner: <a href='tg://user?id={winner}'>Player</a> +100 coins", parse_mode='HTML')
    db("DELETE FROM battles WHERE chat_id=?",(chat_id,))

def message_counter(update: Update, context: CallbackContext):
    chat = update.effective_chat
    if chat.type!= 'group' or update.effective_user.id == ADMIN_ID: return
    stime = int(get_setting("stime","15"))
    message_count[chat.id] = message_count.get(chat.id,0)+1
    if message_count[chat.id] >= stime:
        message_count[chat.id]=0
        waifus = [w for w in get_waifus() if w[3] in DROP_RARITY]
        if not waifus: return
        w = random.choice(waifus)
        last_spawn[chat.id]=w

        rarity = RARITY_MAP[w[3]]
        # NEW CAPTION LOGIC
        if w[4] > 0: # price
            prize_text = f"{rarity} {int(w[4])}₹"
        else:
            prize_text = f"{rarity}"

        caption = f"A New \"{prize_text}\" SealWaifu💫 Appeared...\n\n/Clutch {w[1]} and add in Your Sealwaifu Collection 👾"
        # PHOTO KE SATH SPAWN
        context.bot.send_photo(chat.id, w[5], caption=caption, parse_mode='Markdown')

# --- ADMIN COMMANDS ---
def upload(update: Update, context: CallbackContext):
    if update.effective_user.id!= ADMIN_ID: return
    if len(context.args)<4: update.message.reply_text("Format: /upload name anime rarity price power"); return
    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        update.message.reply_text("Reply to a photo"); return
    name,anime,rarity,price,power = context.args[0],context.args[1],int(context.args[2]),float(context.args[3]),int(context.args[4])
    file_id = update.message.reply_to_message.photo[-1].file_id
    db("INSERT INTO waifus (name,anime,rarity,price,power,file_id) VALUES (?,?,?,?,?,?)",(name,anime,rarity,price,power,file_id))
    update.message.reply_text(f"Uploaded {name}")

def created(update: Update, context: CallbackContext):
    if update.effective_user.id!= ADMIN_ID: return
    if len(context.args)!=3: update.message.reply_text("Format: /created amount code max_uses"); return
    amount,code,max_uses = float(context.args[0]),context.args[1].upper(),int(context.args[2])
    db("INSERT OR REPLACE INTO redeem VALUES (?,?,?,?)",(code,amount,max_uses,""))
    update.message.reply_text(f"✅ Code: {code}\nAmount: {amount}\nMax Uses: {max_uses}")

def stime(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    chat = update.effective_chat
    is_admin = False
    if chat.type in ['group','supergroup']:
        admins = context.bot.get_chat_administrators(chat.id)
        is_admin = any(a.user.id == uid for a in admins)
    if uid!= ADMIN_ID and not is_admin:
        update.message.reply_text("No permission"); return
    if context.args: set_setting("stime",context.args[0])
    update.message.reply_text(f"Spawn time: {get_setting('stime','15')} messages")

def broadcast(update: Update, context: CallbackContext):
    if update.effective_user.id!= ADMIN_ID: return
    msg = ' '.join(context.args)
    users = dbf("SELECT user_id FROM users")
    for u in users:
        try: context.bot.send_message(u[0], f"📢 {msg}", parse_mode='Markdown')
        except: pass
    update.message.reply_text("Broadcast done")

def setqr(update: Update, context: CallbackContext):
    if update.effective_user.id!= ADMIN_ID: return
    set_setting("qr",' '.join(context.args)); update.message.reply_text("QR set")

def setpic(update: Update, context: CallbackContext):
    if update.effective_user.id!= ADMIN_ID: return
    if update.message.reply_to_message and update.message.reply_to_message.photo:
        set_setting("welcome_pic", update.message.reply_to_message.photo[-1].file_id)
        update.message.reply_text("Pic set")

def rwaifu(update: Update, context: CallbackContext): pass # placeholder
def setcaption(update: Update, context: CallbackContext): pass # placeholder
def addbal(update: Update, context: CallbackContext): pass # placeholder
def pick(update: Update, context: CallbackContext): pass # placeholder

def main():
    if not TOKEN or not ADMIN_ID:
        print("BOT_TOKEN or ADMIN_ID missing")
        return
    init_db()
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", helpcmd))
    dp.add_handler(CommandHandler("clutch", clutch))
    dp.add_handler(CommandHandler("hunt", hunt))
    dp.add_handler(CommandHandler("harem", harem))
    dp.add_handler(CommandHandler("bcards", bcards))
    dp.add_handler(CommandHandler("search", search))
    dp.add_handler(CommandHandler("balance", balance))
    dp.add_handler(CommandHandler("redeem", redeem))
    dp.add_handler(CommandHandler("battle", battle))
    dp.add_handler(CommandHandler("upload", upload))
    dp.add_handler(CommandHandler("created", created))
    dp.add_handler(CommandHandler("stime", stime))
    dp.add_handler(CommandHandler("broadcast", broadcast))
    dp.add_handler(CommandHandler("setqr", setqr))
    dp.add_handler(CommandHandler("setpic", setpic))
    dp.add_handler(MessageHandler(Filters.all, message_counter))
    dp.add_handler(CallbackQueryHandler(joinbattle, pattern="joinbattle"))

    print("CLUTCH WAIFU BOT RUNNING")
    updater.start_polling()
    updater.idle()

if __name__=='__main__':
    main()
