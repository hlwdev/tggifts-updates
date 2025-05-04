import asyncio
import pytz
from datetime import datetime

from aiogram import Router, Bot, types
from aiogram.filters import Command, CommandStart
from aiogram.exceptions import TelegramRetryAfter

from sqlalchemy.future import select
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from telethon.tl.types.payments import StarGifts
from telethon import TelegramClient
from telethon.functions import payments

from config import token, admin_ids, api_id, api_hash, channel_id, editing_msg, PROXY
from database.models import async_session, Gift

dp = Router()
bot = Bot(token=token)

notification_states = {}

client = TelegramClient(session='new_session', api_id=api_id, api_hash=api_hash, proxy=PROXY)

async def add_new_gift(gift_id: int):
    async with async_session() as session:
        try:
            session.add(Gift(gift_id=gift_id))
            await session.commit()
        except IntegrityError:
            await session.rollback()

async def get_known_upgradable():
    async with async_session() as session:
        result = await session.execute(select(Gift.gift_id).where(Gift.is_upgradable))
        return {gift_id for (gift_id,) in result}

async def update_upgradable_info(gift_id: int):
    async with async_session() as session:
        try:
            s = select(Gift).where(Gift.gift_id == str(gift_id))
            result = await session.execute(s)
            gift = result.scalar_one_or_none()
            if gift:
                gift.is_upgradable = 1
                await session.commit()
        except IntegrityError:
            await session.rollback()

async def update_soldout_info(gift_id: int):
    async with async_session() as session:
        try:
            s = await session.execute(select(Gift).where(Gift.gift_id==str(gift_id)))
            gift = s.scalar_one_or_none()
            if gift:
                gift.sold_out = 1
                await session.commit()
        except IntegrityError:
            await session.rollback()

async def update_alert_10(gift_id: int):
    async with async_session() as session:
        try:
            s = await session.execute(select(Gift).where(Gift.gift_id==str(gift_id)))
            gift = s.scalar_one_or_none()
            if gift:
                gift.alert_10 = 1
                await session.commit()
        except InterruptedError:
            await session.rollback()

async def update_alert_1(gift_id: int):
    async with async_session() as session:
        try:
            s = await session.execute(select(Gift).where(Gift.gift_id==str(gift_id)))
            gift = s.scalar_one_or_none()
            if gift:
                gift.alert_1 = 1
                await session.commit()
        except InterruptedError:
            await session.rollback()

@dp.message(CommandStart())
async def start(message: types.Message):
    if message.from_user.id in admin_ids:
        await message.answer('Bot is work!')

