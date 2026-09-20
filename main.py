import asyncio
import config
from notifier import bot, dp
from market_scanner import tg_client, scan_internal_tg_market

async def run_market_loop():
    print("[+] Сканер маркета с расчетом флора и фильтром профилей запущен...")
    while True:
        try:
            await scan_internal_tg_market()
        except Exception as e:
            print(f"[!] Ошибка в цикле сканера: {e}")
        
        await asyncio.sleep(config.SCAN_INTERVAL_SECONDS)

async def main():
    print("[1/2] Авторизация Telegram клиента...")
    await tg_client.start()

    print("[2/2] Сброс старых подключений и запуск бота...")
    await bot.delete_webhook(drop_pending_updates=True)

    await asyncio.gather(
        run_market_loop(),
        dp.start_polling(bot)
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен.")
