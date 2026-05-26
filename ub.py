import os
import json
import time
import asyncio
import logging

from pyrogram import Client, filters, idle
from pyrogram.types import Message

from config import API_ID, API_HASH, STRINGS

MENTION_STATUS = {}

logging.basicConfig(level=logging.ERROR)
logging.getLogger("pyrogram").setLevel(logging.CRITICAL)

APPS = []

for num, string in enumerate(STRINGS, start=1):

    client = Client(
        f"userbot{num}",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=string,
        no_updates=False,
        sleep_threshold=30,
        workers=8
    )

    APPS.append(client)

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

    @app.on_message(filters.me & filters.regex(r"^!ping$"))
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

    @app.on_message(filters.me & filters.regex(r"^!d_d$"))
    async def dm_disable(_, msg: Message):

        try:

            user_id = msg.chat.id

            blocked = load_data(BLOCKED_FILE, [])

            if user_id not in blocked:
                blocked.append(user_id)

            save_data(BLOCKED_FILE, blocked)

            x = await msg.reply("DM disabled.")

            await asyncio.sleep(2)

            try:
                await x.delete()
            except:
                pass

        except Exception as e:
            print(e)

        try:
            await msg.delete()
        except:
            pass

        update_activity()

    # =========================
    # DM ALLOW
    # =========================

    @app.on_message(filters.me & filters.regex(r"^!d_a$"))
    async def dm_allow(_, msg: Message):

        try:

            user_id = msg.chat.id

            blocked = load_data(BLOCKED_FILE, [])

            if user_id in blocked:
                blocked.remove(user_id)

            save_data(BLOCKED_FILE, blocked)

            x = await msg.reply("DM enabled.")

            await asyncio.sleep(2)

            try:
                await x.delete()
            except:
                pass

        except Exception as e:
            print(e)

        try:
            await msg.delete()
        except:
            pass

        update_activity()

    # =========================
    # SET DM MESSAGE
    # =========================

    @app.on_message(filters.me & filters.command("set_dmm", prefixes="!"))
    async def set_dmm(_, msg: Message):

        try:

            if len(msg.command) < 2:

                x = await msg.reply("Give a message.")

                await asyncio.sleep(2)

                await x.delete()
                await msg.delete()

                return

            text = " ".join(msg.command[1:])

            save_data(
                DMM_FILE,
                {
                    "message": text
                }
            )

            x = await msg.reply("DM message saved successfully.")

            await asyncio.sleep(2)

            await x.delete()

        except Exception as e:
            print(e)

        try:
            await msg.delete()
        except:
            pass

    # =========================
    # DELETE DM MESSAGE
    # =========================

    @app.on_message(filters.me & filters.regex(r"^!del_dmm$"))
    async def del_dmm(_, msg: Message):

        try:

            save_data(
                DMM_FILE,
                {
                    "message": ""
                }
            )

            x = await msg.reply("DM message deleted.")

            await asyncio.sleep(2)

            await x.delete()

        except Exception as e:
            print(e)

        try:
            await msg.delete()
        except:
            pass

    # =========================
    # ACTIVITY TRACKER
    # =========================

    @app.on_message(filters.me)
    async def activity(_, msg):

        if msg.text:

            if msg.text.startswith("!set_dmm"):
                return

        update_activity()

    # =========================
    # GROUP AUTO DELETE ENABLE
    # =========================

    @app.on_message(filters.me & filters.regex(r"^!del_m$"))
    async def enable_group_delete(_, msg: Message):

        try:

            if not msg.reply_to_message:

                x = await msg.reply("Reply to user.")

                await asyncio.sleep(2)

                await x.delete()

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

            await x.delete()

        except Exception as e:
            print(e)

        try:
            await msg.delete()
        except:
            pass

    # =========================
    # GROUP AUTO DELETE DISABLE
    # =========================

    @app.on_message(filters.me & filters.regex(r"^!stdel_m$"))
    async def disable_group_delete(_, msg: Message):

        try:

            if not msg.reply_to_message:

                x = await msg.reply("Reply to user.")

                await asyncio.sleep(2)

                await x.delete()

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

            await x.delete()

        except Exception as e:
            print(e)

        try:
            await msg.delete()
        except:
            pass

    # =========================
    # GROUP DELETE HANDLER
    # =========================

    @app.on_message(filters.group & ~filters.me)
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

        except Exception as e:
            print(e)

    # =========================
    # MENTION ALL
    # =========================

    @app.on_message(filters.me & filters.command("m_all", prefixes="!"))
    async def mention_all(client, msg: Message):

        global MENTION_STATUS

        try:

            if msg.chat.type.name not in ["GROUP", "SUPERGROUP"]:
                return

            if len(msg.command) < 2:

                x = await msg.reply("Give text.")

                await asyncio.sleep(2)

                await x.delete()
                await msg.delete()

                return

            message_text = " ".join(msg.command[1:])

            chat_id = msg.chat.id

            MENTION_STATUS[chat_id] = True

            await msg.delete()

            async for member in client.get_chat_members(chat_id):

                if not MENTION_STATUS.get(chat_id):
                    break

                user = member.user

                if user.is_bot:
                    continue

                if user.is_deleted:
                    continue

                try:

                    await client.send_message(
                        chat_id,
                        f"[{user.first_name}](tg://user?id={user.id}) {message_text}"
                    )

                    await asyncio.sleep(3)

                except Exception as e:

                    print(f"Mention Error: {e}")

                    continue

        except Exception as e:

            print(f"Main Error: {e}")

    # =========================
    # STOP MENTION ALL
    # =========================

    @app.on_message(filters.me & filters.command("stm_all", prefixes="!"))
    async def stop_mention_all(client, msg: Message):

        global MENTION_STATUS

        try:

            chat_id = msg.chat.id

            MENTION_STATUS[chat_id] = False

            x = await msg.reply("Stopped.")

            await asyncio.sleep(2)

            await x.delete()

        except Exception as e:
            print(e)

        try:
            await msg.delete()
        except:
            pass

    # =========================
    # PRIVATE DM HANDLER
    # =========================

    @app.on_message(
        filters.private
        & ~filters.me
        & filters.text
    )
    async def dm_handler(_, msg: Message):

        try:

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

                    except Exception as e:
                        print(e)

        except Exception as e:
            print(e)


async def main():

    for client in APPS:

        register_handlers(client)

        await client.start()

        me = await client.get_me()

        print(f"Started -> {me.first_name}")

    update_activity()

    await idle()

    for client in APPS:

        await client.stop()


if __name__ == "__main__":

    try:
        asyncio.get_event_loop().run_until_complete(main())

    except Exception as e:
        print(e)
