import os
import json
import time
import asyncio
import logging

from pyrogram import Client, filters, idle
from pyrogram.types import Message
from pyrogram.enums import ChatMembersFilter

from config import API_ID, API_HASH, STRINGS

MENTION_STATUS = {}

logging.basicConfig(level=logging.ERROR)
logging.getLogger("pyrogram").setLevel(logging.CRITICAL)

APPS = []

for num, string in enumerate(STRINGS, start=1):

    app = Client(
        f"userbot{num}",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=string,
        no_updates=False,
        sleep_threshold=30,
        workers=8
    )

    APPS.append(app)

BLOCKED_FILE = "blocked.json"
DMM_FILE = "dmm.json"
ACTIVITY_FILE = "activity.json"
GROUP_DELETE_FILE = "group_delete.json"


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


def register_handlers(app):

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

    @app.on_message(filters.user("me") & filters.regex(r"^!d_d$"))
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

    @app.on_message(filters.user("me") & filters.regex(r"^!d_a$"))
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

    @app.on_message(filters.user("me") & filters.regex(r"^!set_dmm"))
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

    @app.on_message(filters.user("me") & filters.regex(r"^!del_dmm$"))
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
    # GROUP AUTO DELETE ENABLE
    # =========================

    @app.on_message(filters.user("me") & filters.regex(r"^!del_m$"))
    async def enable_group_delete(_, msg: Message):

        try:

            if not msg.reply_to_message:

                x = await msg.reply("Reply to a user message.")

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

            if not msg.chat.type.name in ["SUPERGROUP", "GROUP"]:

                try:
                    await msg.delete()
                except:
                    pass

                return

            user_id = msg.reply_to_message.from_user.id
            chat_id = str(msg.chat.id)

            data = load_data(GROUP_DELETE_FILE, {})

            if chat_id not in data:
                data[chat_id] = []

            if user_id not in data[chat_id]:
                data[chat_id].append(user_id)

            save_data(GROUP_DELETE_FILE, data)

            x = await msg.reply("Auto delete enabled.")

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

    # =========================
    # GROUP AUTO DELETE DISABLE
    # =========================

    @app.on_message(filters.user("me") & filters.regex(r"^!stdel_m$"))
    async def disable_group_delete(_, msg: Message):

        try:

            if not msg.reply_to_message:

                x = await msg.reply("Reply to a user message.")

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

            if not msg.chat.type.name in ["SUPERGROUP", "GROUP"]:

                try:
                    await msg.delete()
                except:
                    pass

                return

            user_id = msg.reply_to_message.from_user.id
            chat_id = str(msg.chat.id)

            data = load_data(GROUP_DELETE_FILE, {})

            if chat_id in data:

                if user_id in data[chat_id]:
                    data[chat_id].remove(user_id)

            save_data(GROUP_DELETE_FILE, data)

            x = await msg.reply("Auto delete disabled.")

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

    # =========================
    # GROUP MESSAGE DELETE HANDLER
    # =========================

    @app.on_message(filters.group & ~filters.user("me"))
    async def group_delete_handler(_, msg: Message):

        try:

            if not msg.from_user:
                return

            user_id = msg.from_user.id
            chat_id = str(msg.chat.id)

            data = load_data(GROUP_DELETE_FILE, {})

            if chat_id not in data:
                return

            if user_id in data[chat_id]:

                try:
                    await msg.delete()
                except:
                    pass

        except:
            pass

    # =========================
    # MENTION ALL
    # =========================

    @app.on_message(filters.user("me") & filters.regex(r"^!m_all"))
    async def mention_all(_, msg: Message):

        global MENTION_STATUS

        try:

            if msg.chat.type.name not in ["GROUP", "SUPERGROUP"]:

                try:
                    await msg.delete()
                except:
                    pass

                return

            text = msg.text.split(None, 1)

            if len(text) < 2:

                x = await msg.reply("Give some text.")

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

            message_text = text[1]

            chat_id = msg.chat.id

            MENTION_STATUS[chat_id] = True

            try:
                await msg.delete()
            except:
                pass

            async for member in app.get_chat_members(chat_id):

                if not MENTION_STATUS.get(chat_id):
                    break

                user = member.user

                if user.is_bot:
                    continue

                try:

                    mention = user.mention

                    await app.send_message(
                        chat_id,
                        f"{mention} {message_text}"
                    )

                    await asyncio.sleep(2)

                except:
                    pass

        except:
            pass

    # =========================
    # STOP MENTION ALL
    # =========================

    @app.on_message(filters.user("me") & filters.regex(r"^!stm_all$"))
    async def stop_mention_all(_, msg: Message):

        global MENTION_STATUS

        try:

            chat_id = msg.chat.id

            MENTION_STATUS[chat_id] = False

            x = await msg.reply("Mention all stopped.")

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

        if user_id in blocked:

            try:
                await msg.delete()
            except:
                pass

            return

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


async def main():

    for app in APPS:

        register_handlers(app)

        await app.start()

        me = await app.get_me()

        print(f"Started -> {me.first_name}")

    update_activity()

    await idle()

    for app in APPS:
        await app.stop()


if __name__ == "__main__":

    try:
        asyncio.get_event_loop().run_until_complete(main())

    except Exception as e:
        print(e)
        