@dp.message(Command('startpars'))
async def start_parsing(message: types.Message):
    if message.from_user.id in admin_ids:
        await message.answer('Monitoring was started!')
        #back
        l: StarGifts = await client(payments.GetStarGiftsRequest(1))
        list = l.gifts
        for gift in list:
            if gift.availability_total:
                    await add_new_gift(gift.id)
                    await update_upgradable_info(gift.id) if gift.upgrade_stars else None
                    await update_soldout_info(gift.id) if gift.sold_out==True else None
        new_upgrades = []   
        new_gifts = []
        cur_gifts = [] 
        cur_sold = []
        new_sold = []
        while True:       
            await asyncio.sleep(5)
            g: StarGifts = await client(payments.GetStarGiftsRequest(2)) 
            gifts_list1 = sorted(
                (g for g in g.gifts if g.availability_total is not None),
                key=lambda gift: gift.stars, reverse=True
            )
            timezone = pytz.timezone('Europe/Moscow')
            now = datetime.now(timezone).strftime('%H:%M:%S')

            new_upgrades.clear()
            cur_gifts.clear()
            new_gifts.clear()
            cur_sold.clear()
            new_sold.clear()

            for gift in gifts_list1:
                if gift.availability_total and gift.sold_out==False:
                    try:
                        gift_id = gift.id
                        current_ratio = gift.availability_remains*100/gift.availability_total

                        emoji = gift.sticker.attributes[1].alt
                        price = gift.stars
                        upgrade_price = gift.upgrade_stars
                        total_count = gift.availability_total
                        remain_count = gift.availability_remains
                        async with async_session() as session:
                            res = await session.execute(select(Gift.gift_id).where(Gift.gift_id==gift_id))
                            fin_res = res.scalar_one_or_none()
                            if not fin_res:
                                if gift.upgrade_stars:
                                    print('yess')
                                    new_gifts.append(f'{emoji} {price}⭐️ (limited: {total_count} gifts, upgradable for: {upgrade_price})\n')
                                    await update_upgradable_info(gift.id)                 
                                else:
                                    new_gifts.append(f'{emoji} {price}⭐️ (limited {total_count} gifts)\n')
                                await add_new_gift(gift.id)
                                await update_upgradable_info(gift.id) if gift.upgrade_stars else None
                                
            
                            cur_gifts.append(f"{emoji} {price}⭐️ {remain_count}/{total_count} ({current_ratio:.1f}%)\n\n")

                            prev_state = notification_states.get(gift_id, {'last_ratio': None})
                            last_ratio = prev_state['last_ratio']
                            notification_states[gift_id] = {
                                'last_ratio': current_ratio,
                                }
                        

                            res1 = await session.execute(select(Gift.gift_id).where(Gift.gift_id==gift_id).where(Gift.alert_10==None))
                            fin_res1 = res1.scalar_one_or_none()
                            res2 = await session.execute(select(Gift.gift_id).where(Gift.gift_id==gift_id).where(Gift.alert_1==None))
                            fin_res2 = res2.scalar_one_or_none()
                            if current_ratio<=10 and last_ratio>10 and fin_res1:
                                await bot.send_message(chat_id=channel_id, text=f'Supply alert!\n\n{emoji} {price}⭐️ {remain_count}/{total_count} is 10% remaining', reply_to_message_id=editing_msg)
                                await update_alert_10(gift_id)
                            elif current_ratio<=1 and last_ratio>1 and fin_res2:
                                await bot.send_message(chat_id=channel_id, text=f'Supply alert!\n\n{emoji} {price}⭐️ {remain_count}/{total_count} is 1% remaining', reply_to_message_id=editing_msg)
                                await update_alert_1(gift_id)
                    except TelegramRetryAfter as e:
                        text = f'{now} - So many requests error'
                        print(text)
                        for admin in admin_ids:
                            await asyncio.sleep(10)
                            await bot.send_message(chat_id=admin, text=text)
                        continue
                    except Exception as e:
                        for admin in admin_ids:
                            await bot.send_message(chat_id=admin, text=f'NEW ERROR IN BACK:\n\n{e}')
                        continue
                if gift.availability_total:
                    async with async_session() as session:
                        q = await session.execute(select(Gift.gift_id).where(Gift.gift_id==gift.id).where(Gift.is_upgradable==None))
                        g_id = q.scalar()
                        if g_id:
                            if gift.upgrade_stars and gift.id==int(g_id):
                                new_upgrades.append(f"{gift.sticker.attributes[1].alt} {gift.stars}⭐️ {gift.availability_remains}/{gift.availability_total} for {gift.upgrade_stars}⭐️\n")
                                await session.execute(update(Gift).where(Gift.gift_id == gift.id).values(is_upgradable=True))
                                await session.commit()
                if gift.sold_out==True:
                    async with async_session() as session:
                        w = await session.execute(select(Gift.gift_id).where(Gift.gift_id==gift.id).where(Gift.sold_out==None))
                        g_id = w.scalar()
                        if g_id:
                            if gift.sold_out==True and gift.id == int(g_id):
                                if gift.upgrade_stars:
                                    new_sold.append(f"{gift.sticker.attributes[1].alt} {gift.stars}⭐️ {gift.availability_remains}/{gift.availability_total} (upgradable for {gift.upgrade_stars})\n")
                                else:
                                    new_sold.append(f"{gift.sticker.attributes[1].alt} {gift.stars}⭐️ {gift.availability_remains}/{gift.availability_total}\n")
                                await session.execute(update(Gift).where(Gift.gift_id==gift.id).values(sold_out=True))
                                await session.commit()
            #Front
            try:
                if new_gifts:
                    msg = '‼️ NEW GIFTS ALERT\n\n'+'\n'.join(new_gifts)
                    await bot.send_message(
                        chat_id=channel_id,
                        text=msg
                    )
                if new_upgrades:
                    msg = '🆙 NEW UPGRADES AVAILABLE:\n\n' + '\n\n'.join(new_upgrades)
                    await bot.send_message(chat_id=channel_id, text=msg)  
                if new_sold:
                    msg = '❌ SOLD OUT:\n\n'+'\n'.join(new_sold)
                    await bot.send_message(chat_id=channel_id, text=msg)
                #current gifts
                msg = '' + ''.join(cur_gifts)
                await bot.edit_message_text(chat_id=channel_id, message_id=editing_msg, text=msg+f'Last update: {now}')
            except Exception as e:
                for admin in admin_ids:
                    await bot.send_message(chat_id=admin, text=f'NEW ERROR:\n\n{e}')
                    continue

@dp.message(Command('send'))
async def ffff(message: types.Message, bot: Bot):
    w = await bot.send_message(chat_id=channel_id, text='aaa')
    msg_id = w.message_id
    await bot.edit_message_text(chat_id=channel_id, message_id=msg_id, text=f'ID of this message:\n\n{msg_id}\n\nPaste this id in config.py')
