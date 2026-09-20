import re
import time
from collections import deque
from typing import Tuple

RECENT_GENDER_HISTORY = deque(maxlen=20)
LAST_FEMALE_TIMESTAMP = time.time()

# Полная расширенная база женских имен (все вариации, славянские, европейские, транслитерация)
FEMALE_NAMES = {
    # А
    "авдотья", "агата", "аглая", "агния", "ада", "аделина", "аделия", "адиля", "аида", "айгуль", 
    "айслу", "алана", "алёна", "алина", "алинка", "алиса", "алла", "альбина", "амина", "амрита", 
    "анастасия", "ангелина", "анжела", "анжелика", "ания", "анна", "антонина", "анфиса", "аня", 
    "арина", "арианна", "армина", "ася", "аэлита", "ая",
    # Б, В
    "бажена", "барбара", "беатрис", "белла", "бибигуль", "богдана", "божена", "бронислава",
    "василиса", "вася", "валя", "валентина", "валерия", "варя", "варвара", "ведана", "велислава", 
    "венера", "вера", "вероника", "веселина", "веста", "виктория", "виолетта", "виола", "вита", 
    "виталина", "влада", "владислава", "владлена",
    # Г, Д
    "габи", "галина", "глафира", "гликерия", "гульнара", "гульшат", "дана", "дария", "дарина", 
    "дарья", "даша", "дея", "джамиля", "джейн", "диана", "дина", "диляра", "доминика", "дора",
    # Е, Ж, З
    "ева", "евгения", "евдокия", "евлампия", "евсения", "екатерина", "елена", "елизавета", 
    "есения", "ефросинья", "жанель", "жанна", "жемчужина", "женя", "зина", "зинаида", "злата", 
    "зоряна", "зоя",
    # И, К
    "иванна", "израиль", "изольда", "инга", "инесса", "инна", "ира", "ираида", "ирина", "ия", 
    "карина", "каролина", "катарина", "катерина", "катя", "кира", "клавдия", "клара", "клавдия", 
    "кристина", "ксении", "ксения",
    # Л, М
    "лада", "лана", "лариса", "лаура", "лейла", "лена", "леокадия", "леся", "лиана", "лидия", 
    "лилия", "лина", "линда", "лира", "лиса", "лидия", "лиза", "лизовета", "линда", "люба", 
    "любовь", "людмила", "люся", "ляля",
    "майя", "маргарита", "марианна", "марика", "марина", "маричка", "мария", "марфа", "марта", 
    "маруся", "маша", "мелания", "милана", "милена", "милица", "мирослава", "мишель", "моника", "муза",
    # Н, О
    "надежда", "нади", "надя", "назгуль", "настасья", "настя", "ната", "натали", "наталия", 
    "наталья", "наташа", "нелли", "ника", "нина", "нонна", "нюра",
    "оксана", "олеся", "ольга", "олюся",
    # П, Р, С
    "павлина", "пелагея", "полина", "прасковья", "пульхерия",
    "рада", "радмила", "раиса", "раissa", "рахель", "ребекка", "регина", "рената", "рима", "римма", 
    "роза", "розалия", "руслана", "руфина",
    "сабина", "сания", "сара", "светлана", "света", "селена", "рафима", "снежана", "соломея", 
    "соломия", "соня", "софия", "софья", "стелла", "степанида", "сусанна", "сэтэла",
    # Т, У, Ф, Х, Э, Ю, Я
    "таисия", "таиса", "тамара", "таня", "татьяна", "теона", "тиана", "тома",
    "ульяна", "устина", "ульяна",
    "фаина", "екла", "флора", "фрида",
    "хлоя", "христина",
    "эвелина", "эдита", "элеонора", "элина", "элла", "эльвира", "эльза", "эмилия", "эрика", "эсма", 
    "юлианна", "юлия", "юнона", "юля",
    "явдоха", "яна", "ярослава", "ярина", "асмин", "яся",

    # Латинская транслитерация и популярные зарубежные имена
    "anna", "anya", "anastasiia", "anastasia", "nastya", "masha", "maria", "marie", "dasha", 
    "polina", "sonya", "sofia", "sofiia", "alina", "lera", "valeria", "valeriya", "katya", 
    "kate", "catherine", "diana", "eva", "ksusha", "kсения", "liza", "yelyzaveta", "yulia", 
    "julia", "kristina", "alice", "alisa", "olya", "olena", "tanya", "marisha", "marina", 
    "oksana", "olesya", "solomiya", "marichka", "daryna", "khrystyna", "iryna", "vladyslava", 
    "bohdana", "milana", "veronika", "svetlana", "ludmila", "nadezhda", "arina", "varvara", 
    "rita", "ulyana", "angelina", "emilia", "zoia", "raisa", "taisia", "kira", "stefa", 
    "kristy", "vika", "zлата", "lilia", "kamilla", "adelina", "regina", "snezhana", "karina",
    "chloe", "mia", "emma", "olivia", "ava", "sophia", "isabella", "amelia", "harper", 
    "evelyn", "abigail", "emily", "elizabeth", "mila", "ella", "avery", "sofia", "camila", 
    "aria", "scarlett", "victoria", "madison", "luna", "grace", "chloe", "penelope", "layla", 
    "riley", "zoey", "nora", "lily", "eleanor", "hannah", "lillian", "addison", "aubrey", 
    "ellie", "stella", "natalie", "zoe", "leah", "hazel", "violet", "aurora", "savannah", 
    "audrey", "brooklyn", "bella", "claire", "skylar", "lucy", "paisley", "everly", "anna", 
    "caroline", "nova", "genesis", "emilia", "kennedy", "samantha", "maya", "willow", 
    "kinsley", "naomi", "aaliyah", "elena", "sarah", "ariana", "allison", "gabriella", "alice", 
    "madelyn", "cora", "ruby", "eva", "serenity", "autumn", "adeline", "hailey", "gianna", 
    "valentina", "isla", "eliana", "quinn", "nevaeh", "ivy", "sadie", "piper", "lydia", 
    "alexa", "josephine", "emery", "julia", "delilah", "arianna", "vivian", "kaylee", "sophie", 
    "brielle", "madeline", "peyton", "rina", "koko", "mimi", "fifi", "lulu"
}

