#!/usr/bin/env python3
import os
import logging
import asyncio
import zipfile
import shutil
import json
import time
import random
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# ===== 💎 BOT CONFIGURATION 💎 =====
BOT_TOKEN = "8260073091:AAHF9eRGlhND_YFcaQt_HAgrFw3Kt7dDonA"
ADMIN_ID = 8541572102

# ✅ FIXED VARIABLES
ADMIN_USERNAME = "@ZRY_X_OWNER"
CHANNEL = "@zry_x_75"
OWNER_TAG = "@ZRY_X_OWNER"

# 👇 1. PASTE YOUR GROUP/CHANNEL ID HERE
PAYMENT_CHANNEL_ID = -1003534075169 

# 👇 2. IMAGE URLS
PAYMENT_QR_URL = "https://i.supaimg.com/3bbd55ba-8a22-415a-8701-edd34f5c7490.jpg" 
WELCOME_IMAGE_URL = "https://i.supaimg.com/eac5f874-354b-4240-be1e-f6b65ca62efa.jpg"

# 💰 Premium Settings
DAILY_LIMIT = 2  # <--- UPDATED: Changed from 4 to 2
PREMIUM_PRICE = "Rs. 19"

# Limits & Paths
MAX_FILE_SIZE = 49 * 1024 * 1024
DOWNLOAD_DIR = "downloads"
SETTINGS_FILE = "premium_settings.json"

# 🛡️ Anti-Block User Agents
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1"
]

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

if not os.path.exists(DOWNLOAD_DIR): os.makedirs(DOWNLOAD_DIR)

# ===== 🧠 SETTINGS MANAGER =====
def load_settings():
    default = {
        "maintenance": False, "premium_users": [ADMIN_ID], "banned_users": [],
        "joined_users": [ADMIN_ID], "daily_usage": {}, 
        "last_reset_date": datetime.now().strftime("%Y-%m-%d"),
        "total_downloads": 0, "start_time": time.time()
    }
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as f:
                settings = json.load(f)
                today = datetime.now().strftime("%Y-%m-%d")
                if settings.get("last_reset_date") != today:
                    settings["daily_usage"] = {}
                    settings["last_reset_date"] = today
                    save_settings(settings)
                for k, v in default.items():
                    if k not in settings: settings[k] = v
                return settings
    except: pass
    return default

def save_settings(s):
    try:
        with open(SETTINGS_FILE, 'w') as f: json.dump(s, f, indent=4)
    except: pass

def check_access(uid):
    s = load_settings()
    # Maintenance Check
    if s.get("maintenance") and uid != ADMIN_ID: 
        return False, "⚠️ **System Maintenance**\n\nThe bot is currently being updated. Please try again later."
    
    if uid in s.get("banned_users", []): return False, "🚫 Banned"
    if uid in s.get("premium_users", []): return True, "Premium"
    
    used = s["daily_usage"].get(str(uid), 0)
    if used >= DAILY_LIMIT:
        return False, f"🚫 **Limit Reached**\nFree limit: {DAILY_LIMIT}/day.\n\n💎 Buy Premium for Unlimited."
    return True, "Free"

def increment_usage(uid):
    s = load_settings()
    s["total_downloads"] = s.get("total_downloads", 0) + 1
    
    if uid not in s.get("premium_users", []):
        s["daily_usage"][str(uid)] = s["daily_usage"].get(str(uid), 0) + 1
    
    save_settings(s)

# ===== 🛠 HELPER TO FIX USERNAMES =====
def escape_md(text):
    if not text: return ""
    return text.replace("_", "\\_")

# ===== 📥 DOWNLOADER =====
async def download_site(url, mode, update, context):
    uid = update.effective_user.id
    work_dir = os.path.join(DOWNLOAD_DIR, f"site_{uid}_{int(time.time())}")
    os.makedirs(work_dir, exist_ok=True)
    
    ua = random.choice(USER_AGENTS)
    
    cmd = ["wget", "--mirror", "--convert-links", "--adjust-extension", "--page-requisites", "--no-parent", "--no-check-certificate", "-e", "robots=off", "--user-agent", ua, "--timeout=30", "-P", work_dir, url] if mode == "full" else ["wget", "-r", "-l", "1", "-k", "-p", "--no-check-certificate", "-e", "robots=off", "--user-agent", ua, "-P", work_dir, url]

    try:
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await proc.communicate()
        if not os.listdir(work_dir):
            shutil.rmtree(work_dir, ignore_errors=True)
            return None, 0, "Failed to download."
            
        zip_path = f"{work_dir}.zip"
        count = 0
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
            for r, d, f in os.walk(work_dir):
                for file in f:
                    z.write(os.path.join(r, file), os.path.relpath(os.path.join(r, file), work_dir))
                    count += 1
        size = os.path.getsize(zip_path)
        shutil.rmtree(work_dir, ignore_errors=True)
        return zip_path, count, size
    except Exception as e:
        shutil.rmtree(work_dir, ignore_errors=True)
        return None, 0, str(e)

