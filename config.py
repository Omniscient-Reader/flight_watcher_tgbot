import os
from dotenv import load_dotenv

# .env файлындағы айнымалыларды жүктейміз
load_dotenv()

# Токенді оқимыз
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Егер токен табылмаса, бағдарлама бірден қателік беріп, тоқтауы керек
if not TELEGRAM_TOKEN:
    raise ValueError("Қате: .env файлында TELEGRAM_TOKEN табылмады!")
