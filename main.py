import os
import re
import json
import time
import threading
import traceback
import statistics
import unicodedata
from urllib.parse import quote, urljoin, urlparse, parse_qsl, urlencode, urlunparse

import requests
from flask import Flask
from bs4 import BeautifulSoup


# ============================================================
# PRICE RADAR V6.1
#
# RADAR DE CELULARES POR MARCA
#
# MARCAS:
# Apple
# Samsung
# Motorola
# Xiaomi
#
# LOJAS:
# Amazon
# Mercado Livre
# Shopee
# Magazine Luiza
# Casas Bahia
# KaBuM
#
# REGRA:
# Só alerta quando o preço encontrado estiver pelo menos
# 20% abaixo da referência dos preços comparáveis.
#
# V6.1:
# - Inicialização mais segura para Render
# - Logs detalhados
# - Telegram via API HTTP
# - Sem dependência do python-telegram-bot
# - Histórico
# - Anti-spam
# - Comparação por modelo + armazenamento
# - Botões clicáveis
# ============================================================


# ============================================================
# CONFIGURAÇÕES
# ============================================================

TELEGRAM_TOKEN = (
    os.getenv("TELEGRAM_BOT_TOKEN")
    or os.getenv("TELEGRAM_TOKEN")
    or os.getenv("BOT_TOKEN")
)

CHAT_ID = os.getenv("CHAT_ID")


# ============================================================
# AFILIADOS
# ============================================================

TAG_AMAZON = (
    os.getenv("TAG_AMAZON")
    or os.getenv("TAG_AM")
    or "suribet06-20"
)

ML_AFILIADO = (
    os.getenv("ML_AFILIADO")
    or "https://meli.la/19nLNPe"
)

SHOPEE_AFILIADO = (
    os.getenv("SHOPEE_AFILIADO")
    or "https://s.shopee.com.br/1BMi2RMcej"
)

SHOPEE_VITRINE = (
    os.getenv("SHOPEE_VITRINE")
    or "https://collshp.com/shops2023?view=storefront"
)


# ============================================================
# RADAR
# ============================================================

INTERVALO_CICLO = int(
    os.getenv("INTERVALO_CICLO")
    or "7200"
)

DESCONTO_MINIMO = float(
    os.getenv("DESCONTO_MINIMO")
    or "20"
)

MAX_RESULTADOS_POR_LOJA = int(
    os.getenv("MAX_RESULTADOS_POR_LOJA")
    or "12"
)


# ============================================================
# ARQUIVOS
# ============================================================

ARQUIVO_HISTORICO = "historico_precos_v61.json"
ARQUIVO_ALERTAS = "alertas_v61.json"


# ============================================================
# MARCAS
# ============================================================

MARCAS = [
    "Apple",
    "Samsung",
    "Motorola",
    "Xiaomi"
]


# ============================================================
# LOJAS
# ============================================================

LOJAS = [
    "Amazon",
    "Mercado Livre",
    "Shopee",
    "Magazine Luiza",
    "Casas Bahia",
    "KaBuM"
]


# ============================================================
# TERMOS DE CELULAR
# ============================================================

TERMOS_CELULAR = [
    "iphone",
    "galaxy",
    "samsung",
    "moto",
    "motorola",
    "xiaomi",
    "redmi",
    "poco",
    "smartphone",
    "celular",
    "telefone"
]


# ============================================================
# TERMOS PARA IGNORAR
# ============================================================

TERMOS_IGNORAR = [
    "capa",
    "capinha",
    "pelicula",
    "película",
    "case",
    "carregador",
    "cabo",
    "fone",
    "headset",
    "suporte",
    "bateria",
    "display",
    "tela",
    "vidro",
    "adaptador",
    "controle",
    "smartwatch",
    "relogio",
    "relógio",
    "tablet",
    "notebook",
    "computador",
    "mouse",
    "teclado",
    "pelicula"
]


# ============================================================
# HEADERS
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/avif,"
        "image/webp,*/*;q=0.8"
    ),
    "Cache-Control": "no-cache"
}


# ============================================================
# SESSION
# ============================================================

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


# ============================================================
# FLASK
# ============================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "PRICE RADAR V6.1 ONLINE"


@app.route("/health")
def health():
    return {
        "status": "online",
        "bot": "Price Radar V6.1",
        "marcas": MARCAS,
        "lojas": LOJAS,
        "desconto_minimo": DESCONTO_MINIMO
    }


@app.route("/status")
def status():
    return {
        "radar": "ONLINE",
        "versao": "V6.1",
        "marcas": MARCAS,
        "lojas": LOJAS,
        "desconto_minimo": f"{DESCONTO_MINIMO}%",
        "intervalo_segundos": INTERVALO_CICLO
    }


# ============================================================
# LOG
# ============================================================

def log(msg):
    print(
        f"[PRICE RADAR] {msg}",
        flush=True
    )


# ============================================================
# JSON
# ============================================================

def carregar_json(caminho):

    try:

        if not os.path.exists(caminho):
            return {}

        with open(
            caminho,
            "r",
            encoding="utf-8"
        ) as arquivo:

            dados = json.load(arquivo)

            if isinstance(dados, dict):
                return dados

            return {}

    except Exception as erro:

        log(
            f"Erro carregando {caminho}: {erro}"
        )

        return {}


def salvar_json(caminho, dados):

    try:

        temporario = caminho + ".tmp"

        with open(
            temporario,
            "w",
            encoding="utf-8"
       
