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
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN") or os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
TAG = os.getenv("TAG_AMAZON") or os.getenv("TAG_AM") or os.getenv("TAG_AMAZON_ID") or "suribet06-20"

BUSCAS = ["iphone 13 128gb","samsung galaxy a15","moto g54 5g","redmi note 13","galaxy s23 fe","iphone 14","poco x6"]

def buscar_oferta(busca):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36","Accept-Language": "pt-BR,pt;q=0.9"}
    try:
        r = requests.get(f"https://www.amazon.com.br/s?k={busca.replace(' ', '+')}", headers=headers, timeout=20)
        soup = BeautifulSoup(r.text, 'lxml')
        item = soup.select_one('[data-component-type="s-search-result"]')
        if not item:
            print(f"Nada achado pra {busca}")
            return None
        titulo = item.h2.text.strip()[:90] if item.h2 else busca
        link_rel = item.h2.a['href'] if item.h2 and item.h2.a else ""
        if not link_rel: return None
        link = f"https://www.amazon.com.br{link_rel.split('?')[0]}?tag={TAG}"
        preco = item.select_one('.a-price.a-offscreen')
        if not preco:
            preco = item.select_one('.a-price.a-offscreen')
        preco_txt = preco.text if preco else "Ver preço na Amazon"
        img = item.select_one('img.s-image')
        img_url = img.get('src') if img else None
        print(f"Oferta achada: {titulo} - {preco_txt}")
        return {"titulo": titulo, "preco": preco_txt, "link": link, "img": img_url}
    except Exception as e:
        print(f"Erro na
