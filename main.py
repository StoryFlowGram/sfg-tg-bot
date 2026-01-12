import logging
import asyncio
from app.settings.create_bot import dp, bot
from app.handlers.start import router_start

async def main():
    dp.include_router(router_start)

    await dp.start_polling(bot)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    asyncio.run(main())
