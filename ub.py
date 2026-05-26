import os
import json
import time
from pyrogram import Client, filters
from pyrogram.types import Message

from config import API_ID, API_HASH, STRING

app = Client(
    "userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=STRING
)

ALLOWED_FILE = "allowed.json"
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
    save_data(ACTIVITY_FILE, {"last_seen": int(time.time())})


def get_last_seen():
    data = load_data(ACTIVITY_FILE, {"last_seen": int(time.time())})
    return data["last_seen"]


@app.on_message(filters.me)
async def activity(_, msg):
    update_activity()


@app.on_message(filters.command("dd", prefixes="!") & filters.private & ~filters.me)
async def block_dm(_, msg: Message):
    pass


@app.on_message(filters.command("dd", prefixes="!") & filters.me)
async def dm_disable(_, msg: Message):
    if not msg.reply_to_message:
        return await msg.delete()

    user_id = msg.reply_to_message.from_user.id

    blocked = load_data(BLOCKED_FILE, [])

    if user_id not in blocked:
        blocked.append(user_id)

    save_data(BLOCKED_FILE, blocked)

    await msg.delete()


@app.on_message(filters.command("da", prefixes="!") & filters.me)
async def dm_allow(_, msg: Message):
    if not msg.reply_to_message:
        return await msg.delete()

    user_id = msg.reply_to_message.from_user.id

    blocked = load_data(BLOCKED_FILE, [])

    if user_id in blocked:
        blocked.remove(user_id)

    save_data(BLOCKED_FILE, blocked)

    await msg.delete()


@app.on_message(filters.command("setdmm", prefixes="!") & filters.me)
async def set_dmm(_, msg: Message):
    text = msg.text.split(None, 1)

    if len(text) < 2:
        return await msg.delete()

    save_data(DMM_FILE, {"message": text[1]})

    await msg.delete()


@app.on_message(filters.command("deldmm", prefixes="!") & filters.me)
async def del_dmm(_, msg: Message):
    save_data(DMM_FILE, {"message": ""})

    await msg.delete()


@app.on_message(filters.private & ~filters.me)
async def dm_handler(_, msg: Message):
    user_id = msg.from_user.id

    blocked = load_data(BLOCKED_FILE, [])

    if user_id in blocked:
        try:
            await msg.delete()
        except:
            pass
        return

    last_seen = get_last_seen()

    if int(time.time()) - last_seen > 300:
        dmm = load_data(DMM_FILE, {"message": ""})

        if dmm["message"]:
            try:
                await msg.reply(
                    dmm["message"],
                    disable_web_page_preview=False
                )
            except:
                pass


print("Userbot Started...")
update_activity()
app.run()
