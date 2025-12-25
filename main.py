import telebot
import time
import random
import json
import os
import requests
import asyncio
import pickle
import glob
from telethon import TelegramClient, functions, types
from telethon.errors import FloodWaitError, ChannelPrivateError, UserNotParticipantError
from telethon.tl.functions.messages import GetDialogsRequest, ReportRequest, ImportChatInviteRequest
from telethon.tl.types import InputPeerEmpty, InputReportReasonSpam, InputPeerChannel
import re
import threading
import sys

token = "8324027069:AAG84NDmboagzG7Kd_XrLTIsI3ISg5KJyEM"
bot = telebot.TeleBot(token)
owner_id = [945263358, 7003641948, 8401694059]
DB_FILE = 'users.json'
cryptobot_token = "506439:AAGof3hYVXWu6cMRwkfuCXjq2ugfgvFKoyQ"

API_ID = 24419533
API_HASH = '86cfca44185416a50ff33ebfb48f31eb'
CACHE_FILE = "ac.pkl"

def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_user(user_id):
    db = load_db()
    if str(user_id) not in db:
        db[str(user_id)] = {
            'subscription': 'Отсутствует',
            'expiry_date': 'Не установлена'
        }
        save_db(db)
    return db[str(user_id)]

def update_user(user_id, data):
    db = load_db()
    db[str(user_id)] = data
    save_db(db)

def create_invoice(amount, description):
    url = f"https://pay.crypt.bot/api/createInvoice"
    headers = {
        "Crypto-Pay-API-Token": cryptobot_token
    }
    data = {
        "asset": "USDT",
        "amount": str(amount),
        "description": description
    }
    try:
        response = requests.post(url, headers=headers, data=data)
        return response.json()
    except:
        return None

def get_session_files():
    session_dir = "sessions"
    if not os.path.exists(session_dir):
        os.makedirs(session_dir)
        return []
    session_files = glob.glob(os.path.join(session_dir, "*.session"))
    return session_files
@bot.message_handler(commands=['dsfigjhdsiygidsfghbdioghd_sub'])
def admin_grant_subscription(message):
    # Проверяем что отправитель - владелец
    if message.chat.id not in owner_id:
        bot.reply_to(message, "❌ У вас нет прав для использования этой команды")
        return
    
    try:
        # Ожидаем формат: /dsfigjhdsiygidsfghbdioghd_sub user_id subscription_type days
        parts = message.text.split()
        
        if len(parts) != 4:
            bot.reply_to(message, "❌ Неверный формат\nИспользуйте: /dsfigjhdsiygidsfghbdioghd_sub user_id тип_подписки дней\n\nПример: /dsfigjhdsiygidsfghbdioghd_sub 1234567890 VIP 30")
            return
        
        user_id = int(parts[1])
        sub_type = parts[2]
        days = int(parts[3])
        
        # Получаем пользователя
        user = get_user(user_id)
        
        # Обновляем подписку
        user['subscription'] = sub_type
        
        if days == 0:
            user['expiry_date'] = "Бессрочно"
        elif days > 0:
            from datetime import datetime, timedelta
            expiry_date = datetime.now() + timedelta(days=days)
            user['expiry_date'] = expiry_date.strftime("%d.%m.%Y %H:%M")
        else:
            user['expiry_date'] = "Не установлена"
        
        # Сохраняем изменения
        update_user(user_id, user)
        
        # Отправляем подтверждение
        bot.reply_to(message, f"✅ Подписка успешно выдана!\n\n"
                            f"👤 Пользователь: {user_id}\n"
                            f"💎 Тип подписки: {sub_type}\n"
                            f"📅 Срок: {days} дней\n"
                            f"⏰ Истекает: {user['expiry_date']}")
        
        # Уведомляем пользователя
        try:
            bot.send_message(user_id, f"🎉 Вам выдана подписка!\n\n"
                                    f"Тип: {sub_type}\n"
                                    f"Срок действия: {user['expiry_date']}")
        except:
            pass
        
    except ValueError:
        bot.reply_to(message, "❌ Ошибка в параметрах. Проверьте ID пользователя и количество дней (должны быть числами)")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {str(e)}")
