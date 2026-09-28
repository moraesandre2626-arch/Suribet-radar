import os
import time
import requests
from bs4 import BeautifulSoup
import telegram
from telegram.constants import ParseMode
import random
import asyncio
import threading
from flask import Flask

# --- WEB SERVER PRA RENDER NÃO DORMIR ---
app = Flask(__name__)
@app.route('/')
def home():
    return '{"status":"Achados Celulares Amazon ONLINE","bot":"Ativo"}'

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- CONFIGS ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID", "@moraescoelho26")
TAG = os.getenv("TAG_AMAZON", os.getenv("TAG_AM", "suribet06-20"))

BUSCAS = ["iphone 13 128gb","samsung galaxy a15","moto g54 5g","redmi note 13","galaxy s23 fe"]

def buscar_oferta(busca):
    headers = {"User-Agent": "Mozilla/5.0","Accept-Language": "pt-BR,pt;q=0.9"}
    try:
        r = requests.get(f"https://www.amazon.com.br/s?k={busca.replace(' ', '+')}", headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, 'lxml')
        item = soup.select_one('[data-component-type="s-search-result"]')
        if not item: return None
        titulo = item.h2.text.strip()[:90] if item.h2 else busca
        link_rel = item.h2.a['href'] if item.h2 and item.h2.a else ""
        if not link_rel: return None
        link = f"https://www.amazon.com.br{link_rel.split('?')[0]}?tag={TAG}"
        preco = item.select_one('.a-price.a-offscreen')
        preco = preco.text if preco else "Ver preço"
        img = item.select_one('img.s-image')
        img = img.get('src') if img else None
        return {"titulo": titulo, "preco": preco, "link": link, "img": img}
    except: return None

async def bot_loop():
    bot = telegram.Bot(token=TOKEN)
    try:
        await bot.send_message(chat_id=CHAT_ID, text="⚡ *Achados Celulares Amazon ATIVADO!*", parse_mode=ParseMode.MARKDOWN)
    except: pass
    print("Bot iniciado!")
    while True:
        busca = random.choice(BUSCAS)
        oferta = buscar_oferta(busca)
        if oferta and oferta['img']:
            texto = f"⚡ *OFERTA RELÂMPAGO*\n\n📱 {oferta['titulo']}\n\n💰 *Por: {oferta['preco']}*\n\n👇 *COMPRE AQUI:*\n{oferta['link']}\n\n⏰ Corre!"
            try:
                await bot.send_photo(chat_id=CHAT_ID, photo=oferta['img'], caption=texto, parse_mode=ParseMode.MARKDOWN)
            except:
                await bot.send_message(chat_id=CHAT_ID, text=texto, parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(7200)

def start_bot():
    asyncio.run(bot_loop())

if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    threading.Thread(target=start_bot).start()