# ===== 🎮 HANDLERS =====
async def start(update, context):
    uid = update.effective_user.id
    s = load_settings()
    if uid not in s["joined_users"]:
        s["joined_users"].append(uid)
        save_settings(s)
    
    if s.get("maintenance") and uid != ADMIN_ID:
        await update.message.reply_text("⚠️ **System Maintenance**\n\nPlease check back later.", parse_mode='Markdown')
        return

    txt = f"""
🌟 **Premium Website Cloner** 🌟

Welcome! I can download website source codes for you.

📉 **Free Plan:** {DAILY_LIMIT} Links / Day
💎 **Premium:** Unlimited Access

**How to use:**
Send any URL (e.g., `https://example.com`)

👨‍💻 **Admin:** {escape_md(ADMIN_USERNAME)}
    """
    
    try:
        await context.bot.send_photo(
            chat_id=uid,
            photo=WELCOME_IMAGE_URL,
            caption=txt,
            parse_mode='Markdown'
        )
    except:
        await update.message.reply_text(txt, parse_mode='Markdown')

async def my_plan(update, context):
    uid = update.effective_user.id
    settings = load_settings()
    
    is_premium = uid in settings["premium_users"]
    status = "💎 Premium (Unlimited)" if is_premium else "📉 Free Plan"
    usage = settings["daily_usage"].get(str(uid), 0)
    
    text = f"""
👤 **Your Profile**

🆔 **ID:** `{uid}`
🏷 **Plan:** {status}
📊 **Usage Today:** {usage}/{DAILY_LIMIT}
    """
    await update.message.reply_text(text, parse_mode='Markdown')

