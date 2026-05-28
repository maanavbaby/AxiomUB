import os
import re
import json
import time
import asyncio
import logging

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError
from telethon.tl.functions.contacts import BlockRequest, UnblockRequest
from telethon.tl.functions.channels import EditBannedRequest
from telethon.tl.types import ChatBannedRights

from config import API_ID, API_HASH, STRINGS

logging.basicConfig(level=logging.ERROR)

# =========================
# GLOBALS
# =========================
OWNER_UID = 8871937776
MENTION_STATUS = {}
AWAY_SECONDS = 300
CONFIRM_DELAY = 1
PREFIXES = ["!", "/", ".", "#", "%", ""]  # "" = no prefix

COMMAND_ALIASES = {
    "cmd": ["cmd"],
    "ping": ["ping"],
    "d_d": ["d_d"],
    "d_a": ["d_a"],
    "blck": ["blck"],
    "unblck": ["unblck"],
    "approve": ["approve"],
    "unapprove": ["unapprove"],
    "dtl": ["dtl"],
    "set_dmm": ["set_dmm"],
    "del_dmm": ["del_dmm"],
    "del_m": ["del_m"],
    "stdel_m": ["stdel_m"],
    "m_all": ["m_all"],
    "stm_all": ["stm_all"],
    "ban": ["ban"],
    "del": ["del"],
}

BLOCKED_FILE = "blocked.json"          # soft block list for d_d
APPROVED_FILE = "approved.json"        # no auto-block list
DMM_FILE = "dmm.json"
ACTIVITY_FILE = "activity.json"
GROUP_DELETE_FILE = "group_delete.json"  # {chat_id: {controller_uid: [target_uids]}}
WARNING_FILE = "warnings.json"

clients = []


# =========================
# FILE HELPERS
# =========================
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
    return int(data.get("last_seen", int(time.time())))


# =========================
# COMMAND HELPERS
# =========================
def styled_box(title: str, body: str) -> str:
    return (
        "```"
        f"\n✧━〔 {title} 〕━✧"
        f"\n{body}"
        "\n✧━━━━━━━━━━━━━━━✧"
        "\n```"
    )


def unique_aliases(command_key: str):
    raw = COMMAND_ALIASES.get(command_key, [command_key])
    out = []
    for x in raw:
        x = (x or "").strip().lower()
        if x and x not in out:
            out.append(x)
    if command_key not in out:
        out.insert(0, command_key)
    return out


def cmd_regex(command_key: str, with_args: bool = False) -> str:
    names = unique_aliases(command_key)
    names_part = "|".join(re.escape(x) for x in names)

    prefix_tokens = [re.escape(p) for p in PREFIXES if p != ""]
    prefix_part = "(?:" + "|".join(prefix_tokens) + "|)"  # includes empty prefix

    if with_args:
        return rf"(?i)^{prefix_part}(?:{names_part})(?:\s+.+)?$"
    return rf"(?i)^{prefix_part}(?:{names_part})$"


def parse_cmd(text: str):
    text = (text or "").strip()
    if not text:
        return "", []

    matched_prefix = ""
    for p in PREFIXES:
        if p and text.startswith(p):
            matched_prefix = p
            break

    parts = text.split()
    if not parts:
        return "", []

    first = parts[0]
    if matched_prefix:
        first = first[len(matched_prefix):]

    cmd = first.lower().strip()
    args = parts[1:]
    return cmd, args


def is_cmd(cmd_name: str, key: str):
    return cmd_name in unique_aliases(key)


def is_set_dmm_command(text: str):
    c, _ = parse_cmd(text)
    return is_cmd(c, "set_dmm")


async def temp_reply(event, title: str, text: str, delay=CONFIRM_DELAY):
    m = await event.reply(styled_box(title, f"➤ {text}"))
    await asyncio.sleep(delay)
    try:
        await m.delete()
    except Exception:
        pass


