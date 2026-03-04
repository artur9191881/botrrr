import time
import requests
from pymongo import MongoClient
from bson.objectid import ObjectId

# ==============================
# ВСТАВЬ СЮДА СВОИ ДАННЫЕ
# ==============================
BOT_TOKEN="8694919208:AAF6eqrbyo1HMkJjIW6owYJYZSpiLn_MiCw"
CHAT_IDS="532319147"
DATABASE_URL="mongodb+srv://miroxlav111:Alex18122008@cluster0.tfjob.mongodb.net/phishing_demo?retryWrites=true&w=majority"
CHAT_ID = "532319147"
DB_NAME = "phishing_demo"
COLLECTION_NAME = "orders"
POLL_SECONDS = 10

# Ссылки для предотвращения "сна" (Render Keep-Alive)
KEEP_ALIVE_URLS = [
    "https://rre-shop-payments.onrender.com",
    "https://rre-shop-api.onrender.com",
    "https://rre-shop.onrender.com"
]
# ==============================

def keep_alive():
    """Отправляет GET запросы на сайты, чтобы они не засыпали."""
    print("🌐 Keeping services alive...")
    for url in KEEP_ALIVE_URLS:
        try:
            r = requests.get(url, timeout=10)
            print(f"✅ {url} - Status: {r.status_code}")
        except Exception as e:
            print(f"⚠️ Failed to ping {url}: {e}")

def send_message(text: str) -> None:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": CHAT_ID, "text": text}, timeout=20)
        r.raise_for_status()
    except Exception as e:
        print("⚠️ Telegram send error:", e)

def pick(order: dict, *keys: str, default: str = "—") -> str:
    for k in keys:
        v = order.get(k)
        if v is None:
            continue
        s = str(v).strip()
        if s != "":
            return s
    return default

def main() -> None:
    if not BOT_TOKEN or "ВСТАВЬ_СЮДА" in BOT_TOKEN:
        raise SystemExit("BOT_TOKEN не задан")
    
    client = MongoClient(DATABASE_URL)
    db = client[DB_NAME]
    col = db[COLLECTION_NAME]

    print("✅ Bot started with Keep-Alive...")
    last_seen_id = None
    
    # Счетчик для пинга (раз в минуту)
    last_ping_time = 0 

    while True:
        current_time = time.time()
        
        # Пинг сайтов раз в 60 секунд
        if current_time - last_ping_time > 60:
            keep_alive()
            last_ping_time = current_time

        try:
            query = {}
            if last_seen_id is not None:
                query = {"_id": {"$gt": last_seen_id}}

            new_orders = list(col.find(query).sort("_id", 1).limit(50))

            for o in new_orders:
                oid = str(o.get("_id", ""))
                name = pick(o, "customerName", "name")
                phone = pick(o, "phone")
                email = pick(o, "email")
                telegram = pick(o, "telegram", default="—")
                product = pick(o, "productTitle", default="—")
                price = pick(o, "productPrice", default="—")
                status = pick(o, "status", default="new")

                msg = (
                    "🆕 Новый заказ\n\n"
                    f"ID: {oid}\n"
                    f"Товар: {product}\n"
                    f"Цена: {price}\n"
                    f"Имя: {name}\n"
                    f"Телефон: {phone}\n"
                    f"Статус: {status}"
                )

                send_message(msg)

                _id = o.get("_id")
                if isinstance(_id, ObjectId):
                    last_seen_id = _id

        except Exception as e:
            print("⚠️ Loop error:", e)

        time.sleep(POLL_SECONDS)

if __name__ == "__main__":
    main()