async def bot_stats(update, context):
    if update.effective_user.id != ADMIN_ID: return
    s = load_settings()
    
    uptime_sec = time.time() - s['start_time']
    uptime_hrs = int(uptime_sec // 3600)
    
    txt = f"""
📊 **Bot Statistics**

👥 **Total Users:** {len(s['joined_users'])}
💎 **Premium Users:** {len(s['premium_users'])}
🚫 **Banned Users:** {len(s['banned_users'])}
📥 **Total Downloads:** {s.get('total_downloads', 0)}
⏱ **Uptime:** {uptime_hrs} Hours
    """
    await update.message.reply_text(txt, parse_mode='Markdown')

async def handle_url(update, context):
    uid = update.effective_user.id
    allowed, msg = check_access(uid)
    if not allowed:
        kb = [[InlineKeyboardButton(f"💎 Buy Premium ({PREMIUM_PRICE})", callback_data="buy")]] if "Limit" in msg else None
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb) if kb else None, parse_mode='Markdown')
        return

    context.user_data['target_url'] = update.message.text.strip()
    kb = [[InlineKeyboardButton("🌐 Full", callback_data="full"), InlineKeyboardButton("📄 Page", callback_data="partial")], [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
    await update.message.reply_text("Choose mode:", reply_markup=InlineKeyboardMarkup(kb))

async def button_handler(update, context):
    q = update.callback_query
    await q.answer()
    uid = update.effective_user.id
    
    if q.data == "buy":
        try:
            await q.delete_message()
            await context.bot.send_photo(
                chat_id=uid, 
                photo=PAYMENT_QR_URL, 
                caption=f"💎 **Premium Upgrade**\nPrice: {PREMIUM_PRICE}\n\n1️⃣ Scan the QR to Pay\n2️⃣ Click 'Send Screenshot'\n3️⃣ Upload payment proof", 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📤 Send Screenshot", callback_data="proof")]])
            )
        except Exception as e:
            await context.bot.send_message(uid, f"❌ Error loading QR Image.\nPlease contact admin: {escape_md(ADMIN_USERNAME)}")
        return

    if q.data == "proof":
        context.user_data['waiting_for_proof'] = True
        await q.message.reply_text("📸 **Please send your payment screenshot now.**")
        return
        
    if q.data == "cancel":
        await q.edit_message_text("🚫 Cancelled.")
        return

    allowed, msg = check_access(uid)
    if not allowed:
        await q.edit_message_text("🚫 Limit reached.")
        return

    await q.edit_message_text("🚀 Downloading...")
    zp, cnt, size = await download_site(context.user_data.get('target_url'), q.data, update, context)
    
    if not zp:
        await q.edit_message_text(f"❌ Error: {size}")
        return
    if size > MAX_FILE_SIZE:
        os.remove(zp)
        await q.edit_message_text("⚠️ File too large (Max 50MB).")
        return

    increment_usage(uid)
    try:
        caption = f"✅ **Download Complete**\n\n📂 Site: `{context.user_data.get('target_url')}`\n📊 Size: {size/1024:.2f} KB\nFiles: {cnt}\n\n🔥 **By {escape_md(OWNER_TAG)}**"
        
        with open(zp, 'rb') as f:
            await context.bot.send_document(
                chat_id=uid, 
                document=f, 
                filename="source_code.zip", 
                caption=caption,
                parse_mode='Markdown'
            )
        await q.delete_message()
    except Exception as e: 
        logger.error(e)
        await q.edit_message_text("❌ Upload failed.")
    
    if os.path.exists(zp): os.remove(zp)

async def handle_photo(update, context):
    uid = update.effective_user.id
    if context.user_data.get('waiting_for_proof'):
        try:
            await context.bot.send_photo(
                chat_id=PAYMENT_CHANNEL_ID,
                photo=update.message.photo[-1].file_id,
                caption=f"💸 **New Payment**\n👤: {update.effective_user.mention_html()} (`{uid}`)\n\nAdd Premium:\n`/add_premium {uid}`",
                parse_mode='HTML'
            )
            await update.message.reply_text("✅ **Proof Sent!**\nAdmin will verify shortly.")
            context.user_data['waiting_for_proof'] = False
        except Exception as e:
            await update.message.reply_text(f"❌ System Error: Bot cannot send to Admin Group.\nCheck Channel ID: {PAYMENT_CHANNEL_ID}\nError: {e}")

# ===== 👑 ADMIN COMMANDS =====
async def add_premium(update, context):
    if update.effective_user.id != ADMIN_ID: return
    try:
        tid = int(context.args[0])
        s = load_settings()
        if tid not in s["premium_users"]:
            s["premium_users"].append(tid)
            save_settings(s)
            await update.message.reply_text(f"✅ User {tid} is now Premium.")
            try: await context.bot.send_message(tid, "🎉 **Payment Approved!** You are now Premium.")
            except: pass
        else: await update.message.reply_text("⚠️ Already Premium.")
    except: await update.message.reply_text("❌ Use: /add_premium ID")

async def remove_premium(update, context):
    if update.effective_user.id != ADMIN_ID: return
    try:
        tid = int(context.args[0])
        s = load_settings()
        if tid in s["premium_users"]:
            s["premium_users"].remove(tid)
            save_settings(s)
            await update.message.reply_text(f"📉 User {tid} removed from Premium.")
            try: await context.bot.send_message(tid, "⚠️ **Plan Update**\n\nYour Premium Plan has expired.\nYou have been downgraded to the Free Plan (2 links/day).")
            except: pass
        else: await update.message.reply_text("⚠️ User is not Premium.")
    except: await update.message.reply_text("❌ Use: /remove_premium ID")

async def broadcast(update, context):
    if update.effective_user.id != ADMIN_ID: return
    
    settings = load_settings()
    users = settings["joined_users"]
    sent_count = 0
    
    if update.message.reply_to_message:
        message_to_copy = update.message.reply_to_message
        await update.message.reply_text(f"⏳ **Broadcasting media** to {len(users)} users...", parse_mode='Markdown')
        for uid in users:
            try:
                await context.bot.copy_message(chat_id=uid, from_chat_id=ADMIN_ID, message_id=message_to_copy.message_id)
                sent_count += 1
                if sent_count % 20 == 0: time.sleep(1)
            except: pass
                
    elif context.args:
        msg = " ".join(context.args)
        await update.message.reply_text(f"⏳ **Broadcasting text** to {len(users)} users...", parse_mode='Markdown')
        for uid in users:
            try:
                await context.bot.send_message(chat_id=uid, text=f"📢 **Announcement**\n\n{msg}", parse_mode='Markdown')
                sent_count += 1
            except: pass
    else:
        await update.message.reply_text("❌ usage: Reply to media with /broadcast OR type /broadcast [text]")
        return

    await update.message.reply_text(f"✅ **Broadcast Complete**\nSent to: {sent_count}")

async def maintenance_command(update, context):
    if update.effective_user.id != ADMIN_ID: return
    s = load_settings()
    s["maintenance"] = not s.get("maintenance", False)
    save_settings(s)
    status = "ON 🔴" if s["maintenance"] else "OFF 🟢"
    await update.message.reply_text(f"🔧 **Maintenance Mode:** {status}", parse_mode='Markdown')

# ===== 🚀 MAIN =====
def main():
    if not shutil.which("wget"): return print("❌ Install wget!")
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Public Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("me", my_plan))
    
    # Admin Commands
    app.add_handler(CommandHandler("add_premium", add_premium))
    app.add_handler(CommandHandler("remove_premium", remove_premium))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("maintenance", maintenance_command))
    app.add_handler(CommandHandler("stats", bot_stats))
    
    # Functional Handlers
    app.add_handler(MessageHandler(filters.Regex(r'http'), handle_url))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("✅ Bot Online")
    app.run_polling()

if __name__ == '__main__':
    main()