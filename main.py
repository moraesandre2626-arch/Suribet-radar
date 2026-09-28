import os
import time
import requests
from flask import Flask
from threading import Thread
import telebot
from bs4 import BeautifulSoup

# --- CONFIGURAÇÃO ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
AFILIADO_TAG = os.getenv("AFILIADO_TAG", "suribet-20")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

@app.route('/')
def home():
    return "Suribet RADAR V6 - ONLINE - Anti-Spam 20%+"

# --- FILTROS QUE VÃO PARAR OS 60 ---
DESCONTO_MINIMO = 20.0
TITULOS_BLOQUEADOS = [
    "Samsung celular na Amazon.com.br",
    "Samsung+celular",
    "celular na Amazon"
]

def eh_oferta_valida(nome, desconto):
    nome_lower = nome.lower()
    if len(nome) < 20: 
        return False
    for b in TITULOS_BLOQUEADOS:
        if b.lower() == nome_lower.strip():
            return False
    if abs(desconto) < DESCONTO_MINIMO:
        return False
    # Tem que parecer celular de verdade
    tem_modelo = any(x in nome_lower for x in ["galaxy", "128gb", "256gb", "moto g", "iphone", "redmi", "poco"])
    if not tem_modelo:
        return False
    return True

def formatar_msg(produto, de, por, desconto, loja, link):
    pct = abs(desconto)
    link_afiliado = link
    if "amazon" in link.lower():
        if "?" in
