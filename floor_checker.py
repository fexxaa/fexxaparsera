import time
from typing import List, Dict, Tuple

# Кэш флора модели: (gift_id, model_name) -> (floor_stars, expire_time)
MODEL_FLOOR_CACHE: Dict[Tuple[int, str], Tuple[int, float]] = {}

# Кэш флора всей коллекции подарка: gift_id -> (floor_stars, expire_time)
COLLECTION_FLOOR_CACHE: Dict[int, Tuple[int, float]] = {}

# Время жизни кэша флора (5 минут)
FLOOR_CACHE_TTL = 300


def extract_item_price(item) -> int:
    """
    Надёжное извлечение цены перепродажи в звёздах из любого объекта лота Telegram.
    """
    if not item:
        return 0

    # 1. Проверяем resell_amount
    resell = getattr(item, "resell_amount", None)
    if isinstance(resell, (int, float)):
        return int(resell)
    if isinstance(resell, list) and len(resell) > 0:
        first = resell[0]
        val = getattr(first, "amount", getattr(first, "stars", None))
        if val is not None:
            return int(val)
    if resell is not None:
        val = getattr(resell, "amount", getattr(resell, "stars", None))
        if val is not None:
            return int(val)

    # 2. Прямые атрибуты объекта
    for field in ("stars", "price", "amount"):
        val = getattr(item, field, None)
        if isinstance(val, (int, float)) and val > 0:
            return int(val)

    return 0


def get_item_model(item) -> str:
    """
    Извлекает название модели подарка (Classic, Gold, Neon и др.)
    """
    attrs = getattr(item, "attributes", []) or []
    for attr in attrs:
        name = getattr(attr, "name", None) or getattr(attr, "model", None)
        if name:
            return str(name).strip()
    return "Classic"


def calculate_clean_floor(prices: List[int]) -> int:
    """
    Вычисляет устойчивый реальный флор:
    - Отсекает нулевые и отрицательные значения
    - Отсекает аномальные дампы и перекиды (например, 25-50 звёзд при основном рынке 1000+)
    """
    valid = sorted([int(p) for p in prices if isinstance(p, (int, float)) and p > 0])
    if not valid:
        return 0

    if len(valid) == 1:
        return valid[0]

    # Если минимальная цена подозрительно мала (<= 50 звёзд), а другие лоты намного дороже
    if valid[0] <= 50 and valid[-1] > 100:
        filtered = [p for p in valid if p > 50]
        if filtered:
            valid = filtered

    # Если есть хотя бы 3 лота и самый первый — аномальный слив (< 40% от второго лота)
    if len(valid) >= 3 and valid[0] < (valid[1] * 0.4):
        return valid[1]

    return valid[0]


def is_floor_cache_expired(gift_id: int) -> bool:
    """
    Проверяет, истек ли кэш флора для данного типа подарка.
    """
    now = time.time()
    if gift_id in COLLECTION_FLOOR_CACHE:
        _, expire_at = COLLECTION_FLOOR_CACHE[gift_id]
        if now < expire_at:
            return False
    return True


def update_market_floors(gift_id: int, items: list):
    """
    Обновляет кэш реального флора для всей коллекции и для каждой конкретной модели.
    """
    now = time.time()
    collection_prices = []
    model_prices: Dict[str, List[int]] = {}

    for it in items:
        p = extract_item_price(it)
        if p <= 0:
            continue

        collection_prices.append(p)
        model = get_item_model(it)
        if model not in model_prices:
            model_prices[model] = []
        model_prices[model].append(p)

    # 1. Записываем общий флор коллекции
    coll_floor = calculate_clean_floor(collection_prices)
    if coll_floor > 50:
        COLLECTION_FLOOR_CACHE[gift_id] = (coll_floor, now + FLOOR_CACHE_TTL)

    # 2. Записываем флор по каждой модели
    for model, m_prices in model_prices.items():
        m_floor = calculate_clean_floor(m_prices)
        if m_floor > 50:
            MODEL_FLOOR_CACHE[(gift_id, model)] = (m_floor, now + FLOOR_CACHE_TTL)


def get_real_floor(gift_id: int, model_name: str = "Classic", item_price: int = 0) -> int:
    """
    Возвращает настоящий флор:
    1. Сначала проверяет точный флор именно этой модели
    2. Затем общий флор коллекции
    3. Если информации нет — берет цену текущего лота (но никогда не возвращает 25!)
    """
    now = time.time()

    # 1. Флор модели
    m_key = (gift_id, model_name)
    if m_key in MODEL_FLOOR_CACHE:
        val, exp = MODEL_FLOOR_CACHE[m_key]
        if now < exp and val > 50:
            return val

    # 2. Общий флор коллекции
    if gift_id in COLLECTION_FLOOR_CACHE:
        val, exp = COLLECTION_FLOOR_CACHE[gift_id]
        if now < exp and val > 50:
            return val

    # 3. Защита: если флор так и не определен, он не может быть 25 звёзд при нормальной цене лота
    if item_price > 50:
        return item_price

    return 500


async def get_real_floor_in_stars(collection_address: str = None) -> int:
    """
    Заглушка обратной совместимости для старых вызовов.
    """
    return 0