# Ласкательные слова и маркеры в никах / описаниях
AFFECTIONATE_WORDS = [
    "зайка", "зая", "зайчонок", "котик", "котенок", "малышка", "принцесса", "солнце", "солнышко", 
    "милашка", "девочка", "киса", "лапочка", "киска", "красотка", "милая", "любимая", "бусинка",
    "сонечко", "зайчик", "кицюня", "малеча", "киця", "мила", "кохана", "принцеса", "красуня",
    "крошка", "сладкая", "глупышка", "звездочка", "нежность", "кошечка", "папина", "мамина",
    "ангелочек", "зефирка", "клубничка", "вишенка", "малинка", "редл", "тучка", "глазурь", 
    "конфетка", "пушистик", "котя", "китти", "милаха", "буся", "бусинка", "малыш", "ляля",
    "sweet", "cutie", "baby", "princess", "girl", "kitty", "fairy", "queen", "sweetheart",
    "honey", "angel", "bunny", "chloe", "cherry", "peach", "blossom", "meow", "badass",
    "babe", "doll", "darling", "sugar", "flower", "rose", "fairy", "magic", "pretty"
]

# Фразы в био от женского рода (например: "самая лучшая", "успешная", "рада", "любимая", "красивая")
FEMALE_BIO_PHRASES = [
    "лучшая", "красивая", "любимая", "счастливая", "единственная", "неповторимая", 
    "милашка", "королева", "богиня", "умница", "мила", "нежная", "сладкая", "девочка",
    "rad", "rada", "zanyata", "free", "blagodarna", "vsem", "poka", "privet",
    "сама", "могла", "хотела", "думала", "знала", "любила", "ждала", "успешна", 
    "рада", "готова", "занята", "устала", "скучаю", "пишите", "тут", "моя", "твоя"
]

GIRL_EMOJIS = [
    "🌸", "🎀", "🩰", "💅", "💄", "🍓", "🧸", "🕊️", "💖", "💕", "💗", "🧚‍♀️", "👸", "✨", 
    "🤍", "🥺", "🦋", "🌷", "🍒", "🍓", "🍉", "⚡", "💌", "💋", "💘", "💝", "💞", "💟",
    "🦄", "🪞", "🩵", "💜", "🩷", "🪽", "🫶", "🥿", "👛", "👑", "🍓"
]