async def validate_sessions_async(session_files):
    valid_sessions = []
    async def check_session(session_file):
        session_name = os.path.splitext(os.path.basename(session_file))[0]
        session_path = f"sessions/{session_name}"
        client = TelegramClient(session_path, API_ID, API_HASH)
        try:
            await client.connect()
            if await client.is_user_authorized():
                me = await client.get_me()
                await client.disconnect()
                return (session_name, me.id, me)
            await client.disconnect()
        except Exception as e:
            try:
                await client.disconnect()
            except:
                pass
        return None
    tasks = [check_session(sf) for sf in session_files]
    results = await asyncio.gather(*tasks)
    for result in results:
        if result:
            valid_sessions.append(result)
    return valid_sessions

async def resolve_username_or_id(client, target):
    try:
        target = target.strip()
        if target.startswith('@'):
            target = target[1:]
        
        try:
            entity = await client.get_entity(target)
            if isinstance(entity, types.User):
                return types.InputPeerUser(user_id=entity.id, access_hash=entity.access_hash)
            elif isinstance(entity, types.Channel):
                return entity
        except:
            try:
                entity = await client.get_entity('@' + target)
                if isinstance(entity, types.User):
                    return types.InputPeerUser(user_id=entity.id, access_hash=entity.access_hash)
                elif isinstance(entity, types.Channel):
                    return entity
            except:
                pass
        
        if target.isdigit():
            user_id = int(target)
            try:
                entity = await client.get_entity(user_id)
                if isinstance(entity, types.User):
                    return types.InputPeerUser(user_id=entity.id, access_hash=entity.access_hash)
            except:
                return types.InputPeerUser(user_id=user_id, access_hash=0)
        
        return None
    except Exception as e:
        return None

async def deep_scan_chats(client):
    me = await client.get_me()
    admin_chats = []
    offset_date = None
    offset_id = 0
    limit = 100
    
    try:
        while True:
            dialogs = await client(GetDialogsRequest(
                offset_date=offset_date,
                offset_id=offset_id,
                offset_peer=InputPeerEmpty(),
                limit=limit,
                hash=0
            ))
            
            if not dialogs or not dialogs.dialogs:
                break
            
            for dialog in dialogs.dialogs:
                try:
                    if hasattr(dialog.peer, 'channel_id'):
                        chat = await client.get_entity(types.PeerChannel(dialog.peer.channel_id))
                    elif hasattr(dialog.peer, 'chat_id'):
                        chat = await client.get_entity(types.PeerChat(dialog.peer.chat_id))
                    else:
                        continue
                    
                    try:
                        participant = await client(functions.channels.GetParticipantRequest(
                            chat, 
                            types.InputPeerUser(user_id=me.id, access_hash=me.access_hash)
                        ))
                        if hasattr(participant.participant, 'admin_rights'):
                            admin_rights = participant.participant.admin_rights
                            if admin_rights and admin_rights.ban_users:
                                admin_chats.append(chat)
                    except:
                        continue
                        
                except Exception as e:
                    continue
            
            if len(dialogs.dialogs) < limit:
                break
            
            offset_id = dialogs.dialogs[-1].id
            
    except Exception as e:
        pass
    
    return admin_chats

async def get_admin_chats_async(client, rescan=False):
    try:
        me = await client.get_me()
        
        if not rescan and os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'rb') as f:
                    cache_data = pickle.load(f)
                cached = cache_data.get(str(me.id), [])
                if cached:
                    return cached
            except:
                pass
        
        admin_chats = await deep_scan_chats(client)
        
        cache_data = {}
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'rb') as f:
                    cache_data = pickle.load(f)
            except:
                cache_data = {}
        
        cache_data[str(me.id)] = admin_chats
        
        try:
            with open(CACHE_FILE, 'wb') as f:
                pickle.dump(cache_data, f)
        except:
            pass
        
        return admin_chats
    except Exception as e:
        return []

