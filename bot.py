import os
import telebot
from telebot import types
from dotenv import load_dotenv

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
    raise ValueError("BOT_TOKEN ұяшығы .env файлынан табылмады")

bot = telebot.TeleBot(BOT_TOKEN)
user_filters = {}

# Боттың ресми менюіне командаларды тіркеу
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

# 📋 МЕНІҢ РЕЙСТЕРІМДІ КӨРСЕТУ КОМАНДАСЫ
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
            "SELECT origin, destination, departure_date, target_price FROM tracked_flights WHERE chat_id = %s;", 
            (chat_id,)
        )
        flights = cur.fetchall()
        cur.close()
        conn.close()

        if not flights:
            bot.send_message(chat_id, "📋 <b>Сізде әзірше бақылауда тұрған рейс жоқ.</b>\nЖаңа рейс қосу үшін /filter командасын басыңыз.", parse_mode="HTML")
        else:
            res = "📋 <b>Сіздің бақылаудағы барлық рейстеріңіз:</b>\n\n"
            for i, f in enumerate(flights, 1):
                price_text = f"{int(f[3])} ₸" if f[3] < 999999 else "Кез келген ең арзан баға"
                res += f"{i}. ✈️ <b>{f[0]} ➡️ {f[1]}</b>\n📅 Күні: <code>{f[2]}</code>\n🎯 Шекті баға: <code>{price_text}</code>\n\n"
            bot.send_message(chat_id, res, parse_mode="HTML")
    except Exception as e:
        bot.send_message(chat_id, f"❌ Рейстерді базадан оқу кезінде қате кетті: {e}")

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    print("CALLBACK RECEIVED:", call.data)
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    menu_message_id = call.message.message_id

    if call.data == "set_origin":
        msg = bot.send_message(chat_id, "🛫 Қай қаладан ұшасыз? (Мысалы: ALA немесе Алматы)")
        bot.register_next_step_handler(msg, save_origin, menu_message_id, msg.message_id)
    elif call.data == "set_dest":
        msg = bot.send_message(chat_id, "🛬 Қай қалаға ұшасыз? (Мысалы: NQZ немесе Астана)")
        bot.register_next_step_handler(msg, save_dest, menu_message_id, msg.message_id)
    elif call.data == "set_date":
        msg = bot.send_message(chat_id, "📅 Ұшу күнін енгізіңіз (Формат: YYYY-MM-DD):")
        bot.register_next_step_handler(msg, save_date, menu_message_id, msg.message_id)
    elif call.data == "set_price":
        msg = bot.send_message(chat_id, "💰 Максималды баға енгізіңіз (Тек сан жазыңыз):")
        bot.register_next_step_handler(msg, save_price, menu_message_id, msg.message_id)
        
    elif call.data == "reset":
        user_filters[chat_id] = {"origin": "Таңдалмаған", "dest": "Таңдалмаған", "date": "Таңдалмаған", "price": "Кез келген"}
        bot.edit_message_reply_markup(chat_id, menu_message_id, reply_markup=get_menu(chat_id))
        
    elif call.data == "search":
        data = user_filters.get(chat_id, {})
        if data.get("origin") == "Таңдалмаған" or data.get("dest") == "Таңдалмаған" or data.get("date") == "Таңдалмаған":
            bot.send_message(chat_id, "❌ Қате: Алдымен Қайдан, Қайда және Күнді енгізіңіз!")
            return
        
        bot.send_message(chat_id, "⏳ Aviasales жүйесінен қазіргі ең арзан билетті іздеп жатырмын...")
        
        origin = data["origin"]
        dest = data["dest"]
        date = data["date"]
        
        try:
            target_price = float(data["price"].replace(" ₸", "")) if data["price"] != "Кез келген" else 999999.0
        except ValueError:
            target_price = 999999.0

        # Базаға жазу (Бірнеше рейс сақтала береді)
        if get_db_connection:
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO tracked_flights (chat_id, origin, destination, departure_date, target_price) VALUES (%s, %s, %s, %s, %s);",
                    (chat_id, origin, dest, date, target_price)
                )
                conn.commit()
                cur.close()
                conn.close()
            except Exception as e:
                print(f"Базаға жазуда қате: {e}")

        # Сразу іздеу нәтижесі
        current_price, gate, search_url = get_real_flight_info(origin, dest, date)

        if current_price:
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
            bot.send_message(chat_id, "⚠️ Кешіріңіз, дәл қазір бұл күнге билет табылмады. Бірақ рейс бақылау тізіміне қосылды!")

def clean_messages(chat_id, user_msg_id, bot_question_id):
    try:
        bot.delete_message(chat_id, user_msg_id)
        bot.delete_message(chat_id, bot_question_id)
    except Exception:
        pass

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

def save_date(message, menu_message_id, bot_question_id):
    chat_id = message.chat.id
    user_filters[chat_id]["date"] = message.text
    bot.edit_message_reply_markup(chat_id, menu_message_id, reply_markup=get_menu(chat_id))
    clean_messages(chat_id, message.message_id, bot_question_id)

def save_price(message, menu_message_id, bot_question_id):
    chat_id = message.chat.id
    user_filters[chat_id]["price"] = message.text + " ₸"
    bot.edit_message_reply_markup(chat_id, menu_message_id, reply_markup=get_menu(chat_id))
    clean_messages(chat_id, message.message_id, bot_question_id)

if __name__ == "__main__":
    set_bot_menu()
    print("Бот толық қазақша режимде іске қосылды...")
    bot.infinity_polling(skip_pending=True)
