# bot_final_v6.py
import telebot, requests, json, os, qrcode
from telebot import types
from io import BytesIO
from datetime import datetime, timedelta

# ==================== CONFIG ====================
TOKEN = "8289058954:AAHsnVOhMrCsKAmorErufBzphSTTpJ7gLtg"            # <-- अपने TOKEN से replace करो
ADMIN_ID = 7856323067              # <-- अगर अलग admin है तो change करो
CHANNEL_USERNAME = "@dubeycrazybottt"
UPI_ID = "panditadeshdubey2002@upi"
UPI_PAYEE_NAME = "instaservice15"
bot = telebot.TeleBot(TOKEN)

USERS_FILE = "users.json"
LOGS_FILE = "search_logs.json"

# ==================== UTIL: file helpers ====================
def load_json(path, default):
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump(default, f)
        return default.copy()
    with open(path, "r") as f:
        try:
            return json.load(f)
        except:
            return default.copy()

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

users = load_json(USERS_FILE, {})
search_logs = load_json(LOGS_FILE, {})

# ==================== PLANS ====================
PLANS = {
    "1d": {"label": "🪙 1 दिन वाला अनलिमिटेड", "price": 19, "days": 1},
    "7d": {"label": "💎 7 दिन वाला अनलिमिटेड", "price": 79, "days": 7},
    "30d": {"label": "👑 30 दिन वाला अनलिमिटेड", "price": 199, "days": 30}
}

user_expected_input = {}  # user_id -> plan_key (when QR shown, waiting for screenshot)

# ==================== QR GENERATION ====================
def generate_qr(upi_id, name, amount):
    upi_link = f"upi://pay?pa={upi_id}&pn={name}&am={amount}&cu=INR"
    img = qrcode.make(upi_link)
    bio = BytesIO()
    bio.name = 'qr.png'
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio

# ==================== PLAN / USER helpers ====================
def activate_user(user_id: int, days: int):
    uid = str(user_id)
    now = datetime.utcnow()
    if uid in users and users[uid].get("expiry"):
        try:
            prev = datetime.fromisoformat(users[uid]["expiry"])
        except:
            prev = now
        if prev > now:
            new_expiry = prev + timedelta(days=days)
        else:
            new_expiry = now + timedelta(days=days)
    else:
        new_expiry = now + timedelta(days=days)

    users[uid] = users.get(uid, {})
    users[uid]["expiry"] = new_expiry.isoformat()
    save_json(USERS_FILE, users)
    return new_expiry

def deactivate_user(user_id: int):
    uid = str(user_id)
    if uid in users and "expiry" in users[uid]:
        users[uid].pop("expiry", None)
        save_json(USERS_FILE, users)
        return True
    return False

def is_active(user_id: int):
    uid = str(user_id)
    if uid not in users or "expiry" not in users[uid]:
        return False
    try:
        expiry = datetime.fromisoformat(users[uid]["expiry"])
    except:
        return False
    return expiry > datetime.utcnow()

def days_left(user_id: int):
    uid = str(user_id)
    if uid not in users or "expiry" not in users[uid]:
        return 0
    try:
        expiry = datetime.fromisoformat(users[uid]["expiry"])
    except:
        return 0
    delta = expiry - datetime.utcnow()
    return max(0, delta.days)

