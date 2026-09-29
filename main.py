import os
import time
import json
import re
import asyncio
import threading
import statistics
import unicodedata
from urllib.parse import quote, urljoin, urlparse, parse_qsl, urlencode, urlunparse

import requests
from flask import Flask
from bs4 import BeautifulSoup
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup


# ============================================================
# PRICE RADAR V6
#
# RADAR POR MARCA
# Apple + Samsung + Motorola + Xiaomi
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

# Amazon
TAG_AMAZON = (
    os.getenv("TAG_AMAZON")
    or os.getenv("TAG_AM")
    or "suribet06-20"
)

# Mercado Livre
ML_AFILIADO = (
    os.getenv("ML_AFILIADO")
    or "https://meli.la/19nLNPe"
)

# Shopee
SHOPEE_AFILIADO = (
    os.getenv("SHOPEE_AFILIADO")
    or "https://s.shopee.com.br/1BMi2RMcej"
)

SHOPEE_VITRINE = (
    os.getenv("SHOPEE_VITRINE")
    or "https://collshp.com/shops2023?view=storefront"
)

# Intervalo entre varreduras
INTERVALO_CICLO = int(
    os.getenv("INTERVALO_CICLO")
    or "7200"
)

# Percentual mínimo da oportunidade
DESCONTO_MINIMO = float(
    os.getenv("DESCONTO_MINIMO")
    or "20"
)

# Quantos resultados tentar analisar por loja/marca
MAX_RESULTADOS_POR_LOJA = int(
    os.getenv("MAX_RESULTADOS_POR_LOJA")
    or "12"
)

# Histórico
ARQUIVO_HISTORICO = "historico_precos_v6.json"

# Memória anti-spam
ARQUIVO_ALERTAS = "alertas_v6.json"


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
# TERMOS PARA GARANTIR QUE SEJA CELULAR
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
    "película",
    "adaptador",
    "controle",
    "smartwatch",
    "relogio",
    "relógio",
    "tablet",
    "notebook",
    "computador",
    "mouse",
    "teclado"
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
    )
}


# ============================================================
# FLASK / RENDER
# ============================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "PRICE RADAR V6 ONLINE"


@app.route("/health")
def health():
    return {
        "status": "online",
        "bot": "Price Radar V6",
        "marcas": MARCAS,
        "desconto_minimo": DESCONTO_MINIMO
    }


@app.route("/status")
def status():
    return {
        "radar": "ONLINE",
        "versao": "V6",
        "marcas": MARCAS,
        "lojas": [
            "Amazon",
            "Mercado Livre",
            "Shopee",
            "Magazine Luiza",
            "Casas Bahia",
            "KaBuM"
        ],
        "desconto_minimo": f"{DESCONTO_MINIMO}%",
        "intervalo_segundos": INTERVALO_CICLO
    }


# ============================================================
# HISTÓRICO
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

            return json.load(arquivo)

    except Exception as erro:

        print(
            f"Erro ao carregar {caminho}:",
            erro
        )

        return {}


def salvar_json(caminho, dados):

    try:

        with open(
            caminho,
            "w",
            encoding="utf-8"
        ) as arquivo:

            json.dump(
                dados,
                arquivo,
                ensure_ascii=False,
                indent=2
            )

    except Exception as erro:

        print(
            f"Erro ao salvar {caminho}:",
            erro
        )


def carregar_historico():
    return carregar_json(
        ARQUIVO_HISTORICO
    )


def salvar_historico(historico):
    salvar_json(
        ARQUIVO_HISTORICO,
        historico
    )


def carregar_alertas():
    return carregar_json(
        ARQUIVO_ALERTAS
    )


def salvar_alertas(alertas):
    salvar_json(
        ARQUIVO_ALERTAS,
        alertas
    )


# ============================================================
# TEXTO
# ============================================================

def normalizar_texto(texto):

    if not texto:
        return ""

   
