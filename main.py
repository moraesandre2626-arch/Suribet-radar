# ============================================================
# PRICE RADAR V5.1
# AMAZON + MERCADO LIVRE + SHOPEE
# TELEGRAM COM BOTÕES CLICÁVEIS
# ============================================================

import os
import re
import json
import time
import hashlib
import threading
import asyncio
import requests

from bs4 import BeautifulSoup
from flask import Flask

import telegram
from telegram.constants import ParseMode
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# ============================================================
# FLASK / RENDER
# ============================================================

app = Flask(__name__)


@app.route("/")
def home():
    return {
        "status": "PRICE RADAR V5.1 ONLINE",
        "bot": "Ativo",
        "lojas": [
            "Amazon",
            "Mercado Livre",
            "Shopee"
        ],
        "telegram_botoes": True
    }


@app.route("/status")
def status():
    return {
        "status": "ONLINE",
        "versao": "V5.1",
        "amazon": "ATIVA",
        "mercado_livre": "ATIVO",
        "shopee": "ATIVA",
        "botoes_telegram": "ATIVOS"
    }


# ============================================================
# CONFIGURAÇÕES
# ============================================================

TOKEN = (
    os.getenv("TELEGRAM_BOT_TOKEN")
    or os.getenv("TELEGRAM_TOKEN")
    or os.getenv("BOT_TOKEN")
)

CHAT_ID = os.getenv("CHAT_ID")


# ============================================================
# AMAZON
# ============================================================

TAG_AMAZON = (
    os.getenv("TAG_AMAZON")
    or os.getenv("TAG_AM")
    or "suribet06-20"
)


# ============================================================
# MERCADO LIVRE
# ============================================================

ML_AFILIADO = os.getenv(
    "ML_AFILIADO",
    "https://meli.la/19nLNPe"
)


# ============================================================
# SHOPEE
# ============================================================

SHOPEE_AFILIADO = os.getenv(
    "SHOPEE_AFILIADO",
    "https://s.shopee.com.br/1BMi2RMcej"
)

SHOPEE_VITRINE = os.getenv(
    "SHOPEE_VITRINE",
    "https://collshp.com/shops2023?view=storefront"
)


# ============================================================
# CONFIGURAÇÃO DO RADAR
# ============================================================

HISTORICO_FILE = "radar_historico_v51.json"

INTERVALO_CICLO = int(
    os.getenv(
        "INTERVALO_CICLO",
        "7200"
    )
)

PAUSA_BUSCAS = 4


# ============================================================
# CELULARES MONITORADOS
# ============================================================

BUSCAS = [

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
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/139.0 Safari/537.36"
    ),

    "Accept-Language":
        "pt-BR,pt;q=0.9"
}


SESSION = requests.Session()

SESSION.headers.update(
    HEADERS
)


# ============================================================
# HISTÓRICO
# ============================================================

def carregar_historico():

    try:

        if os.path.exists(
            HISTORICO_FILE
        ):

            with open(
                HISTORICO_FILE,
                "r",
                encoding="utf-8"
            ) as arquivo:

                return json.load(
                    arquivo
                )

    except Exception as erro:

        print(
            "Erro carregando histórico:",
            erro
        )

    return {}


def salvar_historico(
    historico
):

    try:

        with open(
            HISTORICO_FILE,
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
            "Erro salvando histórico:",
            erro
        )


# ============================================================
# PREÇO
# ============================================================

def converter_preco(
    valor
):

    if not valor:

        return None

    texto = str(
        valor
    )

    texto = (
        texto
        .replace(
            "R$",
            ""
        )
        .replace(
            "\xa0",
            " "
        )
        .strip()
    )

    texto = re.sub(
        r"[^\d,.]",
        "",
        texto
    )

    if not texto:

        return None

    try:

        if "," in texto:

            texto = texto.replace(
                ".",
                ""
            )

            texto = texto.replace(
                ",",
                "."
            )

        return float(
            texto
        )

    except Exception:

        return None


def formatar_preco(
    valor
):

    if valor is None:

        return "Preço não identificado"

    return (
        "R$ "
        +
        f"{valor:,.2f}"
        .replace(
            ",",
            "X"
        )
        .replace(
            ".",
            ","
        )
        .replace(
            "X",
            "."
        )
    )


# ============================================================
# ID
# ============================================================

def gerar_id(
    loja,
    titulo,
    link
):

    base = (
        f"{loja}|"
        f"{titulo}|"
        f"{link}"
    )

    return hashlib.md5(
        base.encode(
            "utf-8"
        )
    ).hexdigest()


