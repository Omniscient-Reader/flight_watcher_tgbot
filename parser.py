import schedule
import os
import time
import requests
from database import get_db_connection
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
AVIASALES_TOKEN = os.getenv("AVIASALES_TOKEN")

def send_telegram_message_with_link(chat_id, text, link_url):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    reply_markup = {
        "inline_keyboard": [[
            {"text": "🎫 Билетті көру және Сатып алу", "url": link_url}
        ]]
    }
    
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": reply_markup
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Хабарлама жіберуде қате: {e}")

def get_last_checked_price(flight_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT current_price FROM flight_price_history WHERE flight_id = %s ORDER BY checked_at DESC LIMIT 1;",
        (flight_id,)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return float(row[0]) if row else None

def get_real_flight_info(origin, destination, departure_date):
    try:
        url = "https://api.travelpayouts.com/v2/prices/latest"
        date_str = departure_date.strftime("%Y-%m-%d") if hasattr(departure_date, "strftime") else str(departure_date)
        
        params = {
            "origin": origin.upper(),
            "destination": destination.upper(),
            "beginning_of_period": date_str,
            "period_type": "day",
            "one_way": "true",
            "currency": "kzt",
            "token": AVIASALES_TOKEN
        }
        
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
        response = requests.get(url, params=params, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            if data and data.get("success") and data.get("data"):
                prices_list = data["data"]
                if prices_list:
                    ticket = prices_list[0]
                    price = int(ticket["value"])
                    gate = ticket.get("gate", "Авиакомпания сайты")
                    
                    parts = date_str.split("-")
                    day = parts[2]
                    month = parts[1]
                    search_url = f"https://www.aviasales.kz/search/{origin.upper()}{day}{month}{destination.upper()}1"
                    
                    return price, gate, search_url
        return None, None, None
    except Exception as e:
        print(f"Aviasales API-мен байланыс үзілді: {e}")
        return None, None, None

def check_prices():
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("SELECT id, chat_id, origin, destination, departure_date, target_price FROM tracked_flights;")
        flights = cur.fetchall()
        
        if not flights:
            print("Бақылауда рейс жоқ...")
            return

        print("\n--- ТЕКСЕРУ БАСТАЛДЫ ---")
        
        for flight in flights:
            flight_id, chat_id, origin, destination, departure_date, target_price = flight
            
            current_price, gate, search_url = get_real_flight_info(origin, destination, departure_date)
            
            if current_price is None:
                print(f"Рейс {origin}->{destination}: Билет табылмады.")
                continue
                
            last_price = get_last_checked_price(flight_id)
            print(f"Рейс {origin}->{destination}: Баға: {current_price} ₸ | Қайда: {gate}")
            
            if current_price <= target_price:
                if last_price is None or current_price < last_price:
                    # Дәл осы жерде мәтінді әдемілеп, пайдаланушыға түсінікті қылдық!
                    message_text = (
                        f"✈️ <b>БИЛЕТ БАҒАСЫ ТӨМЕНДЕДІ!</b> ✈️\n\n"
                        f"📌 <b>Бағыт:</b> {origin.upper()} ➡️ {destination.upper()}\n"
                        f"📅 <b>Күні:</b> {departure_date}\n\n"
                        f"📉 <b>Қазіргі ең арзан баға:</b> <code>{current_price} ₸</code>\n"
                        f"🛒 <b>Қай жерде сатылуда:</b> <b>{gate}</b>\n\n"
                        f"🎯 <i>Сенің күткен бағаң: {target_price} ₸ еді.</i>\n\n"
                        f"Төмендегі батырманы басып, бірден сатып алсаң болады 👇"
                    )
                    send_telegram_message_with_link(chat_id, message_text, search_url)
                    print("--> Пайдаланушыға толық ақпарат жіберілді!")
            
            cur.execute(
                "INSERT INTO flight_price_history (flight_id, current_price) VALUES (%s, %s);",
                (flight_id, current_price)
            )
                
        conn.commit()
    except Exception as e:
        print(f"Парсерде қате: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    print("Ресми парсер автоматты жоспарлау режимінде іске қосылды...")
    
    # Тексеруді дәл сен айтқан уақыттарға қоямыз
    schedule.every().day.at("08:00").do(check_prices)
    schedule.every().day.at("20:00").do(check_prices)
    
    # Тексеру жұмыс істеп тұрғанын білу үшін, бірінші рет қосқанда бір рет тексеріп алады
    check_prices()

    while True:
        schedule.run_pending()
        time.sleep(1) # Жүйені шамадан тыс жүктемес үшін 1 секунд күтіп отырады
