import re
import requests
import json
import os
import time
from datetime import datetime
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

# Bot and SMM API config
BOT_TOKEN = "8022192801:AAGUBcGXj7kkkO6lDu2zToVyptuRkOEDi30"  # New bot token
SMM_API_URL = "https://electrosmm.com/api/v2"  # New API URL
SMM_API_KEY = "c1bf1ad25726b49b42c60d5616a627262363fe40"  # New API key
ADMIN_USER_IDS = [7808280366]  # Updated admin user IDs
DATA_FILE = "data.json"  # File to store credits and QR
SERVICES = {}  # Dynamic service list from API
PRICES = {
    "insta_views": {"name": "Instagram Views", "price": 1.0, "service_id": "3108", "unit": 2000, "min_quantity": 2000},
    "insta_likes": {"name": "Instagram Likes", "price": 10.0, "service_id": "3278", "unit": 100, "min_quantity": 100},
    "insta_followers": {"name": "Instagram Followers", "price": 200.0, "service_id": "3077", "unit": 1000, "min_quantity": 1000}
}  # Pre-added services
USER_CREDITS = {}  # Store user credits
PENDING_PAYMENTS = {}  # Store pending payments
MIN_CREDIT_BUY = 10  # Minimum buy amount in INR
QR_PHOTO = None  # Stores QR code photo file_id

def load_data():
    """Load USER_CREDITS and QR_PHOTO from data.json."""
    global USER_CREDITS, QR_PHOTO
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                USER_CREDITS.update({str(k): v for k, v in data.get('credits', {}).items()})
                QR_PHOTO = data.get('qr_photo', None)
                print(f"[DEBUG] Loaded data: {len(USER_CREDITS)} users, QR: {QR_PHOTO}")
        else:
            print("[DEBUG] No data file found, starting fresh")
    except Exception as e:
        print(f"[DEBUG] Error loading data: {str(e)}")

def save_data():
    """Save USER_CREDITS and QR_PHOTO to data.json."""
    try:
        data = {
            'credits': USER_CREDITS,
            'qr_photo': QR_PHOTO
        }
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f)
        print(f"[DEBUG] Data saved to data.json")
    except Exception as e:
        print(f"[DEBUG] Error saving data: {str(e)}")

def fetch_services():
    """Fetch services from SMM API with retry logic."""
    retries = 3
    for attempt in range(retries):
        try:
            payload = {"key": SMM_API_KEY, "action": "services"}
            response = requests.post(SMM_API_URL, data=payload, timeout=15)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list):
                global SERVICES
                SERVICES = {str(service["service"]): {"name": service["name"], "rate": float(service["rate"])} for service in data if "rate" in service}
                print(f"[DEBUG] Fetched {len(SERVICES)} services from API")
                return True
            else:
                print(f"[DEBUG] Failed to fetch services: {data.get('error', 'Unknown error')}")
                return False
        except Exception as e:
            print(f"[DEBUG] Attempt {attempt + 1}/{retries} failed: {str(e)}")
            if attempt < retries - 1:
                time.sleep(5)
            else:
                print(f"[DEBUG] All retries failed for fetch_services")
                return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome_msg = (
        f"👋 Welcome to RolexSMM Bot, {user.first_name}!\n"
        f"User ID: {user.id}\n"
        "Built by RolexSMM, we offer the cheapest rates for social media services.\n"
        "📋 Use /services to view available services and prices.\n"
        "💰 Use /buycredits to add credits (1 Credit = 1 INR, min 10 INR).\n"
        "🔍 Use /balance to check your credits.\n"
        "📦 Use /order to place an order.\n"
        "📊 Use /status <order_id> to check order status.\n"
        "❌ Use /cancel to stop any ongoing process.\n"
        "🗑️ Use /delete to remove a service.\n"
        "Note: YouTube views is completed by native ads monetize to so you are safee monetizaio complete in 7 days.\n"
        "Note: All services have minimum quantity of 1000 or more, not 100 ok.\n"
        "Contact RolexSMM for support."
    )
    await update.message.reply_text(welcome_msg)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    context.user_data.clear()  # Clear all user states
    if user_id in PENDING_PAYMENTS:
        del PENDING_PAYMENTS[user_id]  # Remove pending payment
    await update.message.reply_text("✅ All ongoing processes cancelled. Start fresh with /buycredits or /order.")
    print(f"[DEBUG] User {user_id} cancelled all processes")

