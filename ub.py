import os
import json
import time
import asyncio
import logging

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.functions.contacts import BlockRequest, UnblockRequest
from telethon.errors import FloodWaitError

from config import API_ID, API_HASH, STRINGS

logging.basicConfig(level=logging.ERROR)

MENTION_STATUS = {}
AWAY_SECONDS = 30

BLOCKED_FILE = "blocked.json"
DMM_FILE = "dmm.json"
ACTIVITY_FILE = "activity.json"
GROUP_DELETE_FILE = "group_delete.json"
WARNING_FILE = "warnings.json"

clients = []


def load_data(file_name, default):
    if not os.path.exists(file_name):
        with open(file_name, "w", encoding="utf-8") as f:
            json.dump(default, f)
    with open(file_name, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(file_name, data):
    with open(file_name, "w", encoding="utf-8") as f:
        json.dump(data, f)


def update_activity():
    save_data(ACTIVITY_FILE, {"last_seen": int(time.time())})


def get_last_seen():
    data = load_data(ACTIVITY_FILE, {"last_seen": int(time.time())})
    return data.get("last_seen", int(time.time()))


def parse_cmd(text: str):
    text = (text or "").strip()
    if not text.startswith("!"):
        return "", []
    parts = text.split()
    cmd = parts[0][1:].lower()
    args = parts[1:]
    return cmd, args


async def temp_reply(event, text, sec=2):
    m = await event.reply(f"`{text}`")
    await asyncio.sleep(sec)
    try:
        await m.delete()
    except Exception:
        pass


async def get_target_user_id(event):
    if event.is_private:
        return event.chat_id
    if event.is_reply:
        reply = await event.get_reply_message()
        if reply and reply.sender_id:
            return reply.sender_id
    return None


def register_handlers(client: TelegramClient):
    @client.on(events.NewMessage(outgoing=True, pattern=r"(?i)^!ping$"))
    async def ping(event):
        start = time.time()
        msg = await event.reply("`Pinging...`")
        ms = round((time.time() - start) * 1000)
        await msg.edit(f"`Pong! {ms}ms`")
        await asyncio.sleep(2)
        try:
            await msg.delete()
        except Exception:
            pass
        try:
            await event.delete()
        except Exception:
            pass
        update_activity()

    # ---------------- DM disable / enable ----------------
    @client.on(events.NewMessage(outgoing=True, pattern=r"(?i)^!d_d$"))
    async def dm_disable(event):
        try:
            uid = await get_target_user_id(event)
            if not uid:
                await temp_reply(event, "REPLY USER IN GROUP OR USE IN DM", 3)
                return

            blocked = load_data(BLOCKED_FILE, [])
            if uid not in blocked:
                blocked.append(uid)
                save_data(BLOCKED_FILE, blocked)

            await temp_reply(event, f"DM DISABLED FOR {uid}")
        except Exception as e:
            print("dm_disable:", e)

        try:
            await event.delete()
        except Exception:
            pass

    @client.on(events.NewMessage(outgoing=True, pattern=r"(?i)^!d_a$"))
    async def dm_allow(event):
        try:
            uid = await get_target_user_id(event)
            if not uid:
                await temp_reply(event, "REPLY USER IN GROUP OR USE IN DM", 3)
                return

            blocked = load_data(BLOCKED_FILE, [])
            if uid in blocked:
                blocked.remove(uid)
                save_data(BLOCKED_FILE, blocked)

            await temp_reply(event, f"DM ENABLED FOR {uid}")
        except Exception as e:
            print("dm_allow:", e)

        try:
            await event.delete()
        except Exception:
            pass

    # ---------------- Hard block / unblock ----------------
    @client.on(events.NewMessage(outgoing=True, pattern=r"(?i)^!blck$"))
    async def hard_block(event):
        try:
            uid = await get_target_user_id(event)
            if not uid:
                await temp_reply(event, "REPLY USER IN GROUP OR USE IN DM", 3)
                return

            blocked = load_data(BLOCKED_FILE, [])
            if uid not in blocked:
                blocked.append(uid)
                save_data(BLOCKED_FILE, blocked)

            await client(BlockRequest(uid))
            await temp_reply(event, f"BLOCKED {uid}")
        except Exception as e:
            print("hard_block:", e)

        try:
            await event.delete()
        except Exception:
            pass

    @client.on(events.NewMessage(outgoing=True, pattern=r"(?i)^!unblck$"))
    async def hard_unblock(event):
        try:
            uid = await get_target_user_id(event)
            if not uid:
                await temp_reply(event, "REPLY USER IN GROUP OR USE IN DM", 3)
                return

            blocked = load_data(BLOCKED_FILE, [])
            if uid in blocked:
                blocked.remove(uid)
                save_data(BLOCKED_FILE, blocked)

            await client(UnblockRequest(uid))
            await temp_reply(event, f"UNBLOCKED {uid}")
        except Exception as e:
            print("hard_unblock:", e)

        try:
            await event.delete()
        except Exception:
            pass

    # ---------------- set / del dmm ----------------
    @client.on(events.NewMessage(outgoing=True, pattern=r"(?i)^!set_dmm(?:\s+.+)?$"))
    async def set_dmm(event):
        try:
            cmd, args = parse_cmd(event.raw_text)
            if cmd != "set_dmm" or not args:
                await temp_reply(event, "USE: !set_dmm <message>", 3)
                try:
                    await event.delete()
                except Exception:
                    pass
                return

            text = " ".join(args)
            save_data(DMM_FILE, {"message": text, "mode": "html"})
            await temp_reply(event, "DMM MESSAGE SAVED")
        except Exception as e:
            print("set_dmm:", e)

        try:
            await event.delete()
        except Exception:
            pass

    @client.on(events.NewMessage(outgoing=True, pattern=r"(?i)^!del_dmm$"))
    async def del_dmm(event):
        try:
            save_data(DMM_FILE, {"message": "", "mode": "html"})
            await temp_reply(event, "DMM MESSAGE DELETED")
        except Exception as e:
            print("del_dmm:", e)

        try:
            await event.delete()
        except Exception:
            pass

    # ---------------- Activity tracker ----------------
    @client.on(events.NewMessage(outgoing=True))
    async def activity_tracker(event):
        text = (event.raw_text or "").lower().strip()
        if text.startswith("!set_dmm"):
            return
        update_activity()

    # ---------------- Group auto delete ----------------
    @client.on(events.NewMessage(outgoing=True, pattern=r"(?i)^!del_m$"))
    async def enable_del(event):
        try:
            if not event.is_group:
                await temp_reply(event, "USE THIS IN GROUP", 3)
                return

            if not event.is_reply:
                await temp_reply(event, "REPLY TO USER MESSAGE", 3)
                return

            reply = await event.get_reply_message()
            if not reply or not reply.sender_id:
                await temp_reply(event, "INVALID REPLY", 3)
                return

            user_id = reply.sender_id
            chat_id = str(event.chat_id)

            data = load_data(GROUP_DELETE_FILE, {})
            if chat_id not in data:
                data[chat_id] = []
            if user_id not in data[chat_id]:
                data[chat_id].append(user_id)
            save_data(GROUP_DELETE_FILE, data)

            await temp_reply(event, f"AUTO DELETE ENABLED FOR {user_id}")
        except Exception as e:
            print("enable_del:", e)

        try:
            await event.delete()
        except Exception:
            pass

    @client.on(events.NewMessage(outgoing=True, pattern=r"(?i)^!stdel_m$"))
    async def disable_del(event):
        try:
            if not event.is_group:
                await temp_reply(event, "USE THIS IN GROUP", 3)
                return

            if not event.is_reply:
                await temp_reply(event, "REPLY TO USER MESSAGE", 3)
                return

            reply = await event.get_reply_message()
            if not reply or not reply.sender_id:
                await temp_reply(event, "INVALID REPLY", 3)
                return

            user_id = reply.sender_id
            chat_id = str(event.chat_id)

            data = load_data(GROUP_DELETE_FILE, {})
            if chat_id in data and user_id in data[chat_id]:
                data[chat_id].remove(user_id)
                if not data[chat_id]:
                    data.pop(chat_id, None)
            save_data(GROUP_DELETE_FILE, data)

            await temp_reply(event, f"AUTO DELETE DISABLED FOR {user_id}")
        except Exception as e:
            print("disable_del:", e)

        try:
            await event.delete()
        except Exception:
            pass

    @client.on(events.NewMessage(incoming=True))
    async def group_delete_handler(event):
        try:
            if not event.is_group:
                return
            if not event.sender_id:
                return

            data = load_data(GROUP_DELETE_FILE, {})
            chat_id = str(event.chat_id)
            if chat_id not in data:
                return

            if event.sender_id in data[chat_id]:
                try:
                    await event.delete()
                except Exception:
                    pass
        except Exception as e:
            print("group_delete_handler:", e)

    # ---------------- Mention all ----------------
    @client.on(events.NewMessage(outgoing=True, pattern=r"(?i)^!m_all(?:\s+.+)?$"))
    async def mention_all(event):
        try:
            if not event.is_group:
                await temp_reply(event, "USE THIS IN GROUP", 3)
                return

            cmd, args = parse_cmd(event.raw_text)
            if cmd != "m_all" or not args:
                await temp_reply(event, "USE: !m_all <text>", 3)
                try:
                    await event.delete()
                except Exception:
                    pass
                return

            text = " ".join(args)
            chat_id = event.chat_id
            MENTION_STATUS[chat_id] = True

            await temp_reply(event, "MENTION ALL STARTED")
            try:
                await event.delete()
            except Exception:
                pass

            async for user in client.iter_participants(chat_id):
                if not MENTION_STATUS.get(chat_id):
                    break
                if user.bot or user.deleted:
                    continue

                try:
                    mention = f"[{user.first_name}](tg://user?id={user.id}) {text}"
                    await client.send_message(chat_id, mention, parse_mode="md")
                    await asyncio.sleep(1.8)
                except FloodWaitError as fw:
                    await asyncio.sleep(fw.seconds + 1)
                except Exception as e:
                    print("mention_all send:", e)
                    continue

        except Exception as e:
            print("mention_all:", e)

    @client.on(events.NewMessage(outgoing=True, pattern=r"(?i)^!stm_all$"))
    async def stop_mention_all(event):
        try:
            chat_id = event.chat_id
            MENTION_STATUS[chat_id] = False
            await temp_reply(event, "MENTION ALL STOPPED")
        except Exception as e:
            print("stop_mention_all:", e)

        try:
            await event.delete()
        except Exception:
            pass

    # ---------------- Incoming DM handler ----------------
    @client.on(events.NewMessage(incoming=True))
    async def dm_handler(event):
        try:
            if not event.is_private:
                return
            if not event.sender_id:
                return

            user_id = event.sender_id

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
            warnings[str(user_id)] = warnings.get(str(user_id), 0) + 1
            count = warnings[str(user_id)]
            save_data(WARNING_FILE, warnings)

            reply_text = (
                f"{dmm['message']}\n\n"
                f"⚠️ Warning {count}/5\n"
                f"Do not spam me."
            )
            await event.reply(reply_text)

            if count >= 5:
                await client(BlockRequest(user_id))
                await event.reply("You are blocked.")
                warnings.pop(str(user_id), None)
                save_data(WARNING_FILE, warnings)

        except Exception as e:
            print("dm_handler:", e)


async def main():
    for i, s in enumerate(STRINGS, start=1):
        c = TelegramClient(StringSession(s), API_ID, API_HASH)
        clients.append(c)

    for c in clients:
        await c.start()
        me = await c.get_me()
        print(f"Started -> {me.first_name}")
        register_handlers(c)

    update_activity()

    print("All clients running...")
    await asyncio.gather(*(c.run_until_disconnected() for c in clients))


if __name__ == "__main__":
    asyncio.run(main())
