import time
import hashlib
import random
import asyncio
from datetime import datetime
from telethon import TelegramClient
from telethon.tl import functions, types
import config
from gender_detector import (
    is_female, 
    check_ru_ua_origin, 
    can_send_gender, 
    record_sent_gender
)
from floor_checker import (
    extract_item_price,
    get_item_model,
    update_market_floors,
    get_real_floor,
    is_floor_cache_expired
)
from notifier import send_log_to_topic

tg_client = TelegramClient("tg_market_session", config.TG_API_ID, config.TG_API_HASH)

SEEN_LISTING_IDS = set()
SENT_SELLERS_IDS = set()  
USER_CACHE = {}


def safe_int(val, default=0) -> int:
    if val is None:
        return default
    try:
        return int(val)
    except Exception:
        return default


async def get_online_status(user) -> str:
    status = getattr(user, "status", None)
    if isinstance(status, types.UserStatusOnline):
        return "В сети"
    elif isinstance(status, types.UserStatusRecently):
        return "Недавно"
    elif isinstance(status, types.UserStatusLastWeek):
        return "На этой неделе"
    return "Недавно"


def is_blockchain_gift(item) -> bool:
    if getattr(item, "owner_address", None):
        return True
    if getattr(item, "exported_to_blockchain", False):
        return True
    if getattr(item, "transferred_to_blockchain", False):
        return True
    return False


def extract_owner_id(item) -> int:
    owner_peer = getattr(item, "owner_id", None)
    if isinstance(owner_peer, int):
        return owner_peer
    if isinstance(owner_peer, types.PeerUser):
        return owner_peer.user_id
    if hasattr(owner_peer, "user_id"):
        return safe_int(getattr(owner_peer, "user_id", 0))
    return 0


def generate_safe_unique_id(slug: str, num: int, item_id: int) -> str:
    base = f"{slug}_{num}_{item_id}".strip("_")
    if len(base) <= 50:
        return base
    hashed = hashlib.md5(base.encode()).hexdigest()[:10]
    return f"{base[:38]}_{hashed}"


async def count_user_nft_gifts(user_peer) -> int:
    nft_count = 0
    try:
        offset = ""
        for _ in range(2):
            saved = await tg_client(functions.payments.GetSavedStarGiftsRequest(
                peer=user_peer, offset=offset, limit=50
            ))
            gifts = getattr(saved, "gifts", [])
            if not gifts:
                break
            
            for g in gifts:
                gift_obj = getattr(g, "gift", g)
                if isinstance(gift_obj, types.StarGiftUnique) or getattr(gift_obj, "num", 0) > 0 or is_blockchain_gift(g):
                    nft_count += 1

            if nft_count > config.MAX_PROFILE_GIFTS:
                return nft_count

            if len(gifts) < 50:
                break
            offset = getattr(saved, "next_offset", "")
            if not offset:
                break
    except Exception:
        pass
    return nft_count


async def inspect_user(user_id: int) -> dict:
    default_info = {
        "is_valid": False,
        "is_female": False,
        "country": "RU",
        "nft_gifts_count": 99,
        "level": 99,
        "has_premium": False,
        "online": "Недавно",
        "username": None,
        "message_text": "Free"
    }
    if not user_id:
        return default_info

    now = time.time()
    if user_id in USER_CACHE:
        data, exp = USER_CACHE[user_id]
        if now < exp:
            return data

    try:
        user_raw = await tg_client(functions.users.GetUsersRequest(id=[user_id]))
        if not user_raw:
            return default_info
        user_obj = user_raw[0]

        has_premium = bool(getattr(user_obj, "premium", False))
        online_str = await get_online_status(user_obj)
        first_name = getattr(user_obj, "first_name", "") or ""
        last_name = getattr(user_obj, "last_name", "") or ""
        username = getattr(user_obj, "username", "") or ""

        user_bio = ""
        level = 1
        try:
            full = await tg_client(functions.users.GetFullUserRequest(id=user_obj))
            full_user_obj = getattr(full, "full_user", full)
            user_bio = getattr(full_user_obj, "about", "") or ""
            level = safe_int(getattr(full_user_obj, "level", 1), default=1)
        except Exception:
            pass

        full_name = f"{first_name} {last_name}".strip()
        
        is_allowed_region, country = check_ru_ua_origin(full_name, user_bio, username)
        seller_is_female = is_female(full_name, user_bio, username)

        bio_lower = user_bio.lower()
        for word in config.FORBIDDEN_BIO_WORDS:
            if word in bio_lower:
                return default_info

        nft_gifts_count = await count_user_nft_gifts(user_obj)
        is_valid = True

        if config.ONLY_RU_UA and not is_allowed_region:
            is_valid = False

        if level > config.MAX_USER_LEVEL:
            is_valid = False

        if nft_gifts_count > config.MAX_PROFILE_GIFTS:
            is_valid = False

        result = {
            "is_valid": is_valid,
            "is_female": seller_is_female,
            "country": country or "RU",
            "nft_gifts_count": nft_gifts_count,
            "level": level,
            "has_premium": has_premium,
            "online": online_str,
            "username": username if username else None,
            "message_text": "Free"
        }
        USER_CACHE[user_id] = (result, now + 600)
        return result
    except Exception as e:
        return default_info


