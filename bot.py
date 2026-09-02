import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import BOT_TOKEN
from db import init_db, get_state, save_state, reset_state
from scenes import SCENES

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


def build_keyboard(choices):
    buttons = []
    for i, choice in enumerate(choices):
        buttons.append([
            InlineKeyboardButton(
                text=choice["text"],
                callback_data=f"choice:{i}"
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def send_scene(user_id: int, chat_id: int, scene_id: str):
    if scene_id not in SCENES:
        await bot.send_message(chat_id, "❌ Ошибка: сцена не найдена. Начни заново: /start")
        return

    scene = SCENES[scene_id]
    state = get_state(user_id)
    flags = state["flags"] if state else ""
    save_state(user_id, scene_id, flags)

    text = scene["text"]
    choices = scene["choices"]

    if not choices:
        await bot.send_message(chat_id, text, parse_mode="HTML")
    else:
        kb = build_keyboard(choices)
        await bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)


def get_current_flags(user_id: int, new_flag: str = "") -> str:
    state = get_state(user_id)
    if not state:
        return new_flag
    existing = state["flags"] or ""
    if new_flag and new_flag not in existing:
        existing = (existing + "," + new_flag) if existing else new_flag
    return existing


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    reset_state(user_id)
    save_state(user_id, "start", "")
    await send_scene(user_id, message.chat.id, "start")


@dp.message(Command("continue"))
async def cmd_continue(message: types.Message):
    user_id = message.from_user.id
    state = get_state(user_id)
    if not state:
        await message.answer("Ты ещё не начинал игру. Нажми /start чтобы начать.")
        return

    scene_id = state["scene"]
    if not scene_id or scene_id not in SCENES:
        await message.answer("Сохранение повреждено. Начни заново: /start")
        reset_state(user_id)
        return

    await message.answer("⏯ Продолжаем с того места, где ты остановился...")
    await send_scene(user_id, message.chat.id, scene_id)


@dp.message(Command("reset"))
async def cmd_reset(message: types.Message):
    user_id = message.from_user.id
    reset_state(user_id)
    await message.answer("Прогресс сброшен. Нажми /start чтобы начать заново.")


@dp.callback_query(F.data.startswith("choice:"))
async def on_choice(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    choice_index = int(callback.data.split(":")[1])

    state = get_state(user_id)
    if not state:
        await callback.answer("Начни игру: /start", show_alert=True)
        return

    current_scene_id = state["scene"]
    if current_scene_id not in SCENES:
        await callback.answer("Ошибка. Начни заново.", show_alert=True)
        return

    current_scene = SCENES[current_scene_id]
    choices = current_scene["choices"]

    if choice_index < 0 or choice_index >= len(choices):
        await callback.answer("Неверный выбор.", show_alert=True)
        return

    choice = choices[choice_index]
    next_scene_id = choice["next"]
    flag = choice.get("flag", "")

    new_flags = get_current_flags(user_id, flag)
    save_state(user_id, next_scene_id, new_flags)

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()

    await send_scene(user_id, callback.message.chat.id, next_scene_id)


async def main():
    init_db()
    print("✅ Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
