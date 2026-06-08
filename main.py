import logging
from datetime import timedelta

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from telegram.request import HTTPXRequest

from config import BOT_TOKEN
from data_manager import init_db, get_all_restart_times, reset_group_stats, delete_restart_time
from interaction import interaction_handler, set_restart_mi, set_restart_mt, log_message_handler
from utils import check_subscription_cb

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def reset_stats_job(context):
    import time
    now = time.time()
    restart_times = get_all_restart_times()
    for chat_id_str, restart_ts in list(restart_times.items()):
        if restart_ts and now >= restart_ts:
            reset_group_stats(chat_id_str)
            delete_restart_time(chat_id_str)
            try:
                await context.bot.send_message(chat_id=int(chat_id_str), text="تم إعادة تعيين إحصائيات التفاعل!")
            except Exception:
                pass


def main():
    init_db()
    config = HTTPXRequest(connection_pool_size=10, connect_timeout=30, read_timeout=30, write_timeout=30, pool_timeout=30)
    app = Application.builder().token(BOT_TOKEN).request(config).get_updates_request(config).build()

    app.add_handler(CommandHandler("MI", set_restart_mi))
    app.add_handler(CommandHandler("MT", set_restart_mt))

    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS & (filters.Regex(r"^تفاعل$") | filters.Regex(r"^التفاعل$")),
        interaction_handler
    ))

    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS,
        log_message_handler
    ))

    app.add_handler(CallbackQueryHandler(check_subscription_cb, pattern=r"^check_subscription$"))

    jq = app.job_queue
    jq.run_repeating(reset_stats_job, interval=60, first=30)

    print("بوت التفاعل يعمل الآن...")
    app.run_polling()


if __name__ == "__main__":
    main()
