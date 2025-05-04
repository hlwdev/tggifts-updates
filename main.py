import logging
import asyncio
from aiogram import Dispatcher, Bot
from aiogram.fsm.storage.memory import MemoryStorage

from handlers import dp
from config import token, PHONE_NUMBER
from database.models import async_main
storage = MemoryStorage()
ll = Dispatcher(storage=storage)
from handlers import client

logging.basicConfig(level=logging.INFO)
bot = Bot(token=token)


ll.include_router(dp)

async def main():
    await async_main()
    await client.start(PHONE_NUMBER)
    await ll.start_polling(bot)
if __name__ == '__main__':
    asyncio.run(main())