async def services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not PRICES:
        await update.message.reply_text("🚫 No services added yet. Contact RolexSMM admins.")
        print(f"[DEBUG] /services failed: PRICES empty")
        return
    response = "📋 Available Services:\n\n"
    for key, info in PRICES.items():
        response += f"{info['name']}: ₹{info['price']} per {info['unit']} (Min: {info['min_quantity']})\n"
    await update.message.reply_text(response)
    print(f"[DEBUG] Services displayed: {list(PRICES.keys())}")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    credits = USER_CREDITS.get(user_id, 0)
    await update.message.reply_text(f"💰 Your balance: {credits} Credits (1 Credit = 1 INR)")

async def buycredits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if QR_PHOTO is None:
        await update.message.reply_text("🚫 No QR code set. Contact RolexSMM admins.")
        return
    await update.message.reply_text("💰 How many credits do you want to buy? (Minimum 10 INR, e.g., 100)")
    context.user_data["state"] = "awaiting_credit_amount"

async def order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global PRICES  # Declare global at the start
    user_id = str(update.effective_user.id)
    if not PRICES:
        # Reinitialize default services if PRICES is empty
        PRICES = {
            "insta_views": {"name": "Instagram Views", "price": 1.0, "service_id": "3108", "unit": 2000, "min_quantity": 2000},
            "insta_likes": {"name": "Instagram Likes", "price": 10.0, "service_id": "3278", "unit": 100, "min_quantity": 100},
            "insta_followers": {"name": "Instagram Followers", "price": 200.0, "service_id": "3077", "unit": 1000, "min_quantity": 1000}
        }
        print(f"[DEBUG] PRICES was empty, reinitialized with insta_views, insta_likes, insta_followers")
    keyboard = [[InlineKeyboardButton(f"📊 {info['name']}", callback_data=f"order_service_{key}")]
                for key, info in PRICES.items()]
    if not keyboard:
        await update.message.reply_text("🚫 No services available. Contact RolexSMM admins.")
        print(f"[DEBUG] /order failed: No buttons generated, PRICES: {list(PRICES.keys())}")
        return
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📦 Select a service to order:", reply_markup=reply_markup)
    context.user_data["state"] = "awaiting_service_selection"
    print(f"[DEBUG] /order called by {user_id}, PRICES: {list(PRICES.keys())}, Buttons: {[btn[0].text for btn in keyboard]}")