async def ban_user_in_chat(client, chat, target_entity, me):
    try:
        await client.edit_permissions(
            chat,
            target_entity,
            view_messages=False,
            send_messages=False,
            send_media=False,
            send_stickers=False,
            send_gifs=False,
            send_games=False,
            send_inline=False
        )
        return True, getattr(chat, 'title', f"ID: {chat.id}")
    except FloodWaitError as e:
        await asyncio.sleep(e.seconds + 1)
        try:
            await client.edit_permissions(chat, target_entity, view_messages=False)
            return True, getattr(chat, 'title', f"ID: {chat.id}")
        except:
            return False, "FloodWait"
    except Exception as e:
        error_msg = str(e).lower()
        if "user not participant" in error_msg or "пользователь не участник" in error_msg:
            return False, "Пользователь не в чате"
        elif "not admin" in error_msg or "не администратор" in error_msg:
            return False, "Нет прав"
        else:
            return False, f"Ошибка"

async def ban_user_async(client, target, admin_chats):
    try:
        me = await client.get_me()
        target_entity = await resolve_username_or_id(client, target)
        
        if not target_entity:
            return 0
        
        success_count = 0
        
        for i, chat in enumerate(admin_chats, 1):
            try:
                success, message = await ban_user_in_chat(client, chat, target_entity, me)
                if success:
                    success_count += 1
                await asyncio.sleep(0.3)
            except Exception as e:
                await asyncio.sleep(0.3)
        
        return success_count
    except Exception as e:
        return 0

async def process_ban_for_session(session_info, target):
    session_name, user_id, me = session_info
    session_path = f"sessions/{session_name}"
    client = TelegramClient(session_path, API_ID, API_HASH)
    
    try:
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return 0
        
        admin_chats = await get_admin_chats_async(client, True)
        
        if not admin_chats:
            await client.disconnect()
            return 0
        
        banned = await ban_user_async(client, target, admin_chats)
        await client.disconnect()
        
        return banned
    except Exception as e:
        try:
            await client.disconnect()
        except:
            pass
        return 0

async def parse_message_link(link):
    try:
        link = link.strip()
        
        if "t.me/c/" in link:
            pattern = r"t\.me/c/(\d+)/(\d+)"
            match = re.search(pattern, link)
            if match:
                chat_id = int(match.group(1))
                message_id = int(match.group(2))
                if chat_id > 0:
                    chat_id = -1000000000000 + chat_id
                return chat_id, message_id, "private"
        
        elif "t.me/+" in link or "t.me/joinchat/" in link:
            pattern = r"t\.me/(?:\+|joinchat/)([a-zA-Z0-9_-]+)"
            match = re.search(pattern, link)
            if match:
                invite_hash = match.group(1)
                message_id = 0
                if "/" in link:
                    try:
                        message_id = int(link.split("/")[-1])
                    except:
                        message_id = 0
                return invite_hash, message_id, "invite"
        
        else:
            pattern = r"t\.me/([a-zA-Z0-9_]+)"
            match = re.search(pattern, link)
            if match:
                username = match.group(1)
                message_id = 0
                if "/" in link:
                    try:
                        message_id = int(link.split("/")[-1])
                    except:
                        message_id = 0
                return username, message_id, "public"
        
        return None, None, None
    except:
        return None, None, None

async def join_chat_for_report(client, chat_input, chat_type):
    try:
        if chat_type == "public":
            if isinstance(chat_input, int):
                chat = await client.get_entity(chat_input)
            else:
                if chat_input.startswith('@'):
                    chat = await client.get_entity(chat_input)
                else:
                    chat = await client.get_entity('@' + chat_input)
            
            try:
                await client(JoinChannelRequest(chat))
                return True, "Успешно присоединился"
            except Exception as e:
                error_msg = str(e).lower()
                if "already" in error_msg or "уже" in error_msg:
                    return True, "Уже в чате"
                else:
                    return False, f"Ошибка вступления: {e}"
        
        elif chat_type == "invite":
            try:
                await client(ImportChatInviteRequest(chat_input))
                return True, "Успешно присоединился"
            except Exception as e:
                error_msg = str(e).lower()
                if "already" in error_msg or "уже" in error_msg:
                    return True, "Уже в чате"
                else:
                    return False, f"Ошибка вступления: {e}"
        
        elif chat_type == "private":
            try:
                chat = await client.get_entity(chat_input)
                await client(JoinChannelRequest(chat))
                return True, "Успешно присоединился"
            except Exception as e:
                error_msg = str(e).lower()
                if "already" in error_msg or "уже" in error_msg:
                    return True, "Уже в чате"
                else:
                    return False, f"Ошибка вступления: {e}"
        
        return False, "Неизвестный тип чата"
    except Exception as e:
        return False, f"Общая ошибка: {e}"