# ============================================================
# AMAZON
# ============================================================

def buscar_amazon(
    busca
):

    print(
        f"🟠 AMAZON → {busca}"
    )

    try:

        url = (
            "https://www.amazon.com.br/s?k="
            +
            requests.utils.quote(
                busca
            )
        )

        resposta = SESSION.get(
            url,
            timeout=25
        )

        if resposta.status_code != 200:

            print(
                "Amazon HTTP:",
                resposta.status_code
            )

            return None

        soup = BeautifulSoup(
            resposta.text,
            "lxml"
        )

        itens = soup.select(
            '[data-component-type="s-search-result"]'
        )

        for item in itens[:10]:

            titulo_tag = item.select_one(
                "h2"
            )

            link_tag = item.select_one(
                "h2 a"
            )

            if (
                not titulo_tag
                or
                not link_tag
            ):

                continue

            titulo = (
                titulo_tag
                .get_text(
                    " ",
                    strip=True
                )
            )

            href = link_tag.get(
                "href",
                ""
            )

            if not href:

                continue

            href = href.split(
                "?"
            )[0]

            link = (
                "https://www.amazon.com.br"
                +
                href
                +
                f"?tag={TAG_AMAZON}"
            )

            preco_tag = item.select_one(
                ".a-price .a-offscreen"
            )

            preco = None

            if preco_tag:

                preco = converter_preco(
                    preco_tag.get_text(
                        strip=True
                    )
                )

            imagem = None

            imagem_tag = item.select_one(
                "img.s-image"
            )

            if imagem_tag:

                imagem = (
                    imagem_tag.get(
                        "src"
                    )
                )

            return {

                "loja": "Amazon",

                "busca": busca,

                "titulo":
                    titulo[:150],

                "preco": preco,

                "link": link,

                "imagem": imagem

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

def buscar_mercado_livre(
    busca
):

    print(
        f"🟡 MERCADO LIVRE → {busca}"
    )

    try:

        url = (
            "https://lista.mercadolivre.com.br/"
            +
            requests.utils.quote(
                busca.replace(
                    " ",
                    "-"
                )
            )
        )

        resposta = SESSION.get(
            url,
            timeout=25
        )

        if resposta.status_code != 200:

            print(
                "Mercado Livre HTTP:",
                resposta.status_code
            )

            return None

        soup = BeautifulSoup(
            resposta.text,
            "lxml"
        )

        itens = soup.select(
            "li.ui-search-layout__item"
        )

        if not itens:

            itens = soup.select(
                ".ui-search-result"
            )

        for item in itens[:10]:

            titulo_tag = (
                item.select_one(
                    "h2"
                )
                or
                item.select_one(
                    ".poly-component__title"
                )
            )

            if not titulo_tag:

                continue

            titulo = (
                titulo_tag
                .get_text(
                    " ",
                    strip=True
                )
            )

            link_tag = item.select_one(
                "a"
            )

            if not link_tag:

                continue

            link = link_tag.get(
                "href",
                ""
            )

            if not link:

                continue

            preco = None

            preco_tag = (
                item.select_one(
                    ".andes-money-amount__fraction"
                )
                or
                item.select_one(
                    ".price-tag-fraction"
                )
            )

            if preco_tag:

                texto_preco = (
                    preco_tag
                    .get_text(
                        " ",
                        strip=True
                    )
                )

                centavos = (
                    item.select_one(
                        ".andes-money-amount__cents"
                    )
                )

                if centavos:

                    texto_preco += (
                        ","
                        +
                        centavos.get_text(
                            strip=True
                        )
                    )

                preco = converter_preco(
                    texto_preco
                )

            imagem = None

            imagem_tag = item.select_one(
                "img"
            )

            if imagem_tag:

                imagem = (
                    imagem_tag.get(
                        "src"
                    )
                    or
                    imagem_tag.get(
                        "data-src"
                    )
                )

            return {

                "loja":
                    "Mercado Livre",

                "busca":
                    busca,

                "titulo":
                    titulo[:150],

                "preco":
                    preco,

                "link":
                    link,

                "imagem":
                    imagem,

                "afiliado_base":
                    ML_AFILIADO

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

def buscar_shopee(
    busca
):

    print(
        f"🟠 SHOPEE → {busca}"
    )

    try:

        url = (
            "https://shopee.com.br/search?keyword="
            +
            requests.utils.quote(
                busca
            )
        )

        resposta = SESSION.get(
            url,
            timeout=25
        )

        if resposta.status_code != 200:

            print(
                "Shopee HTTP:",
                resposta.status_code
            )

            return {

                "loja": "Shopee",

                "busca": busca,

                "titulo": busca,

                "preco": None,

                "link": url,

                "imagem": None,

                "afiliado_base":
                    SHOPEE_AFILIADO,

                "vitrine":
                    SHOPEE_VITRINE

            }

        soup = BeautifulSoup(
            resposta.text,
            "lxml"
        )

        links = soup.select(
            'a[href*="-i."]'
        )

        for link_tag in links[:20]:

            href = link_tag.get(
                "href",
                ""
            )

            if not href:

                continue

            titulo = (
                link_tag
                .get_text(
                    " ",
                    strip=True
                )
            )

            if not titulo:

                titulo = busca

            if href.startswith(
                "/"
            ):

                link_produto = (
                    "https://shopee.com.br"
                    +
                    href
                )

            else:

                link_produto = href

            return {

                "loja":
                    "Shopee",

                "busca":
                    busca,

                "titulo":
                    titulo[:150],

                "preco":
                    None,

                "link":
                    link_produto,

                "imagem":
                    None,

                "afiliado_base":
                    SHOPEE_AFILIADO,

                "vitrine":
                    SHOPEE_VITRINE

            }

        return {

            "loja":
                "Shopee",

            "busca":
                busca,

            "titulo":
                busca,

            "preco":
                None,

            "link":
                url,

            "imagem":
                None,

            "afiliado_base":
                SHOPEE_AFILIADO,

            "vitrine":
                SHOPEE_VITRINE

        }

    except Exception as erro:

        print(
            "Erro Shopee:",
            erro
        )

        return None


# ============================================================
# BUSCAR TODAS
# ============================================================

def buscar_todas_lojas(
    busca
):

    resultados = []

    amazon = buscar_amazon(
        busca
    )

    if amazon:

        resultados.append(
            amazon
        )

    time.sleep(
        PAUSA_BUSCAS
    )

    mercado_livre = (
        buscar_mercado_livre(
            busca
        )
    )

    if mercado_livre:

        resultados.append(
            mercado_livre
        )

    time.sleep(
        PAUSA_BUSCAS
    )

    shopee = buscar_shopee(
        busca
    )

    if shopee:

        resultados.append(
            shopee
        )

    return resultados


# ============================================================
# MENOR PREÇO
# ============================================================

def encontrar_menor_preco(
    resultados
):

    produtos_com_preco = [

        produto

        for produto in resultados

        if produto.get(
            "preco"
        ) is not None

    ]

    if not produtos_com_preco:

        return None

    return min(
        produtos_com_preco,
        key=lambda produto:
            produto["preco"]
    )


# ============================================================
# BOTÕES TELEGRAM
# ============================================================

def criar_botoes(
    resultados
):

    botoes = []

    amazon = next(
        (
            x
            for x in resultados
            if x["loja"] == "Amazon"
        ),
        None
    )

    ml = next(
        (
            x
            for x in resultados
            if x["loja"] ==
            "Mercado Livre"
        ),
        None
    )

    shopee = next(
        (
            x
            for x in resultados
            if x["loja"] ==
            "Shopee"
        ),
        None
    )

    # --------------------------------------------
    # AMAZON
    # --------------------------------------------

    if amazon:

        botoes.append(
            InlineKeyboardButton(
                "🟠 AMAZON",
                url=amazon["link"]
            )
        )

    # --------------------------------------------
    # MERCADO LIVRE
    # --------------------------------------------

    if ml:

        botoes.append(
            InlineKeyboardButton(
                "🟡 MERCADO LIVRE",
                url=ml["link"]
            )
        )

    # --------------------------------------------
    # SHOPEE
    # --------------------------------------------

    if shopee:

        botoes.append(
            InlineKeyboardButton(
                "🟠 MINHA VITRINE SHOPEE",
                url=SHOPEE_VITRINE
            )
        )

    # --------------------------------------------
    # LINK DE AFILIADO SHOPEE
    # --------------------------------------------

    if shopee:

        botoes.append(
            InlineKeyboardButton(
                "🛍️ LINK SHOPEE",
                url=SHOPEE_AFILIADO
            )
        )

    # --------------------------------------------
    # ORGANIZAÇÃO DOS BOTÕES
    # --------------------------------------------

    teclado = []

    linha = []

    for botao in botoes:

        linha.append(
            botao
        )

        if len(linha) == 2:

            teclado.append(
                linha
            )

            linha = []

    if linha:

        teclado.append(
            linha
        )

    return InlineKeyboardMarkup(
        teclado
    )


# ============================================================
# MENSAGEM
# ============================================================

def montar_mensagem(
    busca,
    resultados,
    menor_preco
):

    linhas = []

    linhas.append(
        "🔥 *ACHADO DE CELULAR*"
    )

    linhas.append("")

    linhas.append(
        f"📱 *{busca.upper()}*"
    )

    linhas.append("")

    # AMAZON
    amazon = next(
        (
            x
            for x in resultados
            if x["loja"] ==
            "Amazon"
        ),
        None
    )

    if amazon:

        linhas.append(
            "🟠 *AMAZON*"
        )

        linhas.append(
            f"💰 "
            f"{formatar_preco(amazon['preco'])}"
        )

        linhas.append("")

    # MERCADO LIVRE
    ml = next(
        (
            x
            for x in resultados
            if x["loja"] ==
            "Mercado Livre"
        ),
        None
    )

    if ml:

        linhas.append(
            "🟡 *MERCADO LIVRE*"
        )

        linhas.append(
            f"💰 "
            f"{formatar_preco(ml['preco'])}"
        )

        linhas.append("")

    # SHOPEE
    shopee = next(
        (
            x
            for x in resultados
            if x["loja"] ==
            "Shopee"
        ),
        None
    )

    if shopee:

        linhas.append(
            "🟠 *SHOPEE*"
        )

        if shopee.get(
            "preco"
        ):

            linhas.append(
                f"💰 "
                f"{formatar_preco("
                    shopee['preco']
                )}"
            )

        else:

            linhas.append(
                "💰 Consulte na vitrine"
            )

        linhas.append("")

    # MENOR PREÇO
    if menor_preco:

        linhas.append(
            "🔥 *MENOR PREÇO "
            "IDENTIFICADO*"
        )

        linhas.append(
            f"🏷️ "
            f"{menor_preco['loja']}"
        )

        linhas.append(
            f"💰 "
            f"{formatar_preco("
                menor_preco['preco']
            )}"
        )

        linhas.append("")

    linhas.append(
        "👇 *ESCOLHA ONDE COMPRAR:*"
    )

    return "\n".join(
        linhas
    )


