import os
import requests
from bs4 import BeautifulSoup
import telegram
from telegram.constants import ParseMode
import random
import asyncio
import threading
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return '{"status":"Achados Celulares Amazon ONLINE","bot":"Ativo"}'

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN") or os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
TAG = os.getenv("TAG_AMAZON") or os.getenv("TAG_AM") or "suribet06-20"

BUSCAS = ["iphone 13 128gb","samsung galaxy a15","moto g54 5g","redmi note 13","galaxy s23 fe","poco x6"]

def buscar_oferta(busca):
    headers = {"User-Agent": "Mozilla/5.0","Accept-Language": "pt-BR,pt;q=0.9"}
    try:
        r = requests.get(f"https://www.amazon.com.br/s?k={busca.replace(' ', '+')}", headers=headers, timeout=20)
        soup = BeautifulSoup(r.text, 'lxml')
        item = soup.select_one('[data-component-type="s-search-result"]')
        if not item:
            print(f"Nada achado para {busca}")
            return None
        titulo = item.h2.text.strip()[:90] if item.h2 else busca
        link_rel = item.h2.a['href'] if item.h2 and item.h2.a else ""
        if not link_rel:
            return None
        link = f"https://www.amazon.com.br{link_rel.split('?')[0]}?tag={TAG}"
        preco_tag = item.select_one('.a-price.a-offscreen')
        preco = preco_tag.text if preco_tag else "Ver preco"
        img = item.select_one('img.s-image')
        img_url = img.get('src') if img else None
        return {"titulo": titulo, "preco": preco, "link": link, "img": img_url}
    except Exception as e:
        print("Erro na busca:")
        print(e)
        return None

async def bot_loop():
    if not TOKEN:
        print("ERRO TOKEN vazio")
        return
    bot = telegram.Bot(token=TOKEN)
    print(f"Bot iniciado chat {CHAT_ID}")
    try:
        await bot.send_message(chat_id=CHAT_ID, text="⚡ *Achados Celulares Amazon ATIVADO!*", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        print("Erro ao enviar ativado")
        print(e)

    while True:
        try:
            busca = random.choice(BUSCAS)
            oferta = buscar_oferta(busca)
            if oferta and oferta['img']:
                texto = f"⚡ *OFERTA RELAMPAGO*\n\n📱 {oferta['titulo']}\n\n💰 *Por: {oferta['preco']}*\n\n👇 *COMPRE AQUI:*\n{oferta['link']}\n\n⏰ Corre!"
                try:
                    await bot.send_photo(chat_id=CHAT_ID, photo=oferta['img'], caption=texto, parse_mode=ParseMode.MARKDOWN)
                except:
                    await bot.send_message(chat_id=CHAT_ID, text=texto, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            print("Erro loop")
            print(e)
        await asyncio.sleep(7200)

def start_bot():
    asyncio.run(bot_loop())

if __name__ == "__main__":
    threading.Thread(target=start_bot, daemon=True).start()
    run_web()
