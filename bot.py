import logging
import asyncio
import threading
import requests
import os
import time
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)
from instagrapi import Client
from instagrapi.exceptions import UserNotFound, FollowError

# ====== ТАНЗИМОТ ======
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8800072025:AAEJidzl9vC0K2a7aUL9uINnL5vHDg2dnBU")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "7424107874"))
RENDER_URL = os.environ.get("RENDER_URL", "")
PORT = int(os.environ.get("PORT", 8080))
# ======================

accounts = {}
temp_data = {}
logging.basicConfig(level=logging.INFO)

# ============================================================
# 🌐 FLASK KEEP ALIVE
# ============================================================
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "<html><body style='background:#0a0a0a;color:#00ff88;font-family:monospace;text-align:center;padding:50px'><h1>🤖 Online</h1></body></html>"

@flask_app.route("/ping")
def ping_route():
    return {"status": "ok"}

def run_flask():
    flask_app.run(host="0.0.0.0", port=PORT)

def keep_alive():
    def _ping():
        while True:
            try:
                if RENDER_URL:
                    requests.get(f"{RENDER_URL}/ping", timeout=10)
            except:
                pass
            time.sleep(30)
    threading.Thread(target=_ping, daemon=True).start()

# ============================================================
# HELPERS
# ============================================================
def is_admin(update):
    return update.effective_user.id == ADMIN_ID

async def safe_delete(context, chat_id, message_id):
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except:
        pass

async def animate_dots(context, chat_id, msg_id, base_text, steps=3, delay=0.4):
    for i in range(steps):
        dots = "." * ((i % 3) + 1)
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=msg_id,
                text=base_text + dots,
                parse_mode="Markdown"
            )
        except:
            pass
        await asyncio.sleep(delay)

# ============================================================
# KEYBOARDS
# ============================================================
def main_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Аккаунт илова кун", callback_data="add_account")],
        [InlineKeyboardButton("📋 Аккаунтҳо", callback_data="list_accounts"),
         InlineKeyboardButton("📊 Статус", callback_data="status")],
        [InlineKeyboardButton("🚀 Follow фиристан", callback_data="follow_menu")],
        [InlineKeyboardButton("⚙️ URL танзим", callback_data="seturl")],
    ])

def follow_count_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("10 follow", callback_data="fcount_10"),
         InlineKeyboardButton("50 follow", callback_data="fcount_50")],
        [InlineKeyboardButton("100 follow", callback_data="fcount_100"),
         InlineKeyboardButton("300 follow", callback_data="fcount_300")],
        [InlineKeyboardButton("✏️ Дастӣ нависам", callback_data="fcount_custom")],
        [InlineKeyboardButton("🔙 Бозгашт", callback_data="main_menu")],
    ])

def confirm_kb(action):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Ҳа, бале!", callback_data=f"confirm_{action}"),
         InlineKeyboardButton("❌ Не, бекор", callback_data="cancel")],
    ])

def back_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Бозгашт", callback_data="main_menu")]
    ])

def accounts_kb():
    buttons = []
    for num, acc in accounts.items():
        buttons.append([InlineKeyboardButton(
            f"👤 №{num} — @{acc['username']}", callback_data=f"acc_info_{num}"
        )])
    buttons.append([InlineKeyboardButton("🔙 Бозгашт", callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons)

def account_action_kb(num):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑️ Ҳазф кун", callback_data=f"delete_acc_{num}")],
        [InlineKeyboardButton("🔙 Бозгашт", callback_data="list_accounts")],
    ])

# ============================================================
# PROGRESS BAR
# ============================================================
def progress_bar(current, total, width=10):
    filled = int(width * current / total) if total > 0 else 0
    bar = "█" * filled + "░" * (width - filled)
    pct = int(100 * current / total) if total > 0 else 0
    return f"[{bar}] {pct}%"

# ============================================================
# /start
# ============================================================
async def start(update, context):
    if not is_admin(update):
        return
    if update.message:
        await safe_delete(context, update.effective_chat.id, update.message.message_id)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="🤖 *Instagram Follow Bot*\n\nХуш омадед! Функсияро интихоб кунед:",
        parse_mode="Markdown",
        reply_markup=main_menu_kb()
    )

