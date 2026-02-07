import asyncio
import logging
import aiosqlite
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
import os
from aiogram import Bot, Dispatcher

# Хостинг сам подставит токен из настроек, которые ты укажешь позже
TOKEN = os.getenv('BOT_TOKEN')

bot = Bot(token=TOKEN)
dp = Dispatcher()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

ADMIN_ID = 6938530446  # Твой ID
CHANNEL_ID = "-1003511331392" # ID из @getmyid_bot
CHANNEL_URL = "https://t.me/onlinelav"

# --- СОСТОЯНИЯ ---
class Reg(StatesGroup):
    name = State(); age = State(); city = State(); gender = State(); target_gender = State(); photo = State()

class AdminBroadcast(StatesGroup):
    waiting_for_content = State()

# --- КЛАВИАТУРЫ ---
def main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Смотреть анкеты")],
        [KeyboardButton(text="Моя анкета"), KeyboardButton(text="Кто меня лайкнул?")]
    ], resize_keyboard=True)

def gender_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Мужчина"), KeyboardButton(text="Женщина")]], resize_keyboard=True)

def get_sub_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Подписаться на канал", url=CHANNEL_URL)],
        [InlineKeyboardButton(text="✅ Я подписался", callback_data="check_sub")]
    ])

def action_kb(target_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👎", callback_data=f"dis_{target_id}"), InlineKeyboardButton(text="❤️", callback_data=f"like_{target_id}")],
        [InlineKeyboardButton(text="🚩 Пожаловаться", callback_data=f"report_{target_id}")]
    ])

# --- ПРОВЕРКА ПОДПИСКИ ---
async def is_subscribed(bot: Bot, user_id: int):
    try:
        m = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return m.status in ["member", "administrator", "creator"]
    except Exception as e:
        logging.error(f"Ошибка подписки: {e}")
        return False

