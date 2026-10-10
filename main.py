import asyncio
import logging
import sqlite3
import aiohttp
import base64
import uuid
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = "8735387444:AAExe7opJVLSrJYWyX71WZIu0L-5iGpbR6Q"
ADMIN_ID = 1607756200

SHOP_ID = "1347210"
SECRET_KEY = "live_dnea3gP37htLf-z10IZFywEqB7j12yM-kBOty2dDU08"
RETURN_URL = "https://t.me/delyavpnrobot"

H1_API = "http://de20.h1cloud.net:25091"
H1_TOKEN = "de25bba033ac482b820938d7d3f5ec4bc3b80a8e4c5547eb85cbe10c7ef2a0a1"

NODE_TAG = "🇩🇪 Germany VPN"
SUPPORT_USERNAME = "delyahelpbot"  

CHANNEL_ID = "3916249636"
CHANNEL_URL = "https://t.me/delyavpnn"

EMOJI_BUY    = "5988023995125993550"
EMOJI_KEYS   = "5877332341331857066"
EMOJI_PROF   = "5908808657700655253"
EMOJI_INFO   = "5875206779196935950"
EMOJI_HELP   = "5931415565955503486"
EMOJI_REF    = "5906995262378741881"
EMOJI_BACK   = "5875084456187185124"

TARIFFS = {
    "49":  {"price": 49,  "days": 7},
    "99":  {"price": 99,  "days": 14},
    "299": {"price": 299, "days": 30},
}

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

