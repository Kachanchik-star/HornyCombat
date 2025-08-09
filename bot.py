import os
import json
import random
from datetime import datetime 
from aiogram import Bot, Dispatcher, types# type: ignore
from aiogram.filters import Command# type: ignore
from aiogram.types import Message, InlineQuery, InlineQueryResultArticle, InputTextMessageContent, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery # type: ignore
from dotenv import load_dotenv# type: ignore
from aiogram.utils.keyboard import InlineKeyboardBuilder # type: ignore

async def get_top_text(top_type: str):
    if not players:
        return "Нет данных для таблицы лидеров."

    if top_type == "wins":
        sorted_players = sorted(players.items(), key=lambda x: x[1].get("wins", 0), reverse=True)
        title = "🏆 Топ-10 по победам:"
        value = lambda p: f"{p['wins']} побед"
    elif top_type == "size":
        sorted_players = sorted(players.items(), key=lambda x: (x[1].get("attack", 0) + x[1].get("defense", 0)), reverse=True)
        title = "🥒🍒 Топ-10 по сумме члена и сисек:"
        value = lambda p: f"{p['attack']}см + {p['defense']} lvl"
    elif top_type == "winrate":
        def winrate(p):
            total = p["wins"] + p["losses"]
            return (p["wins"] / total * 100) if total > 0 else 0
        sorted_players = sorted(players.items(), key=lambda x: winrate(x[1]), reverse=True)
        title = "📊 Топ-10 по винрейту:"
        value = lambda p: f"{(p['wins'] / (p['wins'] + p['losses']) * 100):.1f}%" if (p['wins'] + p['losses']) > 0 else "0%"
    else:
        return "Неизвестный тип топа."

    text = f"{title}\n\n"
    for i, (user_id, data) in enumerate(sorted_players[:10], 1):
        name = data.get("name")
        if not name:
            try:
                user = await bot.get_chat(int(user_id))
                name = user.full_name[:20]
                players[user_id]["name"] = name
                save_players()
            except:
                name = f"ID:{user_id}"
        text += f"{i}. {name} — {value(data)}\n"
    return text

def get_top_keyboard(current: str, owner_id: str):
    order = ["wins", "size", "winrate"]
    labels = {"wins": "🏆 Победы", "size": "🥒🍒 Размер", "winrate": "📊 Винрейт"}
    idx = order.index(current)
    next_type = order[(idx + 1) % len(order)]
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data=f"back_to_menu_{owner_id}"),
            InlineKeyboardButton(text=f"➡️ {labels[next_type]}", callback_data=f"top_{next_type}")
        ]
    ])

GROW_COOLDOWN = 2 * 60 * 60  # 2 часа в секундах

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATA_FILE = "players.json"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Загружаем или создаём базу
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        players = json.load(f)
else:
    players = {}

pending_fights = {}  # Для хранения активных вызовов на бой
message_owners = {}  # Для хранения владельцев сообщений {message_id: user_id}

ADMIN_ID = 887888895

def init_player(user_id: str):
    """Инициализация нового игрока"""
    if user_id not in players:
        players[user_id] = {
            "attack": 10,  # стандарт 10 см
            "defense": 2,  # стандарт 2 lvl
            "wins": 0,
            "losses": 0,
            "last_grow": 0
        }
        save_players()

def save_players():
    """Сохранение данных игроков"""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(players, f, ensure_ascii=False, indent=2)

def get_name(user: types.User):
    """Получение имени пользователя"""
    return f"@{user.username}" if user.username else user.full_name[:20]

def get_grow_cooldown_text(user_id: str) -> str:
    """Получение текста с оставшимся временем до следующего роста"""
    now_ts = int(datetime.now().timestamp())
    last_grow_ts = players[user_id]["last_grow"]
    remain = GROW_COOLDOWN - (now_ts - last_grow_ts)
    
    if remain <= 0:
        return "Можно растить! 🌱"
    
    hours = remain // 3600
    minutes = (remain % 3600) // 60
    seconds = remain % 60
    
    if hours > 0:
        return f"Подожди {hours}ч {minutes}м {seconds}с"
    else:
        return f"Подожди {minutes}м {seconds}с"

