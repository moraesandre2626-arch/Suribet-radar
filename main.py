import os
import time
import requests
from flask import Flask
from threading import Thread
import telebot

# --- CONFIGURAÇÃO ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
AFILIADO_AMAZON = os.getenv("AFILIADO_TAG", "suribet-20") # coloca seu tag no Render

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

@app.route('/')
def home():
    return "Suribet RADAR V6 - ONLINE - Anti-Spam"

# --- FILTROS ANTI-SPAM QUE VÃO RESOLVER OS 60 ---
DESCONTO_MINIMO = 20.0
TITULOS_BLOQUEADOS = [
    "Samsung celular na Amazon.com.br",
    "Samsung+celular",
    "celular na",
    "Amazon.com.br"
]

def eh_oferta_valida(nome, desconto):
    nome_lower = nome.lower()
    # 1. Bloqueia nome genérico
    for b in TITULOS_BLOQUEADOS:
        if b.lower() in nome_lower and len(nome) < 40: # se for nome curto e genérico
            return False
    # 2. Bloqueia desconto pequeno
    if abs(desconto) < DESCONTO_MINIMO:
        return False
    # 3. Tem que ter GB ou modelo
    if "gb" not in nome_lower and "galaxy" not in nome_lower and "moto" not in nome_lower and "iphone" not in nome_lower:
        if len(nome) < 15:
            return False
    return True

def formatar_msg(produto, de, por, desconto, loja, link):
    pct = abs(desconto)
    link_afiliado = f"{link}&tag={AFILIADO_AMAZON}" if "amazon" in link.lower() else link

    # Evita link gigante
    if len(link_afiliado) > 150:
        link_afiliado = link.split("?")[0] + f"?tag={AFILIADO_AMAZON}"

    return f"""🔥 *QUEDA BOA! -{pct:.1f}%* 🔥

📱 {produto}

💰 De: R$ {de:.2f}
💸 Por: *R$ {por:.2f}*

🏬 {loja}

👇 *VER OFERTA* 👇
{link_afiliado}
"""

def radar_loop():
    while True:
        try:
            # AQUI ENTRA SUA LÓGICA DE BUSCA
            # Exemplo de como usar o filtro antes