# ==================== CHANNEL JOIN CHECK ====================
def is_user_joined(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

# ==================== CALLBACK: buy plan ====================
@bot.callback_query_handler(func=lambda c: c.data.startswith("buy_"))
def buy_cb(c):
    key = c.data.split("_", 1)[1]
    plan = PLANS.get(key)
    if not plan:
        bot.answer_callback_query(c.id, "Plan nahi mila.")
        return

    img = generate_qr(UPI_ID, UPI_PAYEE_NAME, plan["price"])
    caption = (f"💳 *Plan:* {plan['label']} — ₹{plan['price']}\n"
               f"UPI ID: `{UPI_ID}`\n\n"
               f"Payment ka screenshot yahan bhejein.\n\n"
               f"User ID: `{c.from_user.id}`\n\n"
               f"Note: Screenshot bhejne par bot auto-activate kar dega aur admin ko bhi bhej dega.")
    bot.send_photo(c.message.chat.id, img, caption=caption, parse_mode="Markdown")
    user_expected_input[c.from_user.id] = key
    bot.answer_callback_query(c.id, "QR generated — payment screenshot bhejo jab payment complete ho jaye.")

# ==================== /start & menu ====================
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    if not is_user_joined(user_id):
        join_btn = types.InlineKeyboardMarkup()
        join_btn.add(types.InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME[1:]}"))
        bot.send_message(message.chat.id,
                         f"🚫 पहले हमारे चैनल को जॉइन करें:\n👉 {CHANNEL_USERNAME}\n\nफिर /start दोबारा भेजें ✅",
                         reply_markup=join_btn)
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🔍 Aadhaar Info", "👨‍👩‍👧 Family Info")
    markup.add("📞 Number Info", "🚘 Vehicle Info")
    markup.add("💰 Buy Plan", "📊 Status")
    bot.send_message(message.chat.id, "👋 Welcome! नीचे से अपनी सर्विस चुनें 👇", reply_markup=markup)

# ==================== Buy Plan menu handler ====================
@bot.message_handler(func=lambda m: m.text == "💰 Buy Plan")
def show_plans(message):
    markup = types.InlineKeyboardMarkup()
    for key, plan in PLANS.items():
        markup.add(types.InlineKeyboardButton(text=plan["label"], callback_data=f"buy_{key}"))
    bot.send_message(message.chat.id, "👇 नीचे से अपना प्लान चुनें 👇", reply_markup=markup)

# ==================== STATUS ====================
@bot.message_handler(func=lambda m: m.text == "📊 Status")
def send_status(message):
    uid = message.from_user.id
    active = is_active(uid)
    if active:
        dl = days_left(uid)
        bot.send_message(message.chat.id, f"✅ आपका प्लान active है — बाकी दिनों की संख्या: {dl} दिन\n\nDeveloper: @instaservice15")
    else:
        bot.send_message(message.chat.id, "❌ आपका कोई active प्लान नहीं है। Buy Plan से प्लान लें।")

# ==================== Payment screenshot handler (AUTO-ACTIVATE) ====================
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    uid = message.from_user.id
    # if user was waiting after QR -> auto-activate
    if uid in user_expected_input:
        plan_key = user_expected_input.pop(uid)
        plan = PLANS.get(plan_key)
        days = plan["days"] if plan else 0
        # forward photo to admin
        try:
            caption_admin = (f"📸 Payment screenshot from user `{uid}` for plan *{plan['label']}* — ₹{plan['price']}\n\n"
                             f"Bot ने auto-activate कर दिया है. अगर आप verify करना चाहें तो screenshot देख लें.")
            bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=caption_admin, parse_mode="Markdown")
        except:
            pass
        # AUTO-ACTIVATE now
        try:
            activate_user(uid, days)
            # send confirmation to user (ONLY this message as requested)
            try:
                bot.send_message(uid, "✅ आपका प्लान एक्टिव हो गया ✅\n\nDeveloper: @instaservice15")
            except:
                pass
            # log activation
            search_logs.setdefault(str(uid), []).append({"type":"payment_auto_activate","plan":plan_key,"time":datetime.utcnow().isoformat()})
            save_json(LOGS_FILE, search_logs)
        except Exception as e:
            bot.send_message(uid, "❌ Activation me error aaya. Admin se संपर्क करें.")
    else:
        # regular photo (not payment flow)
        bot.send_message(message.chat.id, "📷 Photo received. Agar ye payment screenshot hai to pehle 'Buy Plan' se plan select karen.")

