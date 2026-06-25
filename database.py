import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    """Базаға қосылу функциясы"""
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "flight_tracker"),
        user=os.getenv("DB_USER", "birzhanmeyrkhan"),  # Сенің Mac-тағы атың
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )

def add_flight_track(chat_id, origin, destination, departure_date, target_price):
    """Пайдаланушы іздеген рейсті базаға сақтау"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO tracked_flights (chat_id, origin, destination, departure_date, target_price)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (chat_id, origin.upper(), destination.upper(), departure_date, target_price)
        )
        flight_id = cur.fetchone()[0]
        conn.commit()
        return flight_id
    except Exception as e:
        print(f"Базаға жазуда қате кетті: {e}")
        conn.rollback()
        return None
    finally:
        cur.close()
        conn.close()