def can_grow(user_id: str) -> bool:
    """Проверка, можно ли расти"""
    now_ts = int(datetime.now().timestamp())
    last_grow_ts = players[user_id]["last_grow"]
    return now_ts - last_grow_ts >= GROW_COOLDOWN

def grow_player(user_id: str) -> dict:
    cucumber_change = random.randint(-2, 13)
    shield_change = random.randint(-2, 5)
    players[user_id]["attack"] += cucumber_change
    players[user_id]["defense"] += shield_change
    players[user_id]["last_grow"] = int(datetime.now().timestamp())
    save_players()
    return {
        "cucumber_change": cucumber_change,
        "shield_change": shield_change,
        "new_attack": players[user_id]["attack"],
        "new_defense": players[user_id]["defense"]
    }

def calculate_battle_damage(attacker_stats, defender_stats):
    """Улучшенная система расчета урона с большей случайностью"""
    attack = attacker_stats["attack"]
    defense = defender_stats["defense"]
    
    # Базовый урон с большим разбросом
    base_damage = attack * random.uniform(0.5, 1.8)  # от 50% до 180% от атаки
    
    # Защита снижает урон, но не полностью
    defense_reduction = defense * random.uniform(0.3, 0.8)  # защита работает от 30% до 80%
    
    # Финальный урон
    damage = base_damage - defense_reduction
    damage = max(1, round(damage))  # минимум 1 урона
    
    # Шанс критического удара (15%)
    is_crit = random.random() < 0.15
    if is_crit:
        damage = int(damage * random.uniform(1.5, 2.5))  # крит от 150% до 250%
    
    # Шанс промаха (10%) - урон становится 0
    is_miss = random.random() < 0.10
    if is_miss:
        damage = 0
        is_crit = False
    
    # Шанс удачного удара (5%) - игнорирует защиту
    is_lucky = random.random() < 0.05
    if is_lucky and not is_miss:
        damage = int(attack * random.uniform(1.2, 2.0))
        return damage, is_crit, is_miss, is_lucky
    
    return damage, is_crit, is_miss, False

def get_profile_text(user_id: str, user: types.User) -> str:
    """Генерация текста профиля"""
    if user_id not in players:
        return "❌ Сначала нужно начать игру!"
    
    p = players[user_id]
    total = p["wins"] + p["losses"]
    winrate = (p["wins"] / total * 100) if total > 0 else 0
    
    return (
        f"👤 Профиль {get_name(user)}\n"
        f"🥒 Член: {p['attack']}см\n"
        f"🍒Сиськи: {p['defense']} lvl\n"
        f"🏆 Побед: {p['wins']}\n"
        f"💀 Поражений: {p['losses']}\n"
        f"📊 Винрейт: {winrate:.1f}%\n\n"
        f"🕐 Рост: {get_grow_cooldown_text(user_id)}"
    )

def get_main_keyboard(owner_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Профиль", callback_data=f"profile_{owner_id}")],
        [InlineKeyboardButton(text="🌱 Вырастить член", callback_data=f"grow_{owner_id}")],
        [InlineKeyboardButton(text="⚔️ Атака", callback_data=f"attack_{owner_id}")],
        [InlineKeyboardButton(text="🏆 Топ", callback_data="top_wins")]
    ])