# ============================================================
# CALLBACK HANDLER
# ============================================================
async def callback_handler(update, context):
    query = update.callback_query
    await query.answer()
    if not is_admin(update):
        return

    data = query.data
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    msg_id = query.message.message_id

    # ─── МЕНЮ АСОСӢ ───
    if data == "main_menu":
        context.user_data.clear()
        temp_data.pop(user_id, None)
        await query.edit_message_text(
            "🤖 *Instagram Follow Bot*\n\nФунксияро интихоб кунед:",
            parse_mode="Markdown", reply_markup=main_menu_kb()
        )

    # ─── АККАУНТ ИЛОВА ───
    elif data == "add_account":
        context.user_data.update({"action": "add_account", "waiting": "username", "msg_id": msg_id})
        await query.edit_message_text(
            "➕ *Аккаунт илова кардан*\n\n"
            "📝 Username-и Instagram-ро бифрист:\n_(бе @, масалан: myusername)_",
            parse_mode="Markdown", reply_markup=back_kb()
        )

    # ─── РӮЙХАТИ АККАУНТҲО ───
    elif data == "list_accounts":
        if not accounts:
            await query.edit_message_text(
                "📋 *Аккаунт нест!*\n\n"
                "⚠️ Барои follow фиристан аввал аккаунт илова кунед.\n\n"
                "➕ Аккаунт илова кунед ва баъд follow кунед!",
                parse_mode="Markdown", reply_markup=back_kb()
            )
        else:
            await query.edit_message_text(
                f"📋 *Аккаунтҳои Instagram:*\n_{len(accounts)} аккаунт мавҷуд аст_",
                parse_mode="Markdown", reply_markup=accounts_kb()
            )

    # ─── МАЪЛУМОТИ АККАУНТ ───
    elif data.startswith("acc_info_"):
        num = int(data.split("_")[-1])
        acc = accounts.get(num)
        if not acc:
            await query.edit_message_text("❌ Аккаунт ёфт нашуд!", reply_markup=back_kb())
            return
        try:
            ui = acc["client"].user_info_by_username(acc["username"])
            text = (
                f"👤 *Аккаунт №{num}*\n\n"
                f"📌 Username: @{ui.username}\n"
                f"🏷️ Ном: {ui.full_name or '—'}\n"
                f"👥 Подписчикон: `{ui.follower_count:,}`\n"
                f"➡️ Подписка: `{ui.following_count:,}`\n"
                f"📸 Постҳо: `{ui.media_count:,}`\n"
                f"✅ Verified: {'Ҳа' if ui.is_verified else 'Не'}"
            )
        except Exception as e:
            text = f"👤 *Аккаунт №{num}*\n@{acc['username']}\n❌ Хато: {e}"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=account_action_kb(num))

    # ─── АККАУНТ ҲАЗФ ───
    elif data.startswith("delete_acc_"):
        num = int(data.split("_")[-1])
        if num in accounts:
            username = accounts[num]["username"]
            del accounts[num]
            new_acc = {i: v for i, (k, v) in enumerate(accounts.items(), 1)}
            accounts.clear()
            accounts.update(new_acc)
            await query.edit_message_text(f"🗑️ @{username} муваффақона ҳазф шуд!", reply_markup=back_kb())
        else:
            await query.edit_message_text("❌ Аккаунт ёфт нашуд!", reply_markup=back_kb())

    # ─── СТАТУС ───
    elif data == "status":
        url = RENDER_URL or "❌ Танзим нашудааст"
        await query.edit_message_text(
            f"📊 *Ҳолати сервер:*\n\n"
            f"🟢 Бот: Кор мекунад\n"
            f"👤 Аккаунтҳо: `{len(accounts)}` та\n"
            f"🌐 Render URL: `{url}`\n"
            f"🔌 Port: `{PORT}`\n"
            f"⏰ Keep Alive: 30 сония",
            parse_mode="Markdown", reply_markup=back_kb()
        )

    # ─── FOLLOW MENU ───
    elif data == "follow_menu":
        if not accounts:
            await query.edit_message_text(
                "⚠️ *Аккаунт нест!*\n\n"
                "━━━━━━━━━━━━━━━\n"
                "📭 Шумо ҳоло ягон аккаунт надоред.\n\n"
                "➕ Аввал аккаунт илова кунед,\n"
                "баъд follow фиристед!",
                parse_mode="Markdown", reply_markup=back_kb()
            )
            return
        context.user_data.update({"action": "follow", "waiting": "follow_target", "msg_id": msg_id})
        await query.edit_message_text(
            "🚀 *Follow фиристан*\n\n"
            f"✅ Аккаунтҳо: `{len(accounts)}` та мавҷуд\n\n"
            "📝 Target username-ро бифрист:\n_(масалан: @zadxpro___)_",
            parse_mode="Markdown", reply_markup=back_kb()
        )

    # ─── FOLLOW COUNT ───
    elif data.startswith("fcount_"):
        val = data.split("_")[1]
        td = temp_data.get(user_id, {})
        td["msg_id"] = msg_id

        if val == "custom":
            context.user_data["waiting"] = "follow_count_custom"
            context.user_data["msg_id"] = msg_id
            temp_data[user_id] = td
            await query.edit_message_text(
                "✏️ *Дастӣ нависед*\n\n"
                f"✅ Аккаунтҳо: `{len(accounts)}` та мавҷуд\n\n"
                "📝 Чанд follow мехоҳед фиристед?\n_(рақам нависед, масалан: 25)_",
                parse_mode="Markdown", reply_markup=back_kb()
            )
        else:
            count = int(val)
            td["count"] = count
            temp_data[user_id] = td
            await _start_follow_process(context, chat_id, msg_id, user_id, count)

    # ─── ТАСДИҚ — АККАУНТ ИЛОВА ───
    elif data == "confirm_add":
        td = temp_data.get(user_id, {})
        username = td.get("username")
        password = td.get("password")
        cl_test = td.get("client_test")
        cmsg_id = context.user_data.get("msg_id", msg_id)

        # Анимация
        for i in range(1, 4):
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=cmsg_id,
                    text=f"⏳ Илова мешавад{'.' * i}\n\n👤 @{username}",
                    parse_mode="Markdown"
                )
            except:
                pass
            await asyncio.sleep(0.4)

        try:
            if not cl_test:
                cl_test = Client()
                cl_test.login(username, password)
            ui = cl_test.user_info_by_username(username)
            num = len(accounts) + 1
            accounts[num] = {"client": cl_test, "username": username, "password": password}
            temp_data.pop(user_id, None)

            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=cmsg_id,
                text=(
                    f"╔══════════════════╗\n"
                    f"║  ✅ МУВАФФАҚОНА!  ║\n"
                    f"╚══════════════════╝\n\n"
                    f"📌 Рақам: №{num}\n"
                    f"👤 @{ui.username}\n"
                    f"🏷️ {ui.full_name or '—'}\n"
                    f"👥 Подписчикон: `{ui.follower_count:,}`\n"
                    f"➡️ Подписка: `{ui.following_count:,}`\n"
                    f"📸 Постҳо: `{ui.media_count:,}`\n\n"
                    f"🎉 Аккаунт №{num} омода!"
                ),
                parse_mode="Markdown", reply_markup=back_kb()
            )
        except Exception as e:
            temp_data.pop(user_id, None)
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=cmsg_id,
                text=f"❌ *Хато:*\n`{str(e)}`",
                parse_mode="Markdown", reply_markup=back_kb()
            )

    # ─── БЕКОР КУН ───
    elif data == "cancel":
        temp_data.pop(user_id, None)
        context.user_data.clear()
        await query.edit_message_text("❌ Амал бекор шуд.", reply_markup=back_kb())

    # ─── URL ТАНЗИМ ───
    elif data == "seturl":
        context.user_data.update({"waiting": "render_url", "msg_id": msg_id})
        await query.edit_message_text(
            "⚙️ *Render URL*\n\n📝 URL-ро бифрист:\n_(масалан: https://my-bot.onrender.com)_",
            parse_mode="Markdown", reply_markup=back_kb()
        )

