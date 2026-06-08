import logging
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters

from data_manager import get_group_stats, get_restart_time, set_restart_time, register_user, increment_stat, log_message
from utils import get_makkah_time, get_hijri_date, get_time_until_restart, force_subscription, check_subscription_cb

logger = logging.getLogger(__name__)

MAX_INTERACTION = 10000


async def interaction_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.effective_chat.type == "private":
        return

    is_subscribed = await force_subscription(update, context)
    if not is_subscribed:
        return

    register_user(update.effective_user)
    chat_id = str(update.effective_chat.id)
    today = get_makkah_time().strftime("%Y-%m-%d")

    stats = get_group_stats(chat_id, today)
    messages = stats.get("messages", 0)
    joined = stats.get("joined", 0)
    left = stats.get("left", 0)
    pins = stats.get("pins", 0)

    percentage = min(100, round((messages / MAX_INTERACTION) * 100, 1))

    now = get_makkah_time()
    makkah_time = now.strftime("%I:%M %p")

    hijri = get_hijri_date()
    hijri_date = f"{hijri.day}/{hijri.month}/{hijri.year}"

    gregorian_date = now.strftime("%Y/%m/%d")

    restart_ts = get_restart_time(chat_id)
    if restart_ts:
        hours, minutes = get_time_until_restart(restart_ts)
        if hours is None:
            restart_text = "تم الانتهاء"
        elif hours == 0 and minutes == 0:
            restart_text = "0 ساعه و 0 دقيقه"
        else:
            restart_text = f"{hours}ساعه و {minutes} دقيقه"
    else:
        restart_text = "غير محدد"

    text = (
        f"- تفاعل المجموعه اليوم ↯.\n"
        f"          ━─━────━────━─━\n"
        f"- انضمام الاعضاء ↫  {joined}\n"
        f"- مغادرة الاعضاء ↫  {left}\n"
        f"- عدد الرسائل ↫  {messages}\n"
        f"- عدد التثبيتات ↫  {pins}\n"
        f"- نسبة التفاعل ↫  {percentage}%\n"
        f"- التوقيت ↫  مكه {makkah_time}\n"
        f"- كم باقي عن الرستارت ↫  {restart_text}\n"
        f"- التاريخ هـ ↫  {hijri_date}\n"
        f"- التاريخ مـ ↫  {gregorian_date}"
    )

    await update.message.reply_text(text)


async def set_restart_mi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or update.effective_chat.type == "private":
        await update.message.reply_text("الاستخدام: /MI [عدد الساعات]")
        return

    is_subscribed = await force_subscription(update, context)
    if not is_subscribed:
        return

    try:
        hours = int(context.args[0])
        if hours <= 0:
            raise ValueError
    except (ValueError, IndexError):
        await update.message.reply_text("أدخل رقم صحيح للساعات")
        return

    chat_id = str(update.effective_chat.id)
    now = get_makkah_time()
    restart_time = now + timedelta(hours=hours)
    restart_timestamp = restart_time.timestamp()
    set_restart_time(chat_id, restart_timestamp)

    await update.message.reply_text(f"تم ضبط الرستارت بعد {hours} ساعات")


async def set_restart_mt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or update.effective_chat.type == "private":
        await update.message.reply_text("الاستخدام: /MT [عدد الدقائق]")
        return

    is_subscribed = await force_subscription(update, context)
    if not is_subscribed:
        return

    try:
        minutes = int(context.args[0])
        if minutes <= 0:
            raise ValueError
    except (ValueError, IndexError):
        await update.message.reply_text("أدخل رقم صحيح للدقائق")
        return

    chat_id = str(update.effective_chat.id)
    now = get_makkah_time()
    restart_time = now + timedelta(minutes=minutes)
    restart_timestamp = restart_time.timestamp()
    set_restart_time(chat_id, restart_timestamp)

    await update.message.reply_text(f"تم ضبط الرستارت بعد {minutes} دقيقة")


async def log_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.effective_chat.type == "private":
        return

    user = update.effective_user
    chat_id = str(update.effective_chat.id)

    register_user(user)
    increment_stat(chat_id, "messages")
    log_message(chat_id, str(user.id))
