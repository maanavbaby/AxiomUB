import os, json, time, asyncio, logging
from pyrogram import Client, filters, idle
from pyrogram.types import Message
from config import API_ID, API_HASH, STRINGS

logging.basicConfig(level=logging.ERROR)

APPS = []
for num, string in enumerate(STRINGS, start=1):
    client = Client(f"userbot{num}", api_id=API_ID, api_hash=API_HASH, session_string=string, workers=8)
    APPS.append(client)

BLOCKED_FILE = "blocked.json"
DMM_FILE = "dmm.json"
ACTIVITY_FILE = "activity.json"
GROUP_DELETE_FILE = "group_delete.json"
WARNING_FILE = "warnings.json"
AWAY_SECONDS = 30
MENTION_STATUS = {}

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

def register_handlers(app: Client):
    prefixes = [".", "!"]

    def get_text(msg: Message):
        return (msg.text or "").strip()

    async def send_confirm(msg: Message, text: str, delay: int = 2):
        x = await msg.reply(f"`{text}`")
        await asyncio.sleep(delay)
        try: await x.delete()
        except: pass

    async def send_error(msg: Message, text: str, delay: int = 3):
        x = await msg.reply(f"`ERROR: {text}`")
        await asyncio.sleep(delay)
        try: await x.delete()
        except: pass

    async def resolve_target_user(msg: Message):
        # prefer reply target, else private chat user
        if msg.reply_to_message and msg.reply_to_message.from_user:
            return msg.reply_to_message.from_user.id
        if msg.chat and msg.chat.type.name == "PRIVATE":
            return msg.chat.id
        return None

    @app.on_message(filters.me & filters.command("ping", prefixes=prefixes))
    async def ping(_, msg: Message):
        start = time.time()
        x = await msg.reply("`Pinging...`")
        ms = round((time.time() - start) * 1000)
        await x.edit(f"`Pong! {ms}ms`")
        await asyncio.sleep(2)
        try: await x.delete()
        except: pass
        try: await msg.delete()
        except: pass
        update_activity()

    @app.on_message(filters.me & filters.command("blck", prefixes=prefixes))
    async def hard_block_user(client, msg: Message):
        try:
            target = await resolve_target_user(msg)
            if not target:
                await send_error(msg, "USE IN DM OR REPLY USER IN GROUP")
                return
            blocked = load_data(BLOCKED_FILE, [])
            if target not in blocked:
                blocked.append(target)
                save_data(BLOCKED_FILE, blocked)
            await client.block_user(target)
            await send_confirm(msg, f"BLOCKED {target}")
        except Exception as e:
            print("Block Error:", e)
        try: await msg.delete()
        except: pass

    @app.on_message(filters.me & filters.command("unblck", prefixes=prefixes))
    async def hard_unblock_user(client, msg: Message):
        try:
            target = await resolve_target_user(msg)
            if not target:
                await send_error(msg, "USE IN DM OR REPLY USER IN GROUP")
                return
            blocked = load_data(BLOCKED_FILE, [])
            if target in blocked:
                blocked.remove(target)
                save_data(BLOCKED_FILE, blocked)
            await client.unblock_user(target)
            await send_confirm(msg, f"UNBLOCKED {target}")
        except Exception as e:
            print("Unblock Error:", e)
        try: await msg.delete()
        except: pass

    @app.on_message(filters.me & filters.command("d_d", prefixes=prefixes))
    async def dm_disable(_, msg: Message):
        try:
            target = await resolve_target_user(msg)
            if not target:
                await send_error(msg, "DM ME USE DIRECTLY OR REPLY USER IN GROUP")
                return
            blocked = load_data(BLOCKED_FILE, [])
            if target not in blocked:
                blocked.append(target)
                save_data(BLOCKED_FILE, blocked)
            await send_confirm(msg, f"DM DISABLED FOR {target}")
        except Exception as e:
            print("d_d Error:", e)
        try: await msg.delete()
        except: pass
        update_activity()

    @app.on_message(filters.me & filters.command("d_a", prefixes=prefixes))
    async def dm_allow(_, msg: Message):
        try:
            target = await resolve_target_user(msg)
            if not target:
                await send_error(msg, "DM ME USE DIRECTLY OR REPLY USER IN GROUP")
                return
            blocked = load_data(BLOCKED_FILE, [])
            if target in blocked:
                blocked.remove(target)
                save_data(BLOCKED_FILE, blocked)
            await send_confirm(msg, f"DM ENABLED FOR {target}")
        except Exception as e:
            print("d_a Error:", e)
        try: await msg.delete()
        except: pass
        update_activity()

    # group auto-delete handler
    @app.on_message(filters.group & ~filters.me)
    async def group_delete_handler(client, msg: Message):
        try:
            if not msg.from_user: return
            user_id = msg.from_user.id
            chat_id = str(msg.chat.id)
            data = load_data(GROUP_DELETE_FILE, {})
            if chat_id in data and user_id in data[chat_id]:
                try: await msg.delete()
                except: pass
        except Exception as e:
            print("Group delete handler error:", e)

    # private DM handler
    @app.on_message(filters.private & ~filters.me & filters.text)
    async def dm_handler(client, msg: Message):
        try:
            if not msg.from_user or msg.from_user.is_bot: return
            user_id = msg.from_user.id
            blocked = load_data(BLOCKED_FILE, [])
            if user_id in blocked: return
            last_seen = get_last_seen()
            if int(time.time()) - last_seen < AWAY_SECONDS: return
            dmm = load_data(DMM_FILE, {"message": "", "mode": "html"})
            if not dmm.get("message"): return
            warnings = load_data(WARNING_FILE, {})
            warnings.setdefault(str(user_id), 0)
            warnings[str(user_id)] += 1
            count = warnings[str(user_id)]
            save_data(WARNING_FILE, warnings)
            reply_text = (f"{dmm['message']}\n\n<b>⚠️ Warning {count}/5</b>\nDo not spam me.")
            await msg.reply(reply_text, parse_mode="HTML")
            if count >= 5:
                await client.block_user(user_id)
                await msg.reply("<b>You are blocked.</b>", parse_mode="HTML")
                warnings.pop(str(user_id), None)
                save_data(WARNING_FILE, warnings)
        except Exception as e:
            print("DM Handler Error:", e)

    # register more handlers as needed...

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
