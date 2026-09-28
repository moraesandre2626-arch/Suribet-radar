import os, time, requests
from telegram import Bot
import asyncio

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
TAG = os.getenv("TAG_AMAZON", "suribet06-20")

async def main():
    bot = Bot(token=TOKEN)
    print(f"Bot Achadinhos iniciado para o canal {CHAT_ID}")
    # Teste inicial
    await bot.send_message(chat_id=CHAT_ID, text="⚡ Achadinhos Relâmpago da Amazon ATIVADO!\n🔒 Só ofertas verificadas\n👇 Fique ligado nas próximas ofertas")
    
    while True:
        await asyncio.sleep(3600) # espera 1h

if __name__ == "__main__":
    asyncio.run(main())