# ============================================================
# ENVIAR TELEGRAM
# ============================================================

async def enviar_telegram(
    bot,
    mensagem,
    botoes
):

    try:

        await bot.send_message(

            chat_id=CHAT_ID,

            text=mensagem,

            parse_mode=ParseMode.MARKDOWN,

            reply_markup=botoes,

            disable_web_page_preview=True

        )

        print(
            "📨 Oferta enviada "
            "com botões!"
        )

        return True

    except Exception as erro:

        print(
            "Erro Telegram:",
            erro
        )

        try:

            await bot.send_message(

                chat_id=CHAT_ID,

                text=mensagem,

                reply_markup=botoes,

                disable_web_page_preview=True

            )

            return True

        except Exception as erro2:

            print(
                "Erro Telegram final:",
                erro2
            )

            return False


# ============================================================
# REGISTRAR
# ============================================================

def registrar_produto(
    produto,
    produto_id,
    historico
):

    historico[
        produto_id
    ] = {

        "loja":
            produto["loja"],

        "titulo":
            produto["titulo"],

        "preco":
            produto["preco"],

        "link":
            produto["link"],

        "data":
            time.time()

    }

    if len(
        historico
    ) > 1500:

        historico = dict(
            list(
                historico.items()
            )[-1200:]
        )

    salvar_historico(
        historico
    )

    return historico