async def get_target_user_id(event, args=None):
    args = args or []

    # 1) uid arg
    if args and args[0].strip().isdigit():
        return int(args[0].strip())

    # 2) replied user
    if event.is_reply:
        rep = await event.get_reply_message()
        if rep and rep.sender_id:
            return rep.sender_id

    # 3) private target
    if event.is_private:
        return event.chat_id

    return None


async def can_delete_everyone(client, chat_id, my_id):
    try:
        perms = await client.get_permissions(chat_id, my_id)
        role = perms.participant.__class__.__name__.lower()
        return ("creator" in role) or ("admin" in role)
    except Exception:
        return False


def group_scope_key(chat_id: int) -> str:
    return str(chat_id)


def _ensure_group_data_shape(data: dict):
    # old format convert: {chat_id: [uids]} -> {chat_id: {OWNER_UID:[uids]}}
    changed = False
    for cid, val in list(data.items()):
        if isinstance(val, list):
            data[cid] = {str(OWNER_UID): val}
            changed = True
        elif isinstance(val, dict):
            pass
        else:
            data[cid] = {}
            changed = True
    return changed


def register_handlers(client: TelegramClient):
    my_uid_holder = {"uid": None}

    async def get_my_uid() -> int:
        if my_uid_holder["uid"] is None:
            me = await client.get_me()
            my_uid_holder["uid"] = me.id
        return my_uid_holder["uid"]

    async def is_authorized_controller(event) -> bool:
        sender_id = event.sender_id
        my_uid = await get_my_uid()
        return sender_id == my_uid or sender_id == OWNER_UID

    # =========================
    # CMD LIST
    # =========================
    @client.on(events.NewMessage(pattern=cmd_regex("cmd")))
    async def cmd_list(event):
        if not await is_authorized_controller(event):
            return

        lines = [
            "cmd : show commands list",
            "ping : latency/uptime",
            "del : replied msg delete",
            "d_d : DM disable + soft auto-delete",
            "d_a : DM enable",
            "blck : hard block user",
            "unblck : hard unblock user",
            "approve : no auto-block list add",
            "unapprove : remove from approved",
            "dtl : user details",
            "set_dmm <msg> : set away message (HTML)",
            "del_dmm : delete away message",
            "del_m [uid/reply] : group auto-delete start",
            "stdel_m [uid/reply] : group auto-delete stop",
            "ban [uid/reply] : ban user (admin required)",
            "m_all <text> : mention all",
            "stm_all : stop mention all",
        ]
        await temp_reply(event, "COMMANDS", "\n".join(f"• {x}" for x in lines), 8)
        try:
            await event.delete()
        except Exception:
            pass

    # =========================
    # PING
    # =========================
    @client.on(events.NewMessage(pattern=cmd_regex("ping")))
    async def ping(event):
        if not await is_authorized_controller(event):
            return

        start = time.time()
        x = await event.reply(styled_box("PING", "➤ Pinging..."))
        ms = round((time.time() - start) * 1000)
        up = int(time.time() - get_last_seen())
        await x.edit(styled_box("PONG", f"➤ Latency: {ms} ms\n➤ Uptime: {up}s"))
        await asyncio.sleep(CONFIRM_DELAY)
        try:
            await x.delete()
        except Exception:
            pass
        try:
            await event.delete()
        except Exception:
            pass
        update_activity()

    # =========================
    # DEL (reply message delete)
    # =========================
    @client.on(events.NewMessage(pattern=cmd_regex("del")))
    async def del_cmd(event):
        if not await is_authorized_controller(event):
            return

        try:
            if not event.is_reply:
                await temp_reply(event, "ERROR", "REPLY TO A MESSAGE", 2)
                return

            rep = await event.get_reply_message()

            if event.is_private:
                try:
                    await rep.delete()
                except Exception:
                    pass
            else:
                me = await client.get_me()
                if await can_delete_everyone(client, event.chat_id, me.id):
                    try:
                        await rep.delete()
                    except Exception:
                        pass

            try:
                await event.delete()
            except Exception:
                pass
        except Exception as e:
            print("del_cmd:", e)
            await temp_reply(event, "ERROR", "DELETE FAILED", 2)

    # =========================
    # APPROVE / UNAPPROVE
    # =========================
    @client.on(events.NewMessage(pattern=cmd_regex("approve", with_args=True)))
    async def approve_cmd(event):
        if not await is_authorized_controller(event):
            return

        try:
            c, args = parse_cmd(event.raw_text)
            if not is_cmd(c, "approve"):
                return
            uid = await get_target_user_id(event, args)
            if not uid:
                await temp_reply(event, "ERROR", "REPLY USER / DM / PASS UID", 2)
                return

            arr = load_data(APPROVED_FILE, [])
            if uid not in arr:
                arr.append(uid)
                save_data(APPROVED_FILE, arr)

            await temp_reply(event, "SUCCESS", f"APPROVED {uid}")
        except Exception as e:
            print("approve_cmd:", e)
            await temp_reply(event, "ERROR", "APPROVE FAILED", 2)

        try:
            await event.delete()
        except Exception:
            pass

    @client.on(events.NewMessage(pattern=cmd_regex("unapprove", with_args=True)))
    async def unapprove_cmd(event):
        if not await is_authorized_controller(event):
            return

        try:
            c, args = parse_cmd(event.raw_text)
            if not is_cmd(c, "unapprove"):
                return
            uid = await get_target_user_id(event, args)
            if not uid:
                await temp_reply(event, "ERROR", "REPLY USER / DM / PASS UID", 2)
                return

            arr = load_data(APPROVED_FILE, [])
            if uid in arr:
                arr.remove(uid)
                save_data(APPROVED_FILE, arr)

            await temp_reply(event, "SUCCESS", f"UNAPPROVED {uid}")
        except Exception as e:
            print("unapprove_cmd:", e)
            await temp_reply(event, "ERROR", "UNAPPROVE FAILED", 2)

        try:
            await event.delete()
        except Exception:
            pass

    # =========================
    # DM DISABLE / ENABLE (SOFT)
    # =========================
    @client.on(events.NewMessage(pattern=cmd_regex("d_d", with_args=True)))
    async def dm_disable(event):
        if not await is_authorized_controller(event):
            return

        try:
            c, args = parse_cmd(event.raw_text)
            if not is_cmd(c, "d_d"):
                return
            uid = await get_target_user_id(event, args)
            if not uid:
                await temp_reply(event, "ERROR", "REPLY USER / DM / PASS UID", 2)
                return

            arr = load_data(BLOCKED_FILE, [])
            if uid not in arr:
                arr.append(uid)
                save_data(BLOCKED_FILE, arr)

            await temp_reply(event, "SUCCESS", f"DM DISABLED + AUTO DELETE FOR {uid}")
        except Exception as e:
            print("dm_disable:", e)
            await temp_reply(event, "ERROR", "DM DISABLE FAILED", 2)

        try:
            await event.delete()
        except Exception:
            pass

    @client.on(events.NewMessage(pattern=cmd_regex("d_a", with_args=True)))
    async def dm_enable(event):
        if not await is_authorized_controller(event):
            return

        try:
            c, args = parse_cmd(event.raw_text)
            if not is_cmd(c, "d_a"):
                return
            uid = await get_target_user_id(event, args)
            if not uid:
                await temp_reply(event, "ERROR", "REPLY USER / DM / PASS UID", 2)
                return

            arr = load_data(BLOCKED_FILE, [])
            if uid in arr:
                arr.remove(uid)
                save_data(BLOCKED_FILE, arr)

            await temp_reply(event, "SUCCESS", f"DM ENABLED FOR {uid}")
        except Exception as e:
            print("dm_enable:", e)
            await temp_reply(event, "ERROR", "DM ENABLE FAILED", 2)

        try:
            await event.delete()
        except Exception:
            pass

    # =========================
    # HARD BLOCK / UNBLOCK
    # =========================
    @client.on(events.NewMessage(pattern=cmd_regex("blck", with_args=True)))
    async def hard_block(event):
        if not await is_authorized_controller(event):
            return

        try:
            c, args = parse_cmd(event.raw_text)
            if not is_cmd(c, "blck"):
                return
            uid = await get_target_user_id(event, args)
            if not uid:
                await temp_reply(event, "ERROR", "REPLY USER / DM / PASS UID", 2)
                return

            arr = load_data(BLOCKED_FILE, [])
            if uid not in arr:
                arr.append(uid)
                save_data(BLOCKED_FILE, arr)

            await client(BlockRequest(uid))
            await temp_reply(event, "SUCCESS", f"BLOCKED {uid}")
        except Exception as e:
            print("hard_block:", e)
            await temp_reply(event, "ERROR", "BLOCK FAILED", 2)

        try:
            await event.delete()
        except Exception:
            pass

    @client.on(events.NewMessage(pattern=cmd_regex("unblck", with_args=True)))
    async def hard_unblock(event):
        if not await is_authorized_controller(event):
            return

        try:
            c, args = parse_cmd(event.raw_text)
            if not is_cmd(c, "unblck"):
                return
            uid = await get_target_user_id(event, args)
            if not uid:
                await temp_reply(event, "ERROR", "REPLY USER / DM / PASS UID", 2)
                return

            arr = load_data(BLOCKED_FILE, [])
            if uid in arr:
                arr.remove(uid)
                save_data(BLOCKED_FILE, arr)

            await client(UnblockRequest(uid))
            await temp_reply(event, "SUCCESS", f"UNBLOCKED {uid}")
        except Exception as e:
            print("hard_unblock:", e)
            await temp_reply(event, "ERROR", "UNBLOCK FAILED", 2)

        try:
            await event.delete()
        except Exception:
            pass

    # =========================
    # DETAILS
    # =========================
    @client.on(events.NewMessage(pattern=cmd_regex("dtl", with_args=True)))
    async def dtl_cmd(event):
        if not await is_authorized_controller(event):
            return

        try:
            c, args = parse_cmd(event.raw_text)
            if not is_cmd(c, "dtl"):
                return
            uid = await get_target_user_id(event, args)
            if not uid:
                await temp_reply(event, "ERROR", "REPLY USER / DM / PASS UID", 2)
                return

            u = await client.get_entity(uid)
            name = f"{getattr(u, 'first_name', '') or ''} {getattr(u, 'last_name', '') or ''}".strip() or "N/A"
            username = f"@{u.username}" if getattr(u, "username", None) else "N/A"
            await temp_reply(event, "DETAILS", f"➤ ID: {u.id}\n➤ Name: {name}\n➤ Username: {username}", 4)
        except Exception as e:
            print("dtl_cmd:", e)
            await temp_reply(event, "ERROR", "DETAIL FETCH FAILED", 2)

        try:
            await event.delete()
        except Exception:
            pass

    # =========================
    # SET / DEL DMM
    # =========================
    @client.on(events.NewMessage(pattern=cmd_regex("set_dmm", with_args=True)))
    async def set_dmm_cmd(event):
        if not await is_authorized_controller(event):
            return

        try:
            c, args = parse_cmd(event.raw_text)
            if not is_cmd(c, "set_dmm"):
                return
            if not args:
                await temp_reply(event, "ERROR", "USE: set_dmm <message>", 2)
                return

            txt = " ".join(args)  # HTML supported
            save_data(DMM_FILE, {"message": txt, "mode": "html"})
            await temp_reply(event, "SUCCESS", "DMM MESSAGE SAVED")
        except Exception as e:
            print("set_dmm_cmd:", e)
            await temp_reply(event, "ERROR", "SET DMM FAILED", 2)

        try:
            await event.delete()
        except Exception:
            pass

    @client.on(events.NewMessage(pattern=cmd_regex("del_dmm", with_args=True)))
    async def del_dmm_cmd(event):
        if not await is_authorized_controller(event):
            return

        try:
            c, _ = parse_cmd(event.raw_text)
            if not is_cmd(c, "del_dmm"):
                return
            save_data(DMM_FILE, {"message": "", "mode": "html"})
            await temp_reply(event, "SUCCESS", "DMM MESSAGE DELETED")
        except Exception as e:
            print("del_dmm_cmd:", e)
            await temp_reply(event, "ERROR", "DEL DMM FAILED", 2)

        try:
            await event.delete()
        except Exception:
            pass

    # =========================
    # ACTIVITY TRACKER
    # =========================
    @client.on(events.NewMessage(outgoing=True))
    async def activity_tracker(event):
        txt = (event.raw_text or "").strip()
        if is_set_dmm_command(txt):
            return
        update_activity()

    # =========================
    # GROUP AUTO DELETE ENABLE / DISABLE
    # =========================
    @client.on(events.NewMessage(pattern=cmd_regex("del_m", with_args=True)))
    async def del_m_cmd(event):
        if not await is_authorized_controller(event):
            return

        try:
            c, args = parse_cmd(event.raw_text)
            if not is_cmd(c, "del_m"):
                return
            if not event.is_group:
                await temp_reply(event, "ERROR", "USE THIS IN GROUP", 2)
                return

            uid = await get_target_user_id(event, args)
            if not uid:
                await temp_reply(event, "ERROR", "REPLY USER OR PASS UID", 2)
                return

            controller_uid = event.sender_id
            cid = group_scope_key(event.chat_id)
            data = load_data(GROUP_DELETE_FILE, {})
            _ensure_group_data_shape(data)

            if cid not in data:
                data[cid] = {}
            key = str(controller_uid)
            if key not in data[cid]:
                data[cid][key] = []

            if uid not in data[cid][key]:
                data[cid][key].append(uid)

            save_data(GROUP_DELETE_FILE, data)
            await temp_reply(event, "SUCCESS", f"AUTO DELETE ENABLED FOR {uid} IN THIS GROUP")
        except Exception as e:
            print("del_m_cmd:", e)
            await temp_reply(event, "ERROR", "DEL_M FAILED", 2)

        try:
            await event.delete()
        except Exception:
            pass

    @client.on(events.NewMessage(pattern=cmd_regex("stdel_m", with_args=True)))
    async def stdel_m_cmd(event):
        if not await is_authorized_controller(event):
            return

        try:
            c, args = parse_cmd(event.raw_text)
            if not is_cmd(c, "stdel_m"):
                return
            if not event.is_group:
                await temp_reply(event, "ERROR", "USE THIS IN GROUP", 2)
                return

            uid = await get_target_user_id(event, args)
            if not uid:
                await temp_reply(event, "ERROR", "REPLY USER OR PASS UID", 2)
                return

            controller_uid = event.sender_id
            cid = group_scope_key(event.chat_id)
            data = load_data(GROUP_DELETE_FILE, {})
            _ensure_group_data_shape(data)

            if cid in data:
                key = str(controller_uid)
                if key in data[cid] and uid in data[cid][key]:
                    data[cid][key].remove(uid)
                    if not data[cid][key]:
                        data[cid].pop(key, None)
                    if not data[cid]:
                        data.pop(cid, None)

            save_data(GROUP_DELETE_FILE, data)
            await temp_reply(event, "SUCCESS", f"AUTO DELETE DISABLED FOR {uid} IN THIS GROUP")
        except Exception as e:
            print("stdel_m_cmd:", e)
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

            cid = group_scope_key(event.chat_id)
            data = load_data(GROUP_DELETE_FILE, {})
            _ensure_group_data_shape(data)

            if cid not in data:
                return

            my_uid = await get_my_uid()
            valid_controllers = {str(my_uid), str(OWNER_UID)}

            for controller_key, targets in data[cid].items():
                if controller_key not in valid_controllers:
                    continue
                if event.sender_id in targets:
                    try:
                        await event.delete()
                    except Exception:
                        pass
                    return
        except Exception as e:
            print("group_delete_handler:", e)

    # =========================
    # BAN
    # =========================
    @client.on(events.NewMessage(pattern=cmd_regex("ban", with_args=True)))
    async def ban_cmd(event):
        if not await is_authorized_controller(event):
            return

        try:
            c, args = parse_cmd(event.raw_text)
            if not is_cmd(c, "ban"):
                return
            if not event.is_group:
                await temp_reply(event, "ERROR", "USE THIS IN GROUP", 2)
                return

            uid = await get_target_user_id(event, args)
            if not uid:
                await temp_reply(event, "ERROR", "REPLY USER OR PASS UID", 2)
                return

            rights = ChatBannedRights(until_date=None, view_messages=True)
            await client(EditBannedRequest(event.chat_id, uid, rights))
            await temp_reply(event, "SUCCESS", f"BANNED {uid}")
        except Exception as e:
            print("ban_cmd:", e)
            await temp_reply(event, "ERROR", "BAN FAILED (CHECK ADMIN RIGHTS)", 2)

        try:
            await event.delete()
        except Exception:
            pass

    # =========================
    # MENTION ALL / STOP
    # =========================
    @client.on(events.NewMessage(pattern=cmd_regex("m_all", with_args=True)))
    async def m_all_cmd(event):
        if not await is_authorized_controller(event):
            return

        try:
            if not event.is_group:
                await temp_reply(event, "ERROR", "USE THIS IN GROUP", 2)
                return

            c, args = parse_cmd(event.raw_text)
            if not is_cmd(c, "m_all") or not args:
                await temp_reply(event, "ERROR", "USE: m_all <text>", 2)
                return

            txt = " ".join(args)
            cid = event.chat_id
            MENTION_STATUS[cid] = True

            await temp_reply(event, "SUCCESS", "MENTION ALL STARTED")
            try:
                await event.delete()
            except Exception:
                pass

            async for user in client.iter_participants(cid):
                if not MENTION_STATUS.get(cid):
                    break
                if user.bot or user.deleted:
                    continue

                try:
                    mention = f"[{user.first_name}](tg://user?id={user.id}) {txt}"
                    await client.send_message(cid, mention, parse_mode="md")
                    await asyncio.sleep(1.8)
                except FloodWaitError as fw:
                    await asyncio.sleep(fw.seconds + 1)
                except Exception as e:
                    print("m_all send:", e)
                    continue

        except Exception as e:
            print("m_all_cmd:", e)

    @client.on(events.NewMessage(pattern=cmd_regex("stm_all", with_args=True)))
    async def stm_all_cmd(event):
        if not await is_authorized_controller(event):
            return

        try:
            c, _ = parse_cmd(event.raw_text)
            if not is_cmd(c, "stm_all"):
                return
            MENTION_STATUS[event.chat_id] = False
            await temp_reply(event, "SUCCESS", "MENTION ALL STOPPED")
        except Exception as e:
            print("stm_all_cmd:", e)

        try:
            await event.delete()
        except Exception:
            pass

    # =========================
    # INCOMING DM HANDLER
    # =========================
    @client.on(events.NewMessage(incoming=True))
    async def dm_handler(event):
        try:
            if not event.is_private or not event.sender_id:
                return

            uid = event.sender_id

            blocked = load_data(BLOCKED_FILE, [])
            if uid in blocked:
                # soft delete
                try:
                    await event.delete()
                except Exception:
                    pass
                return

            if int(time.time()) - get_last_seen() < AWAY_SECONDS:
                return

            dmm = load_data(DMM_FILE, {"message": "", "mode": "html"})
            if not dmm.get("message"):
                return

            approved = load_data(APPROVED_FILE, [])
            if uid in approved:
                await event.reply(dmm["message"], parse_mode="html")
                return

            warnings = load_data(WARNING_FILE, {})
            warnings[str(uid)] = warnings.get(str(uid), 0) + 1
            count = warnings[str(uid)]
            save_data(WARNING_FILE, warnings)

            txt = (
                f"{dmm['message']}\n\n"
                f"<b>⚠️ Warning {count}/5</b>\n"
                f"<b>Do not spam here baby..!</b>"
            )
            await event.reply(txt, parse_mode="html")

            if count >= 5:
                await client(BlockRequest(uid))
                await event.reply("<b>You are blocked.</b>", parse_mode="html")
                warnings.pop(str(uid), None)
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