def get_fight_keyboard(attacker_id: str) -> InlineKeyboardMarkup:
    """Создание клавиатуры для боя"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ Принять бой!", callback_data=f"fight_accept_{attacker_id}")]
    ])

# ===================
# INLINE HANDLERS
# ===================

@dp.inline_query()
async def inline_query_handler(query: InlineQuery):
    """Обработчик inline запросов"""
    user_id = str(query.from_user.id)
    init_player(user_id)
    
    # Создаем статью с главным меню
    article = InlineQueryResultArticle(
        id="main_menu",
        title="🎮 RPG H&C",
        description="Твоя RPG игра с членами и сисками!",
        input_message_content=InputTextMessageContent(
            message_text="🎮 **RPG H&C** - твоя мини-RPG игра!\n\nВыбери действие:",
            parse_mode="Markdown"
        ),
        reply_markup=get_main_keyboard(user_id),
    )
    
    await query.answer([article], cache_time=1)

# ===================
# CALLBACK HANDLERS
# ===================

@dp.callback_query(lambda c: c.data.startswith("profile_"))
async def callback_profile(callback: CallbackQuery):
    """Показ профиля через callback с проверкой владельца"""
    # Извлекаем ID владельца из callback_data
    owner_id = callback.data.replace("profile_", "")
    user_id = str(callback.from_user.id)
    user = callback.from_user  # <--- добавь эту строку

    # Проверяем, что пользователь может видеть только свой профиль
    if owner_id != user_id:
        await callback.answer("❌ Это не твое меню! Создай свое через inline режим", show_alert=True)
        return

    init_player(user_id)

    if user_id not in players:
        await callback.answer("Сначала используй /grow!", show_alert=True)
        return

    p = players[user_id]
    total = p["wins"] + p["losses"]
    winrate = (p["wins"] / total * 100) if total > 0 else 0

    profile_text = (
        f"👤 Профиль {get_name(user)}\n"
        f"🥒 Член: {p['attack']}см\n"
        f"🍒Сиськи: {p['defense']} лвл\n"
        f"🏆 Побед: {p['wins']}\n"
        f"💀 Поражений: {p['losses']}\n"
        f"📊 Винрейт: {winrate:.1f}%"
    )

    if callback.inline_message_id:
        await bot.edit_message_text(
            text=profile_text,
            inline_message_id=callback.inline_message_id,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data=f"back_to_menu_{user_id}")]
            ])
        )
    else:
        await callback.message.edit_text(
            text=profile_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data=f"back_to_menu_{user_id}")]
            ])
        )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("grow_"))
async def callback_grow(callback: CallbackQuery):
    """Рост огурца через callback с проверкой владельца"""
    # Извлекаем ID владельца из callback_data
    owner_id = callback.data.replace("grow_", "")
    user_id = str(callback.from_user.id)
    
    if owner_id != user_id:
        await callback.answer("❌ Это не твое меню! Создай свое через inline режим", show_alert=True)
        return
    
    init_player(user_id)

    if not can_grow(user_id):
        cooldown_text = get_grow_cooldown_text(user_id)
        
        if callback.inline_message_id:
            await bot.edit_message_text(
                text=f"⏰ {cooldown_text}",
                inline_message_id=callback.inline_message_id,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data=f"back_to_menu_{user_id}")]
                ])
            )
        else:
            await callback.message.edit_text(
                f"⏰ {cooldown_text}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data=f"back_to_menu_{user_id}")]
                ])
            )
        await callback.answer("Еще рано растить! ⏰")
        return

    # Новая система роста с большими значениями
    result = grow_player(user_id)
    
    # Эмодзи для изменений
    cucumber_emoji = "📈" if result["cucumber_change"] > 0 else "📉" if result["cucumber_change"] < 0 else "➡️"
    shield_emoji = "📈" if result["shield_change"] > 0 else "📉" if result["shield_change"] < 0 else "➡️"
    
    # Дополнительные эмодзи для больших изменений
    if result["cucumber_change"] >= 10:
        cucumber_emoji = "🚀"
    elif result["cucumber_change"] <= -2:
        cucumber_emoji = "💥"
        
    if result["shield_change"] >= 4:
        shield_emoji = "🚀"
    elif result["shield_change"] <= -2:
        shield_emoji = "💥"

    grow_text = (
        f"🌱 **Результат роста:**\n\n"
        f"🥒 Член: {cucumber_emoji} {result['cucumber_change']:+}см (теперь {result['new_attack']}см)\n"
        f"🍒Сиськи: {shield_emoji} {result['shield_change']:+} lvl (теперь {result['new_defense']} lvl)"
    )
    
    if callback.inline_message_id:
        await bot.edit_message_text(
            text=grow_text,
            inline_message_id=callback.inline_message_id,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data=f"back_to_menu_{user_id}")]
            ])
        )
    else:
        await callback.message.edit_text(
            grow_text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data=f"back_to_menu_{user_id}")]
            ])
        )
    await callback.answer("Ты вырос! 🌱")

@dp.callback_query(lambda c: c.data.startswith("attack_"))
async def callback_attack(callback: CallbackQuery):
    """Вызов на бой через callback (убираем проверку владельца для атаки)"""
    # Извлекаем ID владельца из callback_data
    owner_id = callback.data.replace("attack_", "")
    user_id = str(callback.from_user.id)
    
    init_player(owner_id)  # инициализируем владельца (того, кто вызвал)
    
    p = players[owner_id]
    
    # Создаем уникальный fight_id для этого боя
    fight_id = f"fight_{owner_id}_{int(datetime.now().timestamp())}"
    
    attack_text = (
        f"⚔ {get_name(callback.from_user)} вызывает на бой!\n"
        f"Член: {p['attack']}, Сиськи: {p['defense']}\n"
        f"Побед: {p['wins']}, поражений: {p['losses']}\n"
    )
    
    if callback.inline_message_id:
        await bot.edit_message_text(
            text=attack_text,
            inline_message_id=callback.inline_message_id,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⚔️ Согласиться", callback_data=f"accept_{fight_id}")]
            ])
        )
    else:
        await callback.message.edit_text(
            text=attack_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⚔️ Согласиться", callback_data=f"accept_{fight_id}")]
            ])
        )
    
    # Сохраняем информацию о вызове
    pending_fights[fight_id] = owner_id
    
    await callback.answer("Ты готов к бою! ⚔️")

@dp.callback_query(lambda c: c.data.startswith("accept_"))
async def callback_fight_accept(callback: CallbackQuery):
    fight_id = callback.data.replace("accept_", "")
    if fight_id not in pending_fights:
        await callback.answer("Этот бой уже завершен!", show_alert=True)
        return

    attacker_id = pending_fights[fight_id]
    defender_id = str(callback.from_user.id)

    if attacker_id == defender_id:
        await callback.answer("Нельзя сражаться с самим собой! 🤪", show_alert=True)
        return

    if attacker_id not in players or defender_id not in players:
        await callback.answer("Один из игроков не инициализирован!", show_alert=True)
        return

    # Проверка на минимальные значения для боя
    if players[attacker_id]["attack"] < 3 or players[attacker_id]["defense"] < 1:
        await callback.answer("У противника слишком маленький член или защита для боя!", show_alert=True)
        return
    if players[defender_id]["attack"] < 3 or players[defender_id]["defense"] < 1:
        await callback.answer("У тебя слишком маленький член или защита для боя!", show_alert=True)
        return

    # НОВАЯ система боя с рандомом
    attacker = players[attacker_id]
    defender = players[defender_id]

    # Рассчитываем урон для каждого игрока
    dmg1, crit1, miss1, lucky1 = calculate_battle_damage(attacker, defender)
    dmg2, crit2, miss2, lucky2 = calculate_battle_damage(defender, attacker)

    # Определяем победителя
    winner_attack_bonus = random.randint(2, 5)
    winner_defense_bonus = random.randint(1, 3)

    if dmg1 > dmg2:
        attacker["wins"] += 1
        defender["losses"] += 1
        attacker["attack"] += winner_attack_bonus
        attacker["defense"] += winner_defense_bonus
        defender["attack"] -= winner_attack_bonus
        defender["defense"] -= winner_defense_bonus
        # ↓↓↓ Добавь это ↓↓↓
        try:
            attacker_user = await bot.get_chat(int(attacker_id))
            attacker_name = f"@{attacker_user.username}" if attacker_user.username else attacker_user.full_name[:20]
        except:
            attacker_name = "Атакующий"
        result = f"🏆 Победитель: {attacker_name}"
        winner_bonus = f"\n🎁 Получает: +{winner_attack_bonus}см члена, +{winner_defense_bonus} lvl сисек"
    elif dmg2 > dmg1:
        defender["wins"] += 1
        attacker["losses"] += 1
        defender["attack"] += winner_attack_bonus
        defender["defense"] += winner_defense_bonus
        attacker["attack"] -= winner_attack_bonus
        attacker["defense"] -= winner_defense_bonus
        result = f"🏆 Победитель: {get_name(callback.from_user)}"
        winner_bonus = f"\n🎁 Получает: +{winner_attack_bonus}см члена,+{winner_defense_bonus} lvl сисек"
    else:
        result = "🤝 Ничья! Никто не получает награды."
        winner_bonus = ""

    save_players()
    del pending_fights[fight_id]

    # Формируем детальный результат боя
    try:
        attacker_user = await bot.get_chat(int(attacker_id))
        attacker_name = f"@{attacker_user.username}" if attacker_user.username else attacker_user.full_name[:20]
    except:
        attacker_name = "Атакующий"
    
    text = "⚔️ **Результат боя:**\n\n"
    
    # Результат атаки первого игрока
    text += f"🔸 {attacker_name}:\n"
    if miss1:
        text += f"   💨 Промах! (0 урона)"
    else:
        text += f"   💥 {dmg1} урона"
        if crit1:
            text += " 🔥КРИТ!"
        if lucky1:
            text += " ⭐УДАЧА!"
    text += "\n"
    
    # Результат атаки второго игрока
    text += f"🔹 {get_name(callback.from_user)}:\n"
    if miss2:
        text += f"   💨 Промах! (0 урона)"
    else:
        text += f"   💥 {dmg2} урона"
        if crit2:
            text += " 🔥КРИТ!"
        if lucky2:
            text += " ⭐УДАЧА!"
    text += "\n\n"
    
    text += result + winner_bonus

    # Обновляем сообщение с результатом боя
    if callback.inline_message_id:
        await bot.edit_message_text(
            text=text,
            inline_message_id=callback.inline_message_id,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Новый бой", callback_data=f"back_to_menu_{defender_id}")]
            ])
        )
    else:
        await callback.message.edit_text(
            text=text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Новый бой", callback_data=f"back_to_menu_{defender_id}")]
            ])
        )
    
    await callback.answer("Бой завершен! ⚔️")

@dp.callback_query(lambda c: c.data.startswith("back_to_menu_"))
async def callback_back_to_menu(callback: CallbackQuery):
    """Возврат к главному меню с проверкой владельца"""
    # Извлекаем ID владельца из callback_data
    owner_id = callback.data.replace("back_to_menu_", "")
    user_id = str(callback.from_user.id)
    
    # Проверяем, что пользователь может управлять только своим меню
    if owner_id != user_id:
        await callback.answer("❌ Это не твое меню! Создай свое через inline режим", show_alert=True)
        return
    
    menu_text = "🎮 **RPG H&C** - твоя мини-RPG игра!\n\nВыбери действие:"
    
    if callback.inline_message_id:
        await bot.edit_message_text(
            text=menu_text,
            inline_message_id=callback.inline_message_id,
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(user_id)
        )
    else:
        await callback.message.edit_text(
            text=menu_text,
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(user_id)
        )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("top_"))
async def callback_top_table(callback: CallbackQuery):
    top_type = callback.data.replace("top_", "")
    owner_id = str(callback.from_user.id)
    text = await get_top_text(top_type)
    kb = get_top_keyboard(top_type, owner_id)
    if callback.inline_message_id:
        await bot.edit_message_text(
            text=text,
            inline_message_id=callback.inline_message_id,
            reply_markup=kb
        )
    else:
        await callback.message.edit_text(
            text=text,
            reply_markup=kb
        )
    await callback.answer()

# ===================
# ОБЫЧНЫЕ КОМАНДЫ (для совместимости)
# ===================

@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Команда старт"""
    user_id = str(message.from_user.id)
    init_player(user_id)
    
    await message.answer(
        f"🎮 Добро пожаловать в **RPG H&C**, (автор @knnzas), {get_name(message.from_user)}!\n\n"
        f"Как играть:\n"
        f"Ты можешь использовать бота двумя способами:\n"
        f"1️⃣ **Inline режим**: напиши `@{(await bot.get_me()).username}` в любом чате\n"
        f"2️⃣ **Команды**: /grow, /profile, /fight\n\n"
        f"🌱 **Возможности:**\n"
        f"• Расти свой член для - Атаки\n"
        f"• Увеличивать уровень своих Сисек для - Защиты\n"
        f"• Сражаться с другими игроками в боях\n"
        f"• Смотреть свой профиль для статистики\n"
        f"• В боях есть криты, промахи и удача!\n"
        f"• Даже слабый игрок может победить сильного!\n\n"
        f"Удачи в приключениях! 🌱",
        parse_mode="Markdown"
    )

