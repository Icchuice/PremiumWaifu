import asyncio
import sqlite3
import random
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import Application, CommandHandler, CallbackContext, CallbackQueryHandler, MessageHandler, filters

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

def db(q,p=()):
    conn=sqlite3.connect(DB_FILE);c=conn.cursor();c.execute(q,p);conn.commit();conn.close()
def dbf(q,p=()):
    conn=sqlite3.connect(DB_FILE);c=conn.cursor();c.execute(q,p);r=c.fetchall();conn.close();return r

def init_db():
    db("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0)")
    db("CREATE TABLE IF NOT EXISTS waifus (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, anime TEXT, rarity INTEGER, price REAL DEFAULT 0, power INTEGER DEFAULT 0, file_id TEXT)")
    db("CREATE TABLE IF NOT EXISTS harem (user_id INTEGER, waifu_id INTEGER, PRIMARY KEY(user_id, waifu_id))")
    db("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    db("CREATE TABLE IF NOT EXISTS redeem (code TEXT PRIMARY KEY, amount REAL, used INTEGER DEFAULT 0)")

def get_setting(key, default=""):
    res = dbf("SELECT value FROM settings WHERE key=?",(key,))
    return res[0][0] if res else default

# ===== USER COMMANDS =====
async def start(update: Update, context: CallbackContext):
    caption = get_setting("welcome", "**WELCOME TO CLUTCH WAIFU BOT**\n\nCollect waifus, build your harem, BATTLE!")
    pic = get_setting("welcome_pic")
    keyboard = [[InlineKeyboardButton("Channel", url=CHANNEL_URL), InlineKeyboardButton("Group", url=GROUP_URL)]]
    if pic:
        await update.message.reply_photo(pic, caption=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else:
        await update.message.reply_text(caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def helpcmd(update: Update, context: CallbackContext): # NEW
    text = """**AVAILABLE COMMANDS**

**User Commands:**
/clutch <name> - Claim free waifu
/hunt <name> - Buy paid waifu
/harem - View your collection
/bcards - View battle cards
/search <id> - Search waifu by ID
/balance - Check balance
/addbal - Add balance
/redeem <code> - Redeem code
/battle - Start battle
/pick <id> - Choose card in battle

**Admin Commands:**
/upload <name> <anime> <rarity> [price] [power]
/rwaifu <id> - Remove waifu
/setqr - Set QR photo
/setcaption <text>
/setpic - Set welcome pic
/created <amount> <code>
/stime <messages>
/broadcast - Reply to message"""
    await update.message.reply_text(text, parse_mode='Markdown')

async def clutch(update: Update, context: CallbackContext):
    if update.effective_chat.type == 'private': return await update.message.reply_text("Error: Use this command only in group")
    if not context.args: return await update.message.reply_text("Usage: `/clutch waifu-name`", parse_mode='Markdown')
    name = " ".join(context.args).lower()
    res = dbf("SELECT id, price FROM waifus WHERE LOWER(name)=?",(name,))
    if not res: return await update.message.reply_text("Error: Wrong name!")
    wid, price = res[0]
    if price > 0: return await update.message.reply_text("Error: This is paid waifu. Use /hunt")
    uid = update.effective_user.id
    db("INSERT OR IGNORE INTO users VALUES (?,0)",(uid,))
    if dbf("SELECT * FROM harem WHERE user_id=? AND waifu_id=?",(uid, wid)): return await update.message.reply_text("Already owned!")
    db("INSERT INTO harem VALUES (?,?)",(uid, wid))
    await update.message.reply_text(f"Success: You claimed `{name}`!", parse_mode='Markdown')

async def hunt(update: Update, context: CallbackContext):
    if update.effective_chat.type == 'private': return await update.message.reply_text("Error: Use in group")
    if not context.args: return await update.message.reply_text("Usage: `/hunt waifu-name`", parse_mode='Markdown')
    name = " ".join(context.args).lower()
    res = dbf("SELECT id, price FROM waifus WHERE LOWER(name)=?",(name,))
    if not res: return await update.message.reply_text("Error: Wrong name!")
    wid, price = res[0]
    if price == 0: return await update.message.reply_text("Error: Free waifu. Use /clutch")
    uid = update.effective_user.id
    db("INSERT OR IGNORE INTO users VALUES (?,0)",(uid,))
    bal = dbf("SELECT balance FROM users WHERE user_id=?",(uid,)); bal = bal[0][0] if bal else 0
    if bal < price: return await update.message.reply_text(f"Error: Need `{price}₹`. Balance: `{bal}₹`", parse_mode='Markdown')
    if dbf("SELECT * FROM harem WHERE user_id=? AND waifu_id=?",(uid, wid)): return await update.message.reply_text("Already owned!")
    db("UPDATE users SET balance = balance -? WHERE user_id=?",(price, uid))
    db("INSERT INTO harem VALUES (?,?)",(uid, wid))
    await update.message.reply_text(f"Purchased: `{name}` for `{price}₹`!", parse_mode='Markdown')

async def harem(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    res = dbf("SELECT w.id, w.name, w.anime, w.rarity, w.file_id FROM harem h JOIN waifus w ON h.waifu_id=w.id WHERE h.user_id=?",(uid,))
    if not res: return await update.message.reply_text("Your harem is empty")
    media = [InputMediaPhoto(r[4], caption=f"ID: {r[0]}\nName: {r[1]}\nAnime: {r[2]}\nRarity: {RARITY_MAP.get(r[3])}") for r in res[:10]]
    await update.message.reply_media_group(media)
    await update.message.reply_text(f"**YOUR HAREM**\nTotal: `{len(res)}`", parse_mode='Markdown')

async def bcards(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    res = dbf("SELECT w.id, w.name, w.anime, w.power, w.file_id FROM harem h JOIN waifus w ON h.waifu_id=w.id WHERE h.user_id=? AND w.rarity=12",(uid,))
    if not res: return await update.message.reply_text("No Battle Cards found. Collect 💀 Battle rarity waifus")
    media = [InputMediaPhoto(r[4], caption=f"ID: {r[0]}\nName: {r[1]}\nAnime: {r[2]}\nPower: {r[3]}") for r in res[:10]]
    await update.message.reply_media_group(media)
    await update.message.reply_text(f"**YOUR BATTLE CARDS**\nTotal: `{len(res)}`", parse_mode='Markdown')

async def search(update: Update, context: CallbackContext):
    if not context.args: return await update.message.reply_text("Usage: `/search waifu-id`")
    wid = int(context.args[0])
    res = dbf("SELECT * FROM waifus WHERE id=?",(wid,))
    if not res: return await update.message.reply_text("Error: Waifu not found")
    w = res[0]
    await update.message.reply_photo(w[6], caption=f"ID: {w[0]}\nName: {w[1]}\nAnime: {w[2]}\nRarity: {RARITY_MAP.get(w[3])}\nPower: {w[5]}\nPrice: {w[4]}₹", parse_mode='Markdown')

async def balance(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    db("INSERT OR IGNORE INTO users VALUES (?,0)",(uid,))
    bal = dbf("SELECT balance FROM users WHERE user_id=?",(uid,)); bal = bal[0][0] if bal else 0
    await update.message.reply_text(f"**YOUR BALANCE**\n`{bal}₹`", parse_mode='Markdown')

async def addbal(update: Update, context: CallbackContext):
    qr = get_setting("qr")
    if not qr: return await update.message.reply_text("Error: Admin has not set QR")
    keyboard = [[InlineKeyboardButton("SEND PROOF", url="https://t.me/OwnerSween")]]
    await update.message.reply_photo(qr, caption="PAY HERE & SEND SCREENSHOT TO ADMIN @OwnerSween", reply_markup=InlineKeyboardMarkup(keyboard))

async def redeem(update: Update, context: CallbackContext):
    if not context.args: return await update.message.reply_text("Usage: `/redeem CODE`")
    code = context.args[0]
    res = dbf("SELECT amount, used FROM redeem WHERE code=?",(code,))
    if not res or res[0][1]: return await update.message.reply_text("Error: Invalid or Used Code")
    amount = res[0][0]
    db("UPDATE redeem SET used=1 WHERE code=?",(code,))
    uid = update.effective_user.id
    db("INSERT OR IGNORE INTO users VALUES (?,0)",(uid,))
    db("UPDATE users SET balance = balance +? WHERE user_id=?",(amount, uid))
    await update.message.reply_text(f"Success: Redeemed. +{amount}₹ Added to balance")

# ===== BATTLE SYSTEM =====
async def battle(update: Update, context: CallbackContext):
    if update.effective_chat.type!= 'group': return await update.message.reply_text("Error: Battle only in group")
    chat_id = update.effective_chat.id
    if chat_id in active_battles: return await update.message.reply_text("Error: Battle already running")
    keyboard = [[InlineKeyboardButton("⚔️ COME TO FIGHT", callback_data=f"joinbattle_{update.effective_user.id}")]]
    active_battles[chat_id] = {"p1": update.effective_user, "p2": None, "round": 0, "score": {update.effective_user.id: 0}, "cards": {}}
    await update.message.reply_text(f"**⚔️ BATTLE ARENA OPENED ⚔️**\n\n{update.effective_user.first_name} initiated a battle.\nFormat: 7 Rounds\nRule: Choose Battle Card each round. Highest Power wins the round.", reply_markup=InlineKeyboardMarkup(keyboard))

async def joinbattle(update: Update, context: CallbackContext):
    q = update.callback_query; await q.answer()
    chat_id = q.message.chat.id
    if chat_id not in active_battles: return
    battle = active_battles[chat_id]
    if battle["p2"]: return await q.answer("Battle Full", show_alert=True)
    if q.from_user.id == battle["p1"].id: return await q.answer("You are Player 1", show_alert=True)
    battle["p2"] = q.from_user; battle["score"][q.from_user.id] = 0
    await q.message.edit_text("**ARENA IS FULL. BATTLE STARTING NOW.**\n\nRound 1/7\nBoth players use /pick <waifu_id> to select card")
    await asyncio.sleep(3); await start_round(chat_id, context)

async def pick(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    if chat_id not in active_battles: return
    battle = active_battles[chat_id]; uid = update.effective_user.id
    if uid not in [battle["p1"].id, battle.get("p2", {}).id]: return
    if not context.args: return await update.message.reply_text("Usage: `/pick waifu_id`")
    wid = int(context.args[0])
    res = dbf("SELECT power FROM waifus w JOIN harem h ON w.id=h.waifu_id WHERE w.id=? AND h.user_id=? AND w.rarity=12",(wid, uid))
    if not res: return await update.message.reply_text("Error: You do not own this Battle Card")
    battle["cards"][uid] = res[0][0]
    await update.message.reply_text(f"Card Locked. Power: `{res[0][0]}`", parse_mode='Markdown')

async def start_round(chat_id, context):
    battle = active_battles[chat_id]; battle["round"] += 1; battle["cards"] = {}
    await context.bot.send_message(chat_id, f"**ROUND {battle['round']}/7**\nSelect your Battle Card.\nCommand: `/pick <id>`\nTime Limit: 20 seconds")
    await asyncio.sleep(20); await end_round(chat_id, context)

async def end_round(chat_id, context):
    battle = active_battles[chat_id]; p1, p2 = battle["p1"].id, battle["p2"].id
    p1_power = battle["cards"].get(p1, 0); p2_power = battle["cards"].get(p2, 0)
    if p1_power > p2_power: battle["score"][p1] += 1; winner = battle["p1"].first_name
    elif p2_power > p1_power: battle["score"][p2] += 1; winner = battle["p2"].first_name
    else: winner = "DRAW"
    await context.bot.send_message(chat_id, f"**ROUND {battle['round']} RESULT**\n\n{battle['p1'].first_name}: {p1_power} Power\n{battle['p2'].first_name}: {p2_power} Power\nWinner: {winner}\n\n**SCORE:** {battle['p1'].first_name} {battle['score'][p1]} - {battle['score'][p2]} {battle['p2'].first_name}")
    if battle["round"] >= 7:
        if battle["score"][p1] > battle["score"][p2]: final = f"WINNER: {battle['p1'].first_name}"
        elif battle["score"][p2] > battle["score"][p1]: final = f"WINNER: {battle['p2'].first_name}"
        else: final = "RESULT: DRAW"
        await context.bot.send_message(chat_id, f"**BATTLE OVER**\n\n{final}"); del active_battles[chat_id]
    else: await asyncio.sleep(3); await start_round(chat_id, context)

# ===== ADMIN COMMANDS =====
async def setqr(update: Update, context: CallbackContext):
    if update.effective_user.id!= ADMIN_ID: return
    file_id = update.message.reply_to_message.photo[-1].file_id
    db("INSERT OR REPLACE INTO settings VALUES ('qr',?)",(file_id,)); await update.message.reply_text("QR Set Successfully")

async def upload(update: Update, context: CallbackContext):
    if update.effective_user.id!= ADMIN_ID: return
    if not update.message.reply_to_message.photo: return await update.message.reply_text("Error: Reply to a photo")
    args = context.args
    if len(args) < 3: return await update.message.reply_text("Usage: `/upload name anime rarity [price] [power]`", parse_mode='Markdown')
    name, anime, rarity = args[0], args[1], int(args[2])
    price = float(args[3]) if len(args) > 3 else 0
    power = int(args[4]) if len(args) > 4 else 0
    file_id = update.message.reply_to_message.photo[-1].file_id
    db("INSERT INTO waifus (name, anime, rarity, price, power, file_id) VALUES (?,?,?,?,?,?)",(name, anime, rarity, price, power, file_id))
    await update.message.reply_text(f"Uploaded Successfully\nName: {name}\nRarity: {RARITY_MAP.get(rarity)}\nPower: {power}\nPrice: {price}₹", parse_mode='Markdown')

async def rwaifu(update: Update, context: CallbackContext):
    if update.effective_user.id!= ADMIN_ID: return
    db("DELETE FROM waifus WHERE id=?",(int(context.args[0]),)); await update.message.reply_text("Waifu Removed")

async def setcaption(update: Update, context: CallbackContext):
    if update.effective_user.id!= ADMIN_ID: return
    db("INSERT OR REPLACE INTO settings VALUES ('welcome',?)",(" ".join(context.args),)); await update.message.reply_text("Welcome caption updated")

async def setpic(update: Update, context: CallbackContext):
    if update.effective_user.id!= ADMIN_ID: return
    file_id = update.message.reply_to_message.photo[-1].file_id
    db("INSERT OR REPLACE INTO settings VALUES ('welcome_pic',?)",(file_id,)); await update.message.reply_text("Welcome picture updated")

async def created(update: Update, context: CallbackContext):
    if update.effective_user.id!= ADMIN_ID: return
    db("INSERT OR REPLACE INTO redeem VALUES (?,?,0)",(context.args[1], float(context.args[0]))); await update.message.reply_text(f"Redeem Code Created: {context.args[1]} = {context.args[0]}₹")

async def stime(update: Update, context: CallbackContext):
    if update.effective_user.id!= ADMIN_ID: return
    db("INSERT OR REPLACE INTO settings VALUES ('stime',?)",(context.args[0],)); await update.message.reply_text(f"Spawn time set to {context.args[0]} messages")

async def broadcast(update: Update, context: CallbackContext):
    if update.effective_user.id!= ADMIN_ID: return
    msg = update.message.reply_to_message
    users = dbf("SELECT user_id FROM users")
    count = 0
    for u in users:
        try:
            if msg.photo: await context.bot.send_photo(u[0], msg.photo[-1].file_id, caption=msg.caption)
            else: await context.bot.send_message(u[0], msg.text)
            count += 1
        except: pass
    await update.message.reply_text(f"Broadcast Completed. Sent to {count} users")

# ===== AUTO SPAWN =====
async def message_counter(update: Update, context: CallbackContext):
    if update.effective_chat.type!= 'group' or update.effective_user.id == ADMIN_ID: return
    count = int(get_setting("msg_count", "0")) + 1
    stime = int(get_setting("stime", "15"))
    db("INSERT OR REPLACE INTO settings VALUES ('msg_count',?)",(str(count),))
    if count >= stime:
        db("INSERT OR REPLACE INTO settings VALUES ('msg_count','0')")
        waifus = dbf("SELECT * FROM waifus WHERE rarity IN ({})".format(','.join('?'*len(DROP_RARITY))), DROP_RARITY)
        if waifus:
            weights = {4:1,5:2,6:3,7:4,8:5,9:8,10:12,11:20,12:10}
            w = random.choices(waifus, weights=[weights.get(x[3], 1) for x in waifus])[0]
            rarity_text, price = RARITY_MAP.get(w[3]), w[4]
            if price > 0:
                caption = f"A New {rarity_text} {int(price)}₹ SealWaifu Appeared.\n/Clutch Character Name to add to your Collection"
                switch_query = "/Clutch "
            else:
                caption = f'A New "{rarity_text}" SealWaifu Appeared.\n/Clutch Character Name to add to your Collection'
                switch_query = "/Clutch "
            keyboard = [[InlineKeyboardButton("CLUTCH", switch_inline_query_current_chat=switch_query)]]
            await context.bot.send_photo(update.effective_chat.id, w[6], caption=caption, reply_markup=InlineKeyboardMarkup(keyboard))

async def main():
    if not TOKEN or not ADMIN_ID:
        print("BOT_TOKEN or ADMIN_ID missing in env")
        return
    init_db()
    app = Application.builder().token(TOKEN).build()

    # USER COMMANDS
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", helpcmd))
    app.add_handler(CommandHandler("clutch", clutch))
    app.add_handler(CommandHandler("hunt", hunt))
    app.add_handler(CommandHandler("harem", harem))
    app.add_handler(CommandHandler("bcards", bcards))
    app.add_handler(CommandHandler("search", search))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("addbal", addbal))
    app.add_handler(CommandHandler("redeem", redeem))
    app.add_handler(CommandHandler("battle", battle))
    app.add_handler(CommandHandler("pick", pick))

    # ADMIN COMMANDS
    app.add_handler(CommandHandler("setqr", setqr))
    app.add_handler(CommandHandler("upload", upload))
    app.add_handler(CommandHandler("rwaifu", rwaifu))
    app.add_handler(CommandHandler("setcaption", setcaption))
    app.add_handler(CommandHandler("setpic", setpic))
    app.add_handler(CommandHandler("created", created))
    app.add_handler(CommandHandler("stime", stime))
    app.add_handler(CommandHandler("broadcast", broadcast))

    # SYSTEM
    app.add_handler(MessageHandler(filters.ALL, message_counter))
    app.add_handler(CallbackQueryHandler(joinbattle, pattern="joinbattle"))

    print("CLUTCH WAIFU BOT RUNNING")
    await app.run_polling()

if __name__=='__main__':
    asyncio.run(main())