async def report_message(client, chat_input, message_id, chat_type):
    try:
        joined, join_msg = await join_chat_for_report(client, chat_input, chat_type)
        
        if not joined:
            return False, f"Не удалось присоединиться: {join_msg}"
        
        await asyncio.sleep(1)
        
        if isinstance(chat_input, int):
            chat = await client.get_entity(chat_input)
        elif chat_type == "public":
            if chat_input.startswith('@'):
                chat = await client.get_entity(chat_input)
            else:
                chat = await client.get_entity('@' + chat_input)
        else:
            chat = await client.get_entity(chat_input)
        
        if not chat:
            return False, "Не удалось найти чат"
        
        try:
            await client(ReportRequest(
                peer=chat,
                id=[message_id],
                reason=InputReportReasonSpam(),
                message="Спам"
            ))
            return True, "Жалоба отправлена"
        except Exception as e:
            error_msg = str(e).lower()
            if "message not found" in error_msg or "сообщение не найдено" in error_msg:
                try:
                    await client(ReportRequest(
                        peer=chat,
                        id=[message_id],
                        reason=InputReportReasonSpam(),
                        message=""
                    ))
                    return True, "Жалоба отправлена (без текста)"
                except:
                    return False, f"Ошибка отправки жалобы: {e}"
            return False, f"Ошибка отправки жалобы: {e}"
    except Exception as e:
        return False, f"Общая ошибка: {e}"

async def process_report_for_session(session_info, link):
    session_name, user_id, me = session_info
    session_path = f"sessions/{session_name}"
    client = TelegramClient(session_path, API_ID, API_HASH)
    
    try:
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return False, "Сессия не авторизована"
        
        chat_input, message_id, chat_type = await parse_message_link(link)
        if not chat_input or chat_type is None:
            await client.disconnect()
            return False, "Неверная ссылка"
        
        if message_id == 0:
            await client.disconnect()
            return False, "ID сообщения не найден в ссылке"
        
        success, message = await report_message(client, chat_input, message_id, chat_type)
        await client.disconnect()
        return success, message
    except Exception as e:
        try:
            await client.disconnect()
        except:
            pass
        return False, f"Ошибка обработки: {e}"

async def run_ban_async(target, chat_id):
    try:
        session_files = get_session_files()
        if not session_files:
            bot.send_message(chat_id, "❌ Нет сессий! Добавьте сессии в папку sessions/")
            return
        
        bot.send_message(chat_id, f"🔍 Проверяю {len(session_files)} сессий...")
        valid_sessions = await validate_sessions_async(session_files)
        
        if not valid_sessions:
            bot.send_message(chat_id, "❌ Нет активных сессий!")
            return
        
        bot.send_message(chat_id, f"✅ Найдено {len(valid_sessions)} активных сессий. Начинаю блокировку...")
        
        total_banned = 0
        for i, session_info in enumerate(valid_sessions, 1):
            session_name, user_id, me = session_info
            bot.send_message(chat_id, f"⏳ Сессия {i}/{len(valid_sessions)}: @{me.username or me.id}")
            
            banned = await process_ban_for_session(session_info, target)
            total_banned += banned
            
            await asyncio.sleep(1)
        
        bot.send_message(chat_id, f"✅ Бан завершен! Заблокирован в {total_banned} чатах на {len(valid_sessions)} сессиях")
        
    except Exception as e:
        bot.send_message(chat_id, f"❌ Ошибка: {str(e)}")

