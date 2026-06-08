import io
import logging

import arabic_reshaper
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import pytz
from hijri_converter import Hijri

from config import REQUIRED_CHANNELS

logger = logging.getLogger(__name__)

MAKKAH_TZ = pytz.timezone("Asia/Riyadh")


def get_makkah_time():
    return datetime.now(MAKKAH_TZ)


def get_hijri_date():
    now = get_makkah_time()
    try:
        hijri = Hijri(now.year, now.month, now.day)
        return hijri
    except (OverflowError, ValueError):
        return None


def get_time_until_restart(restart_timestamp):
    if restart_timestamp is None:
        return None, None
    now = get_makkah_time()
    restart_dt = datetime.fromtimestamp(restart_timestamp, tz=MAKKAH_TZ)
    diff = restart_dt - now
    if diff.total_seconds() <= 0:
        return 0, 0
    total_minutes = int(diff.total_seconds() // 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return hours, minutes


def fix_arabic(text):
    reshaped_text = arabic_reshaper.reshape(text)
    return get_display(reshaped_text)


def get_current_date():
    return datetime.now().strftime("%Y-%m-%d")


async def check_subscription(context, user_id):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    channels_not_subscribed = []
    for channel in REQUIRED_CHANNELS:
        try:
            member = await context.bot.get_chat_member(chat_id=f"@{channel}", user_id=user_id)
            if member.status not in ["member", "administrator", "creator"]:
                channels_not_subscribed.append(channel)
        except Exception:
            channels_not_subscribed.append(channel)
    return channels_not_subscribed


async def force_subscription(update, context):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    user_id = update.effective_user.id
    not_subscribed = await check_subscription(context, user_id)
    if not not_subscribed:
        return True
    buttons = []
    for channel in not_subscribed:
        buttons.append([InlineKeyboardButton(f"اشترك @{channel}", url=f"https://t.me/{channel}")])
    buttons.append([InlineKeyboardButton("اشتكت", callback_data="check_subscription")])
    markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(
        "يجب الاشتراك في القنوات التالية أولاً:",
        reply_markup=markup
    )
    return False


async def check_subscription_cb(update, context):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    not_subscribed = await check_subscription(context, user_id)
    if not not_subscribed:
        await query.message.edit_text("تم التحقق بنجاح! يمكنك استخدام البوت الآن.")
        return True
    buttons = []
    for channel in not_subscribed:
        buttons.append([InlineKeyboardButton(f"اشترك @{channel}", url=f"https://t.me/{channel}")])
    buttons.append([InlineKeyboardButton("اشتكت", callback_data="check_subscription")])
    markup = InlineKeyboardMarkup(buttons)
    await query.message.edit_text(
        "لم تشترك في جميع القنوات بعد:",
        reply_markup=markup
    )
    return False
