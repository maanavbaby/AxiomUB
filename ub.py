import os
import json
import time
import asyncio
import logging
import re

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.functions.contacts import BlockRequest, UnblockRequest
from telethon.tl.functions.channels import EditBannedRequest
from telethon.tl.types import ChatBannedRights
from telethon.errors import FloodWaitError

from config import API_ID, API_HASH, STRINGS

logging.basicConfig(level=logging.ERROR)

MENTION_STATUS = {}
AWAY_SECONDS = 30
CONFIRM_DELAY = 1

# keep "" last
PREFIXES = ["!", "/", ".", "#", "%", ""]

# command aliases: add your custom alias in the "" slot
COMMAND_ALIASES = {
    "ping": ["ping", ""],
    "d_d": ["d_d", "chup"],
    "d_a": ["d_a", "bhok"],
    "blck": ["blck", "fuck"],
    "unblck": ["unblck", ""],
    "dtl": ["dtl", "inf"],
    "set_dmm": ["set_dmm", ""],
    "del_dmm": ["del_dmm", ""],
    "del_m": ["del_m", "chupp"],
    "stdel_m": ["stdel_m", ""],
    "m_all": ["m_all", "alll"],
    "stm_all": ["stm_all", "ruk"],
    "ban": ["ban", "fuckk"],
}

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


def styled_box(title: str, body: str) -> str:
    return (
        "```"
        f"\n✧━〔 {title} 〕━✧"
        f"\n{body}"
        "\n✧━━━━━━━━━━━━━━━✧"
        "\n```"
    )


def unique_clean_aliases(key: str):
    items = COMMAND_ALIASES.get(key, [key])
    cleaned = []
    for x in items:
        x = (x or "").strip().lower()
        if x and x not in cleaned:
            cleaned.append(x)
    if key not in cleaned:
        cleaned.insert(0, key)
    return cleaned


def cmd_regex(command_key: str, with_args: bool = False) -> str:
    # multiple command names (alias support)
    names = unique_clean_aliases(command_key)
    names_part = "|".join(re.escape(n) for n in names)

    # multiple prefixes including empty
    prefix_part = r"(?:!|/|\.|#|%|)"
    if with_args:
        return rf"(?i)^{prefix_part}(?:{names_part})(?:\s+.+)?$"
    return rf"(?i)^{prefix_part}(?:{names_part})$"


def parse_cmd(text: str):
    text = (text or "").strip()
    if not text:
        return "", []

    matched_prefix = None
    for p in PREFIXES:
        if p and text.startswith(p):
            matched_prefix = p
            break
    if matched_prefix is None:
        matched_prefix = ""  # no prefix mode

    parts = text.split()
    if not parts:
        return "", []

    first = parts[0]
    if matched_prefix and first.startswith(matched_prefix):
        first = first[len(matched_prefix):]

    cmd = first.lower().strip()
    args = parts[1:]
    return cmd, args


def is_command_match(cmd_name: str, command_key: str) -> bool:
    return cmd_name in unique_clean_aliases(command_key)


async def temp_reply(event, title: str, text: str, sec=CONFIRM_DELAY):
    m = await event.reply(styled_box(title, f"➤ {text}"))
    await asyncio.sleep(sec)
    try:
        await m.delete()
    except Exception:
        pass


async def get_target_user_id(event, args=None):
    args = args or []
    # priority 1: UID in args
    if args:
        maybe = args[0].strip()
        if maybe.isdigit():
            return int(maybe)

    # priority 2: replied user
    if event.is_reply:
        reply = await event.get_reply_message()
        if reply and reply.sender_id:
            return reply.sender_id

    # priority 3: private chat target
    if event.is_private:
        return event.chat_id

    return None


def is_set_dmm_command(text: str) -> bool:
    cmd, _ = parse_cmd(text)
    return is_command_match(cmd, "set_dmm")