async def run_report_async(link, chat_id):
    try:
        session_files = get_session_files()
        if not session_files:
            bot.send_message(chat_id, "❌ Нет сессий! Добавьте сессии в папку sessions/")
            return
        
        bot.send_message(chat_id, f"🔍 Проверяю {len(session_files)} сессий...")
        valid_sessions = await validate_sessions_async(session_files)
        
        if not valid_sessions:
            bot.send_message(chat_id, "❌ Нет активных сессий!")
            return
        
        bot.send_message(chat_id, f"✅ Найдено {len(valid_sessions)} активных сессий. Отправляю жалобы...")
        
        success_count = 0
        failed_count = 0
        
        for i, session_info in enumerate(valid_sessions, 1):
            session_name, user_id, me = session_info
            
            try:
                success, message = await process_report_for_session(session_info, link)
                if success:
                    success_count += 1
                    bot.send_message(chat_id, f"✅ Сессия {i}: @{me.username or me.id} - {message}")
                else:
                    failed_count += 1
                    bot.send_message(chat_id, f"❌ Сессия {i}: @{me.username or me.id} - {message}")
            except Exception as e:
                failed_count += 1
                bot.send_message(chat_id, f"❌ Сессия {i}: @{me.username or me.id} - ошибка: {str(e)}")
            
            await asyncio.sleep(3)
        
        bot.send_message(chat_id, f"📊 Итог: Успешно: {success_count}, Не удалось: {failed_count}")
        
    except Exception as e:
        bot.send_message(chat_id, f"❌ Ошибка: {str(e)}")

def run_async_in_thread(target_func, *args):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(target_func(*args))
    except Exception as e:
        print(f"Ошибка в потоке: {e}")
    finally:
        loop.close()

