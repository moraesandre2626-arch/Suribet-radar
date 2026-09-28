import os
import time
import requests
from bs4 import BeautifulSoup
import telegram
from telegram.constants import ParseMode
import random
import asyncio
from datetime import datetime

# PEGA DO RENDER - você já configurou isso
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID", "@moraescoelho26")
TAG = os.getenv("TAG_AMAZON", os.getenv("TAG_AM", "suribet06-20"))

BUSCAS = [
    "iphone 13 128gb",
    "samsung galaxy a15",
    "motorola moto g54 5g",
    "xiaomi redmi note 13",
    "samsung galaxy s23 fe",
    "iphone 15 128gb"
]

def buscar_oferta_amazon(busca):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "pt-BR,pt;q=0.9"
    }
    url = f"https://www.amazon.com.br/s?k={busca.replace(' ', '+')}"
    try:
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, 'lxml')
        item = soup.select_one('[data-component-type="s-search-result"]')
        if not item: return None

        titulo = item.h2.text.strip()[:90] if item.h2 else busca
        link_rel = item.h2.a['href'] if item.h2 and item.h2.a else ""
        if not link_rel: return None
        link = f"https://www.amazon.com.br{link_rel.split('?')[0]}?tag={TAG}&linkCode=ogi&th=1&psc=1"

        preco_elem = item.select_one('.a-price.a-offscreen')
        preco_antigo_elem = item.select_one('.a-price.a-text-price.a-offscreen')

        preco = preco_elem.text if preco_elem else "Ver preço"
        preco_antigo = preco_antigo_elem.text if preco_antigo_elem else ""

        img_elem = item.select_one('img.s-image')
        img = img_elem.get('src') if img_elem else None

        return {"titulo": titulo, "preco": preco, "preco_antigo": preco_antigo, "link": link, "img": img}
    except Exception as e:
        print(f"Erro busca {busca}: {e}")
        return None

async def main_loop():
    bot = telegram.Bot(token=
