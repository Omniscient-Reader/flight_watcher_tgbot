import os
import telebot
from telebot import types
from dotenv import load_dotenv
from datetime import datetime

# Деректер базасы мен парсерді қосу
try:
    from database import get_db_connection
except ImportError:
    get_db_connection = None

try:
    from parser import get_real_flight_info
except ImportError:
    def get_real_flight_info(origin, dest, date):
        return 42500, "FlyArystan", f"https://www.aviasales.kz/search/{origin}{date[5:7]}{date[8:10]}{dest}1"

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN ұяшығы .env файлынан табылдамады")

bot = telebot.TeleBot(BOT_TOKEN)

active_questions = {}
user_filters = {}

def set_bot_menu():
    commands = [
        types.BotCommand("filter", "🌪 Іздеу сүзгісі (Фильтр)"),
        types.BotCommand("collections", "📋 Менің рейстерім")
    ]
    bot.set_my_commands(commands)

def get_menu(chat_id):
    if chat_id not in user_filters:
        user_filters[chat_id] = {
            "origin": "Таңдалмаған",
            "dest": "Таңдалмаған",
            "date": "Таңдалмаған",
            "price": "Кез келген"
        }
    data = user_filters[chat_id]
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(f"🛫 Қайдан: {data['origin']}", callback_data="set_origin"),
        types.InlineKeyboardButton(f"🛬 Қайда: {data['dest']}", callback_data="set_dest")
    )
    markup.add(
        types.InlineKeyboardButton(f"📅 Күні: {data['date']}", callback_data="set_date"),
        types.InlineKeyboardButton(f"💰 Баға: {data['price']}", callback_data="set_price")
    )
    markup.add(types.InlineKeyboardButton("🔄 Тазалау", callback_data="reset"))
    markup.add(types.InlineKeyboardButton("🔍 Іздеу (Қазір табу)", callback_data="search"))
    return markup

@bot.message_handler(commands=["start", "filter"])
def start(message):
    bot.send_message(
        message.chat.id,
        "🌪 <b>Авиарейстерді іздеу сүзгісі:</b>\nКеректі бағыт пен күнді таңдаңыз 👇",
        parse_mode="HTML",
        reply_markup=get_menu(message.chat.id)
    )

@bot.message_handler(commands=["collections"])
def list_collections(message):
    chat_id = message.chat.id
    if not get_db_connection:
        bot.send_message(chat_id, "⚠️ Деректер базасына қосылу модулі (database.py) табылмады.")
        return

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, origin, destination, departure_date, target_price FROM tracked_flights WHERE chat_id = %s;", 
            (chat_id,)
        )
        flights = cur.fetchall()
        cur.close()
        conn.close()

        if not flights:
            bot.send_message(chat_id, "📋 <b>Сізде әзірше бақылауда тұрған рейс жоқ.</b>\nЖаңа рейс қосу үшін /filter командасын басыңыз.", parse_mode="HTML")
        else:
            bot.send_message(chat_id, "📋 <b>Сіздің бақылаудағы рейстеріңіз:</b>\n<i>Өшіргіңіз келген рейстің астындағы батырманы басыңыз:</i>", parse_mode="HTML")
            
            for f in flights:
                flight_id, origin, dest, date, price = f
                price_text = f"{int(price)} ₸" if price < 999999 else "Кез келген ең арзан баға"
                text = f"✈️ <b>{origin} ➡️ {dest}</b>\n📅 Күні: <code>{date}</code>\n🎯 Шекті баға: <code>{price_text}</code>"
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton(f"❌ Осы рейсті өшіру", callback_data=f"del_{flight_id}"))
                bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
                
    except Exception as e:
        bot.send_message(chat_id, f"❌ Рейстерді базадан оқу кезінде қате кетті: {e}")

