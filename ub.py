import os
import json
import time
import asyncio
import logging

from pyrogram import Client, filters, idle
from pyrogram.types import Message

from config import API_ID, API_HASH, STRINGS

MENTION_STATUS = {}
AWAY_SECONDS = 30

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
WARNING_FILE = "warnings.json"


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
    def get_command_text(msg: Message) -> str:
        if not msg.text:
            return ""
        return msg.text.strip()

    def parse_command_args(msg: Message):
        text = get_command_text(msg)
        if not text.startswith("!"):
            return "", []
        parts = text.split()
        command = parts[0][1:].lower()
        return command, parts[1:]

    async def send_confirm(msg: Message, text: str, delay: int = 2):
        x = await msg.reply(f"`{text}`")
        await asyncio.sleep(delay)
        try:
            await x.delete()
        except:
            pass

    async def send_error(msg: Message, text: str, delay: int = 3):
        x = await msg.reply(f"`ERROR: {text}`")
        await asyncio.sleep(delay)
        try:
            await x.delete()
        except:
            pass

    # =========================
    # PING
    # =========================

    @app.on_message(filters.me & filters.regex(r"(?i)^!ping$"))
    async def ping(_, msg: Message):

        start = time.time()

        x = await msg.reply("`Pinging...`")

        end = time.time()

        ms = round((end - start) * 1000)

        await x.edit(f"`Pong! {ms}ms`")

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
    # DM DISABLE / ENABLE
    # =========================

    @app.on_message(filters.me & filters.regex(r"(?i)^!d_d$"))
    async def dm_disable(_, msg: Message):

        try:
            target_user_id = None

            if msg.chat.type.name == "PRIVATE":
                target_user_id = msg.chat.id
            elif msg.reply_to_message and msg.reply_to_message.from_user:
                target_user_id = msg.reply_to_message.from_user.id

            if not target_user_id:
                await send_error(msg, "DM ME USE DIRECTLY OR REPLY USER IN GROUP")
                return

            blocked = load_data(BLOCKED_FILE, [])

            if target_user_id not in blocked:
                blocked.append(target_user_id)

            save_data(BLOCKED_FILE, blocked)

            await send_confirm(msg, f"DM DISABLED FOR {target_user_id}")

        except Exception as e:
            print(e)

        try:
            await msg.delete()
        except:
            pass

        update_activity()

    @app.on_message(filters.me & filters.regex(r"(?i)^!d_a$"))
    async def dm_allow(_, msg: Message):

        try:
            target_user_id = None

            if msg.chat.type.name == "PRIVATE":
                target_user_id = msg.chat.id
            elif msg.reply_to_message and msg.reply_to_message.from_user:
                target_user_id = msg.reply_to_message.from_user.id

            if not target_user_id:
                await send_error(msg, "DM ME USE DIRECTLY OR REPLY USER IN GROUP")
                return

            blocked = load_data(BLOCKED_FILE, [])

            if target_user_id in blocked:
                blocked.remove(target_user_id)

            save_data(BLOCKED_FILE, blocked)

            await send_confirm(msg, f"DM ENABLED FOR {target_user_id}")

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

    @app.on_message(filters.me & filters.regex(r"(?i)^!set_dmm(\s+.+)?$"))
    async def set_dmm(_, msg: Message):

        try:

            command, args = parse_command_args(msg)
            if command != "set_dmm":
                return

            if len(args) < 1:

                await send_error(msg, "USE: !set_dmm <message>")
                await msg.delete()

                return

            text = " ".join(args)

            save_data(
                DMM_FILE,
                {
                    "message": text,
                    "mode": "html"
                }
            )

            await send_confirm(msg, "DMM MESSAGE SAVED")

        except Exception as e:
            print(e)

        try:
            await msg.delete()
        except:
            pass

    # =========================
    # DELETE DM MESSAGE
    # =========================

    @app.on_message(filters.me & filters.regex(r"(?i)^!del_dmm$"))
    async def del_dmm(_, msg: Message):

        try:

            save_data(
                DMM_FILE,
                {
                    "message": ""
                }
            )

            await send_confirm(msg, "DMM MESSAGE DELETED")

        except Exception as e:
            print(e)

        try:
            await msg.delete()
        except:
            pass

    # =========================
    # ACTIVITY TRACKER
    # =========================

    @app.on_message(filters.me & filters.text)
    async def activity(_, msg):

        text = get_command_text(msg).lower()
        if text.startswith("!set_dmm"):
            return

        update_activity()

    # =========================
    # GROUP AUTO DELETE ENABLE / DISABLE
    # =========================

    @app.on_message(filters.me & filters.regex(r"(?i)^!del_m$"))
    async def enable_group_delete(client, msg: Message):

        try:

            if msg.chat.type.name not in ["GROUP", "SUPERGROUP"]:
                await send_error(msg, "USE THIS COMMAND IN GROUP")
                return

            me = await client.get_me()
            my_member = await client.get_chat_member(msg.chat.id, me.id)
            if my_member.status not in ["administrator", "owner"]:
                await send_error(msg, "I MUST BE GROUP ADMIN")
                return

            if not msg.reply_to_message or not msg.reply_to_message.from_user:

                await send_error(msg, "REPLY TO A USER MESSAGE")

                return

            user_id = msg.reply_to_message.from_user.id
            chat_id = str(msg.chat.id)

            data = load_data(GROUP_DELETE_FILE, {})

            if chat_id not in data:
                data[chat_id] = []

            if user_id not in data[chat_id]:
                data[chat_id].append(user_id)

            save_data(GROUP_DELETE_FILE, data)

            await send_confirm(msg, f"AUTO DELETE ENABLED FOR {user_id}")

        except Exception as e:
            print(e)

        try:
            await msg.delete()
        except:
            pass

    @app.on_message(filters.me & filters.regex(r"(?i)^!stdel_m$"))
    async def disable_group_delete(_, msg: Message):

        try:

            if not msg.reply_to_message or not msg.reply_to_message.from_user:

                await send_error(msg, "REPLY TO A USER MESSAGE")

                return

            user_id = msg.reply_to_message.from_user.id
            chat_id = str(msg.chat.id)

            data = load_data(GROUP_DELETE_FILE, {})

            if chat_id in data and user_id in data[chat_id]:
                data[chat_id].remove(user_id)

            save_data(GROUP_DELETE_FILE, data)

            await send_confirm(msg, f"AUTO DELETE DISABLED FOR {user_id}")

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
    async def group_delete_handler(client, msg: Message):

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
                except Exception:
                    pass

        except Exception as e:
            print(e)

    # =========================
    # MENTION ALL
    # =========================

    @app.on_message(filters.me & filters.regex(r"(?i)^!m_all(\s+.+)?$"))
    async def mention_all(client, msg: Message):

        global MENTION_STATUS

        try:

            if msg.chat.type.name not in ["GROUP", "SUPERGROUP"]:
                await send_error(msg, "USE THIS COMMAND IN GROUP")
                return

            command, args = parse_command_args(msg)
            if command != "m_all":
                return

            if len(args) < 1:

                await send_error(msg, "USE: !m_all <text>")
                await msg.delete()

                return

            me = await client.get_me()
            my_member = await client.get_chat_member(msg.chat.id, me.id)
            if my_member.status not in ["administrator", "owner"]:
                await send_error(msg, "I MUST BE GROUP ADMIN")
                return

            message_text = " ".join(args)

            chat_id = msg.chat.id

            MENTION_STATUS[chat_id] = True

            await send_confirm(msg, "MENTION ALL STARTED")
            await msg.delete()

            async for member in client.get_chat_members(chat_id):

                if not MENTION_STATUS.get(chat_id):
                    break

                user = member.user

                if user.is_bot or user.is_deleted:
                    continue

                try:
                    await client.send_message(
                        chat_id,
                        f"[{user.first_name}](tg://user?id={user.id}) {message_text}"
                    )
                    await asyncio.sleep(2)

                except Exception as e:
                    print(f"Mention Error: {e}")
                    continue

        except Exception as e:
            print(f"Main Error: {e}")

    # =========================
    # STOP MENTION ALL
    # =========================

    @app.on_message(filters.me & filters.regex(r"(?i)^!stm_all$"))
    async def stop_mention_all(_, msg: Message):

        global MENTION_STATUS

        try:

            chat_id = msg.chat.id
            MENTION_STATUS[chat_id] = False
            await send_confirm(msg, "MENTION ALL STOPPED")

        except Exception as e:
            print(e)

        try:
            await msg.delete()
        except:
            pass

    # =========================
    # PRIVATE DM HANDLER
    # =========================

    @app.on_message(filters.private & ~filters.me & filters.text)
    async def dm_handler(client, msg: Message):

        try:

            if not msg.from_user:
                return

            user_id = msg.from_user.id

            if msg.from_user.is_bot:
                return

            blocked = load_data(BLOCKED_FILE, [])

            if user_id in blocked:
                return

            last_seen = get_last_seen()

            if int(time.time()) - last_seen < AWAY_SECONDS:
                return

            dmm = load_data(DMM_FILE, {"message": "", "mode": "html"})

            if not dmm.get("message"):
                return

            warnings = load_data(WARNING_FILE, {})

            if str(user_id) not in warnings:
                warnings[str(user_id)] = 0

            warnings[str(user_id)] += 1
            count = warnings[str(user_id)]

            save_data(WARNING_FILE, warnings)

            reply_text = (
                f"{dmm['message']}\n\n"
                f"<b>⚠️ Warning {count}/5</b>\n"
                f"Do not spam me."
            )

            await msg.reply(reply_text, parse_mode="HTML")

            if count >= 5:

                await client.block_user(user_id)

                await msg.reply("<b>You are blocked.</b>", parse_mode="HTML")

                warnings.pop(str(user_id), None)
                save_data(WARNING_FILE, warnings)

        except Exception as e:
            print(f"DM Handler Error: {e}")


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