@dp.message(Command("grow"))
async def cmd_grow(message: Message):
    """Команда роста (совместимость)"""
    user_id = str(message.from_user.id)
    init_player(user_id)
    
    if not can_grow(user_id):
        cooldown_text = get_grow_cooldown_text(user_id)
        await message.answer(f"⏰ {cooldown_text}")
        return
    
    result = grow_player(user_id)
    cucumber_emoji = "📈" if result["cucumber_change"] > 0 else "📉" if result["cucumber_change"] < 0 else "➡️"
    shield_emoji = "📈" if result["shield_change"] > 0 else "📉" if result["shield_change"] < 0 else "➡️"
    
    # Специальные эмодзи для экстремальных значений
    if result["cucumber_change"] >= 10:
        cucumber_emoji = "🚀"
    elif result["cucumber_change"] <= -2:
        cucumber_emoji = "💥"
        
    if result["shield_change"] >= 4:
        shield_emoji = "🚀"
    elif result["shield_change"] <= -2:
        shield_emoji = "💥"
    
    await message.answer(
        f"🌱 **Результат роста:**\n\n"
        f"🥒 Член: {cucumber_emoji} {result['cucumber_change']:+}см (теперь {result['new_attack']}см)\n"
        f"🍒Сиськи: {shield_emoji} {result['shield_change']:+} lvl (теперь {result['new_defense']} lvl)",
        parse_mode="Markdown"
    )