# ============================================================
# CICLO
# ============================================================

async def executar_ciclo(
    bot
):

    print("")
    print(
        "=" * 65
    )

    print(
        "🚀 PRICE RADAR V5.1"
    )

    print(
        "🔎 NOVO CICLO"
    )

    print(
        "=" * 65
    )

    historico = (
        carregar_historico()
    )

    enviados = 0

    for numero, busca in enumerate(
        BUSCAS,
        start=1
    ):

        print("")
        print(
            f"📱 [{numero}/"
            f"{len(BUSCAS)}] "
            f"{busca}"
        )

        try:

            resultados = (
                buscar_todas_lojas(
                    busca
                )
            )

            if not resultados:

                print(
                    "❌ Nada encontrado"
                )

                continue

            menor_preco = (
                encontrar_menor_preco(
                    resultados
                )
            )

            produto_referencia = (

                menor_preco
                if menor_preco
                else resultados[0]

            )

            produto_id = gerar_id(

                produto_referencia[
                    "loja"
                ],

                produto_referencia[
                    "titulo"
                ],

                produto_referencia[
                    "link"
                ]

            )

            if produto_id in historico:

                print(
                    "⏭️ Já enviado"
                )

                continue

            mensagem = (
                montar_mensagem(
                    busca,
                    resultados,
                    menor_preco
                )
            )

            botoes = (
                criar_botoes(
                    resultados
                )
            )

            enviado = (
                await enviar_telegram(
                    bot,
                    mensagem,
                    botoes
                )
            )

            if enviado:

                historico = (
                    registrar_produto(
                        produto_referencia,
                        produto_id,
                        historico
                    )
                )

                enviados += 1

            await asyncio.sleep(
                PAUSA_BUSCAS
            )

        except Exception as erro:

            print(
                f"❌ Erro em {busca}:",
                erro
            )

    print("")
    print(
        "=" * 65
    )

    print(
        f"📨 ENVIADOS: {enviados}"
    )

    print(
        f"🗂️ HISTÓRICO: "
        f"{len(historico)}"
    )

    print(
        "=" * 65
    )


