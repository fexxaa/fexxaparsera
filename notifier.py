import time
import json
import sqlite3
import asyncio
from datetime import datetime
from typing import Optional, Tuple
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.types import (
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    CallbackQuery,
    LinkPreviewOptions
)
from aiogram.exceptions import TelegramForbiddenError
import config

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

# Сохраняем базу данных в постоянную папку /app/data/
DB_FILE = "/app/data/market_logs.db"

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                is_claimed INTEGER DEFAULT 0,
                claimed_by TEXT,
                created_at REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cooldowns (
                user_id INTEGER PRIMARY KEY,
                last_claim REAL
            )
        """)
        conn.commit()

init_db()

def save_log_to_db(gift_id: str, gift_data: dict):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO logs (id, data, is_claimed, created_at) VALUES (?, ?, 0, ?)",
            (gift_id, json.dumps(gift_data, ensure_ascii=False), time.time())
        )
        conn.commit()

def get_log_from_db(gift_id: str) -> Optional[dict]:
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute("SELECT data, is_claimed FROM logs WHERE id = ?", (gift_id,))
        row = cur.fetchone()
        if row:
            data = json.loads(row[0])
            data["is_claimed"] = bool(row[1])
            return data
    return None

def try_claim_log_in_db(gift_id: str, user_id: int) -> bool:
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute("SELECT is_claimed FROM logs WHERE id = ?", (gift_id,))
        row = cur.fetchone()
        if not row or row[0] == 1:
            return False
        cur.execute("UPDATE logs SET is_claimed = 1, claimed_by = ? WHERE id = ?", (str(user_id), gift_id))
        conn.commit()
        return True

def release_log_in_db(gift_id: str):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("UPDATE logs SET is_claimed = 0, claimed_by = NULL WHERE id = ?", (gift_id,))
        conn.commit()

def check_user_cooldown(user_id: int, cd_seconds: int = 20) -> Tuple[bool, int]:
    now = time.time()
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute("SELECT last_claim FROM cooldowns WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if row:
            passed = now - row[0]
            if passed < cd_seconds:
                return False, int(cd_seconds - passed) + 1
    return True, 0

def update_user_cooldown(user_id: int):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("INSERT OR REPLACE INTO cooldowns (user_id, last_claim) VALUES (?, ?)", (user_id, time.time()))
        conn.commit()

def get_topic_by_floor(gift: dict) -> Optional[int]:
    try:
        is_girl = gift.get("is_female", False)
        country = gift.get("country", "")

        # ЖЕСТКАЯ ФИЛЬТРАЦИЯ: Если это девушка из RU или UA, отправляем СТРОГО в топик 3497
        if is_girl and country in ("RU", "UA"):
            return config.TOPIC_IDS.get("girl_ru_ua")

        # Если это парень или другой регион, в топик 3497 он НИКОГДА не попадет. 
        # Распределяем парней по обычным ценовым топикам:
        floor_stars = gift["floor_stars"]
        tiers = config.FLOOR_TIERS
        if floor_stars < tiers["cheap_max"]:
            return config.TOPIC_IDS.get("cheap")
        elif tiers["cheap_max"] <= floor_stars < tiers["medium_max"]:
            return config.TOPIC_IDS.get("medium")
        elif tiers["medium_max"] <= floor_stars < tiers["expensive_max"]:
            return config.TOPIC_IDS.get("expensive")
        elif tiers["expensive_max"] <= floor_stars < tiers["premium_max"]:
            return config.TOPIC_IDS.get("premium")
        elif tiers["premium_max"] <= floor_stars < tiers["premier_max"]:
            return config.TOPIC_IDS.get("premier")
        else:
            return config.TOPIC_IDS.get("vip")
    except Exception:
        return None

async def send_log_to_topic(gift: dict):
    # Дополнительная проверка на уровне отправки: парней категорически не пускаем в топик девушек
    is_girl = gift.get("is_female", False)
    country = gift.get("country", "")
    if not (is_girl and country in ("RU", "UA")):
        # Если определился не как девушка RU/UA, но почему-то попал сюда — проверяем по ценам
        pass

    thread_id = get_topic_by_floor(gift)
    status_premium = "С премиумом" if gift["has_premium"] else "Без премиума"
    time_str = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    save_log_to_db(gift["id"], gift)

    caption = (
        "🎒 New gifts - claim it :)\n\n"
        f"🎁 Подарок: {gift['name']}\n"
        f"⭐ Цена: {gift['stars_price']} ⭐ / {gift['ton_price']} TON\n"
        f"📊 Флор модели: {gift['floor_stars']} ⭐\n"
        f"🤝 Модель: {gift['model']}\n"
        f"📍 Онлайн: {gift['online']}\n"
        f"🐺 NFT подарков в профиле: {gift['gifts_count']}\n"
        f"↗️ Уровень: {gift['level']}\n"
        f"💬 Сообщение: {gift['message']}\n"
        f"⚡ Статус: {status_premium}\n"
        f"⌛ {time_str}\n\n"
        f'Сделано с любовью от <a href="https://t.me/{config.CREDITS_USERNAME}">{config.CREDITS_NAME}</a>'
    )

    owner_username = gift.get("owner_username")

    keyboard_rows = []
    if owner_username:
        keyboard_rows.append([InlineKeyboardButton(text="View Owner ↗", url=f"https://t.me/{owner_username}")])

    keyboard_rows.append([InlineKeyboardButton(text="Gift Link ❐", url=gift["gift_url"])])
    keyboard_rows.append([InlineKeyboardButton(text="Занять лог", callback_data=f"claim_{gift['id']}")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    preview_opts = LinkPreviewOptions(
        is_disabled=False,
        url=gift["gift_url"],
        prefer_large_media=True,
        show_above_text=True
    )

    await asyncio.sleep(2)

    try:
        kwargs = {
            "chat_id": config.CHAT_ID,
            "text": caption,
            "parse_mode": ParseMode.HTML,
            "link_preview_options": preview_opts,
            "reply_markup": keyboard
        }
        if thread_id:
            kwargs["message_thread_id"] = thread_id

        sent_msg = await bot.send_message(**kwargs)
        print(f"  └── [Telegram] Лог отправлен в топик ID: {thread_id} | Девушка: {is_girl} ({country})")
    except Exception as e:
        print(f"  └── [ОШИБКА ОТПРАВКИ В TELEGRAM]: {e}")

@dp.callback_query(F.data.startswith("claim_"))
async def process_claim(callback: CallbackQuery):
    gift_id = callback.data.replace("claim_", "", 1)
    user = callback.from_user
    username_display = f"@{user.username}" if user.username else user.first_name

    cooldown_seconds = getattr(config, "CLAIM_COOLDOWN_SECONDS", 20)
    can_claim, remaining = check_user_cooldown(user.id, cooldown_seconds)
    if not can_claim:
        await callback.answer(
            f"⏳ Кулдаун! Подождите ещё {remaining} сек. перед тем как взять следующий лог.",
            show_alert=True
        )
        return

    gift = get_log_from_db(gift_id)
    if not gift:
        await callback.answer("❌ Этот лог не найден или устарел!", show_alert=True)
        return

    if gift.get("is_claimed") or not try_claim_log_in_db(gift_id, user.id):
        await callback.answer("❌ Этот лог уже занят другим участником!", show_alert=True)
        return

    owner_id = gift.get("owner_id")
    owner_username = gift.get("owner_username")

    if owner_username:
        owner_line = f"👤 @{owner_username}"
        profile_url = f"https://t.me/{owner_username}"
    elif owner_id and int(owner_id) > 0:
        owner_line = f'👤 <a href="tg://user?id={owner_id}">Профиль</a>'
        profile_url = f"tg://user?id={owner_id}"
    else:
        owner_line = "👤 Аноним"
        profile_url = gift["gift_url"]

    status_str = "Premium ✅" if gift.get("has_premium") else "Premium ❌"
    msg_value = gift.get("message", "Free")
    gift_clean_title = gift.get("title") or gift.get("name", "Gift").split("#")[0].strip()

    dm_text = (
        f'<a href="{gift["gift_url"]}">&#8203;</a>'
        "🔔 <b>Thanks for buying!</b>\n\n"
        f"🎁 <b>Gift:</b> {gift_clean_title}\n"
        f"⭐ <b>Price:</b> {gift['stars_price']} ⭐ / {gift['ton_price']} TON\n"
        f"🤝 <b>Model:</b> {gift['model']}\n"
        f"💬 <b>Message:</b> {msg_value}\n"
        f"⚡ <b>Status:</b> {status_str}\n\n"
        f"{owner_line}"
    )

    dm_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть профиль ↗", url=profile_url)]
        ]
    )

    dm_preview_opts = LinkPreviewOptions(
        is_disabled=False,
        url=gift["gift_url"],
        prefer_large_media=True,
        show_above_text=False
    )

    try:
        await bot.send_message(
            chat_id=user.id,
            text=dm_text,
            parse_mode=ParseMode.HTML,
            link_preview_options=dm_preview_opts,
            reply_markup=dm_keyboard
        )
        update_user_cooldown(user.id)
    except TelegramForbiddenError:
        release_log_in_db(gift_id)
        await callback.answer(
            "⚠️ Напишите боту в ЛС команду /start, чтобы он мог отправить вам контакт!",
            show_alert=True
        )
        return
    except Exception as e:
        print(f"[Ошибка отправки в ЛС]: {e}")
        release_log_in_db(gift_id)
        await callback.answer("⚠️ Не удалось отправить сообщение в ЛС!", show_alert=True)
        return

    await callback.answer("✅ Лог занят! Чат с продавцом отправлен вам в ЛС.", show_alert=True)

    try:
        cleaned_text = f"🔒 Лог занят: {username_display}"
        await callback.message.edit_text(
            text=cleaned_text,
            reply_markup=None,
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
    except Exception as e:
        print(f"[Ошибка обновления сообщения при занятии]: {e}")