def reset_next_step_safely(chat_id):
    bot.clear_step_handler_by_chat_id(chat_id=chat_id)
    if chat_id in active_questions:
        try:
            bot.delete_message(chat_id, active_questions[chat_id])
        except Exception:
            pass

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    print("CALLBACK RECEIVED:", call.data)
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    menu_message_id = call.message.message_id

    if call.data.startswith("del_"):
        flight_id = int(call.data.split("_")[1])
        if get_db_connection:
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("DELETE FROM tracked_flights WHERE id = %s AND chat_id = %s;", (flight_id, chat_id))
                conn.commit()
                cur.close()
                conn.close()
                bot.delete_message(chat_id, menu_message_id)
                bot.send_message(chat_id, "🗑 Рейс бақылау тізімінен сәтті өшірілді!")
            except Exception as e:
                bot.send_message(chat_id, f"❌ Өшіру кезінде қате кетті: {e}")
        return

    if call.data == "set_origin":
        reset_next_step_safely(chat_id)
        msg = bot.send_message(chat_id, "🛫 Қай қаладан ұшасыз? (Мысалы: ALA немесе Алматы)")
        active_questions[chat_id] = msg.message_id
        bot.register_next_step_handler(msg, save_origin, menu_message_id, msg.message_id)

    elif call.data == "set_dest":
        reset_next_step_safely(chat_id)
        msg = bot.send_message(chat_id, "🛬 Қай қалаға ұшасыз? (Мысалы: NQZ немесе Астана)")
        active_questions[chat_id] = msg.message_id
        bot.register_next_step_handler(msg, save_dest, menu_message_id, msg.message_id)

    elif call.data == "set_date":
        reset_next_step_safely(chat_id)
        msg = bot.send_message(chat_id, "📅 Ұшу күнін енгізіңіз (Формат: YYYY-MM-DD):")
        active_questions[chat_id] = msg.message_id
        bot.register_next_step_handler(msg, save_date, menu_message_id, msg.message_id)

    elif call.data == "set_price":
        reset_next_step_safely(chat_id)
        msg = bot.send_message(chat_id, "💰 Максималды баға енгізіңіз (Тек сан жазыңыз):")
        active_questions[chat_id] = msg.message_id
        bot.register_next_step_handler(msg, save_price, menu_message_id, msg.message_id)
        
    elif call.data == "reset":
        reset_next_step_safely(chat_id)
        user_filters[chat_id] = {"origin": "Таңдалмаған", "dest": "Таңдалмаған", "date": "Таңдалмаған", "price": "Кез келген"}
        bot.edit_message_reply_markup(chat_id, menu_message_id, reply_markup=get_menu(chat_id))
        
    elif call.data == "search":
        reset_next_step_safely(chat_id)
        data = user_filters.get(chat_id, {})
        if data.get("origin") == "Таңдалмаған" or data.get("dest") == "Таңдалмаған" or data.get("date") == "Таңдалмаған":
            bot.send_message(chat_id, "❌ Қате: Алдымен Қайдан, Қайда және Күнді енгізіңіз!")
            return
        
        bot.send_message(chat_id, "⏳ Aviasales жүйесінен қазіргі ең арзан билетті іздеп жатырмын...")
        
        origin = data["origin"]
        dest = data["dest"]
        date = data["date"]
        
        try:
            raw_price = data["price"].replace(" ₸", "").strip()
            target_price = float(raw_price) if raw_price != "Кез келген" else 999999.0
        except ValueError:
            target_price = 999999.0

        if get_db_connection:
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                
                # 2. ДУБЛИКАТТАН ҚОРҒАУ (Сен берген логика)
                cur.execute(
                    """
                    SELECT id FROM tracked_flights 
                    WHERE chat_id=%s AND origin=%s AND destination=%s AND departure_date=%s
                    """,
                    (chat_id, origin, dest, date)
                )
                existing = cur.fetchone()

                if existing:
                    bot.send_message(chat_id, "⚠️ Бұл рейс бақылауда тұр.")
                    cur.close()
                    conn.close()
                    return

                # Егер дубликат болмаса, базаға жазамыз
                cur.execute(
                    """
                    INSERT INTO tracked_flights (chat_id, origin, destination, departure_date, target_price) 
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (chat_id, origin, dest, date, target_price)
                )
                conn.commit()
                cur.close()
                conn.close()
            except Exception as e:
                print(f"Базамен жұмыста қате: {e}")

        current_price, gate, search_url = get_real_flight_info(origin, dest, date)

        if current_price:
            if current_price <= target_price or target_price == 999999.0:
                result_text = f"✈️ <b>Ең арзан билет табылды!</b>\n\n" \
                              f"🛫 Бағыт: {origin} ➡️ {dest}\n" \
                              f"📅 Күні: {date}\n" \
                              f"💵 Қазіргі бағасы: <code>{current_price} ₸</code>\n" \
                              f"🛒 Сатушы: {gate}\n\n" \
                              f"📌 <i>Рейс бақылауға алынды! Баға сағат 08:00 мен 20:00-де автоматты түрде тексеріліп тұрады. Барлық рейстерді көру үшін: /collections</i>"
                
                inline_btn = types.InlineKeyboardMarkup()
                inline_btn.add(types.InlineKeyboardButton(text="🎫 Билетті көру және алу", url=search_url))
                bot.send_message(chat_id, result_text, parse_mode="HTML", reply_markup=inline_btn)
            else:
                user_price_text = f"{int(target_price)} ₸"
                not_match_text = f"📌 <b>Рейс бақылауға қосылды!</b>\n\n" \
                                 f"🛫 Бағыт: {origin} ➡️ {dest}\n" \
                                 f"📅 Күні: {date}\n" \
                                 f"🎯 Сіз күткен баға: <code>{user_price_text}</code>\n" \
                                 f"💵 Қазіргі ең арзан баға: <code>{current_price} ₸</code> ({gate})\n\n" \
                                 f"⚠️ <i>Қазіргі баға сіз орнатқан шектен жоғары. Билет бағасы {user_price_text}-ге немесе одан да төмен түскен кезде бот сізге автоматты түрде хабарлама жібереді!</i>"
                bot.send_message(chat_id, not_match_text, parse_mode="HTML")
        else:
            bot.send_message(chat_id, "⚠️ Кешіріңіз, дәл қазір бұл күнге билет табылмады. Бірақ рейс бақылау тізіміне қосылды!")

def clean_messages(chat_id, user_msg_id, bot_question_id):
    try:
        bot.delete_message(chat_id, user_msg_id)
        bot.delete_message(chat_id, bot_question_id)
    except Exception:
        pass
    if chat_id in active_questions:
        active_questions.pop(chat_id, None)

def save_origin(message, menu_message_id, bot_question_id):
    chat_id = message.chat.id
    user_filters[chat_id]["origin"] = message.text.upper()
    bot.edit_message_reply_markup(chat_id, menu_message_id, reply_markup=get_menu(chat_id))
    clean_messages(chat_id, message.message_id, bot_question_id)

def save_dest(message, menu_message_id, bot_question_id):
    chat_id = message.chat.id
    user_filters[chat_id]["dest"] = message.text.upper()
    bot.edit_message_reply_markup(chat_id, menu_message_id, reply_markup=get_menu(chat_id))
    clean_messages(chat_id, message.message_id, bot_question_id)

# 1. КҮН ФОРМАТЫН ТЕКСЕРУ (Сен берген логика түзетілді)
def save_date(message, menu_message_id, bot_question_id):
    chat_id = message.chat.id

    try:
        datetime.strptime(message.text, "%Y-%m-%d")
    except ValueError:
        # Пайдаланушы қате жазса, ескі хабарламаларды тазалап, қайта дұрыс сұраймыз
        clean_messages(chat_id, message.message_id, bot_question_id)
        msg = bot.send_message(
            chat_id,
            "❌ Күн форматы қате! Формат YYYY-MM-DD болуы керек.\nМысалы: 2026-09-15\n\n📅 Қайтадан енгізіңіз:"
        )
        active_questions[chat_id] = msg.message_id
        bot.register_next_step_handler(msg, save_date, menu_message_id, msg.message_id)
        return

    user_filters[chat_id]["date"] = message.text

    try:
        bot.edit_message_reply_markup(
            chat_id,
            menu_message_id,
            reply_markup=get_menu(chat_id) # Осы жердегі функция аты жөнделді
        )
    except:
        pass

    clean_messages(chat_id, message.message_id, bot_question_id)

def save_price(message, menu_message_id, bot_question_id):
    chat_id = message.chat.id
    user_filters[chat_id]["price"] = message.text + " ₸"
    bot.edit_message_reply_markup(chat_id, menu_message_id, reply_markup=get_menu(chat_id))
    clean_messages(chat_id, message.message_id, bot_question_id)

if __name__ == "__main__":
    set_bot_menu()
    print("Бот жаңа қорғаныс функцияларымен іске қосылды...")
    bot.infinity_polling(skip_pending=True)
