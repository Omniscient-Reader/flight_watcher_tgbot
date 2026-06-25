import os
import telebot
from telebot import types
from database import get_db_connection
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

# Қала атауларын ИАТА кодтарына айналдыру сөздігі
CITY_CODES = {
    "ALMATY": "ALA", "АЛМАТЫ": "ALA", "ALM": "ALA", "АЛМ": "ALA", "ALA": "ALA",
    "ASTANA": "NQZ", "АСТАНА": "NQZ", "AST": "NQZ", "АСT": "NQZ", "NQZ": "NQZ",
    "SHYMKENT": "CIT", "ШЫМКЕНТ": "CIT", "SHYM": "CIT", "ШЫМ": "CIT", "CIT": "CIT",
    "AKTAU": "SCO", "АҚТАУ": "SCO", "SCO": "SCO",
    "ATYRAU": "GUW", "АТЫРАУ": "GUW", "GUW": "GUW",
    "AKTOBE": "AKX", "АҚТӨБЕ": "AKX", "AKX": "AKX",
    "KARAGANDA": "KGF", "ҚАРАҒАНДЫ": "KGF", "KGF": "KGF",
    "TARAZ": "DMB", "ТАРАЗ": "DMB", "DMB": "DMB",
    "UST-KAMENOGORSK": "UKK", "ӨСКЕМЕН": "UKK", "UKK": "UKK",
    "SEMEY": "PLX", "СЕМЕЙ": "PLX", "PLX": "PLX",
    "URALSK": "URA", "ОРАЛ": "URA", "URA": "URA",
    "KOSTANAY": "KSN", "ҚОСТАНАЙ": "KSN", "KSN": "KSN",
    "KYZYLORDA": "KZO", "ҚЫЗЫЛОРДА": "KZO", "KZO": "KZO",
    "PAVLODAR": "PWQ", "ПАВЛОДАР": "PWQ", "PWQ": "PWQ",
    "PETROPAVLOVSK": "PPK", "ПЕТРОПАВЛ": "PPK", "PPK": "PPK"
}

def get_city_code(text):
    cleaned = text.strip().upper()
    if cleaned in CITY_CODES:
        return CITY_CODES[cleaned]
    return cleaned[:3]

def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_add = types.KeyboardButton("➕ Жаңа рейс қосу")
    btn_list = types.KeyboardButton("📋 Менің рейстерім")
    btn_del = types.KeyboardButton("❌ Рейсті өшіру")
    markup.add(btn_add, btn_list)
    markup.add(btn_del)
    return markup