# --- БД ---
async def init_db():
    async with aiosqlite.connect("dating.db") as db:
        await db.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, name TEXT, age INTEGER, city TEXT, gender TEXT, target_gender TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS photos (user_id INTEGER, photo_id TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS actions (from_id INTEGER, to_id INTEGER, type TEXT, UNIQUE(from_id, to_id))")
        await db.commit()

router = Router()

# --- СТАРТ ---
@router.message(CommandStart())
async def start(message: types.Message, state: FSMContext, bot: Bot):
    await state.clear()
    if not await is_subscribed(bot, message.from_user.id):
        return await message.answer("<b>Добро пожаловать!</b>\nДля доступа к OnlineLav подпишись на канал.", reply_markup=get_sub_kb())
    
    async with aiosqlite.connect("dating.db") as db:
        async with db.execute("SELECT name FROM users WHERE user_id = ?", (message.from_user.id,)) as c:
            if await c.fetchone(): return await message.answer("С возвращением!", reply_markup=main_kb())
    
    await message.answer("Начнем регистрацию! Как тебя зовут?")
    await state.set_state(Reg.name)

@router.callback_query(F.data == "check_sub")
async def check_sub_cb(call: types.CallbackQuery, bot: Bot, state: FSMContext):
    if await is_subscribed(bot, call.from_user.id):
        await call.message.delete()
        await start(call.message, state, bot)
    else: await call.answer("Вы всё еще не подписаны! ❌", show_alert=True)

# --- РЕГИСТРАЦИЯ ---
@router.message(Reg.name)
async def r_name(m: types.Message, state: FSMContext):
    await state.update_data(name=m.text); await m.answer("Твой возраст?"); await state.set_state(Reg.age)

@router.message(Reg.age)
async def r_age(m: types.Message, state: FSMContext):
    if not m.text.isdigit(): return await m.answer("Цифрами!")
    await state.update_data(age=int(m.text)); await m.answer("Город?"); await state.set_state(Reg.city)

@router.message(Reg.city)
async def r_city(m: types.Message, state: FSMContext):
    await state.update_data(city=m.text.capitalize()); await m.answer("Твой пол?", reply_markup=gender_kb()); await state.set_state(Reg.gender)

@router.message(Reg.gender)
async def r_gender(m: types.Message, state: FSMContext):
    await state.update_data(gender=m.text); await m.answer("Кто интересует?", reply_markup=gender_kb()); await state.set_state(Reg.target_gender)

@router.message(Reg.target_gender)
async def r_target(m: types.Message, state: FSMContext):
    await state.update_data(target_gender=m.text, ph=[]); await m.answer("Пришли фото и нажми /done"); await state.set_state(Reg.photo)

@router.message(Reg.photo, F.photo)
async def r_ph(m: types.Message, state: FSMContext):
    d = await state.get_data(); ph = d.get('ph'); ph.append(m.photo[-1].file_id)
    await state.update_data(ph=ph); await m.answer(f"Фото получено ({len(ph)}). Еще или /done")

@router.message(Reg.photo, Command("done"))
async def r_done(m: types.Message, state: FSMContext):
    d = await state.get_data()
    if not d.get('ph'): return await m.answer("Нужно хотя бы одно фото!")
    async with aiosqlite.connect("dating.db") as db:
        await db.execute("INSERT OR REPLACE INTO users VALUES (?,?,?,?,?,?)", (m.from_user.id, d['name'], d['age'], d['city'], d['gender'], d['target_gender']))
        for p in d['ph']: await db.execute("INSERT INTO photos VALUES (?,?)", (m.from_user.id, p))
        await db.commit()
    await state.clear(); await m.answer("Готово!", reply_markup=main_kb())

# --- ЛЕНТА ---
@router.message(F.text == "Смотреть анкеты")
async def feed(m: types.Message, bot: Bot):
    if not await is_subscribed(bot, m.from_user.id): return await m.answer("Подпишись!", reply_markup=get_sub_kb())
    async with aiosqlite.connect("dating.db") as db:
        async with db.execute("SELECT city, target_gender FROM users WHERE user_id=?", (m.from_user.id,)) as c: me = await c.fetchone()
        if not me: return await m.answer("Создай анкету!")
        q = "SELECT * FROM users WHERE city=? AND gender=? AND user_id!=? AND user_id NOT IN (SELECT to_id FROM actions WHERE from_id=?) ORDER BY RANDOM() LIMIT 1"
        async with db.execute(q, (me[0], me[1], m.from_user.id, m.from_user.id)) as c:
            u = await c.fetchone()
            if not u: return await m.answer("Анкет нет! Сбрось дизлайки.")
            async with db.execute("SELECT photo_id FROM photos WHERE user_id=? LIMIT 1", (u[0],)) as cp:
                p = await cp.fetchone(); await m.answer_photo(p[0], caption=f"🔥 {u[1]}, {u[2]}\n📍 {u[3]}", reply_markup=action_kb(u[0]))

@router.callback_query(F.data.startswith("like_") | F.data.startswith("dis_"))
async def handle_act(call: types.CallbackQuery, bot: Bot):
    act, t_id = call.data.split("_"); t_id = int(t_id); my_id = call.from_user.id
    async with aiosqlite.connect("dating.db") as db:
        await db.execute("INSERT OR IGNORE INTO actions VALUES (?,?,?)", (my_id, t_id, 'like' if act=='like' else 'dislike'))
        await db.commit()
        if act == 'like':
            async with db.execute("SELECT * FROM actions WHERE from_id=? AND to_id=? AND type='like'", (t_id, my_id)) as c:
                if await c.fetchone():
                    await bot.send_message(my_id, f"🎉 Взаимно! [Написать](tg://user?id={t_id})", parse_mode="Markdown")
                    await bot.send_message(t_id, "🎉 У вас новый мэтч!")
    await call.message.delete(); await feed(call.message, bot)

# --- МОЯ АНКЕТА ---
@router.message(F.text == "Моя анкета")
async def my_prof(m: types.Message):
    async with aiosqlite.connect("dating.db") as db:
        async with db.execute("SELECT * FROM users WHERE user_id=?", (m.from_user.id,)) as c:
            u = await c.fetchone()
            if not u: return await m.answer("Нет анкеты.")
            async with db.execute("SELECT photo_id FROM photos WHERE user_id=? LIMIT 1", (m.from_user.id,)) as cp:
                p = await cp.fetchone()
                kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔄 Сброс дизлайков", callback_data="res")], [InlineKeyboardButton(text="🗑 Удалить", callback_data="del")]])
                await m.answer_photo(p[0], caption=f"Твоя анкета:\n👤 {u[1]}, {u[2]}\n📍 {u[3]}", reply_markup=kb)

# --- КТО МЕНЯ ЛАЙКНУЛ ---
@router.message(F.text == "Кто меня лайкнул?")
async def show_likers(m: types.Message):
    async with aiosqlite.connect("dating.db") as db:
        q = """SELECT u.* FROM users u JOIN actions a ON u.user_id = a.from_id 
               WHERE a.to_id = ? AND a.type = 'like' 
               AND u.user_id NOT IN (SELECT to_id FROM actions WHERE from_id = ?) LIMIT 1"""
        async with db.execute(q, (m.from_user.id, m.from_user.id)) as c:
            u = await c.fetchone()
            if not u: return await m.answer("Новых лайков нет.")
            async with db.execute("SELECT photo_id FROM photos WHERE user_id=? LIMIT 1", (u[0],)) as cp:
                p = await cp.fetchone(); await m.answer_photo(p[0], caption=f"Ты понравился: {u[1]}, {u[2]}", reply_markup=action_kb(u[0]))

@router.callback_query(F.data == "res")
async def res_dis(c: types.CallbackQuery):
    async with aiosqlite.connect("dating.db") as db: await db.execute("DELETE FROM actions WHERE from_id=? AND type='dislike'", (c.from_user.id,)); await db.commit()
    await c.answer("Сброшено!", show_alert=True)

@router.callback_query(F.data == "del")
async def del_ank(c: types.CallbackQuery):
    async with aiosqlite.connect("dating.db") as db: 
        await db.execute("DELETE FROM users WHERE user_id=?", (c.from_user.id,))
        await db.execute("DELETE FROM photos WHERE user_id=?", (c.from_user.id,))
        await db.commit()
    await c.message.answer("Удалено."); await c.answer()

@router.message(Command("stats"))
async def stats(m: types.Message):
    if m.from_user.id == ADMIN_ID:
        async with aiosqlite.connect("dating.db") as db:
            async with db.execute("SELECT COUNT(*) FROM users") as c: count = await c.fetchone()
        await m.answer(f"Юзеров: {count[0]}")

async def main():
    await init_db()
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher(); dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO); asyncio.run(main())