# ============================================================
# FOLLOW PROCESS — АСОСӢ
# ============================================================
async def _start_follow_process(context, chat_id, msg_id, user_id, count):
    td = temp_data.get(user_id, {})
    target = td.get("target")
    acc_count = len(accounts)

    # Санҷиш — агар аккаунт кам бошад
    if acc_count < count:
        warning = (
            f"⚠️ *Аккаунт кам аст!*\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🎯 Дархост: `{count}` follow\n"
            f"👤 Мавҷуд: `{acc_count}` аккаунт\n"
            f"━━━━━━━━━━━━━━━\n\n"
            f"📌 Минималан `1` то `{acc_count}` follow\n"
            f"фиристода мешавад, зеро шумо\n"
            f"танҳо `{acc_count}` аккаунт доред.\n\n"
            f"➕ Аккаунтҳои бештар илова кунед\n"
            f"барои `{count}` follow фиристан!\n\n"
            f"⏳ `{acc_count}` follow оғоз мешавад..."
        )
        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id,
            text=warning, parse_mode="Markdown"
        )
        await asyncio.sleep(2)
        count = acc_count

    # Анимацияи оғоз
    await context.bot.edit_message_text(
        chat_id=chat_id, message_id=msg_id,
        text=(
            f"🚀 *Follow фиристан оғоз шуд!*\n\n"
            f"🎯 Target: @{target}\n"
            f"📊 Ҳаҷм: `{count}` follow\n\n"
            f"⏳ Омода мешавад..."
        ),
        parse_mode="Markdown"
    )
    await asyncio.sleep(1)

    # Натиҷаҳо
    success = 0
    already_followed = 0
    failed = 0
    results = []

    # Маълумоти пеш аз амал
    try:
        first_cl = list(accounts.values())[0]["client"]
        before_info = first_cl.user_info_by_username(target)
        before_count = before_info.follower_count
        target_uid = first_cl.user_id_from_username(target)
    except Exception as e:
        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id,
            text=f"❌ Target ёфт нашуд: `{e}`",
            parse_mode="Markdown", reply_markup=back_kb()
        )
        return

    for i, (num, acc) in enumerate(list(accounts.items())[:count]):
        cl = acc["client"]
        acc_username = acc["username"]

        # Анимацияи ҷараён
        bar = progress_bar(i, count)
        status_text = (
            f"🚀 *Follow фиристан...*\n\n"
            f"🎯 Target: @{target}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"{bar}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"⏳ Аккаунт №{num} (@{acc_username})...\n\n"
            f"✅ Муваффақ: `{success}`\n"
            f"🔄 Аллакай follow: `{already_followed}`\n"
            f"❌ Хато: `{failed}`"
        )

        try:
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=msg_id,
                text=status_text, parse_mode="Markdown"
            )
        except:
            pass

        # Follow кардан
        try:
            cl.user_follow(target_uid)
            success += 1
            results.append(f"✅ №{num} @{acc_username} → follow кард")
        except FollowError as e:
            err_str = str(e).lower()
            if "already" in err_str or "following" in err_str:
                already_followed += 1
                results.append(f"🔄 №{num} @{acc_username} → аллакай follow карда буд")
            else:
                failed += 1
                results.append(f"❌ №{num} @{acc_username} → хато")
        except Exception as e:
            err_str = str(e).lower()
            if "already" in err_str:
                already_followed += 1
                results.append(f"🔄 №{num} @{acc_username} → аллакай follow карда буд")
            else:
                failed += 1
                results.append(f"❌ №{num} @{acc_username} → {str(e)[:30]}")

        await asyncio.sleep(1.5)  # Танаффус

    # Маълумоти баъд аз амал
    await asyncio.sleep(2)
    try:
        after_info = first_cl.user_info_by_username(target)
        after_count = after_info.follower_count
        diff = after_count - before_count
        diff_str = f"+{diff}" if diff >= 0 else str(diff)
    except:
        after_count = before_count
        diff_str = f"+{success}"

    # Натиҷаи ниҳоӣ — Анимация
    for frame in ["📊", "📈", "🎯"]:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=msg_id,
                text=f"{frame} *Ҳисоб мешавад...*",
                parse_mode="Markdown"
            )
        except:
            pass
        await asyncio.sleep(0.3)

    # Натиҷаи охирин
    result_lines = "\n".join(results[-20:])  # Охирин 20 та
    if len(results) > 20:
        result_lines = f"_(Танҳо охирин 20 нишон дода мешавад)_\n\n" + result_lines

    final_text = (
        f"🎉 *Follow фиристан анҷом ёфт!*\n\n"
        f"🎯 Target: @{target}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📊 *Натиҷа:*\n"
        f"✅ Follow шуд: `{success}`\n"
        f"🔄 Аллакай follow: `{already_followed}`\n"
        f"❌ Хато: `{failed}`\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📈 *Подписчикон:*\n"
        f"▪️ Пеш: `{before_count:,}`\n"
        f"▪️ Баъд: `{after_count:,}`\n"
        f"▪️ Тағйир: `{diff_str}`\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"📋 *Тафсилот:*\n{result_lines}"
    )

    # Агар матн хеле дароз бошад
    if len(final_text) > 4000:
        final_text = (
            f"🎉 *Follow анҷом ёфт!*\n\n"
            f"🎯 @{target}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"✅ Follow: `{success}`\n"
            f"🔄 Аллакай: `{already_followed}`\n"
            f"❌ Хато: `{failed}`\n"
            f"━━━━━━━━━━━━━━━\n"
            f"▪️ Пеш: `{before_count:,}`\n"
            f"▪️ Баъд: `{after_count:,}`\n"
            f"▪️ Тағйир: `{diff_str}`"
        )

    temp_data.pop(user_id, None)
    await context.bot.edit_message_text(
        chat_id=chat_id, message_id=msg_id,
        text=final_text, parse_mode="Markdown", reply_markup=back_kb()
    )