# ==================== ADMIN: /activate & /deactivate ====================
@bot.message_handler(commands=['activate'])
def cmd_activate(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ सिर्फ़ admin ही यह command चला सकता है.")
        return
    args = message.text.split()
    if len(args) != 3:
        bot.reply_to(message, "Usage: /activate <user_id> <days>\nउदाहरण: /activate 123456789 7")
        return
    try:
        target_id = int(args[1])
        days = int(args[2])
    except:
        bot.reply_to(message, "Invalid arguments. user_id और days number होना चाहिए.")
        return
    new_expiry = activate_user(target_id, days)
    bot.reply_to(message, f"✅ User `{target_id}` activated for {days} day(s).")
    try:
        bot.send_message(target_id, "✅ आपका प्लान एक्टिव हो गया ✅\n\nDeveloper: @instaservice15")
    except:
        bot.reply_to(message, "User ko message भेजने में error — शायद user ne bot ko block kiya hua hai ya data galat hai.")

@bot.message_handler(commands=['deactivate'])
def cmd_deactivate(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ सिर्फ़ admin ही यह command चला सकता है.")
        return
    args = message.text.split()
    if len(args) != 2:
        bot.reply_to(message, "Usage: /deactivate <user_id>\nउदाहरण: /deactivate 123456789")
        return
    try:
        target_id = int(args[1])
    except:
        bot.reply_to(message, "Invalid user_id.")
        return
    ok = deactivate_user(target_id)
    if ok:
        bot.reply_to(message, f"✅ User `{target_id}` deactivated.")
        try:
            bot.send_message(target_id, "❌ आपका प्लान deactivate कर दिया गया है।")
        except:
            pass
    else:
        bot.reply_to(message, "User के पास active plan नहीं था.")

# ==================== API UTIL: safe get with fallback ====================
def safe_get(d, keys, fallback="N/A"):
    if not isinstance(d, dict):
        return fallback
    for k in keys:
        if k in d and d[k]:
            return d[k]
    return fallback

# ==================== API HANDLERS (with plan check & formatted output) ====================
# Aadhaar
@bot.message_handler(func=lambda m: m.text == "🔍 Aadhaar Info")
def ask_aadhaar(message):
    if not is_active(message.from_user.id):
        bot.send_message(message.chat.id, "❌ आपका प्लान active नहीं है — पहले प्लान खरीदें या admin से संपर्क करें.")
        return
    bot.send_message(message.chat.id, "कृपया 12 अंकों का आधार नंबर भेजें 🔢")
    bot.register_next_step_handler(message, fetch_aadhaar)

def fetch_aadhaar(message):
    aadhar = message.text.strip()
    url = f"https://aadhaar-api-2-latest.vercel.app/info?aadhar={aadhar}"
    try:
        r = requests.get(url, timeout=12)
        data = r.json() if r.status_code == 200 else {}
        result = (
            f"🪪 Aadhaar Info\n"
            f"👤 Name: {safe_get(data, ['name','full_name'])}\n"
            f"📍 State: {safe_get(data, ['state'])}\n"
            f"🗓 DOB: {safe_get(data, ['dob','date_of_birth'])}\n"
            f"🧾 Gender: {safe_get(data, ['gender'])}\n\n"
            f"👨‍💻 Developer: @instaservice15"
        )
        bot.send_message(message.chat.id, result)
        # log
        search_logs.setdefault(str(message.from_user.id), []).append({"type":"aadhaar","query":aadhar,"time":datetime.utcnow().isoformat()})
        save_json(LOGS_FILE, search_logs)
    except:
        bot.send_message(message.chat.id, "❌ Error fetching Aadhaar info.")

# Family
@bot.message_handler(func=lambda m: m.text == "👨‍👩‍👧 Family Info")
def ask_family(message):
    if not is_active(message.from_user.id):
        bot.send_message(message.chat.id, "❌ आपका प्लान active नहीं है — पहले प्लान खरीदें या admin से संपर्क करें.")
        return
    bot.send_message(message.chat.id, "कृपया मोबाइल नंबर भेजें 📱")
    bot.register_next_step_handler(message, fetch_family)

def fetch_family(message):
    number = message.text.strip()
    url = f"https://familyinfoapi.vercel.app/fetch?number={number}"
    try:
        r = requests.get(url, timeout=12)
        data = r.json() if r.status_code == 200 else {}
        members = data.get("members") if isinstance(data.get("members"), list) else []
        result = (
            f"👨‍👩‍👧 Family Info\n"
            f"👤 Head: {safe_get(data, ['head','name'])}\n"
            f"🏠 Address: {safe_get(data, ['address'])}\n"
            f"👨 Members: {len(members)}\n\n"
            f"👨‍💻 Developer: @instaservice15"
        )
        bot.send_message(message.chat.id, result)
        search_logs.setdefault(str(message.from_user.id), []).append({"type":"family","query":number,"time":datetime.utcnow().isoformat()})
        save_json(LOGS_FILE, search_logs)
    except:
        bot.send_message(message.chat.id, "❌ Error fetching Family info.")

# Number
@bot.message_handler(func=lambda m: m.text == "📞 Number Info")
def ask_number(message):
    if not is_active(message.from_user.id):
        bot.send_message(message.chat.id, "❌ आपका प्लान active नहीं है — पहले प्लान खरीदें या admin से संपर्क करें.")
        return
    bot.send_message(message.chat.id, "कृपया मोबाइल नंबर भेजें 📞")
    bot.register_next_step_handler(message, fetch_number)

def fetch_number(message):
    number = message.text.strip()
    url = f"https://numberapi.vercel.app/info?number={number}"
    try:
        r = requests.get(url, timeout=12)
        data = r.json() if r.status_code == 200 else {}
        result = (
            f"📞 Number Info\n"
            f"📱 Number: {safe_get(data, ['number'])}\n"
            f"🌐 Location: {safe_get(data, ['location','region','city'])}\n"
            f"🏢 Operator: {safe_get(data, ['operator','carrier'])}\n\n"
            f"👨‍💻 Developer: @instaservice15"
        )
        bot.send_message(message.chat.id, result)
        search_logs.setdefault(str(message.from_user.id), []).append({"type":"number","query":number,"time":datetime.utcnow().isoformat()})
        save_json(LOGS_FILE, search_logs)
    except:
        bot.send_message(message.chat.id, "❌ Error fetching Number info.")

# Vehicle
@bot.message_handler(func=lambda m: m.text == "🚘 Vehicle Info")
def ask_vehicle(message):
    if not is_active(message.from_user.id):
        bot.send_message(message.chat.id, "❌ आपका प्लान active नहीं है — पहले प्लान खरीदें या admin से संपर्क करें.")
        return
    bot.send_message(message.chat.id, "कृपया वाहन नंबर भेजें 🚗 (जैसे MH12AB1234)")
    bot.register_next_step_handler(message, fetch_vehicle)

def fetch_vehicle(message):
    number = message.text.strip()
    url = f"https://vehicleapi.vercel.app/info?number={number}"
    try:
        r = requests.get(url, timeout=12)
        data = r.json() if r.status_code == 200 else {}
        result = (
            f"🚘 Vehicle Info\n"
            f"🔢 Reg No: {safe_get(data, ['reg_no','registration'])}\n"
            f"🚗 Model: {safe_get(data, ['model'])}\n"
            f"🏭 Maker: {safe_get(data, ['maker','manufacturer'])}\n"
            f"📅 Reg Date: {safe_get(data, ['reg_date','registration_date'])}\n\n"
            f"👨‍💻 Developer: @instaservice15"
        )
        bot.send_message(message.chat.id, result)
        search_logs.setdefault(str(message.from_user.id), []).append({"type":"vehicle","query":number,"time":datetime.utcnow().isoformat()})
        save_json(LOGS_FILE, search_logs)
    except:
        bot.send_message(message.chat.id, "❌ Error fetching Vehicle info.")

# ==================== RUN BOT ====================
print("🤖 Bot is running... Developer: @instaservice15")
bot.infinity_polling()