db = sqlite3.connect("vpn.db", check_same_thread=False)
db.execute("PRAGMA journal_mode=WAL")
db.execute("PRAGMA synchronous=NORMAL")
cur = db.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT,
    full_name TEXT,
    balance INTEGER DEFAULT 0,
    sub_until TEXT,
    client_name TEXT,
    vless_link TEXT,
    created_at TEXT
)
""")
db.commit()

pending = {}
processed_payments = set()

session: aiohttp.ClientSession | None = None

async def get_session() -> aiohttp.ClientSession:
    global session
    if session is None or session.closed:
        session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=False, limit=50, ttl_dns_cache=300),
            timeout=aiohttp.ClientTimeout(total=8)
        )
    return session

def user_row(uid):
    cur.execute("SELECT id, username, full_name, balance, sub_until, client_name, vless_link, created_at FROM users WHERE id=?", (uid,))
    return cur.fetchone()

def save_user(u):
    cur.execute("SELECT id FROM users WHERE id=?", (u.id,))
    if cur.fetchone() is None:
        cur.execute(
            "INSERT INTO users (id, username, full_name, created_at) VALUES (?, ?, ?, ?)",
            (u.id, u.username, u.full_name, datetime.now().isoformat())
        )
    else:
        cur.execute("UPDATE users SET username=?, full_name=? WHERE id=?", (u.username, u.full_name, u.id))
    db.commit()

def grant_sub(uid, days):
    r = user_row(uid)
    if not r:
        return None
    now = datetime.now()
    if r[4] and datetime.fromisoformat(r[4]) > now:
        until = datetime.fromisoformat(r[4]) + timedelta(days=days)
    else:
        until = now + timedelta(days=days)
    cur.execute("UPDATE users SET sub_until=? WHERE id=?", (until.isoformat(), uid))
    db.commit()
    return until

def save_client(uid, client_name, link):
    cur.execute("UPDATE users SET client_name=?, vless_link=? WHERE id=?", (client_name, link, uid))
    db.commit()

def nice_link(vless):
    if not vless:
        return vless
    base = vless.split("#")[0]
    tag = NODE_TAG.replace(" ", "%20")
    return f"{base}#{tag}"

def copy_kb(link):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Скопировать ключ", copy_text=types.CopyTextButton(text=link), style="success")],
        [InlineKeyboardButton(text="Назад", callback_data="back", style="primary", icon_custom_emoji_id=EMOJI_BACK)],
    ])

async def check_sub(uid):
    if CHANNEL_ID == "@твой_канал":
        return True
    try:
        m = await bot.get_chat_member(CHANNEL_ID, uid)
        return m.status in ("creator", "administrator", "member")
    except Exception as e:
        print("SUB CHECK ERR:", e)
        return True

def sub_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Подписаться", url=CHANNEL_URL, style="primary")],
        [InlineKeyboardButton(text="Проверить", callback_data="check_sub", style="success")],
    ])

async def h1_create(name, days):
    s = await get_session()
    headers = {"Authorization": f"Bearer {H1_TOKEN}", "Content-Type": "application/json"}
    try:
        async with s.post(f"{H1_API}/create", json={"name": name, "days": days}, headers=headers) as r:
            if r.status in (200, 201):
                return await r.json()
            print("H1 CREATE ERR:", r.status, await r.text())
    except Exception as e:
        print("H1 CREATE EXC:", e)
    return None

async def h1_info(name):
    s = await get_session()
    headers = {"Authorization": f"Bearer {H1_TOKEN}"}
    try:
        async with s.get(f"{H1_API}/info", params={"name": name}, headers=headers) as r:
            if r.status == 200:
                return await r.json()
    except Exception as e:
        print("H1 INFO EXC:", e)
    return None

async def h1_edit(name, days):
    s = await get_session()
    headers = {"Authorization": f"Bearer {H1_TOKEN}", "Content-Type": "application/json"}
    try:
        async with s.patch(f"{H1_API}/edit", json={"name": name, "days": days}, headers=headers) as r:
            if r.status in (200, 201):
                return await r.json()
            print("H1 EDIT ERR:", r.status, await r.text())
    except Exception as e:
        print("H1 EDIT EXC:", e)
    return None

async def h1_delete(name):
    s = await get_session()
    headers = {"Authorization": f"Bearer {H1_TOKEN}"}
    try:
        async with s.delete(f"{H1_API}/clients/{name}", headers=headers) as r:
            return r.status in (200, 204)
    except Exception as e:
        print("H1 DELETE EXC:", e)
    return False

async def get_or_create_client(uid, days):
    name = f"user_{uid}"
    info = await h1_info(name)
    if info and info.get("ok") and info.get("client"):
        await h1_edit(name, days)
        info2 = await h1_info(name)
        if info2 and info2.get("ok"):
            info = info2
    else:
        r = await h1_create(name, days)
        if not r or not r.get("ok"):
            return None
        info = r
    c = info["client"]
    links = c.get("inbound_links") or []
    vless = links[0]["link"] if links else ""
    sub_url = c.get("sub_url") or ""
    return {"name": name, "vless": vless, "sub_url": sub_url, "client": c}

async def create_pay(uid, price):
    s = await get_session()
    auth = base64.b64encode(f"{SHOP_ID}:{SECRET_KEY}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json",
        "Idempotence-Key": str(uuid.uuid4())
    }
    data = {
        "amount": {"value": f"{price}.00", "currency": "RUB"},
        "capture": True,
        "confirmation": {"type": "redirect", "return_url": RETURN_URL},
        "description": f"Оплата {price} руб.",
        "metadata": {"user_id": str(uid)}
    }
    try:
        async with s.post("https://api.yookassa.ru/v3/payments", json=data, headers=headers) as r:
            if r.status == 200:
                j = await r.json()
                return j["confirmation"]["confirmation_url"], j["id"]
            print("YOOKASSA CREATE ERR:", r.status, await r.text())
    except Exception as e:
        print("YOOKASSA CREATE EXC:", e)
    return None, None

async def check_pay(pid):
    s = await get_session()
    auth = base64.b64encode(f"{SHOP_ID}:{SECRET_KEY}".encode()).decode()
    headers = {"Authorization": f"Basic {auth}"}
    try:
        async with s.get(f"https://api.yookassa.ru/v3/payments/{pid}", headers=headers) as r:
            if r.status == 200:
                j = await r.json()
                uid = j.get("metadata", {}).get("user_id")
                return j.get("status") == "succeeded", uid
    except Exception as e:
        print("YOOKASSA CHECK EXC:", e)
    return False, None

def menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Купить VPN", callback_data="buy", style="primary", icon_custom_emoji_id=EMOJI_BUY)],
        [
            InlineKeyboardButton(text="Мои ключи", callback_data="keys", icon_custom_emoji_id=EMOJI_KEYS),
            InlineKeyboardButton(text="Профиль", callback_data="prof", icon_custom_emoji_id=EMOJI_PROF),
        ],
        [
            InlineKeyboardButton(text="Инструкция", callback_data="info", icon_custom_emoji_id=EMOJI_INFO),
            InlineKeyboardButton(text="Поддержка", callback_data="help", style="danger", icon_custom_emoji_id=EMOJI_HELP),
        ],
        [InlineKeyboardButton(text="Рефералка", callback_data="ref", style="success", icon_custom_emoji_id=EMOJI_REF)],
    ])

def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data="back", style="primary", icon_custom_emoji_id=EMOJI_BACK)]
    ])

def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пользователи", callback_data="adm_users", style="primary")],
        [InlineKeyboardButton(text="Поиск по ID", callback_data="adm_search", style="primary")],
        [InlineKeyboardButton(text="Выдать подписку", callback_data="adm_grant", style="success")],
        [InlineKeyboardButton(text="Забрать подписку", callback_data="adm_revoke", style="danger")],
        [InlineKeyboardButton(text="Статистика", callback_data="adm_stats", style="primary")],
        [InlineKeyboardButton(text="Рассылка /send", callback_data="adm_send", style="primary")],
    ])

def admin_user_kb(uid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="+30 дней", callback_data=f"adm_add_{uid}_30", style="success")],
        [InlineKeyboardButton(text="+90 дней", callback_data=f"adm_add_{uid}_90", style="success")],
        [InlineKeyboardButton(text="+365 дней", callback_data=f"adm_add_{uid}_365", style="success")],
        [InlineKeyboardButton(text="Сбросить подписку", callback_data=f"adm_reset_{uid}", style="danger")],
        [InlineKeyboardButton(text="Назад", callback_data="adm_users", style="primary")],
    ])

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    save_user(m.from_user)
    if not await check_sub(m.from_user.id):
        return await m.answer("Чтобы пользоваться ботом, подпишись на канал:", reply_markup=sub_kb())
    await m.answer("Добро пожаловать в VPN-бота.\nВыбери действие:", reply_markup=menu())

@dp.callback_query(F.data == "check_sub")
async def cb_check_sub(c: types.CallbackQuery):
    if await check_sub(c.from_user.id):
        await c.message.edit_text("Добро пожаловать в VPN-бота.\nВыбери действие:", reply_markup=menu())
    else:
        await c.answer("Ты ещё не подписан", show_alert=True)

@dp.message(Command("admin"))
async def cmd_admin(m: types.Message):
    if m.from_user.id != ADMIN_ID:
        return
    await m.answer("Админ-панель:", reply_markup=admin_kb())

@dp.message(Command("send"))
async def cmd_send(m: types.Message):
    if m.from_user.id != ADMIN_ID:
        return
    text = m.text.replace("/send", "", 1).strip()
    if not text:
        return await m.answer("Использование: /send текст сообщения")
    cur.execute("SELECT id FROM users")
    ids = [r[0] for r in cur.fetchall()]
    ok = fail = 0
    for uid in ids:
        try:
            await bot.send_message(uid, text)
            ok += 1
        except Exception as e:
            print("SEND ERR", uid, e)
            fail += 1
        await asyncio.sleep(0.05)
    await m.answer(f"Рассылка завершена.\nДоставлено: {ok}\nНе доставлено: {fail}")

@dp.callback_query(F.data == "adm_send")
async def adm_send(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return await c.answer()
    await c.message.edit_text("Чтобы сделать рассылку, напиши:\n\n/send текст сообщения", reply_markup=admin_kb())
    await c.answer()

@dp.callback_query(F.data == "adm_users")
async def adm_users(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return await c.answer()
    cur.execute("SELECT id, username, full_name, sub_until FROM users ORDER BY created_at DESC LIMIT 20")
    rows = cur.fetchall()
    if not rows:
        return await c.message.edit_text("Пользователей нет.", reply_markup=admin_kb())
    text = "Последние 20 пользователей:\n\n"
    for r in rows:
        sub = r[3][:10] if r[3] else "нет"
        text += f"ID {r[0]} | @{r[1] or '-'} | {r[2]} | до {sub}\n"
    await c.message.edit_text(text, reply_markup=admin_kb())
    await c.answer()

@dp.callback_query(F.data == "adm_search")
async def adm_search(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return await c.answer()
    pending[c.from_user.id] = "search"
    await c.message.edit_text("Отправь ID пользователя для поиска:")
    await c.answer()

@dp.callback_query(F.data == "adm_grant")
async def adm_grant(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return await c.answer()
    pending[c.from_user.id] = "grant"
    await c.message.edit_text("Отправь ID пользователя для выдачи подписки:")
    await c.answer()

@dp.callback_query(F.data == "adm_revoke")
async def adm_revoke(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return await c.answer()
    pending[c.from_user.id] = "revoke"
    await c.message.edit_text("Отправь ID пользователя для сброса подписки:")
    await c.answer()

@dp.callback_query(F.data == "adm_stats")
async def adm_stats(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return await c.answer()
    cur.execute("SELECT COUNT(*) FROM users")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM users WHERE sub_until IS NOT NULL AND sub_until > ?", (datetime.now().isoformat(),))
    active = cur.fetchone()[0]
    await c.message.edit_text(f"Статистика:\n\nВсего: {total}\nС активной подпиской: {active}", reply_markup=admin_kb())
    await c.answer()

@dp.callback_query(F.data.startswith("adm_add_"))
async def adm_add(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return await c.answer()
    await c.answer()
    _, _, uid, days = c.data.split("_")
    uid = int(uid)
    days = int(days)
    r = user_row(uid)
    if not r:
        cur.execute(
            "INSERT INTO users (id, username, full_name, created_at) VALUES (?, ?, ?, ?)",
            (uid, None, "admin_added", datetime.now().isoformat())
        )
        db.commit()
    cl = await get_or_create_client(uid, days)
    if not cl:
        return await c.message.edit_text("Клиент не создался в h1cloud", reply_markup=admin_user_kb(uid))
    until = grant_sub(uid, days)
    link = nice_link(cl["vless"])
    save_client(uid, cl["name"], link)
    try:
        await bot.send_message(uid, f"Тебе выдана подписка на {days} дней.\nЖми «Мои ключи» чтобы получить ссылку.")
    except Exception as e:
        print("NOTIFY ERR:", e)
    await c.message.edit_text(
        f"Пользователю {uid} выдано +{days} дней.\nПодписка до: {until.strftime('%Y-%m-%d')}\nКлиент: {cl['name']}",
        reply_markup=admin_user_kb(uid)
    )

@dp.callback_query(F.data.startswith("adm_reset_"))
async def adm_reset(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return await c.answer()
    await c.answer()
    uid = int(c.data.split("_")[2])
    r = user_row(uid)
    if r and r[5]:
        await h1_delete(r[5])
    cur.execute("UPDATE users SET sub_until=NULL, client_name=NULL, vless_link=NULL WHERE id=?", (uid,))
    db.commit()
    try:
        await bot.send_message(uid, "Твоя подписка сброшена.")
    except Exception:
        pass
    await c.message.edit_text(f"Подписка и клиент пользователя {uid} сброшены.", reply_markup=admin_user_kb(uid))

@dp.message(F.from_user.id == ADMIN_ID, F.text)
async def adm_text(m: types.Message):
    mode = pending.get(m.from_user.id)
    if not mode:
        return
    if not m.text.isdigit():
        await m.answer("Нужен числовой ID.")
        return
    uid = int(m.text)
    r = user_row(uid)
    if not r:
        await m.answer("Пользователь не найден.")
        pending.pop(m.from_user.id, None)
        return
    if mode == "search":
        sub = r[4][:10] if r[4] else "нет"
        status = "есть" if r[4] and datetime.fromisoformat(r[4]) > datetime.now() else "нет"
        client = r[5] or "-"
        await m.answer(
            f"ID: {r[0]}\nUsername: @{r[1] or '-'}\nИмя: {r[2]}\nБаланс: {r[3]}\nПодписка: {status}\nДо: {sub}\nКлиент: {client}\nСоздан: {r[7][:10]}",
            reply_markup=admin_user_kb(uid)
        )
    elif mode == "grant":
        await m.answer("Выбери срок:", reply_markup=admin_user_kb(uid))
    elif mode == "revoke":
        if r[5]:
            await h1_delete(r[5])
        cur.execute("UPDATE users SET sub_until=NULL, client_name=NULL, vless_link=NULL WHERE id=?", (uid,))
        db.commit()
        await m.answer(f"Подписка {uid} сброшена.", reply_markup=admin_user_kb(uid))
    pending.pop(m.from_user.id, None)

@dp.callback_query(F.data == "buy")
async def cb_buy(c: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="7 дней — 49 руб.",  callback_data="pay_49", style="primary")],
        [InlineKeyboardButton(text="14 дней — 99 руб.", callback_data="pay_99", style="primary")],
        [InlineKeyboardButton(text="30 дней — 299 руб.", callback_data="pay_299", style="primary")],
        [InlineKeyboardButton(text="Назад", callback_data="back", style="primary")],
    ])
    await c.message.edit_text("Выбери тариф:", reply_markup=kb)
    await c.answer()

@dp.callback_query(F.data.startswith("pay_"))
async def cb_pay(c: types.CallbackQuery):
    await c.answer()
    tid = c.data[4:]
    if tid not in TARIFFS:
        return
    price = TARIFFS[tid]["price"]
    url, pid = await create_pay(c.from_user.id, price)
    if url:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="ОПЛАТИТЬ", url=url, style="success")],
            [InlineKeyboardButton(text="ПРОВЕРИТЬ", callback_data=f"chk_{pid}_{tid}", style="danger")],
            [InlineKeyboardButton(text="Назад", callback_data="buy", style="primary")],
        ])
        await c.message.edit_text(f"Оплата {price} руб.\n\nНажми кнопку ниже:", reply_markup=kb)
    else:
        await c.message.edit_text("Ошибка создания платежа. Смотри консоль бота.")

@dp.callback_query(F.data.startswith("chk_"))
async def cb_check(c: types.CallbackQuery):
    await c.answer()
    _, pid, tid = c.data.split("_")
    if pid in processed_payments:
        return await c.message.edit_text("Этот платёж уже обработан.")
    ok, uid = await check_pay(pid)
    if ok and str(uid) == str(c.from_user.id):
        processed_payments.add(pid)
        days = TARIFFS.get(tid, {}).get("days", 30)
        await c.message.edit_text("Оплата прошла. Создаю ключ...")
        cl = await get_or_create_client(c.from_user.id, days)
        if not cl:
            return await c.message.edit_text("Оплата прошла, но ключ не создался. Напиши в поддержку.")
        link = nice_link(cl["vless"])
        grant_sub(c.from_user.id, days)
        save_client(c.from_user.id, cl["name"], link)
        await c.message.edit_text(
            f"Оплата прошла. Твой ключ на {days} дней.\n\nНажми кнопку ниже, потом вставь в Happ.",
            reply_markup=copy_kb(link)
        )
    else:
        await c.message.edit_text("Платёж ещё не оплачен. Попробуй позже.")

@dp.callback_query(F.data == "keys")
async def cb_keys(c: types.CallbackQuery):
    if not await check_sub(c.from_user.id):
        await c.answer()
        return await c.message.edit_text("Сначала подпишись на канал:", reply_markup=sub_kb())
    r = user_row(c.from_user.id)
    if not r:
        save_user(c.from_user)
        r = user_row(c.from_user.id)
    sub = r[4] if r and r[4] else None
    vless = r[6] if r else None
    if sub and datetime.fromisoformat(sub) > datetime.now():
        if vless:
            await c.message.edit_text(
                f"Твои ключи:\n\nПодписка активна до {sub[:10]}\n\nКлюч готов. Нажми кнопку ниже чтобы скопировать.",
                reply_markup=copy_kb(vless)
            )
        else:
            await c.message.edit_text("Твои ключи:\n\nКлюч не найден. Пиши в поддержку.", reply_markup=back_kb())
    else:
        await c.message.edit_text("Твои ключи:\n\nАктивной подписки нет.", reply_markup=back_kb())
    await c.answer()

@dp.callback_query(F.data == "prof")
async def cb_prof(c: types.CallbackQuery):
    if not await check_sub(c.from_user.id):
        await c.answer()
        return await c.message.edit_text("Сначала подпишись на канал:", reply_markup=sub_kb())
    r = user_row(c.from_user.id)
    if not r:
        save_user(c.from_user)
        r = user_row(c.from_user.id)
    sub = r[4][:10] if r and r[4] else "нет"
    status = "есть" if r[4] and datetime.fromisoformat(r[4]) > datetime.now() else "нет"
    await c.message.edit_text(
        f"Профиль\n\nID: {r[0]}\nИмя: {r[2]}\nБаланс: {r[3]} руб.\nПодписка: {status}\nДо: {sub}",
        reply_markup=back_kb()
    )
    await c.answer()

@dp.callback_query(F.data == "info")
async def cb_info(c: types.CallbackQuery):
    await c.message.edit_text(
        "Инструкция\n\n1. Скачай Happ.\n2. Нажми + и добавь из ссылки.\n3. Нажми «Мои ключи» и скопируй ключ.\n4. Вставь в Happ.\n5. Подключись.",
        reply_markup=back_kb()
    )
    await c.answer()

@dp.callback_query(F.data == "help")
async def cb_help(c: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Написать в поддержку", url=f"https://t.me/{SUPPORT_USERNAME}", style="primary")],
        [InlineKeyboardButton(text="Назад", callback_data="back", style="primary", icon_custom_emoji_id=EMOJI_BACK)],
    ])
    await c.message.edit_text(
        "Поддержка\n\nНажми кнопку ниже, чтобы написать админу.",
        reply_markup=kb
    )
    await c.answer()

@dp.callback_query(F.data == "ref")
async def cb_ref(c: types.CallbackQuery):
    if not await check_sub(c.from_user.id):
        await c.answer()
        return await c.message.edit_text("Сначала подпишись на канал:", reply_markup=sub_kb())
    uid = c.from_user.id
    uname = (await bot.get_me()).username
    link = f"https://t.me/{uname}?start=ref_{uid}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Поделиться", url=f"https://t.me/share/url?url={link}", style="success", icon_custom_emoji_id=EMOJI_REF)],
        [InlineKeyboardButton(text="Назад", callback_data="back", style="primary", icon_custom_emoji_id=EMOJI_BACK)],
    ])
    await c.message.edit_text(f"Реферальная система\n\nТвоя ссылка:\n{link}", reply_markup=kb)
    await c.answer()

@dp.callback_query(F.data == "back")
async def cb_back(c: types.CallbackQuery):
    await c.message.edit_text("Главное меню:", reply_markup=menu())
    await c.answer()

@dp.errors()
async def err_handler(e: types.ErrorEvent):
    print("ERROR:", e.exception)

async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        if session and not session.closed:
            asyncio.run(session.close())
