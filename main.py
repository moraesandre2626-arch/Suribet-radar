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
# TELEGRAM COM BOTÕES
# ============================================================

TELEGRAM_TOKEN = (
    os.getenv("TELEGRAM_BOT_TOKEN")
    or os.getenv("TELEGRAM_TOKEN")
    or os.getenv("BOT_TOKEN")
)

CHAT_ID = os.getenv("CHAT_ID")

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

INTERVALO_CICLO = int(
    os.getenv("INTERVALO_CICLO")
    or "7200"
)

ARQUIVO_HISTORICO = "historico_precos.json"


# ============================================================
# FLASK / RENDER
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
# PRODUTOS
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
        ) as arquivo:

            return json.load(arquivo)

    except Exception as erro:

        print(
            "Erro ao carregar histórico:",
            erro
        )

        return {}


def salvar_historico(historico):

    try:

        with open(
            ARQUIVO_HISTORICO,
            "w",
            encoding="utf-8"
        ) as arquivo:

            json.dump(
                historico,
                arquivo,
                ensure_ascii=False,
                indent=2
            )

    except Exception as erro:

        print(
            "Erro ao salvar histórico:",
            erro
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
            r"[^\d,.]",
            "",
            texto
        )

        if not texto:
            return None

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

    valor_formatado = (
        f"{valor:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )

    return "R$ " + valor_formatado


# ============================================================
# AMAZON
# ============================================================

def buscar_amazon(produto):

    try:

        url = (
            "https://www.amazon.com.br/s?k="
            + produto.replace(" ", "+")
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

        produtos = soup.select(
            "div[data-component-type='s-search-result']"
        )

        for item in produtos:

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

            link = (
                link_el.get("href")
                if link_el
                else url
            )

            if link.startswith("/"):

                link = (
                    "https://www.amazon.com.br"
                    + link
                )

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
                "produto": titulo_el.get_text(
                    " ",
                    strip=True
                ),
                "preco": preco,
                "link": link_afiliado
            }

        return None

    except Exception as erro:

        print(
            "Erro Amazon:",
            erro
        )

        return None


# ============================================================
# MERCADO LIVRE
# ============================================================

def buscar_mercadolivre(produto):

    try:

        url = (
            "https://lista.mercadolivre.com.br/"
            + produto.replace(" ", "-")
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

            titulo_el = (
                item.select_one(
                    "a.poly-component__title"
                )
                or
                item.select_one("h2")
            )

            preco_el = item.select_one(
                "span.andes-money-amount__fraction"
            )

            link_el = item.select_one(
                "a"
            )

            if not titulo_el:
                continue

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

            link = (
                link_el.get("href")
                if link_el
                else url
            )

            return {
                "loja": "Mercado Livre",
                "produto": titulo_el.get_text(
                    " ",
                    strip=True
                ),
                "preco": preco,
                "link": link
            }

        return None

    except Exception as erro:

        print(
            "Erro Mercado Livre:",
            erro
        )

        return None


# ============================================================
# SHOPEE
# ============================================================

def buscar_shopee(produto):

    url = (
        "https://shopee.com.br/search?keyword="
        + produto.replace(" ", "%20")
    )

    try:

        resposta = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        if resposta.status_code != 200:

            print(
                "Shopee HTTP:",
                resposta.status_code
            )

            return {
                "loja": "Shopee",
                "produto": produto,
                "preco": None,
                "link": url
            }

        soup = BeautifulSoup(
            resposta.text,
            "html.parser"
        )

        links = soup.select(
            "a[href]"
        )

        for elemento in links:

            href = elemento.get(
                "href"
            )

            if not href:
                continue

            if "-i." not in href:
                continue

            if href.startswith("/"):

                href = (
                    "https://shopee.com.br"
                    + href
                )

            titulo = elemento.get_text(
                " ",
                strip=True
            )

            if not titulo:
                titulo = produto

            return {
                "loja": "Shopee",
                "produto": titulo,
                "preco": None,
                "link": href
            }

        return {
            "loja": "Shopee",
            "produto": produto,
            "preco": None,
            "link": url
        }

    except Exception as erro:

        print(
            "Erro Shopee:",
            erro
        )

        return {
            "loja": "Shopee",
            "produto": produto,
            "preco": None,
            "link": url
        }


# ============================================================
# BUSCAR PRODUTO
# ============================================================

def buscar_produto(produto):

    print("")
    print("================================")
    print(
        "PROCURANDO:",
        produto
    )
    print("================================")

    resultados = []

    amazon = buscar_amazon(
        produto
    )

    if amazon:

        resultados.append(
            amazon
        )

        print(
            "Amazon:",
            formatar_preco(
                amazon["preco"]
            )
        )

    else:

        print(
            "Amazon: não encontrado"
        )

    mercado_livre = buscar_mercadolivre(
        produto
    )

    if mercado_livre:

        resultados.append(
            mercado_livre
        )

        print(
            "Mercado Livre:",
            formatar_preco(
                mercado_livre["preco"]
            )
        )

    else:

        print(
            "Mercado Livre: não encontrado"
        )

    shopee = buscar_shopee(
        produto
    )

    if shopee:

        resultados.append(
            shopee
        )

        print(
            "Shopee:",
            formatar_preco(
                shopee.get("preco")
            )
        )

    else:

        print(
            "Shopee: não encontrado"
        )

    return {
        "produto": produto,
        "resultados": resultados
    }


# ============================================================
# MENOR PREÇO
# ============================================================

def encontrar_menor_preco(resultados):

    validos = []

    for item in resultados:

        if item.get("preco") is not None:

            validos.append(
                item
            )

    if not validos:
        return None

    return min(
        validos,
        key=lambda item: item["preco"]
    )


# ============================================================
# MENSAGEM TELEGRAM
# ============================================================

def montar_mensagem(dados):

    produto = dados["produto"]

    resultados = dados["resultados"]

    lojas = {}

    for item in resultados:

        lojas[item["loja"]] = item

    menor = encontrar_menor_preco(
        resultados
    )

    linhas = []

    linhas.append(
        "📱 <b>OPORTUNIDADE ENCONTRADA</b>"
    )

    linhas.append(
        "━━━━━━━━━━━━━━━━━━"
    )

    linhas.append(
        f"📦 <b>{produto}</b>"
    )

    linhas.append("")

    # AMAZON
    linhas.append(
        "🟠 <b>Amazon</b>"
    )

    amazon = lojas.get(
        "Amazon"
    )

    if amazon and amazon.get("preco") is not None:

        linhas.append(
            f"💰 {formatar_preco(amazon['preco'])}"
        )

    else:

        linhas.append(
            "💰 preço não identificado"
        )

    linhas.append("")

    # MERCADO LIVRE
    linhas.append(
        "🟡 <b>Mercado Livre</b>"
    )

    mercado = lojas.get(
        "Mercado Livre"
    )

    if mercado and mercado.get("preco") is not None:

        linhas.append(
            f"💰 {formatar_preco(mercado['preco'])}"
        )

    else:

        linhas.append(
            "💰 preço não identificado"
        )

    linhas.append("")

    # SHOPEE
    linhas.append(
        "🟠 <b>Shopee</b>"
    )

    shopee = lojas.get(
        "Shopee"
    )

    if shopee and shopee.get("preco") is not None:

        linhas.append(
            f"💰 {formatar_preco(shopee['preco'])}"
        )

    else:

        linhas.append(
            "💰 preço não identificado"
        )

    linhas.append("")

    linhas.append(
        "━━━━━━━━━━━━━━━━━━"
    )

    if menor:

        linhas.append(
            "🔥 <b>MENOR PREÇO IDENTIFICADO</b>"
        )

        linhas.append(
            f"🏪 {menor['loja']}"
        )

        linhas.append(
            f"💰 {formatar_preco(menor['preco'])}"
        )

    else:

        linhas.append(
            "🔎 <b>Preços ainda não identificados.</b>"
        )

    linhas.append("")

    linhas.append(
        "📲 Escolha uma loja abaixo:"
    )

    return "\n".join(
        linhas
    )


# ============================================================
# BOTÕES TELEGRAM
# ============================================================

def montar_botoes(dados):

    lojas = {}

    for item in dados["resultados"]:

        lojas[item["loja"]] = item

    botoes = []

    amazon = lojas.get(
        "Amazon"
    )

    if amazon:

        botoes.append(
            [
                InlineKeyboardButton(
                    "🟠 AMAZON",
                    url=amazon["link"]
                )
            ]
        )

    mercado = lojas.get(
        "Mercado Livre"
    )

    if mercado:

        botoes.append(
            [
                InlineKeyboardButton(
                    "🟡 MERCADO LIVRE",
                    url=mercado["link"]
                )
            ]
        )

    botoes.append(
        [
            InlineKeyboardButton(
                "🟠 MINHA VITRINE SHOPEE",
                url=SHOPEE_VITRINE
            )
        ]
    )

    shopee = lojas.get(
        "Shopee"
    )

    if shopee:

        botoes.append(
            [
                InlineKeyboardButton(
                    "🛍️ LINK SHOPEE",
                    url=shopee["link"]
                )
            ]
        )

    else:

        botoes.append(
            [
                InlineKeyboardButton(
                    "🛍️ LINK SHOPEE",
                    url=SHOPEE_AFILIADO
                )
            ]
        )

    return InlineKeyboardMarkup(
        botoes
    )


# ============================================================
# TELEGRAM
# ============================================================

async def enviar_telegram_async(
    mensagem,
    botoes
):

    if not TELEGRAM_TOKEN:

        print(
            "ERRO: token do Telegram não configurado."
        )

        return False

    if not CHAT_ID:

        print(
            "ERRO: CHAT_ID não configurado."
        )

        return False

    try:

        bot = Bot(
            token=TELEGRAM_TOKEN
        )

        await bot.send_message(
            chat_id=CHAT_ID,
            text=mensagem,
            parse_mode="HTML",
            reply_markup=botoes,
            disable_web_page_preview=False
        )

        print(
            "✅ Mensagem enviada para o Telegram."
        )

        return True

    except Exception as erro:

        print(
            "❌ Erro Telegram:",
            erro
        )

        return False


def enviar_telegram(
    mensagem,
    botoes
):

    try:

        return asyncio.run(
            enviar_telegram_async(
                mensagem,
                botoes
            )
        )

    except Exception as erro:

        print(
            "Erro asyncio Telegram:",
            erro
        )

        return False


# ============================================================
# VERIFICAR OPORTUNIDADE
# ============================================================

def oportunidade_nova(
    produto,
    dados,
    historico
):

    menor = encontrar_menor_preco(
        dados["resultados"]
    )

    if not menor:

        return False

    preco_atual = menor["preco"]

    chave = produto.lower()

    preco_anterior = historico.get(
        chave
    )

    historico[
        chave
    ] = preco_atual

    if preco_anterior is None:

        return True

    if preco_atual < preco_anterior:

        return True

    return False


# ============================================================
# CICLO
# ============================================================

def executar_ciclo():

    print("")
    print("########################################")
    print("🚀 PRICE RADAR V5.1")
    print("🔎 INICIANDO NOVO CICLO")
    print("########################################")

    historico = carregar_historico()

    for produto in PRODUTOS:

        try:

            dados = buscar_produto(
                produto
            )

            nova_oportunidade = oportunidade_nova(
                produto,
                dados,
                historico
            )

            salvar_historico(
                historico
            )

            if nova_oportunidade:

                mensagem = montar_mensagem(
                    dados
                )

                botoes = montar_botoes(
                    dados
                )

                enviar_telegram(
                    mensagem,
                    botoes
                )

                print(
                    "🔥 OPORTUNIDADE ENVIADA:",
                    produto
                )

            else:

                print(
                    "⏭️ Sem nova queda:",
                    produto
                )

        except Exception as erro:

            print(
                "❌ Erro no produto",
                produto,
                ":",
                erro
            )

        time.sleep(3)

    print("")
    print(
        "✅ CICLO FINALIZADO."
    )

    print(
        "⏰ Próximo ciclo em",
        INTERVALO_CICLO,
        "segundos."
    )


# ============================================================
# THREAD DO RADAR
# ============================================================

def iniciar_radar():

    print(
        "🚀 Thread do Price Radar iniciada."
    )

    while True:

        try:

            executar_ciclo()

        except Exception as erro:

            print(
                "❌ Erro no ciclo:",
                erro
            )

        time.sleep(
            INTERVALO_CICLO
        )


# ============================================================
# INICIALIZAÇÃO
# ============================================================

if __name__ == "__main__":

    print(
        "========================================"
    )

    print(
        "📡 PRICE RADAR V5.1"
    )

    print(
        "========================================"
    )

    print(
        "Amazon afiliado:",
        TAG_AMAZON
    )

    print(
        "Mercado Livre:",
        ML_AFILIADO
    )

    print(
        "Shopee:",
        SHOPEE_AFILIADO
    )

    print(
        "Vitrine Shopee:",
        SHOPEE_VITRINE
    )

    print(
        "Intervalo:",
        INTERVALO_CICLO,
        "segundos"
    )

    print(
        "========================================"
    )

    thread = threading.Thread(
        target=iniciar_radar,
        daemon=True
    )

    thread.start()

    porta = int(
        os.getenv(
            "PORT",
            "10000"
        )
    )

    app.run(
        host="0.0.0.0",
        port=porta
    )
