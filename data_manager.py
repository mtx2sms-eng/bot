import logging
import os
from typing import Optional, Any
from datetime import datetime

from config import MONGO_URI, DB_NAME

logger = logging.getLogger(__name__)

client = None
db = None
USE_MONGITA = False


def init_db():
    global client, db, USE_MONGITA
    if MONGO_URI:
        from pymongo import MongoClient, ASCENDING
        from pymongo.errors import ConnectionFailure
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        try:
            client.admin.command("ping")
            logger.info("Connected to MongoDB successfully.")
        except ConnectionFailure:
            logger.error("Failed to connect to MongoDB.")
            raise
        db = client[DB_NAME]
        db.group_stats.create_index([("chat_id", ASCENDING), ("date", ASCENDING)], unique=True)
        db.message_counters.create_index([("chat_id", ASCENDING), ("date", ASCENDING)], unique=True)
        db.message_logs.create_index([("chat_id", ASCENDING), ("date", ASCENDING)])
        USE_MONGITA = False
    else:
        from mongita import MongitaClientDisk
        data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_data")
        client = MongitaClientDisk(data_dir)
        db = client[DB_NAME]
        USE_MONGITA = True
        logger.info("Using local mongita database at %s", data_dir)


def _today_makkah():
    from utils import get_makkah_time
    return get_makkah_time().strftime("%Y-%m-%d")


def _upsert(collection, filter_doc, update_doc):
    doc = collection.find_one(filter_doc)
    if doc is None:
        init_doc = dict(filter_doc)
        for op, fields in update_doc.items():
            if op == "$inc":
                for k, v in fields.items():
                    init_doc[k] = v
            elif op == "$set":
                for k, v in fields.items():
                    init_doc[k] = v
        collection.insert_one(init_doc)
    else:
        collection.update_one(filter_doc, update_doc)


def _upsert_nested(collection, filter_doc, set_fields: dict):
    doc = collection.find_one(filter_doc)
    if doc is None:
        init_doc = dict(filter_doc)
        for k, v in set_fields.items():
            parts = k.split(".")
            current = init_doc
            for part in parts[:-1]:
                current = current.setdefault(part, {})
            current[parts[-1]] = v
        collection.insert_one(init_doc)
    else:
        collection.update_one(filter_doc, {"$set": set_fields})


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
    filter_doc = {"chat_id": str(chat_id), "date": date}
    if USE_MONGITA:
        _upsert(db.group_stats, filter_doc, {"$inc": {stat_key: amount}})
    else:
        db.group_stats.update_one(filter_doc, {"$inc": {stat_key: amount}}, upsert=True)


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
    key = f"restart_times.{str(chat_id)}"
    if USE_MONGITA:
        _upsert_nested(db.settings, {"_id": "bot_settings"}, {key: timestamp})
    else:
        db.settings.update_one(
            {"_id": "bot_settings"},
            {"$set": {key: timestamp}},
            upsert=True,
        )


def get_all_restart_times() -> dict:
    settings = db.settings.find_one({"_id": "bot_settings"})
    if settings:
        return settings.get("restart_times", {})
    return {}


def delete_restart_time(chat_id: str):
    settings = db.settings.find_one({"_id": "bot_settings"})
    if settings:
        rt = settings.get("restart_times", {})
        key = str(chat_id)
        if key in rt:
            del rt[key]
            db.settings.update_one(
                {"_id": "bot_settings"},
                {"$set": {"restart_times": rt}},
            )


def register_user(user) -> None:
    uid = str(user.id)
    doc = db.users.find_one({"_id": uid})
    if doc is None:
        db.users.insert_one({
            "_id": uid,
            "name": user.first_name,
            "username": user.username or "",
            "party_id": None,
        })
    else:
        db.users.update_one(
            {"_id": uid},
            {"$set": {"name": user.first_name, "username": user.username or ""}},
        )


def register_group(chat) -> None:
    if chat.type != "private":
        settings = db.settings.find_one({"_id": "bot_settings"})
        if settings is None:
            db.settings.insert_one({"_id": "bot_settings", "groups": [chat.id], "restart_times": {}})
        else:
            groups = settings.get("groups", [])
            if chat.id not in groups:
                groups.append(chat.id)
                db.settings.update_one({"_id": "bot_settings"}, {"$set": {"groups": groups}})


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
    date_str = now.strftime("%y/%#m/%#d")

    counter_filter = {"chat_id": str(chat_id), "date": today}
    counter_doc = db.message_counters.find_one(counter_filter)

    if counter_doc is None:
        db.message_counters.insert_one({**counter_filter, "count": 1})
        count = 1
    else:
        count = counter_doc["count"] + 1
        db.message_counters.update_one(counter_filter, {"$inc": {"count": 1}})

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
