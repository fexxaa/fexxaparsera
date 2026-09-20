import asyncio
from telethon import TelegramClient
from telethon.tl.functions.account import CheckUsernameRequest
from telethon.errors import UsernameOccupiedError, UsernameInvalidError

# Укажите свои данные от My.Telegram.org (или используйте те же, что в config.py вашего проекта)
API_ID = 1234567  # Замените на ваш api_id
API_HASH = "your_api_hash"  # Замените на ваш api_hash

client = TelegramClient("checker_session", API_ID, API_HASH)

async def check_username(username: str):
    username = username.lstrip("@").strip()
    try:
        result = await client(CheckUsernameRequest(username=username))
        if result:
            print(f"[+] Юзернейм @{username} СВОБОДЕН!")
        else:
            print(f"[-] Юзернейм @{username} занят.")
    except UsernameOccupiedError:
        print(f"[-] Юзернейм @{username} уже занят.")
    except UsernameInvalidError:
        print(f"[!] Юзернейм @{username} некорректный.")
    except Exception as e:
        print(f"[!] Ошибка при проверке @{username}: {e}")

async def main():
    await client.start()
    print("[+] Чекер запущен!")
    
    # Список юзернеймов для проверки
    usernames_to_check = [
        "durov",
        "test_username_123456789_free",
    ]

    for uname in usernames_to_check:
        await check_username(uname)
        await asyncio.sleep(1) # Задержка во избежание флуд-веийтов

if __name__ == "__main__":
    asyncio.run(main())