async def delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_USER_IDS:
        await update.message.reply_text("🚫 Only RolexSMM admins can delete services.")
        return
    if not PRICES:
        await update.message.reply_text("🚫 No services to delete. Add with /addservice.")
        return
    keyboard = [[InlineKeyboardButton(f"🗑️ Delete {info['name']}", callback_data=f"delete_service_{key}")]
                for key, info in PRICES.items()]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🗑️ Select a service to delete:", reply_markup=reply_markup)
    context.user_data["state"] = "awaiting_delete_selection"
    print(f"[DEBUG] /delete called by {update.effective_user.id}, PRICES: {list(PRICES.keys())}")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        args = context.args
        if len(args) != 1:
            await update.message.reply_text("Format: /status order_id\nExample: /status 123456")
            return
        order_id = args[0]
        payload = {
            "key": SMM_API_KEY,
            "action": "status",
            "order": order_id
        }
        response = requests.post(SMM_API_URL, data=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        if "status" in data:
            await update.message.reply_text(
                f"📊 Order Status:\n"
                f"Order ID: {order_id}\n"
                f"Status: {data['status']}\n"
                f"Start Count: {data.get('start_count', 'N/A')}\n"
                f"Remains: {data.get('remains', 'N/A')}\n"
                f"Currency: {data.get('currency', 'N/A')}\n"
                f"Charge: {data.get('charge', 'N/A')}"
            )
        else:
            await update.message.reply_text(f"🚫 Error: {data.get('error', 'Failed to fetch status')}")
    except Exception as e:
        await update.message.reply_text(f"🚫 Error: {str(e)}")

async def updateprices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_USER_IDS:
        await update.message.reply_text("🚫 Only RolexSMM admins can update prices.")
        return
    try:
        args = context.args
        if len(args) != 2:
            await update.message.reply_text("Format: /updateprices key price\nExample: /updateprices insta_followers 200.0")
            return
        key, price = args
        if key not in PRICES:
            await update.message.reply_text(f"🚫 Invalid service key. Available: {', '.join(PRICES.keys()) if PRICES else 'None'}")
            return
        price = float(price)
        if price < 0.1:
            await update.message.reply_text("🚫 Price must be at least 0.1.")
            return
        PRICES[key]["price"] = price
        await update.message.reply_text(f"✅ Updated {PRICES[key]['name']} to ₹{price} per {PRICES[key]['unit']}")
        print(f"[DEBUG] Price updated: {key} to ₹{price}, PRICES: {list(PRICES.keys())}")
    except Exception as e:
        await update.message.reply_text(f"🚫 Error: {str(e)}")

async def updateqr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_USER_IDS:
        await update.message.reply_text("🚫 Only RolexSMM admins can update QR code.")
        return
    await update.message.reply_text("📸 Please send the new QR code photo.")
    context.user_data["state"] = "awaiting_qr_photo"

async def addservice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_USER_IDS:
        await update.message.reply_text("🚫 Only RolexSMM admins can add services.")
        return
    try:
        args = context.args
        if len(args) == 1:
            service_id = args[0]
            if not SERVICES:
                if not fetch_services():
                    keyboard = [
                        [InlineKeyboardButton("Yes", callback_data=f"confirm_service_manual_{service_id}"),
                         InlineKeyboardButton("No", callback_data="cancel_service")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await update.message.reply_text(
                        f"🚫 Failed to fetch services from API. Confirm manually adding service ID {service_id}?",
                        reply_markup=reply_markup
                    )
                    context.user_data["state"] = "awaiting_service_confirmation"
                    print(f"[DEBUG] API failed, prompting manual confirmation for service_id: {service_id}")
                    return
            if service_id not in SERVICES:
                keyboard = [
                    [InlineKeyboardButton("Yes", callback_data=f"confirm_service_manual_{service_id}"),
                     InlineKeyboardButton("No", callback_data="cancel_service")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    f"🚫 Invalid service ID: {service_id}. Fetch services with: curl -X POST {SMM_API_URL} -d \"key={SMM_API_KEY}&action=services\"\n"
                    f"Confirm manually adding service ID {service_id}?",
                    reply_markup=reply_markup
                )
                context.user_data["state"] = "awaiting_service_confirmation"
                print(f"[DEBUG] Invalid service_id {service_id}, prompting manual confirmation")
                return
            name = SERVICES[service_id]["name"]
            rate = SERVICES[service_id]["rate"]
            price = rate * 1.3  # Add 30% markup
            key = re.sub(r'[^a-z0-9]', '_', name.lower().replace('instagram', 'insta').replace('youtube', 'yt'))
            unit = 2000 if "views" in name.lower() else 1000 if "followers" in name.lower() else 100
            min_quantity = 2000 if "views" in name.lower() else 1000 if "followers" in name.lower() else 100
            PRICES[key] = {"name": name, "price": price, "service_id": service_id, "unit": unit, "min_quantity": min_quantity}
            await update.message.reply_text(f"✅ Added service: {name}, ₹{price} per {unit} (Min: {min_quantity})")
            context.user_data.clear()  # Clear state after addition
            print(f"[DEBUG] Service added from ID: {key}, {name}, ₹{price}, ID: {service_id}, PRICES: {list(PRICES.keys())}")
            return
        elif len(args) != 4:
            await update.message.reply_text("Format: /addservice key name price service_id\nOr: /addservice service_id (auto-fetch name/price + 30%)")
            return
        key, name, price, service_id = args
        if not SERVICES:
            if not fetch_services():
                keyboard = [
                    [InlineKeyboardButton("Yes", callback_data=f"confirm_service_{key}_{name}_{price}_{service_id}_1000_1000"),
                     InlineKeyboardButton("No", callback_data="cancel_service")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    f"🚫 Failed to fetch services from API. Confirm manually adding service ID {service_id} ({name}, ₹{price}/1000)?",
                    reply_markup=reply_markup
                )
                context.user_data["state"] = "awaiting_service_confirmation"
                print(f"[DEBUG] API failed, prompting manual confirmation for service_id: {service_id}")
                return
        if service_id not in SERVICES:
            keyboard = [
                [InlineKeyboardButton("Yes", callback_data=f"confirm_service_{key}_{name}_{price}_{service_id}_1000_1000"),
                 InlineKeyboardButton("No", callback_data="cancel_service")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"🚫 Invalid service ID: {service_id}. Fetch services with: curl -X POST {SMM_API_URL} -d \"key={SMM_API_KEY}&action=services\"\n"
                f"Confirm manually adding service ID {service_id} ({name}, ₹{price}/1000)?",
                reply_markup=reply_markup
            )
            context.user_data["state"] = "awaiting_service_confirmation"
            print(f"[DEBUG] Invalid service_id {service_id}, prompting manual confirmation")
            return
        price = float(price)
        if price < 0.1:
            await update.message.reply_text("🚫 Price must be at least 0.1.")
            return
        unit = 2000 if "views" in name.lower() else 1000 if "followers" in name.lower() else 100
        min_quantity = 2000 if "views" in name.lower() else 1000 if "followers" in name.lower() else 100
        PRICES[key] = {"name": name, "price": price, "service_id": service_id, "unit": unit, "min_quantity": min_quantity}
        await update.message.reply_text(f"✅ Added service: {name}, ₹{price} per {unit} (Min: {min_quantity})")
        context.user_data.clear()  # Clear state after addition
        print(f"[DEBUG] Service added manually: {key}, {name}, ₹{price}, ID: {service_id}, PRICES: {list(PRICES.keys())}")
    except Exception as e:
        await update.message.reply_text(f"🚫 Error: {str(e)}")
        print(f"[DEBUG] Error in addservice: {str(e)}")

async def addcredits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_USER_IDS:
        await update.message.reply_text("🚫 Only RolexSMM admins can use /addcredits.")
        return
    try:
        args = context.args
        if len(args) != 2:
            await update.message.reply_text("Format: /addcredits user_id amount\nExample: /addcredits 123456789 100")
            return
        user_id, amount = args
        amount = float(amount)
        USER_CREDITS[user_id] = USER_CREDITS.get(user_id, 0) + amount
        save_data()  # Save credits to file
        await update.message.reply_text(f"✅ Added {amount} credits to user {user_id}")
        await context.bot.send_message(user_id, f"🎉 Your RolexSMM account credited with {amount} credits on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}. Thanks for adding balance!")
    except Exception as e:
        await update.message.reply_text(f"🚫 Error: {str(e)}")

async def received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_USER_IDS:
        await update.message.reply_text("🚫 Only RolexSMM admins can use /received.")
        return
    try:
        args = context.args
        if len(args) != 2:
            await update.message.reply_text("Format: /received user_id amount\nExample: /received 123456789 100")
            return
        user_id, amount = args
        amount = float(amount)
        USER_CREDITS[user_id] = USER_CREDITS.get(user_id, 0) + amount
        save_data()  # Save credits to file
        await update.message.reply_text(f"✅ Added {amount} credits to user {user_id}")
        await context.bot.send_message(user_id, f"🎉 Payment successful! Your RolexSMM account credited with {amount} credits on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}. Thanks for adding balance!")
    except Exception as e:
        await update.message.reply_text(f"🚫 Error: {str(e)}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global QR_PHOTO
    user_id = str(update.effective_user.id)
    
    # Handle QR photo uploads
    if context.user_data.get("state") == "awaiting_qr_photo":
        if update.message.photo:
            QR_PHOTO = update.message.photo[-1].file_id
            save_data()  # Save QR to file
            await update.message.reply_text("✅ QR code photo uploaded successfully!")
            context.user_data["state"] = None
            print(f"[DEBUG] QR photo updated by {update.effective_user.username or 'None'}, file_id: {QR_PHOTO}")
        else:
            await update.message.reply_text("🚫 Please send a valid QR code photo.")
            print(f"[DEBUG] Non-photo message received in awaiting_qr_photo: {update.message.text or 'No text'}")
        return
    
    # Handle credit amount
    if context.user_data.get("state") == "awaiting_credit_amount":
        try:
            amount = float(update.message.text.strip())
            if amount < MIN_CREDIT_BUY:
                await update.message.reply_text(f"🚫 Invalid amount. Minimum is {MIN_CREDIT_BUY} INR.")
                return
            PENDING_PAYMENTS[user_id] = amount
            keyboard = [[InlineKeyboardButton("Paid", callback_data=f"paid_{user_id}_{amount}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_photo(QR_PHOTO, caption=f"💳 Pay ₹{amount} using the QR code above.\nAfter payment, click 'Paid' to send screenshot.", reply_markup=reply_markup)
            context.user_data["state"] = "awaiting_paid_click"
            print(f"[DEBUG] Credit amount {amount} set for user {user_id}")
        except ValueError:
            await update.message.reply_text("🚫 Invalid amount. Enter a number (e.g., 100).")
        except AttributeError:
            await update.message.reply_text("🚫 No QR code set. Contact RolexSMM admins.")
        return
    
    # Handle quantity for order
    if context.user_data.get("state") == "awaiting_quantity":
        try:
            quantity = int(update.message.text.strip())
            service = context.user_data.get("service")
            if service not in PRICES:
                await update.message.reply_text("🚫 Invalid service. Try /order again.")
                context.user_data.clear()  # Clear state
                print(f"[DEBUG] Invalid service {service} for user {user_id}")
                return
            min_quantity = PRICES[service]["min_quantity"]
            if quantity < min_quantity:
                await update.message.reply_text(f"🚫 Quantity must be at least {min_quantity}.")
                print(f"[DEBUG] Invalid quantity {quantity} for service {service}, min: {min_quantity}")
                return
            context.user_data["quantity"] = quantity
            link_prompt = f"🔗 Enter the link for {PRICES[service]['name']} (e.g., https://instagram.com/p/xyz)"
            if service == "insta_followers":
                link_prompt += "\nPlease send the profiles link, profiles must be public. Turn flag for review off. If flag for review on, money not can be refunded ok."
            await update.message.reply_text(link_prompt)
            context.user_data["state"] = "awaiting_link"
            print(f"[DEBUG] Quantity {quantity} set for user {user_id}, service: {service}")
        except ValueError:
            await update.message.reply_text("🚫 Invalid quantity. Enter a number (e.g., 1000).")
            print(f"[DEBUG] Invalid quantity input for user {user_id}: {update.message.text}")
        return
    
    # Handle link for order
    if context.user_data.get("state") == "awaiting_link":
        link = update.message.text.strip()
        if not re.match(r"^https?://", link):
            await update.message.reply_text("🚫 Invalid link. Must start with http:// or https://.")
            print(f"[DEBUG] Invalid link for user {user_id}: {link}")
            return
        user_id = str(update.effective_user.id)
        service = context.user_data.get("service")
        quantity = context.user_data.get("quantity")
        try:
            if not SERVICES:
                if not fetch_services():
                    await update.message.reply_text("🚫 Failed to fetch services from API. Contact RolexSMM admins.")
                    print(f"[DEBUG] Failed to fetch services for order by {user_id}")
                    return
            service_id = PRICES[service]["service_id"]
            if service_id not in SERVICES:
                await update.message.reply_text(f"🚫 Invalid service ID: {service_id}. Contact RolexSMM admins.")
                print(f"[DEBUG] Invalid service_id {service_id} for order by {user_id}")
                return
            cost = PRICES[service]["price"] * (quantity / PRICES[service]["unit"])
            if USER_CREDITS.get(user_id, 0) < cost:
                await update.message.reply_text(f"🚫 Insufficient credits. Need {cost} credits, you have {USER_CREDITS.get(user_id, 0)}. Use /buycredits.")
                print(f"[DEBUG] Insufficient credits for user {user_id}: need {cost}, have {USER_CREDITS.get(user_id, 0)}")
                return
            
            # Place order via SMM API with retry
            retries = 3
            for attempt in range(retries):
                try:
                    payload = {
                        "key": SMM_API_KEY,
                        "action": "add",
                        "service": service_id,
                        "link": link,
                        "quantity": quantity
                    }
                    print(f"[DEBUG] Sending API payload for user {user_id}: {payload}")
                    response = requests.post(SMM_API_URL, data=payload, timeout=15)
                    response.raise_for_status()
                    data = response.json()
                    break
                except Exception as e:
                    print(f"[DEBUG] Attempt {attempt + 1}/{retries} failed for order: {str(e)}")
                    if attempt < retries - 1:
                        time.sleep(5)
                    else:
                        await update.message.reply_text(f"🚫 Error placing order: {str(e)}")
                        print(f"[DEBUG] Order failed for user {user_id} after {retries} attempts")
                        return
            
            if "order" in data:
                USER_CREDITS[user_id] -= cost
                save_data()  # Save credits after order
                await update.message.reply_text(
                    f"✅ Order placed!\n"
                    f"Service: {PRICES[service]['name']}\n"
                    f"Quantity: {quantity}\n"
                    f"Link: {link}\n"
                    f"Order ID: {data['order']}\n"
                    f"Cost: {cost} credits\n"
                    f"Remaining Balance: {USER_CREDITS[user_id]} credits\n"
                    f"Check status with /status {data['order']}"
                )
                context.user_data["state"] = None
                print(f"[DEBUG] Order placed for user {user_id}, service: {service}, order_id: {data['order']}, quantity: {quantity}")
            else:
                await update.message.reply_text(f"🚫 Error: {data.get('error', 'Failed to place order')}")
                print(f"[DEBUG] API error for user {user_id}: {data}")
        except Exception as e:
            await update.message.reply_text(f"🚫 Error: {str(e)}")
            print(f"[DEBUG] Order error for user {user_id}: {str(e)}")
        return
    
    # Handle screenshot uploads
    if context.user_data.get("state") == "awaiting_screenshot":
        if update.message.photo:
            amount = PENDING_PAYMENTS.get(user_id, 0)
            screenshot = update.message.photo[-1].file_id
            keyboard = [[InlineKeyboardButton("Received", callback_data=f"received_{user_id}_{amount}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            for admin_id in ADMIN_USER_IDS:
                try:
                    await context.bot.send_photo(
                        admin_id,
                        screenshot,
                        caption=(
                            f"🔔 New Payment Request\n"
                            f"User ID: {user_id}\n"
                            f"Username: @{update.effective_user.username or 'None'}\n"
                            f"Amount: ₹{amount}\n"
                            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                            f"\n📌 Please verify the payment amount in the screenshot.\n"
                            f"Click 'Received' to approve if amount matches."
                        ),
                        reply_markup=reply_markup
                    )
                    print(f"[DEBUG] Payment request sent to admin {admin_id}")
                except Exception as e:
                    print(f"[DEBUG] Failed to send payment request to admin {admin_id}: {str(e)}")
            await update.message.reply_text("✅ Payment request submitted!")
            context.user_data["state"] = None
            print(f"[DEBUG] Screenshot sent for user {user_id}, amount: {amount}")
        else:
            await update.message.reply_text("🚫 Please send a valid payment screenshot.")
            print(f"[DEBUG] Non-photo sent in awaiting_screenshot for user {user_id}")
        return

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    
    if query.data.startswith("order_service_"):
        try:
            service = query.data[len("order_service_"):]  # Extract service key
            print(f"[DEBUG] Button callback received: {query.data}, extracted service: {service}, PRICES keys: {list(PRICES.keys())}")
            if service not in PRICES:
                await query.message.reply_text("🚫 Invalid service selected. Try /order again.")
                context.user_data.clear()  # Clear state to prevent corruption
                print(f"[DEBUG] Invalid service {service} selected by user {user_id}")
                return
            context.user_data["service"] = service
            context.user_data["state"] = "awaiting_quantity"
            await query.message.reply_text(f"🔢 Enter quantity for {PRICES[service]['name']} (Min: {PRICES[service]['min_quantity']}):")
            print(f"[DEBUG] Service {service} selected by user {user_id}, min_quantity: {PRICES[service]['min_quantity']}")
        except Exception as e:
            await query.message.reply_text("🚫 Error processing button. Try /order again.")
            context.user_data.clear()
            print(f"[DEBUG] Button callback error for user {user_id}: {str(e)}")
    
    elif query.data.startswith("delete_service_"):
        if query.from_user.id not in ADMIN_USER_IDS:
            await query.message.reply_text("🚫 Only RolexSMM admins can delete services.")
            return
        try:
            service_key = query.data[len("delete_service_"):]
            if service_key in PRICES:
                service_name = PRICES[service_key]["name"]
                del PRICES[service_key]
                await query.message.edit_text(f"✅ Service '{service_name}' deleted! Use /services to verify.")
                context.user_data["state"] = None
                print(f"[DEBUG] Service deleted: {service_key}, PRICES now: {list(PRICES.keys())}")
            else:
                await query.message.edit_text("🚫 Service not found. Try /delete again.")
                print(f"[DEBUG] Service {service_key} not found for deletion by user {user_id}")
        except Exception as e:
            await query.message.reply_text("🚫 Error deleting service. Try /delete again.")
            print(f"[DEBUG] Delete service error: {str(e)}")
    
    elif query.data.startswith("paid_"):
        try:
            amount = float(query.data.split("_")[2])
            PENDING_PAYMENTS[user_id] = amount
            await query.message.reply_text("📸 Now send the payment screenshot.")
            context.user_data["state"] = "awaiting_screenshot"
            print(f"[DEBUG] Paid button clicked for user {user_id}, amount: {amount}")
        except Exception as e:
            await query.message.reply_text("🚫 Error processing payment button. Try /buycredits again.")
            print(f"[DEBUG] Paid button error for user {user_id}: {str(e)}")
    
    elif query.data.startswith("received_"):
        if query.from_user.id not in ADMIN_USER_IDS:
            await query.message.reply_text("🚫 Only RolexSMM admins can approve.")
            return
        try:
            parts = query.data.split("_")
            user_id = parts[1]
            amount = float(parts[2])
            if PENDING_PAYMENTS.get(user_id, 0) == amount:
                USER_CREDITS[user_id] = USER_CREDITS.get(user_id, 0) + amount
                del PENDING_PAYMENTS[user_id]
                save_data()  # Save credits after approval
                await query.message.edit_caption(caption=query.message.caption + "\n✅ Approved!")
                try:
                    await context.bot.send_message(user_id, f"🎉 Payment successful! Your RolexSMM account credited with {amount} credits on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}. Thanks for adding balance!")
                    print(f"[DEBUG] Payment approved for user {user_id}, amount: {amount}")
                except Exception as e:
                    print(f"[DEBUG] Failed to notify user {user_id}: {str(e)}")
            else:
                await query.message.reply_text("🚫 Amount mismatch. Payment not approved.")
                print(f"[DEBUG] Amount mismatch for user {user_id}, expected {PENDING_PAYMENTS.get(user_id, 0)}, got {amount}")
        except Exception as e:
            await query.message.reply_text("🚫 Error approving payment.")
            print(f"[DEBUG] Received button error for user {user_id}: {str(e)}")
    
    elif query.data.startswith("confirm_service_"):
        if query.from_user.id not in ADMIN_USER_IDS:
            await query.message.reply_text("🚫 Only RolexSMM admins can confirm services.")
            return
        try:
            parts = query.data.split("_")
            key, name, price, service_id, unit, min_quantity = parts[1], parts[2], float(parts[3]), parts[4], int(parts[5]), int(parts[6])
            PRICES[key] = {"name": name, "price": price, "service_id": service_id, "unit": unit, "min_quantity": min_quantity}
            await query.message.edit_text(f"✅ Added service: {name}, ₹{price} per {unit} (Min: {min_quantity})")
            context.user_data["state"] = None
            print(f"[DEBUG] Service confirmed: {key}, {name}, ₹{price}, ID: {service_id}, PRICES: {list(PRICES.keys())}")
        except Exception as e:
            await query.message.reply_text("🚫 Error confirming service.")
            print(f"[DEBUG] Confirm service error: {str(e)}")
    
    elif query.data.startswith("confirm_service_manual_"):
        if query.from_user.id not in ADMIN_USER_IDS:
            await query.message.reply_text("🚫 Only RolexSMM admins can confirm services.")
            return
        try:
            service_id = query.data.split("_")[3]
            name = f"Service {service_id}"  # Placeholder name
            price = 1.0 if service_id == "3108" else 200.0 if service_id == "3077" else 10.0 if service_id == "3278" else 0.5  # Default prices
            key = f"service_{service_id}"
            unit = 2000 if service_id == "3108" else 1000 if service_id == "3077" else 100
            min_quantity = 2000 if service_id == "3108" else 1000 if service_id == "3077" else 100
            PRICES[key] = {"name": name, "price": price, "service_id": service_id, "unit": unit, "min_quantity": min_quantity}
            await query.message.edit_text(f"✅ Added service: {name}, ₹{price} per {unit} (Min: {min_quantity})")
            context.user_data["state"] = None
            print(f"[DEBUG] Service confirmed manual: {key}, {name}, ₹{price}, ID: {service_id}, PRICES: {list(PRICES.keys())}")
        except Exception as e:
            await query.message.reply_text("🚫 Error confirming manual service.")
            print(f"[DEBUG] Confirm manual service error: {str(e)}")
    
    elif query.data == "cancel_service":
        await query.message.edit_text("🚫 Service addition cancelled.")
        context.user_data["state"] = None
        print(f"[DEBUG] Service addition cancelled by user {user_id}")

def main():
    load_data()  # Load credits and QR on startup
    fetch_services()  # Fetch services on startup
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("services", services))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("buycredits", buycredits))
    app.add_handler(CommandHandler("order", order))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("delete", delete))
    app.add_handler(CommandHandler("updateprices", updateprices))
    app.add_handler(CommandHandler("updateqr", updateqr))
    app.add_handler(CommandHandler("addservice", addservice))
    app.add_handler(CommandHandler("addcredits", addcredits))
    app.add_handler(CommandHandler("received", received))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("[DEBUG] Bot started)
    app.run_polling()

if __name__ = "__main__":
    main()