async def fetch_resale_items(gift_id: int) -> list:
    items = []
    current_offset = ""
    try:
        data = await tg_client(functions.payments.GetResaleStarGiftsRequest(
            gift_id=gift_id,
            offset=current_offset,
            limit=20
        ))
        batch = getattr(data, "gifts", [])
        if batch:
            items.extend(batch)
    except Exception:
        pass
    return items


async def process_single_category(gift_type):
    global SENT_SELLERS_IDS
    title_type = getattr(gift_type, "title", "Gift")
    recent_items = await fetch_resale_items(gift_type.id)
    if not recent_items:
        return

    if is_floor_cache_expired(gift_type.id):
        try:
            cheapest_data = await tg_client(functions.payments.GetResaleStarGiftsRequest(
                gift_id=gift_type.id,
                offset="",
                limit=15,
                sort_by_price=True
            ))
            cheapest_items = getattr(cheapest_data, "gifts", [])
            if cheapest_items:
                update_market_floors(gift_type.id, cheapest_items)
        except Exception:
            update_market_floors(gift_type.id, recent_items)
    else:
        update_market_floors(gift_type.id, recent_items)

    sent_from_category = 0

    for item in recent_items:
        if sent_from_category >= 2:
            break

        raw_item_id = safe_int(getattr(item, "id", 0))
        num = safe_int(getattr(item, "num", 0))
        slug = getattr(item, "slug", None)

        title_raw = getattr(item, "title", None) or title_type
        clean_title = title_raw.split("#")[0].strip()

        if not slug:
            title_slug = "".join(c for c in clean_title if c.isalnum())
            slug = f"{title_slug}-{num}" if num > 0 else f"{title_slug}-{raw_item_id}"

        unique_id = generate_safe_unique_id(slug, num, raw_item_id)

        if unique_id in SEEN_LISTING_IDS:
            continue

        if not config.ALLOW_BLOCKCHAIN and is_blockchain_gift(item):
            SEEN_LISTING_IDS.add(unique_id)
            continue

        stars_price = extract_item_price(item)
        if stars_price <= 0:
            continue

        owner_id = extract_owner_id(item)
        
        if owner_id in SENT_SELLERS_IDS:
            SEEN_LISTING_IDS.add(unique_id)
            continue

        seller = await inspect_user(owner_id)

        if not seller["is_valid"]:
            SEEN_LISTING_IDS.add(unique_id)
            continue

        is_girl = seller["is_female"]
        country = seller["country"]

        ton_price = round(stars_price / 132.14, 2)
        model_name = get_item_model(item)
        real_floor_stars = get_real_floor(gift_type.id, model_name, stars_price)
        if real_floor_stars <= 50:
            real_floor_stars = stars_price

        gift_url = f"https://t.me/nft/{slug}"
        gift_payload = {
            "id": unique_id,
            "title": clean_title,
            "num": num,
            "name": f"{clean_title} #{num}",
            "stars_price": stars_price,
            "ton_price": ton_price,
            "floor_stars": real_floor_stars,
            "model": model_name,
            "online": seller["online"],
            "gifts_count": seller["nft_gifts_count"],
            "level": seller["level"],
            "message": seller["message_text"],
            "has_premium": seller["has_premium"],
            "owner_username": seller["username"],
            "owner_id": owner_id,
            "gift_url": gift_url,
            "is_female": is_girl,
            "country": country
        }

        from notifier import get_topic_by_floor
        thread_id = get_topic_by_floor(gift_payload)
        if thread_id == config.TOPIC_IDS.get("girl_ru_ua") and not (is_girl and country in ("RU", "UA")):
            SEEN_LISTING_IDS.add(unique_id)
            continue

        await send_log_to_topic(gift_payload)
        record_sent_gender(is_girl)
        
        if owner_id > 0:
            SENT_SELLERS_IDS.add(owner_id)

        SEEN_LISTING_IDS.add(unique_id)
        sent_from_category += 1

        gender_tag = "Девушка 🌸" if is_girl else f"Парень ({country})"
        print(f"[+] УСПЕХ! Отправлен лог [{gender_tag}] [Регион: {country}] (ур: {seller['level']}, NFT подарков: {seller['nft_gifts_count']}): {clean_title} #{num} | Цена: {stars_price} ⭐")


async def scan_internal_tg_market():
    global SEEN_LISTING_IDS, SENT_SELLERS_IDS
    if len(SEEN_LISTING_IDS) > 4000:
        SEEN_LISTING_IDS.clear()
    
    if len(SENT_SELLERS_IDS) > 5000:
        SENT_SELLERS_IDS = set(list(SENT_SELLERS_IDS)[2500:])

    try:
        res = await tg_client(functions.payments.GetStarGiftsRequest(hash=0))
        gifts_to_check = [
            g for g in getattr(res, "gifts", [])
            if safe_int(getattr(g, "availability_resale", 0)) > 0
        ]

        random.shuffle(gifts_to_check)

        tasks = [process_single_category(g_type) for g_type in gifts_to_check[:12]]
        await asyncio.gather(*tasks)

        await asyncio.sleep(3)

    except Exception as e:
        print(f"[Ошибка сканирования маркета]: {e}")
        await asyncio.sleep(2)