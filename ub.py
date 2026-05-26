import os
import json
import time
import asyncio
import logging

from pyrogram import Client, filters
from pyrogram.types import Message

from config import API_ID, API_HASH, STRING

logging.basicConfig(level=logging.ERROR)
logging.getLogger("pyrogram").setLevel(logging.CRITICAL)

app = Client(
    "userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=STRING,
    no_updates=False,
    sleep_threshold=30,
    workers=8
)

BLOCKED_FILE = "blocked.json"
DMM_FILE = "dmm.json"
ACTIVITY_FILE = "activity.json"


def load_data(file, default):

    if not os.path.exists(file):

        with open(file, "w") as f:
            json.dump(default, f)

    with open(file, "r") as f:
        return json.load(f)


def save_data(file, data):

    with open(file, "w") as f:
        json.dump(data, f)


def update_activity():

    save_data(
        ACTIVITY_FILE,
        {
            "last_seen": int(time.time())
        }
    )


def get_last_seen():

    data = load_data(
        ACTIVITY_FILE,
        {
            "last_seen": int(time.time())
        }
    )

    return data["last_seen"]


# =========================
# PING
# =========================

@app.on_message(filters.user("me") & filters.regex(r"^!ping$"))
async def ping(_, msg: Message):

    start = time.time()

    x = await msg.reply("Pinging...")

    end = time.time()

    ms = round((end - start) * 1000)

    await x.edit(f"Pong! {ms}ms")

    await asyncio.sleep(2)

    try:
        await x.delete()
    except:
        pass

    try:
        await msg.delete()
    except:
        pass

    update_activity()


# =========================
# DM DISABLE
# =========================

@app.on_message(filters.user("me") & filters.regex(r"^!dd$"))
async def dm_disable(_, msg: Message):

    try:

        user_id = msg.chat.id

        blocked = load_data(BLOCKED_FILE, [])

        if user_id not in blocked:
            blocked.append(user_id)

        save_data(BLOCKED_FILE, blocked)

    except:
        pass

    try:
        await msg.delete()
    except:
        pass

    update_activity()


# =========================
# DM ALLOW
# =========================

@app.on_message(filters.user("me") & filters.regex(r"^!da$"))
async def dm_allow(_, msg: Message):

    try:

        user_id = msg.chat.id

        blocked = load_data(BLOCKED_FILE, [])

        if user_id in blocked:
            blocked.remove(user_id)

        save_data(BLOCKED_FILE, blocked)

    except:
        pass

    try:
        await msg.delete()
    except:
        pass

    update_activity()


# =========================
# SET DM MESSAGE
# =========================

# =========================
# SET DM MESSAGE
# =========================

@app.on_message(filters.user("me") & filters.regex(r"^!setdmm"))
async def set_dmm(_, msg: Message):

    try:

        text = msg.text.split(None, 1)

        if len(text) < 2:

            x = await msg.reply("Give a message.")

            await asyncio.sleep(2)

            try:
                await x.delete()
            except:
                pass

            try:
                await msg.delete()
            except:
                pass

            return

        save_data(
            DMM_FILE,
            {
                "message": text[1]
            }
        )

        x = await msg.reply("DM message saved successfully.")

        await asyncio.sleep(2)

        try:
            await x.delete()
        except:
            pass

    except:
        pass

    try:
        await msg.delete()
    except:
        pass

    update_activity()


# =========================
# DELETE DM MESSAGE
# =========================

# =========================
# DELETE DM MESSAGE
# =========================

@app.on_message(filters.user("me") & filters.regex(r"^!deldmm$"))
async def del_dmm(_, msg: Message):

    try:

        save_data(
            DMM_FILE,
            {
                "message": ""
            }
        )

        x = await msg.reply("DM message deleted successfully.")

        await asyncio.sleep(2)

        try:
            await x.delete()
        except:
            pass

    except:
        pass

    try:
        await msg.delete()
    except:
        pass

    update_activity()


# =========================
# ACTIVITY TRACKER
# =========================

@app.on_message(filters.user("me"))
async def activity(_, msg):

    update_activity()


# =========================
# PRIVATE DM HANDLER
# =========================

@app.on_message(
    filters.private
    & ~filters.user("me")
    & filters.text
)
async def dm_handler(_, msg: Message):

    if not msg.from_user:
        return

    user_id = msg.from_user.id

    blocked = load_data(BLOCKED_FILE, [])

    # BLOCKED USER
    if user_id in blocked:

        try:
            await msg.delete()
        except:
            pass

        return

    # OFFLINE AUTO REPLY
    last_seen = get_last_seen()

    if int(time.time()) - last_seen > 300:

        dmm = load_data(
            DMM_FILE,
            {
                "message": ""
            }
        )

        if dmm["message"]:

            try:

                await msg.reply(
                    dmm["message"],
                    disable_web_page_preview=False,
                    parse_mode="html"
                )

            except:
                pass


print("Userbot Started...")
update_activity()

try:
    app.run()
except Exception as e:
    print(e)
