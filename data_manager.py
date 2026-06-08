import logging
from typing import Optional
from datetime import datetime

from pymongo import MongoClient, ASCENDING
from pymongo.errors import ConnectionFailure

from config import MONGO_URI, DB_NAME

logger = logging.getLogger(__name__)

client: MongoClient = None
db = None


def init_db():
    global client, db
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
        logger.info("Connected to MongoDB successfully.")
    except ConnectionFailure:
        logger.error("Failed to connect to MongoDB.")
        raise
    db = client[DB_NAME]
    db.group_stats.create_index(
        [("chat_id", ASCENDING), ("date", ASCENDING)], unique=True
    )
    db.message_counters.create_index(
        [("chat_id", ASCENDING), ("date", ASCENDING)], unique=True
    )
    db.message_logs.create_index([("chat_id", ASCENDING), ("date", ASCENDING)])
    logger.info("Database initialized and indexes created.")


def _today():
    return datetime.now().strftime("%Y-%m-%d")


def _today_makkah():
    from utils import get_makkah_time
    return get_makkah_time().strftime("%Y-%m-%d")


def get_group_stats(chat_id: str, date: str = None) -> dict:
    if date is None:
        date = _today_makkah()
    doc = db.group_stats.find_one({"chat_id": str(chat_id), "date": date})
    if doc:
        return doc
    return {"messages": 0, "joined": 0, "left": 0, "pins": 0}


def increment_stat(chat_id: str, stat_key: str, amount: int = 1, date: str = None):
    if date is None:
        date = _today_makkah()
    db.group_stats.update_one(
        {"chat_id": str(chat_id), "date": date},
        {"$inc": {stat_key: amount}},
        upsert=True,
    )


def reset_group_stats(chat_id: str, date: str = None):
    if date is None:
        date = _today_makkah()
    db.group_stats.delete_one({"chat_id": str(chat_id), "date": date})


def get_restart_time(chat_id: str) -> Optional[float]:
    settings = db.settings.find_one({"_id": "bot_settings"})
    if settings:
        return settings.get("restart_times", {}).get(str(chat_id))
    return None


def set_restart_time(chat_id: str, timestamp: float):
    db.settings.update_one(
        {"_id": "bot_settings"},
        {"$set": {f"restart_times.{str(chat_id)}": timestamp}},
        upsert=True,
    )


def get_all_restart_times() -> dict:
    settings = db.settings.find_one({"_id": "bot_settings"})
    if settings:
        return settings.get("restart_times", {})
    return {}


def delete_restart_time(chat_id: str):
    db.settings.update_one(
        {"_id": "bot_settings"},
        {"$unset": {f"restart_times.{str(chat_id)}": ""}},
    )


def register_user(user) -> None:
    db.users.update_one(
        {"_id": str(user.id)},
        {
            "$set": {
                "name": user.first_name,
                "username": user.username or "",
            },
            "$setOnInsert": {"party_id": None},
        },
        upsert=True,
    )


def register_group(chat) -> None:
    if chat.type != "private":
        db.settings.update_one(
            {"_id": "bot_settings"},
            {"$addToSet": {"groups": chat.id}},
            upsert=True,
        )


def get_user_party(user_id) -> tuple:
    user = db.users.find_one({"_id": str(user_id)})
    if user:
        pid = user.get("party_id")
        if pid:
            party = db.parties.find_one({"_id": pid})
            if party:
                return pid, party
    return None, None


def log_message(chat_id: str, user_id: str) -> dict:
    from utils import get_makkah_time

    today = _today_makkah()
    now = get_makkah_time()
    time_str = now.strftime("%H-%M")
    date_str = now.strftime("%y/%-m/%-d")

    result = db.message_counters.find_one_and_update(
        {"chat_id": str(chat_id), "date": today},
        {"$inc": {"count": 1}},
        upsert=True,
        return_document=True,
    )
    count = result["count"]

    formatted = f"{user_id}-{date_str}({time_str})-{count}"

    db.message_logs.insert_one({
        "chat_id": str(chat_id),
        "user_id": str(user_id),
        "date": today,
        "time": time_str,
        "message_number": count,
        "formatted": formatted,
    })

    return {"number": count, "formatted": formatted}