def register_handlers(client: TelegramClient):
    @client.on(events.NewMessage(outgoing=True, pattern=cmd_regex("ping")))
    async def ping(event):
        start = time.time()
        msg = await event.reply(styled_box("PING", "➤ Pinging..."))
        ms = round((time.time() - start) * 1000)
        uptime = int(time.time() - get_last_seen())

        await msg.edit(
            styled_box(
                "PONG",
                f"➤ Latency: {ms} ms\n➤ Uptime: {uptime}s"
            )
        )
        await asyncio.sleep(CONFIRM_DELAY)
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
    @client.on(events.NewMessage(outgoing=True, pattern=cmd_regex("d_d", with_args=True)))
    async def dm_disable(event):
        try:
            cmd, args = parse_cmd(event.raw_text)
            if not is_command_match(cmd, "d_d"):
                return

            uid = await get_target_user_id(event, args)
            if not uid:
                await temp_reply(event, "ERROR", "REPLY USER / USE DM / OR PASS UID", 2)
                return

            blocked = load_data(BLOCKED_FILE, [])
            if uid not in blocked:
                blocked.append(uid)
                save_data(BLOCKED_FILE, blocked)

            await temp_reply(event, "SUCCESS", f"DM DISABLED FOR {uid}")
        except Exception as e:
            print("dm_disable:", e)
            await temp_reply(event, "ERROR", "DM DISABLE FAILED", 2)

        try:
            await event.delete()
        except Exception:
            pass

    @client.on(events.NewMessage(outgoing=True, pattern=cmd_regex("d_a", with_args=True)))
    async def dm_allow(event):
        try:
            cmd, args = parse_cmd(event.raw_text)
            if not is_command_match(cmd, "d_a"):
                return

            uid = await get_target_user_id(event, args)
            if not uid:
                await temp_reply(event, "ERROR", "REPLY USER / USE DM / OR PASS UID", 2)
                return

            blocked = load_data(BLOCKED_FILE, [])
            if uid in blocked:
                blocked.remove(uid)
                save_data(BLOCKED_FILE, blocked)

            await temp_reply(event, "SUCCESS", f"DM ENABLED FOR {uid}")
        except Exception as e:
            print("dm_allow:", e)
            await temp_reply(event, "ERROR", "DM ENABLE FAILED", 2)

        try:
            await event.delete()
        except Exception:
            pass

    # ---------------- Hard block / unblock ----------------
    @client.on(events.NewMessage(outgoing=True, pattern=cmd_regex("blck", with_args=True)))
    async def hard_block(event):
        try:
            cmd, args = parse_cmd(event.raw_text)
            if not is_command_match(cmd, "blck"):
                return

            uid = await get_target_user_id(event, args)
            if not uid:
                await temp_reply(event, "ERROR", "REPLY USER / USE DM / OR PASS UID", 2)
                return

            blocked = load_data(BLOCKED_FILE, [])
            if uid not in blocked:
                blocked.append(uid)
                save_data(BLOCKED_FILE, blocked)

            await client(BlockRequest(uid))
            await temp_reply(event, "SUCCESS", f"BLOCKED {uid}")
        except Exception as e:
            print("hard_block:", e)
            await temp_reply(event, "ERROR", "BLOCK FAILED", 2)

        try:
            await event.delete()
        except Exception:
            pass

    @client.on(events.NewMessage(outgoing=True, pattern=cmd_regex("unblck", with_args=True)))
    async def hard_unblock(event):
        try:
            cmd, args = parse_cmd(event.raw_text)
            if not is_command_match(cmd, "unblck"):
                return

            uid = await get_target_user_id(event, args)
            if not uid:
                await temp_reply(event, "ERROR", "REPLY USER / USE DM / OR PASS UID", 2)
                return

            blocked = load_data(BLOCKED_FILE, [])
            if uid in blocked:
                blocked.remove(uid)
                save_data(BLOCKED_FILE, blocked)

            await client(UnblockRequest(uid))
            await temp_reply(event, "SUCCESS", f"UNBLOCKED {uid}")
        except Exception as e:
            print("hard_unblock:", e)
            await temp_reply(event, "ERROR", "UNBLOCK FAILED", 2)

        try:
            await event.delete()
        except Exception:
            pass

    # ---------------- details ----------------
    @client.on(events.NewMessage(outgoing=True, pattern=cmd_regex("dtl", with_args=True)))
    async def details_cmd(event):
        try:
            cmd, args = parse_cmd(event.raw_text)
            if not is_command_match(cmd, "dtl"):
                return

            uid = await get_target_user_id(event, args)
            if not uid:
                await temp_reply(event, "ERROR", "REPLY USER / USE DM / OR PASS UID", 2)
                return

            user = await client.get_entity(uid)
            name = f"{getattr(user, 'first_name', '') or ''} {getattr(user, 'last_name', '') or ''}".strip() or "N/A"
            username = f"@{user.username}" if getattr(user, "username", None) else "N/A"

            await temp_reply(
                event,
                "DETAILS",
                f"➤ ID: {user.id}\n➤ Name: {name}\n➤ Username: {username}",
                4
            )
        except Exception as e:
            print("details_cmd:", e)
            await temp_reply(event, "ERROR", "DETAIL FETCH FAILED", 2)

        try:
            await event.delete()
        except Exception:
            pass

    # ---------------- set / del dmm ----------------
    @client.on(events.NewMessage(outgoing=True, pattern=cmd_regex("set_dmm", with_args=True)))
    async def set_dmm(event):
        try:
            cmd, args = parse_cmd(event.raw_text)
            if not is_command_match(cmd, "set_dmm"):
                return

            if not args:
                await temp_reply(event, "ERROR", "USE: set_dmm <message>", 2)
                try:
                    await event.delete()
                except Exception:
                    pass
                return

            text = " ".join(args)
            save_data(DMM_FILE, {"message": text, "mode": "html"})
            await temp_reply(event, "SUCCESS", "DMM MESSAGE SAVED")
        except Exception as e:
            print("set_dmm:", e)
            await temp_reply(event, "ERROR", "SET DMM FAILED", 2)

        try:
            await event.delete()
        except Exception:
            pass

    @client.on(events.NewMessage(outgoing=True, pattern=cmd_regex("del_dmm", with_args=True)))
    async def del_dmm(event):
        try:
            cmd, _ = parse_cmd(event.raw_text)
            if not is_command_match(cmd, "del_dmm"):
                return

            save_data(DMM_FILE, {"message": "", "mode": "html"})
            await temp_reply(event, "SUCCESS", "DMM MESSAGE DELETED")
        except Exception as e:
            print("del_dmm:", e)
            await temp_reply(event, "ERROR", "DEL DMM FAILED", 2)

        try:
            await event.delete()
        except Exception:
            pass

    # ---------------- Activity tracker ----------------
    @client.on(events.NewMessage(outgoing=True))
    async def activity_tracker(event):
        text = (event.raw_text or "").strip()
        if is_set_dmm_command(text):
            return
        update_activity()

    # ---------------- Group auto delete ----------------
    @client.on(events.NewMessage(outgoing=True, pattern=cmd_regex("del_m", with_args=True)))
    async def enable_del(event):
        try:
            cmd, args = parse_cmd(event.raw_text)
            if not is_command_match(cmd, "del_m"):
                return

            if not event.is_group:
                await temp_reply(event, "ERROR", "USE THIS IN GROUP", 2)
                return

            user_id = await get_target_user_id(event, args)
            if not user_id:
                await temp_reply(event, "ERROR", "REPLY USER OR PASS UID", 2)
                return

            chat_id = str(event.chat_id)
            data = load_data(GROUP_DELETE_FILE, {})
            if chat_id not in data:
                data[chat_id] = []
            if user_id not in data[chat_id]:
                data[chat_id].append(user_id)
            save_data(GROUP_DELETE_FILE, data)

            await temp_reply(event, "SUCCESS", f"AUTO DELETE ENABLED FOR {user_id}")
        except Exception as e:
            print("enable_del:", e)
            await temp_reply(event, "ERROR", "DEL_M FAILED", 2)

        try:
            await event.delete()
        except Exception:
            pass

    @client.on(events.NewMessage(outgoing=True, pattern=cmd_regex("stdel_m", with_args=True)))
    async def disable_del(event):
        try:
            cmd, args = parse_cmd(event.raw_text)
            if not is_command_match(cmd, "stdel_m"):
                return

            if not event.is_group:
                await temp_reply(event, "ERROR", "USE THIS IN GROUP", 2)
                return

            user_id = await get_target_user_id(event, args)
            if not user_id:
                await temp_reply(event, "ERROR", "REPLY USER OR PASS UID", 2)
                return

            chat_id = str(event.chat_id)
            data = load_data(GROUP_DELETE_FILE, {})
            if chat_id in data and user_id in data[chat_id]:
                data[chat_id].remove(user_id)
                if not data[chat_id]:
                    data.pop(chat_id, None)
            save_data(GROUP_DELETE_FILE, data)

            await temp_reply(event, "SUCCESS", f"AUTO DELETE DISABLED FOR {user_id}")
        except Exception as e:
            print("disable_del:", e)
            await temp_reply(event, "ERROR", "STDEL_M FAILED", 2)

        try:
            await event.delete()
        except Exception:
            pass

    @client.on(events.NewMessage(incoming=True))
    async def group_delete_handler(event):
        try:
            if not event.is_group or not event.sender_id:
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

    # ---------------- Ban command ----------------
    @client.on(events.NewMessage(outgoing=True, pattern=cmd_regex("ban", with_args=True)))
    async def ban_user(event):
        try:
            cmd, args = parse_cmd(event.raw_text)
            if not is_command_match(cmd, "ban"):
                return

            if not event.is_group:
                await temp_reply(event, "ERROR", "USE THIS IN GROUP", 2)
                return

            uid = await get_target_user_id(event, args)
            if not uid:
                await temp_reply(event, "ERROR", "REPLY USER OR PASS UID", 2)
                return

            rights = ChatBannedRights(
                until_date=None,
                view_messages=True
            )
            await client(EditBannedRequest(event.chat_id, uid, rights))
            await temp_reply(event, "SUCCESS", f"BANNED {uid}")
        except Exception as e:
            print("ban_user:", e)
            await temp_reply(event, "ERROR", "BAN FAILED (CHECK ADMIN RIGHTS)", 2)

        try:
            await event.delete()
        except Exception:
            pass

    # ---------------- Mention all ----------------
    @client.on(events.NewMessage(outgoing=True, pattern=cmd_regex("m_all", with_args=True)))
    async def mention_all(event):
        try:
            if not event.is_group:
                await temp_reply(event, "ERROR", "USE THIS IN GROUP", 2)
                return

            cmd, args = parse_cmd(event.raw_text)
            if not is_command_match(cmd, "m_all") or not args:
                await temp_reply(event, "ERROR", "USE: m_all <text>", 2)
                try:
                    await event.delete()
                except Exception:
                    pass
                return

            text = " ".join(args)
            chat_id = event.chat_id
            MENTION_STATUS[chat_id] = True

            await temp_reply(event, "SUCCESS", "MENTION ALL STARTED")
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

    @client.on(events.NewMessage(outgoing=True, pattern=cmd_regex("stm_all", with_args=True)))
    async def stop_mention_all(event):
        try:
            cmd, _ = parse_cmd(event.raw_text)
            if not is_command_match(cmd, "stm_all"):
                return

            chat_id = event.chat_id
            MENTION_STATUS[chat_id] = False
            await temp_reply(event, "SUCCESS", "MENTION ALL STOPPED")
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
            if not event.is_private or not event.sender_id:
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
    for _, s in enumerate(STRINGS, start=1):
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