@dp.message(Command("profile"))
async def cmd_profile(message: Message):
    """Команда профиля (совместимость)"""
    user_id = str(message.from_user.id)
    init_player(user_id)
    
    profile_text = get_profile_text(user_id, message.from_user)
    await message.answer(profile_text)

@dp.message(Command("fight"))
async def cmd_fight(message: Message):
    """Команда боя (совместимость)"""
    if not message.reply_to_message:
        await message.answer("Ответь этой командой на сообщение игрока, чтобы вызвать его на бой!")
        return
    
    user_id = str(message.from_user.id)
    init_player(user_id)
    
    p = players[user_id]
    await message.answer(
        f"⚔️ **{get_name(message.from_user)} готов к бою!**\n\n"
        f"🥒 Член: {p['attack']}см\n"
        f"🍒Сиськи: {p['defense']} lvl\n"
        f"🏆 Побед: {p['wins']}\n"
        f"💀 Поражений: {p['losses']}\n\n"
        f"Кто осмелится принять вызов?\n"
        f"💡 *Теперь в боях есть криты, промахи и удача!*",
        parse_mode="Markdown",
        reply_markup=get_fight_keyboard(user_id)
    )

@dp.message(Command("admin_reset_all"))
async def admin_reset_all(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Нет доступа.")
        return
    for user_id in players:
        players[user_id] = {
            "attack": 10,
            "defense": 2,
            "wins": 0,
            "losses": 0,
            "last_grow": 0
        }
    save_players()
    await message.answer("✅ Все пользователи сброшены.")

@dp.message(Command("admin_reset"))
async def admin_reset(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Нет доступа.")
        return
    if not message.reply_to_message:
        await message.answer("Ответь этой командой на сообщение пользователя для сброса.")
        return
    target_id = str(message.reply_to_message.from_user.id)
    players[target_id] = {
        "attack": 10,
        "defense": 2,
        "wins": 0,
        "losses": 0,
        "last_grow": 0
    }
    save_players()
    await message.answer(f"✅ Пользователь {get_name(message.reply_to_message.from_user)} сброшен.")

@dp.message(Command("admin_set"))
async def admin_set(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Нет доступа.")
        return
    if not message.reply_to_message:
        await message.answer("Ответь этой командой на сообщение пользователя.\nФормат: /admin_set 15 3")
        return
    args = message.text.split()
    if len(args) != 3:
        await message.answer("Формат: /admin_set <см> <lvl>\nПример: /admin_set 15 3")
        return
    try:
        attack = int(args[1])
        defense = int(args[2])
    except ValueError:
        await message.answer("Значения должны быть числами.")
        return
    target_id = str(message.reply_to_message.from_user.id)
    if target_id not in players:
        init_player(target_id)
    players[target_id]["attack"] = attack
    players[target_id]["defense"] = defense
    save_players()
    await message.answer(f"✅ Установлено {attack}см и {defense} lvl для {get_name(message.reply_to_message.from_user)}.")
@dp.message(Command("top"))
async def cmd_top(message: Message):
    user_id = str(message.from_user.id)
    text = await get_top_text("wins")
    kb = get_top_keyboard("wins", user_id)
    await message.answer(text, reply_markup=kb)
if __name__ == "__main__":
    import asyncio
    print("🚀 RPG H&C бот запущен!")
    asyncio.run(dp.start_polling(bot))