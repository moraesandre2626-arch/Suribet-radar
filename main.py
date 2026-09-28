import os
import time
import json
import re
import asyncio
import threading
import requests

from flask import Flask
from bs4 import BeautifulSoup

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup


# ============================================================
# PRICE RADAR V5.1
# CELULARES + AMAZON + MERCADO LIVRE + SHOPEE
# TELEGRAM COM BOTÕES CLICÁVEIS
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

TAG_AMAZON = os.getenv(
    "TAG_AMAZON",
    os.getenv("TAG_AM", "suribet06-20")
)

ML_AFILIADO = os.getenv(
    "ML_AFILIADO",
    "https://meli.la/19nLNPe"
)

SHOPEE_AFILIADO = os.getenv(
    "SHOPEE_AFILIADO",
    "https://s.shopee.com.br/1BMi2RMcej"
)

SHOPEE_VITRINE = os.getenv(
    "SHOPEE_VITRINE",
    "https://collshp.com/shops2023?view=storefront"
)

INTERVALO_CICLO = int(
    os.getenv("INTERVALO_CICLO", "7200")
)

ARQUIVO_HISTORICO = "historico_precos.json"


# ============================================================
# FLASK - RENDER
# ============================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "PRICE RADAR V5.1 ONLINE"


@app.route("/health")
def health():
    return {
        "status": "online",
        "bot": "Price Radar V5.1"
    }


# ============================================================
# PRODUTOS MONITORADOS
# ============================================================

PRODUTOS = [

    "iPhone 13 128GB",
    "iPhone 14 128GB",
    "iPhone 15 128GB",

    "Samsung Galaxy A15",
    "Samsung Galaxy A16",
    "Samsung Galaxy A25",
    "Samsung Galaxy A35",
    "Samsung Galaxy A55",
    "Samsung Galaxy S23 FE",
    "Samsung Galaxy S24",

    "Motorola Moto G54 5G",
    "Motorola Moto G55 5G",
    "Motorola Moto G75 5G",

    "Redmi Note 13",
    "Redmi Note 14",

    "POCO X6",
    "POCO X6 Pro"
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
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"
}


# ============================================================
# HISTÓRICO
# ============================================================

def carregar_historico():

    try:

        if not os.path.exists(ARQUIVO_HISTORICO):
            return {}

        with open(
            ARQUIVO_HISTORICO,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except Exception:

        return {}


def salvar_historico(historico):

    try:

        with open(
            ARQUIVO_HISTORICO,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                historico,
                f,
                ensure_ascii=False,
                indent=2
            )

    except Exception as e:

        print(
            "Erro ao salvar histórico:",
            e
        )


# ============================================================
# PREÇO
# ============================================================

def converter_preco(texto):

    if texto is None:
        return None

    try:

        texto = str(texto)

        texto = texto.replace(
            "R$",
            ""
        )

        texto = texto.replace(
            " ",
            ""
        )

        texto = re.sub(
            r"[^\d,\.]",
            "",
            texto
        )

        if not texto:
            return None

        # Exemplo:
        # 1.299,90 -> 1299.90

        if "," in texto:

            texto = texto.replace(
                ".",
                ""
            )

            texto = texto.replace(
                ",",
                "."
            )

        valor = float(texto)

        if valor <= 0:
            return None

        return valor

    except Exception:

        return None


def formatar_preco(valor):

    if valor is None:
        return "não encontrado"

    return (
        "R$ "
        + f"{valor:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


# ============================================================
# AMAZON
# ============================================================

def buscar_amazon(produto):

    try:

        query = produto.replace(
            " ",
            "+"
        )

        url = (
            "https://www.amazon.com.br/"
            "s?k="
            + query
        )

        resposta = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        if resposta.status_code != 200:

            print(
                "Amazon HTTP:",
                resposta.status_code
            )

            return None

        soup = BeautifulSoup(
            resposta.text,
            "html.parser"
        )

        itens = soup.select(
            "div[data-component-type='s-search-result']"
        )

        for item in itens:

            titulo_el = item.select_one(
                "h2 a span"
            )

            preco_el = item.select_one(
                "span.a-price span.a-offscreen"
            )

            link_el = item.select_one(
                "h2 a"
            )

            if not titulo_el:
                continue

            titulo = titulo_el.get_text(
                " ",
                strip=True
            )

            if not preco_el:
                continue

            preco = converter_preco(
                preco_el.get_text(
                    " ",
                    strip=True
                )
            )

            if preco is None:
                continue

            link = None

            if link_el and link_el.get("href"):

                link = link_el.get(
                    "href"
                )

                if link.startswith("/"):

                    link = (
                        "https://www.amazon.com.br"
                        + link
                    )

            if not link:
                link = url

            # Adiciona tag de afiliado
            separador = (
                "&"
                if "?" in link
                else "?"
            )

            link_afiliado = (
                link
                + separador
                + "tag="
                + TAG_AMAZON
            )

            return {
                "loja": "Amazon",
                "produto": titulo,
                "preco": preco,
                "link": link_afiliado
            }

        return None

    except Exception as e:

        print(
            "Erro Amazon:",
            e
        )

        return None


# ============================================================
# MERCADO LIVRE
# ============================================================

def buscar_mercadolivre(produto):

    try:

        query = produto.replace(
            " ",
            "-"
        )

        url = (
            "https://lista.mercadolivre.com.br/"
            + query
        )

        resposta = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        if resposta.status_code != 200:

            print(
                "Mercado Livre HTTP:",
                resposta.status_code
            )

            return None

        soup = BeautifulSoup(
            resposta.text,
            "html.parser"
        )

        itens = soup.select(
            "li.ui-search-layout__item"
        )

        for item in itens:

            titulo_el = item.select_one(
                "a.poly-component__title"
            )

            if not titulo_el:

                titulo_el = item.select_one(
                    "h2"
                )

            preco_el = item.select_one(
                "span.andes-money-amount__fraction"
            )

            link_el = item.select_one(
                "a"
            )

            if not titulo_el:
                continue

            titulo = titulo_el.get_text(
                " ",
                strip=True
            )

            if not preco_el:
                continue

            preco_texto = (
                preco_el.get_text(
                    " ",
                    strip=True
                )
            )

            preco = converter_preco(
                preco_texto
            )

            if preco is None:
                continue

            link = None

            if link_el:

                link = link_el.get(
                    "href"
                )

            if not link:
                link = url

            return {
                "loja": "Mercado Livre",
                "produto": titulo,
                "preco": preco,
                "link": link
            }

        return None

    except Exception as e:

        print(
           
