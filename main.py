import os
import time
import requests
from bs4 import BeautifulSoup
import telegram
from telegram.constants import ParseMode
import random
from datetime import datetime

# SUAS CONFIGS
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID", "@moraescoelho26")
TAG = "suribet06-20" # sua tag da Amazon

# Lista de buscas que dão comissão boa
BUSCAS = [
    "iphone 13 128gb",
    "samsung galaxy a15",
    "motorola moto g54 5g",
    "xiaomi redmi note 13",
    "samsung galaxy s23"
]

def buscar_oferta_amazon(busca):
    """Busca produto na Amazon Brasil"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "pt-BR,pt;q=0.9"
    }
    url = f"https://www.amazon.com.br/s?k={busca.replace(' ', '+')}&s=price-asc-rank"
    try:
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, 'lxml')

        # Pega primeiro produto com preço
        item = soup.select_one('[data-component-type="s-search-result"]')
        if not item: return None

        titulo = item.h2.text.strip()[:80] if item.h2 else busca
        link_rel = item.h2.a['href'] if item.h2 and item.h2.a else ""
        link = f"https://www.amazon.com.br{link_rel.split('?')[0]}?tag={TAG}"

        preco_elem = item.select_one('.a-price.a-offscreen')
        preco_antigo_elem = item.select_one('.a-price.a-text-price.a-offscreen')

        preco = preco_elem.text if preco_elem else "Ver preço"
        preco_antigo = preco_antigo_elem.text if preco_antigo_elem else ""

        img_elem = item.select_one('img.s-image')
        img = img_elem['src'] if img_elem else None

        return {
            "titulo": titulo,
            "preco": preco,
            "preco_antigo": preco_antigo,
            "link": link,
            "img": img
        }
    except Exception as e:
        print(f"Erro na busca {busca}: {e}")
        return None

async def main_loop():
    bot = telegram.Bot(token=TOKEN)

    # Mensagem de inicio
    await bot.send_message(chat_id=CHAT_ID, text="⚡ *Achados Celulares Amazon ATIVADO!*\n\nAgora vou postar as melhores ofertas de 2 em 2 horas com seu link afiliado.", parse_mode=ParseMode.MARKDOWN)
    print("Bot iniciado!")

    while True:
        busca = random.choice(BUSCAS)
        print(f"Buscando: {busca}")
        oferta = buscar_oferta_amazon(busca)

        if oferta and oferta['img']:
            desconto_txt = ""
            if oferta['preco_antigo']:
                desconto_txt = f"~De: {oferta['preco_antigo']}~\n"

            texto = f"""
⚡ *OFERTA RELÂMPAGO*

📱 {oferta['titulo']}

{desconto_txt}💰 *Por: {oferta['preco']}*

✅ Vendido pela Amazon
🚚 Frete GRÁTIS Prime
🔒 Oferta verificada agora

👇 *COMPRE AQUI:*
{oferta['link']}

⏰ Corre que acaba rápido!
#amazon #oferta #celular
            """
            try:
                await bot.send_photo(
                    chat_id=CHAT_ID,
                    photo=oferta['img'],
                    caption=texto,
                    parse_mode=ParseMode.MARKDOWN
                )
                print("Oferta postada!")
            except Exception as e:
                print(f"Erro ao postar: {e}")
                await bot.send_message(chat_id=CHAT_ID, text=texto, parse_mode=ParseMode.MARKDOWN)

        # Espera 2 horas
        time.sleep(7200)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main_loop())