def get_cancel_menu():
    """Тоқтату (Аборт) батырмасы"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton("❌ Тоқтату"))
    return markup

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        f"Сәлем, {message.from_user.first_name}! 👋\n"
        f"Төмендегі мәзірді қолданып, рейстеріңізді басқара аласыз 👇"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=get_main_menu())

# 1. 📋 МЕНІҢ РЕЙСТЕРІМДІ КӨРСЕТУ
@bot.message_handler(func=lambda message: message.text == "📋 Менің рейстерім")
def list_flights(message):
    chat_id = message.chat.id
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT origin, destination, departure_date, target_price FROM tracked_flights WHERE chat_id = %s;", (chat_id,))
    flights = cur.fetchall()
    cur.close()
    conn.close()

    if not flights:
        bot.send_message(chat_id, "Сізде әзірше бақылауда тұрған рейс жоқ.")
    else:
        res = "📋 <b>Сіздің бақылаудағы рейстеріңіз:</b>\n\n"
        for f in flights:
            price_text = f"{int(f[3])} ₸" if f[3] < 999999 else "Кез келген ең арзан баға"
            res += f"✈️ {f[0]} ➡️ {f[1]}\n📅 Күні: {f[2]}\n🎯 Баға: {price_text}\n\n"
        bot.send_message(chat_id, res, parse_mode="HTML")

# 2. ➕ ЖАҢА РЕЙС ҚОСУ СЕРИЯСЫ
@bot.message_handler(func=lambda message: message.text == "➕ Жаңа рейс қосу")
def start_add_flight(message):
    msg = bot.send_message(message.chat.id, "🛫 <b>Қай қаладан ұшасыз?</b> (Мысалы: Алматы немесе ALA):", parse_mode="HTML", reply_markup=get_cancel_menu())
    bot.register_next_step_handler(msg, process_origin_step)

def process_origin_step(message):
    chat_id = message.chat.id
    text = message.text.strip()
    
    if text == "❌ Тоқтату":
        bot.send_message(chat_id, "Деректерді енгізу тоқтатылды 🛑", reply_markup=get_main_menu())
        return

    if len(text) < 3:
        msg = bot.send_message(chat_id, "❌ Қала аты немесе коды тым қысқа! Қайта жазыңыз:", parse_mode="HTML", reply_markup=get_cancel_menu())
        bot.register_next_step_handler(msg, process_origin_step)
        return

    origin = get_city_code(text)
    msg = bot.send_message(chat_id, "🛬 <b>Қай қалаға ұшасыз?</b> (Мысалы: Астана немесе NQZ):", parse_mode="HTML", reply_markup=get_cancel_menu())
    bot.register_next_step_handler(msg, process_destination_step, origin)

def process_destination_step(message, origin):
    chat_id = message.chat.id
    text = message.text.strip()
    
    if text == "❌ Тоқтату":
        bot.send_message(chat_id, "Деректерді енгізу тоқтатылды 🛑", reply_markup=get_main_menu())
        return

    if len(text) < 3:
        msg = bot.send_message(chat_id, "❌ Қала аты немесе коды тым қысқа! Қайта жазыңыз:", parse_mode="HTML", reply_markup=get_cancel_menu())
        bot.register_next_step_handler(msg, process_destination_step, origin)
        return

    destination = get_city_code(text)
    msg = bot.send_message(chat_id, "📅 <b>Ұшу күнін жазыңыз</b> (Мысалы: 2026-09-15):", parse_mode="HTML", reply_markup=get_cancel_menu())
    bot.register_next_step_handler(msg, process_date_step, origin, destination)

def process_date_step(message, origin, destination):
    chat_id = message.chat.id
    date_text = message.text.strip()
    
    if date_text == "❌ Тоқтату":
        bot.send_message(chat_id, "Деректерді енгізу тоқтатылды 🛑", reply_markup=get_main_menu())
        return

    try:
        datetime.strptime(date_text, "%Y-%m-%d")
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add(types.KeyboardButton("🤷‍♂️ Маған бәрібір (Кез келген баға)"))
        markup.add(types.KeyboardButton("❌ Тоқтату"))
        
        msg = bot.send_message(
            chat_id, 
            "💰 <b>Қандай бағадан төмен болса ескертейін?</b>\n(Бағаны теңгемен (тг) жазыңыз немесе мәзірдегі батырманы басыңыз):", 
            parse_mode="HTML", 
            reply_markup=markup
        )
        bot.register_next_step_handler(msg, process_price_step, origin, destination, date_text)
    except ValueError:
        msg = bot.send_message(chat_id, "❌ Қате формат! Күнді <code>2026-09-15</code> үлгісінде қайта жазыңыз:", parse_mode="HTML", reply_markup=get_cancel_menu())
        bot.register_next_step_handler(msg, process_date_step, origin, destination)

def process_price_step(message, origin, destination, departure_date):
    chat_id = message.chat.id
    text = message.text.strip()
    
    if text == "❌ Тоқтату":
        bot.send_message(chat_id, "Деректерді енгізу тоқтатылды 🛑", reply_markup=get_main_menu())
        return

    if text == "🤷‍♂️ Маған бәрібір (Кез келген баға)":
        target_price = 999999
    else:
        try:
            target_price = float(text)
        except ValueError:
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            markup.add(types.KeyboardButton("🤷‍♂️ Маған бәрібір (Кез келген баға)"))
            markup.add(types.KeyboardButton("❌ Тоқтату"))
            msg = bot.send_message(chat_id, "❌ Тек санмен (тг) жазыңыз немесе мәзірдегі батырманы басыңыз:", reply_markup=markup)
            bot.register_next_step_handler(msg, process_price_step, origin, destination, departure_date)
            return

    save_flight_to_db(chat_id, origin, destination, departure_date, target_price)

# 3. ❌ РЕЙСТЕРДІ ӨШІРУ МЕНЮІ
@bot.message_handler(func=lambda message: message.text == "❌ Рейсті өшіру")
def delete_flights_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton("🗑 Барлық рейстерді өшіру"), types.KeyboardButton("⬅️ Артқа"))
    
    msg = bot.send_message(
        message.chat.id, 
        "📋 Рейстерді өшіру мәзіріне қош келдіңіз.\nТөмендегі мәзірден керекті әрекетті таңдаңыз 👇",
        reply_markup=markup
    )
    bot.register_next_step_handler(msg, process_delete_step)

def process_delete_step(message):
    text = message.text.strip()
    chat_id = message.chat.id
    
    if text == "🗑 Барлық рейстерді өшіру":
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM tracked_flights WHERE chat_id = %s;", (chat_id,))
        conn.commit()
        cur.close()
        conn.close()
        bot.send_message(chat_id, "💥 Барлық рейстеріңіз базадан толықтай өшірілді!", reply_markup=get_main_menu())
    else:
        bot.send_message(chat_id, "Бас мәзірге қайтыңыз 👇", reply_markup=get_main_menu())

def save_flight_to_db(chat_id, origin, destination, departure_date, target_price):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO tracked_flights (chat_id, origin, destination, departure_date, target_price) VALUES (%s, %s, %s, %s, %s);",
            (chat_id, origin, destination, departure_date, target_price)
        )
        conn.commit()
        cur.close()
        conn.close()

        price_show = f"{int(target_price)} ₸" if target_price < 999999 else "Кез келген ең арзан баға"
        success_text = (
            f"✅ <b>Рейс сәтті бақылауға алынды!</b>\n\n"
            f"🛫 Қайдан: {origin}\n"
            f"🛬 Қайда: {destination}\n"
            f"📅 Күні: {departure_date}\n"
            f"🎯 Күткен баға: {price_show}\n"
        )
        bot.send_message(chat_id, success_text, parse_mode="HTML", reply_markup=get_main_menu())
    except Exception as e:
        bot.send_message(chat_id, "❌ Базаға сақтау кезінде қате кетті.")

if __name__ == "__main__":
    bot.infinity_polling()