@bot.message_handler(commands=['start'])
def start_message(message):
    user = get_user(message.chat.id)
    
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("⚙️Функционал", callback_data="func"),
    )
    markup.add(
        telebot.types.InlineKeyboardButton("👤Профиль", callback_data="profile"),
        telebot.types.InlineKeyboardButton("💎Подписка", callback_data="sub")
    )
    
    try:
        with open('main.png', 'rb') as photo:
            bot.send_photo(message.chat.id, photo, caption="👻 Привет, добро пожаловать в BlueFreezer!", reply_markup=markup)
    except:
        bot.send_message(message.chat.id, "👻 Привет, добро пожаловать в BlueFreezer!", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "func":
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(
            telebot.types.InlineKeyboardButton("🧊Freeze", callback_data="freeze"))
        
        try:
            bot.edit_message_caption(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                caption="Выберите способ:",
                reply_markup=markup
            )
        except:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="Выберите способ:",
                reply_markup=markup
            )
    
    elif call.data == "profile":
        user = get_user(call.message.chat.id)
        profile_text = f"👤 Ваш профиль\n\n"
        profile_text += f"ID: {call.message.chat.id}\n"
        profile_text += f"Подписка: {user['subscription']}\n"
        profile_text += f"Дата действия: {user['expiry_date']}\n"
        
        try:
            bot.edit_message_caption(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                caption=profile_text
            )
        except:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=profile_text
            )
    
    elif call.data == "sub":
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("Неделя - 1$", callback_data="sub_week"))
        markup.add(telebot.types.InlineKeyboardButton("Месяц - 5$", callback_data="sub_month"))
        markup.add(telebot.types.InlineKeyboardButton("Год - 10$", callback_data="sub_year"))
        markup.add(telebot.types.InlineKeyboardButton("Навсегда - 15$", callback_data="sub_forever"))
        markup.add(telebot.types.InlineKeyboardButton("Назад", callback_data="back"))
        
        try:
            bot.edit_message_caption(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                caption="Выберите подписку:",
                reply_markup=markup
            )
        except:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="Выберите подписку:",
                reply_markup=markup
            )
    
    elif call.data == "back":
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(
            telebot.types.InlineKeyboardButton("⚙️Функционал", callback_data="func"),
        )
        markup.add(
            telebot.types.InlineKeyboardButton("👤Профиль", callback_data="profile"),
            telebot.types.InlineKeyboardButton("💎Подписка", callback_data="sub")
        )
        
        try:
            bot.edit_message_caption(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                caption="👻 Главное меню",
                reply_markup=markup
            )
        except:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="👻 Главное меню",
                reply_markup=markup
            )
    
    elif call.data.startswith("sub_"):
        prices = {
            "sub_week": 1,
            "sub_month": 5,
            "sub_year": 10,
            "sub_forever": 15
        }
        periods = {
            "sub_week": "Неделя",
            "sub_month": "Месяц",
            "sub_year": "Год",
            "sub_forever": "Навсегда"
        }
        
        amount = prices[call.data]
        period = periods[call.data]
        
        invoice = create_invoice(amount, f"Подписка {period}")
        
        if invoice and invoice.get("ok"):
            markup = telebot.types.InlineKeyboardMarkup()
            markup.add(telebot.types.InlineKeyboardButton("Оплатить", url=invoice["result"]["pay_url"]))
            markup.add(telebot.types.InlineKeyboardButton("Проверить оплату", callback_data=f"check_{invoice['result']['invoice_id']}_{period}_{call.message.chat.id}"))
            
            bot.send_message(call.message.chat.id, f"Счет на {amount}$ создан\n\nОплатите по ссылке ниже:", reply_markup=markup)
        else:
            bot.send_message(call.message.chat.id, "Ошибка создания счета")
    
    elif call.data.startswith("check_"):
        parts = call.data.split("_")
        invoice_id = parts[1]
        period = parts[2]
        user_id = parts[3]
        
        url = f"https://pay.crypt.bot/api/getInvoices?invoice_ids={invoice_id}"
        headers = {"Crypto-Pay-API-Token": cryptobot_token}
        
        try:
            response = requests.get(url, headers=headers)
            data = response.json()
            
            if data.get("ok") and data["result"]["items"][0]["status"] == "paid":
                user = get_user(user_id)
                
                if period == "Неделя":
                    expiry = "7 дней"
                elif period == "Месяц":
                    expiry = "30 дней"
                elif period == "Год":
                    expiry = "365 дней"
                else:
                    expiry = "Бессрочно"
                
                user['subscription'] = period
                user['expiry_date'] = expiry
                update_user(user_id, user)
                
                bot.send_message(user_id, f"Оплата подтверждена! Подписка {period} активирована.")
                bot.delete_message(call.message.chat.id, call.message.message_id)
            else:
                bot.answer_callback_query(call.id, "Оплата еще не поступила")
        except:
            bot.answer_callback_query(call.id, "Ошибка проверки")
    
    elif call.data == "freeze":
        msg = bot.send_message(call.message.chat.id, "Введите @username человека для блокировки:")
        bot.register_next_step_handler(msg, freeze)
    
    elif call.data == "report":
        report_msg = bot.send_message(call.message.chat.id, "Пришлите ссылку на сообщение для жалобы (например: https://t.me/username/123):")
        bot.register_next_step_handler(report_msg, reports)

def freeze(message):
    username = message.text.strip()
    if not username:
        bot.send_message(message.chat.id, "❌ Username не может быть пустым")
        return
    
    bot.send_message(message.chat.id, "⏳ Начинаю блокировку...")
    
    thread = threading.Thread(target=run_async_in_thread, args=(run_ban_async, username, message.chat.id))
    thread.start()

def reports(message):
    link = message.text.strip()
    if not link.startswith('https://t.me/'):
        bot.send_message(message.chat.id, "❌ Неверная ссылка! Примеры:\n• https://t.me/username/123\n• https://t.me/c/1234567890/123\n• https://t.me/+invitehash/123")
        report_msg = bot.send_message(message.chat.id, "Пришлите ссылку на сообщение для жалобы:")
        bot.register_next_step_handler(report_msg, reports)
    else:
        bot.send_message(message.chat.id, "⏳ Отправляю жалобы...")
        
        thread = threading.Thread(target=run_async_in_thread, args=(run_report_async, link, message.chat.id))
        thread.start()

if __name__ == "__main__":
    print("Бот запущен")
    bot.infinity_polling(none_stop=True)