# ============================================================
# MESSAGE HANDLER
# ============================================================
async def message_handler(update, context):
    if not is_admin(update):
        return

    waiting = context.user_data.get("waiting")
    action = context.user_data.get("action")
    text = update.message.text.strip()
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    msg_id = context.user_data.get("msg_id")

    await safe_delete(context, chat_id, update.message.message_id)

    if not waiting:
        return

    # ─── USERNAME ───
    if waiting == "username" and action == "add_account":
        username = text.replace("@", "")
        temp_data[user_id] = {"username": username}
        context.user_data["waiting"] = "password"
        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id,
            text=(
                f"➕ *Аккаунт илова кардан*\n\n"
                f"✅ Username: `@{username}`\n\n"
                f"🔑 Акнун паролро бифрист:"
            ),
            parse_mode="Markdown", reply_markup=back_kb()
        )

    # ─── ПАРОЛЬ ───
    elif waiting == "password" and action == "add_account":
        password = text
        td = temp_data.get(user_id, {})
        username = td.get("username", "")
        temp_data[user_id] = {"username": username, "password": password}
        context.user_data["waiting"] = None

        # Анимация
        for i in range(1, 4):
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=msg_id,
                    text=f"🔍 *Санҷиш{'.' * i}*\n\n👤 @{username}",
                    parse_mode="Markdown"
                )
            except:
                pass
            await asyncio.sleep(0.4)

        try:
            cl_test = Client()
            cl_test.login(username, password)
            ui = cl_test.user_info_by_username(username)
            temp_data[user_id]["client_test"] = cl_test

            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=msg_id,
                text=(
                    f"✅ *Маълумот дуруст аст!*\n\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"👤 @{ui.username}\n"
                    f"🏷️ {ui.full_name or '—'}\n"
                    f"👥 Подписчикон: `{ui.follower_count:,}`\n"
                    f"➡️ Подписка: `{ui.following_count:,}`\n"
                    f"📸 Постҳо: `{ui.media_count:,}`\n"
                    f"━━━━━━━━━━━━━━━\n\n"
                    f"❓ *Шумо аниқ мехоҳед илова кунед?*"
                ),
                parse_mode="Markdown", reply_markup=confirm_kb("add")
            )
        except Exception as e:
            temp_data.pop(user_id, None)
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=msg_id,
                text=f"❌ *Username ё пароль нодуруст!*\n\n`{str(e)}`",
                parse_mode="Markdown", reply_markup=back_kb()
            )

    # ─── FOLLOW TARGET ───
    elif waiting == "follow_target":
        target = text.replace("@", "")
        temp_data[user_id] = {"target": target, "msg_id": msg_id}
        context.user_data["waiting"] = None

        try:
            cl = list(accounts.values())[0]["client"]
            ui = cl.user_info_by_username(target)

            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=msg_id,
                text=(
                    f"🎯 *Target маълумот:*\n\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"👤 @{ui.username}\n"
                    f"🏷️ {ui.full_name or '—'}\n"
                    f"👥 Подписчикон: `{ui.follower_count:,}`\n"
                    f"➡️ Подписка: `{ui.following_count:,}`\n"
                    f"━━━━━━━━━━━━━━━\n\n"
                    f"📊 *Чанд follow мехоҳед фиристед?*\n"
                    f"_(Шумо `{len(accounts)}` аккаунт доред)_"
                ),
                parse_mode="Markdown", reply_markup=follow_count_kb()
            )
        except Exception as e:
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=msg_id,
                text=f"❌ Target ёфт нашуд: `{e}`",
                parse_mode="Markdown", reply_markup=back_kb()
            )

    # ─── FOLLOW COUNT ДАСТӢ ───
    elif waiting == "follow_count_custom":
        try:
            count = int(text)
            if count <= 0:
                raise ValueError("Рақам бояд мусбат бошад")
            context.user_data["waiting"] = None
            await _start_follow_process(context, chat_id, msg_id, user_id, count)
        except ValueError:
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=msg_id,
                text="❌ Рақами дуруст ворид кунед!\n_(масалан: 25)_",
                parse_mode="Markdown", reply_markup=back_kb()
            )

    # ─── RENDER URL ───
    elif waiting == "render_url":
        global RENDER_URL
        RENDER_URL = text
        context.user_data["waiting"] = None
        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id,
            text=f"✅ *URL танзим шуд!*\n\n🌐 `{RENDER_URL}`\n⏰ Keep Alive: 30 сония",
            parse_mode="Markdown", reply_markup=back_kb()
        )

# ============================================================
# 🚀 MAIN
# ============================================================
def main():
    threading.Thread(target=run_flask, daemon=True).start()
    keep_alive()

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    logging.info("✅ Бот оғоз шуд!")
    app.run_polling()

if __name__ == "__main__":
    main()