# ============================================================
# BOT LOOP
# ============================================================

async def bot_loop():

    if not TOKEN:

        print(
            "❌ TOKEN DO TELEGRAM "
            "NÃO CONFIGURADO"
        )

        return

    if not CHAT_ID:

        print(
            "❌ CHAT_ID "
            "NÃO CONFIGURADO"
        )

        return

    bot = telegram.Bot(
        token=TOKEN
    )

    print("")
    print(
        "=========================================="
    )

    print(
        "📡 PRICE RADAR V5.1"
    )

    print(
        "=========================================="
    )

    print(
        "🟠 Amazon: ATIVA"
    )

    print(
        "🟡 Mercado Livre: ATIVO"
    )

    print(
        "🟠 Shopee: ATIVA"
    )

    print(
        "🔘 Botões Telegram: ATIVOS"
    )

    print(
        f"🏷️ Amazon: {TAG_AMAZON}"
    )

    print(
        f"🏪 Vitrine Shopee:"
        f" {SHOPEE_VITRINE}"
    )

    print(
        f"🔎 Modelos: "
        f"{len(BUSCAS)}"
    )

    print(
        "=========================================="
    )

    # --------------------------------------------
    # MENSAGEM DE ATIVAÇÃO
    # --------------------------------------------

    try:

        await bot.send_message(

            chat_id=CHAT_ID,

            text=(
                "🚀 *PRICE RADAR V5.1 "
                "ATIVADO!*\n\n"

                "📱 Amazon + Mercado Livre "
                "+ Shopee\n"

                f"🔎 {len(BUSCAS)} "
                "celulares monitorados\n"

                "🏷️ Links preparados\n"

                "🔘 Botões de compra "
                "ativados\n"

                "🏪 Sua vitrine Shopee "
                "integrada\n\n"

                "⚡ Radar procurando "
                "ofertas..."
            ),

            parse_mode=ParseMode.MARKDOWN

        )

    except Exception as erro:

        print(
            "Erro ativação:",
            erro
        )

    # --------------------------------------------
    # LOOP INFINITO
    # --------------------------------------------

    while True:

        try:

            await executar_ciclo(
                bot
            )

        except Exception as erro:

            print(
                "❌ Erro geral:",
                erro
            )

        horas = (
            INTERVALO_CICLO
            / 3600
        )

        print(
            f"😴 Próximo ciclo em "
            f"{horas:.1f} horas."
        )

        await asyncio.sleep(
            INTERVALO_CICLO
        )


# ============================================================
# THREAD
# ============================================================

def iniciar_bot():

    try:

        asyncio.run(
            bot_loop()
        )

    except Exception as erro:

        print(
            "❌ Erro fatal:",
            erro
        )


# ============================================================
# WEB
# ============================================================

def iniciar_web():

    porta = int(
        os.environ.get(
            "PORT",
            "10000"
        )
    )

    app.run(

        host="0.0.0.0",

        port=porta

    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    thread = threading.Thread(

        target=iniciar_bot,

        daemon=True

    )

    thread.start()

    iniciar_web()
