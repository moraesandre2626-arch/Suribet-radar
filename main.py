import os, time, requests
from flask import Flask
from threading import Thread
import telebot
from bs4 import BeautifulSoup

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
AFILIADO_TAG = os.getenv("AFILIADO_TAG", "suribet-20")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

@app.route('/')
def home():
    return "Suribet RADAR V7 - ONLINE"

DESCONTO_MINIMO = 20.0

def eh_oferta_valida(nome, desconto):
    if not nome or len(nome) < 20:
        return False
    n = nome.lower()
    if n.strip() == "samsung celular na amazon.com.br":
        return False
    if abs(desconto) < DESCONTO_MINIMO:
        return False
    if not any(x in n for x in ["galaxy","128gb","256gb","moto","iphone","redmi","poco","a54"]):
        return False
    return True

def formatar_msg(produto, de, por, desconto, loja, link):
    pct = abs(desconto)
    base = link.split("?")[0]
    link_af = f"{base}?tag={AFILIADO_TAG}"
    return f"🔥 QUEDA -{pct:.1f}% 🔥\n\n📱 {produto}\n\n💰 De: R$ {de:.2f}\n💸 Por: R$ {por:.2f}\n\n🏬 {loja}\n\n👇 VER OFERTA 👇\n{link_af}"

def buscar_amazon():
    headers = {"User-Agent": "Mozilla/5.0"}
    url = "https://www.amazon.com.br/s?k=samsung+galaxy+a54+128gb"
    try:
        r = requests.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
        ofertas = []
        for item in soup.select("div[data-component-type='s-search-result']")[:10]:
            try:
                titulo = item.h2.text.strip()
                preco_tag = item.select_one("span.a-price span.a-offscreen")
                if not preco_tag:
                    continue
                preco_atual = float(preco_tag.text.replace("R$","").replace(".","").replace(",",".").strip())
                preco_orig_tag = item.select_one("span.a-price.a-text-price span.a-offscreen")
                if not preco_orig_tag:
                    continue
                preco_orig = float(preco_orig_tag.text.replace("R$","").replace(".","").replace(",",".").strip())
                if preco_orig <= preco_atual:
                    continue
                desconto = ((preco_atual - preco_orig) / preco_orig) * 100
                link_tag = item.h2.a.get("href")
                link = "https://www.amazon.com.br" + link_tag
                ofertas.append((titulo, preco_orig, preco_atual, desconto, "Amazon", link))
            except Exception:
                continue
        return ofertas
    except Exception as e:
        print(f"Erro: {e}")
        return []

def radar_loop():
    print("RADAR V7 INICIADO")
    enviados = set()
    while True:
        try:
            for nome, de, por, desc, loja, link in buscar_amazon():
                if nome in enviados:
                    continue
                if eh_oferta_valida(nome, desc):
                    msg = formatar_msg(nome, de, por, desc, loja, link)
                    bot.send_message(CHAT_ID, msg)
                    enviados.add(nome)
            time.sleep(300)
        except Exception as e:
            print(f"Erro loop: {e}")
            time.sleep(60)

Thread(target=radar_loop, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
