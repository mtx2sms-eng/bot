import os

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
MONGO_URI = os.environ.get("MONGO_URI", "")
DB_NAME = os.environ.get("DB_NAME", "bot_interactions")

if not BOT_TOKEN:
    raise ValueError(
        "BOT_TOKEN is not set. "
        "On Railway, add it in the Variables tab of your service."
    )

if not MONGO_URI:
    raise ValueError(
        "MONGO_URI is not set. "
        "On Railway, add it in the Variables tab of your service."
    )

HIZB_COOLDOWN_SECONDS = 60

REQUIRED_CHANNELS = [
    "MI_CX_0",
    "MT_CK_0",
    "MT_X2_S",
]

(
    CREATE_NAME, CREATE_IDEOLOGY, CREATE_RELIGION,
    CREATE_CHANNEL, CREATE_PHOTO,
    EDIT_NAME, EDIT_PHOTO,
    KICK_MEMBER, JOIN_BY_ID, SEND_BROADCAST,
) = range(10)