FEMALE_SUFFIXES = (
    "очка", "ечка", "уля", "юля", "ушка", "юшка", "ичка", "уня", "уся", "юся", 
    "ая", "яя", "ова", "ева", "ина", "ых", "их", "ук", "юк", "ко", "енька", "онька",
    "аша", "оша", "уша", "юша", "ица", "ыца", "эсса", "ис", "исс"
)

FOREIGN_SCRIPTS_PATTERN = re.compile(
    r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\u4E00-\u9FFF\u3040-\u30FF\u0E00-\u0E7F\u0900-\u097F\u0590-\u05FF]"
)

RU_UA_MARKERS = [
    "_ru", "rus", "_rf", "msk", "spb", "moscow", "russia", "рф", "москва", "питер", "россия",
    "_ua", "ukr", "_ukr", "kiev", "kyiv", "lviv", "odesa", "odessa", "kharkiv", "dnipro", "ukraine", "уа", "украина", "київ"
]


def check_ru_ua_origin(name: str, bio: str, username: str) -> Tuple[bool, str]:
    full_text = f"{name or ''} {bio or ''} {username or ''}"
    lowered = full_text.lower()

    if FOREIGN_SCRIPTS_PATTERN.search(full_text):
        return False, ""

    if re.search(r"[а-яА-ЯёЁіІїЇєЄґҐ]", full_text):
        is_ua = bool(re.search(r"[іІїЇєЄґҐ]", full_text)) or any(tag in lowered for tag in ["_ua", "ukr", "kyiv", "украина", "київ"])
        return True, "UA" if is_ua else "RU"

    for tag in RU_UA_MARKERS:
        if tag in lowered:
            return True, "UA" if ("ua" in tag or "ukr" in tag or "kyiv" in tag or "украина" in tag) else "RU"

    tokens = set(re.findall(r"\b[a-zA-Z]+\b", lowered))
    for t in tokens:
        if len(t) > 4 and t.endswith(("ova", "eva", "ina", "aya", "ov", "ev", "in", "iy", "ko", "uk", "sky")):
            return True, "RU"

    return True, "RU"


def is_female(name: str, bio: str, username: str) -> bool:
    """Глубокий анализ: имена, уменьшительные формы, суффиксы, био от женского рода и эмодзи."""
    full_text = f"{name or ''} {bio or ''} {username or ''}".lower()
    
    tokens = re.findall(r"\b[a-zA-Zа-яА-ЯёЁіІїЇєЄґҐ]+\b", full_text)

    # 1. Проверка по словарю имен
    for token in tokens:
        if token in FEMALE_NAMES:
            return True

    # 2. Проверка ласкательных слов
    for aff in AFFECTIONATE_WORDS:
        if aff in full_text:
            return True

    # 3. Проверка фраз в био / описании от женского рода (например, "самая лучшая")
    for phrase in FEMALE_BIO_PHRASES:
        if phrase in full_text:
            return True

    # 4. Анализ морфологических окончаний (например, слова на -ая/-яя, -очка)
    for token in tokens:
        if len(token) > 3 and token.endswith(FEMALE_SUFFIXES):
            return True

    # 5. Проверка по специфичным женским эмодзи
    emoji_count = sum(1 for char in full_text if char in GIRL_EMOJIS)
    if emoji_count >= 1:
        return True

    # 6. Подстроки в никнеймах
    female_substrings = [
        "girl", "miss", "queen", "princess", "kitty", "fox", "bunny", "anya", "nastya", 
        "masha", "vika", "chka", "sweet", "baby", "angel", "lulu", "koko", "fifi", 
        "rina", "yulia", "yana", "oksana", "alina", "lera"
    ]
    
    cleaned_text = full_text.replace(" ", "").replace("_", "")
    for sub in female_substrings:
        if sub in cleaned_text:
            if len(sub) > 3 or f"_{sub}" in full_text or f"{sub}_" in full_text or len(cleaned_text) < 12:
                return True

    return False


def can_send_gender(is_girl: bool) -> bool:
    global LAST_FEMALE_TIMESTAMP
    return True


def record_sent_gender(is_girl: bool):
    global LAST_FEMALE_TIMESTAMP
    if is_girl:
        LAST_FEMALE_TIMESTAMP = time.time()
    RECENT_GENDER_HISTORY.append(is_girl)