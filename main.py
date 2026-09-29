import os
import re
import json
import time
import threading
import traceback
import statistics
import unicodedata
from urllib.parse import quote, urljoin, urlparse, parse_qs, urlencode, urlunparse

import requests
from flask import Flask
from bs4 import BeautifulSoup


# ============================================================
# PRICE RADAR V6.2
#
# CELULARES POR MARCA
#
# Amazon
# Mercado Livre
# Shopee
# Magazine Luiza
# Casas Bahia
# KaBuM
#
# NOVO:
# - Link direto do produto
# - Foto do produto
# - Telegram envia foto + oferta
# - Botão abre o produto encontrado
# - Amazon recebe tag de afiliado
# - Fallback para mensagem sem foto
# ============================================================


APP_VERSION = "PRICE RADAR V6.2"

PORT = int(
    os.getenv(
        "PORT",
        "10000"
    )
)


# ============================================================
# TELEGRAM
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
# CONFIGURAÇÕES
# ============================================================

INTERVALO_CICLO = int(
    os.getenv(
        "INTERVALO_CICLO",
        "7200"
    )
)

DESCONTO_MINIMO = float(
    os.getenv(
        "DESCONTO_MINIMO",
        "0.20"
    )
)

TIMEOUT = int(
    os.getenv(
        "REQUEST_TIMEOUT",
        "20"
    )
)

ARQUIVO_HISTORICO = (
    "historico_precos.json"
)

ARQUIVO_ALERTAS = (
    "alertas_enviados.json"
)


# ============================================================
# HEADERS
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/140.0.0.0 "
        "Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/avif,"
        "image/webp,*/*;q=0.8"
    ),
    "Accept-Language": (
        "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
    ),
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}


# ============================================================
# MARCAS
# ============================================================

MARCAS = {

    "Samsung": [
        "Samsung Galaxy A",
        "Samsung Galaxy S",
        "Samsung Galaxy M",
        "Samsung Galaxy Z",
    ],

    "Motorola": [
        "Motorola Moto G",
        "Motorola Moto E",
        "Motorola Edge",
        "Motorola Razr",
    ],

    "Apple": [
        "Apple iPhone",
    ],

    "Xiaomi": [
        "Xiaomi Redmi",
        "Xiaomi Poco",
        "Xiaomi Redmi Note",
        "Xiaomi Poco X",
        "Xiaomi Poco M",
        "Xiaomi Poco F",
    ],
}


# ============================================================
# LOJAS
# ============================================================

LOJAS = [
    "Amazon",
    "Mercado Livre",
    "Shopee",
    "Magazine Luiza",
    "Casas Bahia",
    "KaBuM",
]


# ============================================================
# FLASK
# ============================================================

app = Flask(__name__)


ULTIMO_CICLO = {
    "inicio": None,
    "fim": None,
    "produtos": 0,
    "ofertas": 0,
    "alertas": 0,
    "erro": None,
}


LOCK = threading.Lock()


# ============================================================
# LOG
# ============================================================

def log(mensagem):

    print(
        f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
        f"{mensagem}",
        flush=True,
    )


# ============================================================
# JSON
# ============================================================

def carregar_json(
    caminho,
    padrao,
):

    try:

        if not os.path.exists(
            caminho
        ):
            return padrao

        with open(
            caminho,
            "r",
            encoding="utf-8",
        ) as arquivo:

            return json.load(
                arquivo
            )

    except Exception as erro:

        log(
            f"Erro lendo {caminho}: {erro}"
        )

        return padrao


def salvar_json(
    caminho,
    dados,
):

    try:

        temporario = (
            caminho + ".tmp"
        )

        with open(
            temporario,
            "w",
            encoding="utf-8",
        ) as arquivo:

            json.dump(
                dados,
                arquivo,
                ensure_ascii=False,
                indent=2,
            )

        os.replace(
            temporario,
            caminho,
        )

    except Exception as erro:

        log(
            f"Erro salvando {caminho}: {erro}"
        )


# ============================================================
# TEXTO
# ============================================================

def normalizar_texto(
    texto
):

    texto = str(
        texto or ""
    )

    texto = unicodedata.normalize(
        "NFKD",
        texto,
    )

    texto = "".join(
        c
        for c in texto
        if not unicodedata.combining(c)
    )

    texto = texto.lower()

    texto = re.sub(
        r"\s+",
        " ",
        texto,
    ).strip()

    return texto


# ============================================================
# PREÇO
# ============================================================

def converter_preco(
    valor
):

    if valor is None:
        return None

    texto = str(
        valor
    ).strip()

    texto = texto.replace(
        "\xa0",
        " ",
    )

    padroes = [

        r"R\$\s*([\d.]+,\d{2})",

        r"R\$\s*([\d]+,\d{2})",

        r"(?<!\d)"
        r"([\d.]+,\d{2})"
        r"(?!\d)",
    ]

    for padrao in padroes:

        resultado = re.search(
            padrao,
            texto,
            flags=re.I,
        )

        if not resultado:
            continue

        numero = resultado.group(
            1
        )

        numero = (
            numero
            .replace(
                ".",
                "",
            )
            .replace(
                ",",
                ".",
            )
        )

        try:

            preco = float(
                numero
            )

            if (
                100
                <= preco
                <= 100000
            ):
                return preco

        except ValueError:
            pass

    return None


def moeda(
    valor
):

    if valor is None:
        return "N/D"

    texto = f"{valor:,.2f}"

    texto = (
        texto
        .replace(
            ",",
            "X",
        )
        .replace(
            ".",
            ",",
        )
        .replace(
            "X",
            ".",
        )
    )

    return (
        f"R$ {texto}"
    )


# ============================================================
# CAPACIDADE
# ============================================================

def extrair_capacidade(
    texto
):

    texto = normalizar_texto(
        texto
    )

    encontrados = re.findall(
        r"(?<!\d)"
        r"(32|64|128|256|512|1024)"
        r"\s*gb\b",
        texto,
    )

    if encontrados:

        return (
            f"{encontrados[0]}GB"
        )

    encontrados_tb = re.findall(
        r"(?<!\d)"
        r"(1|2)"
        r"\s*tb\b",
        texto,
    )

    if encontrados_tb:

        return (
            f"{encontrados_tb[0]}TB"
        )

    return ""


# ============================================================
# MODELO
# ============================================================

def normalizar_modelo(
    titulo
):

    texto = normalizar_texto(
        titulo
    )

    capacidade = (
        extrair_capacidade(
            texto
        )
    )

    modelo = ""


    # --------------------------------------------------------
    # APPLE
    # --------------------------------------------------------

    match = re.search(
        r"\biphone\s*"
        r"(\d{1,2}"
        r"(?:\s*"
        r"(?:pro max|pro|plus|mini|e)"
        r")?)",
        texto,
        flags=re.I,
    )

    if match:

        modelo = (
            "iPhone "
            + re.sub(
                r"\s+",
                " ",
                match.group(1),
            ).strip()
        )


    # --------------------------------------------------------
    # SAMSUNG
    # --------------------------------------------------------

    if not modelo:

        match = re.search(
            r"\bgalaxy\s+"
            r"([asmzf]\s*\d{1,3}"
            r"(?:\s*"
            r"(?:5g|4g|fe|ultra|plus|\+)"
            r")*)",
            texto,
            flags=re.I,
        )

        if match:

            modelo = (
                "Galaxy "
                + re.sub(
                    r"\s+",
                    " ",
                    match.group(1),
                ).strip()
            )


    # --------------------------------------------------------
    # MOTOROLA
    # --------------------------------------------------------

    if not modelo:

        match = re.search(
            r"\b("
            r"moto\s+[a-z]?\s*\d{1,3}"
            r"|edge\s+\d{1,3}"
            r"|razr\s+\d{1,2}"
            r")",
            texto,
            flags=re.I,
        )

        if match:

            modelo = re.sub(
                r"\s+",
                " ",
                match.group(1),
            ).strip().title()


    # --------------------------------------------------------
    # XIAOMI
    # --------------------------------------------------------

    if not modelo:

        match = re.search(
            r"\b("
            r"redmi\s+note\s+\d+[a-z]*"
            r"|redmi\s+\d+[a-z]*"
            r"|poco\s+[a-z]+\s*\d+[a-z]*"
            r"|poco\s+\d+[a-z]*"
            r")",
            texto,
            flags=re.I,
        )

        if match:

            modelo = re.sub(
                r"\s+",
                " ",
                match.group(1),
            ).strip().title()


    # --------------------------------------------------------
    # FALLBACK
    # --------------------------------------------------------

    if not modelo:

        modelo = normalizar_texto(
            titulo
        )

    if capacidade:

        return (
            f"{modelo} "
            f"{capacidade}"
        ).strip()

    return modelo.strip()


# ============================================================
# MARCA
# ============================================================

def detectar_marca(
    titulo
):

    texto = normalizar_texto(
        titulo
    )

    if "iphone" in texto:
        return "Apple"

    if (
        "samsung" in texto
        or "galaxy" in texto
    ):
        return "Samsung"

    if (
        "motorola" in texto
        or "moto g" in texto
        or "moto e" in texto
        or "edge " in texto
    ):
        return "Motorola"

    if (
        "xiaomi" in texto
        or "redmi" in texto
        or "poco" in texto
    ):
        return "Xiaomi"

    return None


# ============================================================
# URLS DE PESQUISA
# ============================================================

def url_amazon(
    busca
):

    return (
        "https://www.amazon.com.br/s?k="
        + quote(busca)
        + "&tag="
        + quote(TAG_AMAZON)
    )


def url_ml(
    busca
):

    return (
        "https://lista.mercadolivre.com.br/"
        + quote(busca)
    )


def url_shopee(
    busca
):

    return (
        "https://shopee.com.br/search?keyword="
        + quote(busca)
    )


def url_magalu(
    busca
):

    return (
        "https://www.magazineluiza.com.br/"
        "?s="
        + quote(busca)
    )


def url_casas_bahia(
    busca
):

    return (
        "https://www.casasbahia.com.br/"
        "busca/"
        + quote(busca)
    )


def url_kabum(
    busca
):

    return (
        "https://www.kabum.com.br/"
        "busca/"
        + quote(busca)
    )


# ============================================================
# URL
# ============================================================

def link_valido(
    url
):

    if not url:
        return False

    url = str(
        url
    ).strip()

    return (
        url.startswith(
            "http://"
        )
        or url.startswith(
            "https://"
        )
    )


def limpar_url(
    url
):

    if not link_valido(
        url
    ):
        return None

    return str(
        url
    ).strip()


def url_mesmo_dominio(
    url,
    dominios
):

    try:

        host = urlparse(
            url
        ).netloc.lower()

        return any(
            dominio in host
            for dominio in dominios
        )

    except Exception:
        return False


# ============================================================
# IMAGEM
# ============================================================

def imagem_valida(
    url
):

    if not link_valido(
        url
    ):
        return False

    texto = url.lower()

    if (
        texto.startswith(
            "data:"
        )
    ):
        return False

    if (
        ".svg" in texto
        or "logo" in texto
        or "icon" in texto
        or "sprite" in texto
        or "avatar" in texto
    ):
        return False

    return True


def extrair_imagem_elemento(
    elemento,
    base_url
):

    if not elemento:
        return None

    atributos = [

        "src",

        "data-src",

        "data-original",

        "data-lazy-src",

        "data-image",

        "data-image-url",

        "data-srcset",

        "srcset",
    ]

    for atributo in atributos:

        valor = elemento.get(
            atributo
        )

        if not valor:
            continue

        # srcset pode conter várias URLs
        if (
            "srcset" in atributo
            or "," in valor
        ):

            partes = [
                p.strip()
                for p in valor.split(",")
                if p.strip()
            ]

            if partes:

                valor = (
                    partes[-1]
                    .split(" ")[0]
                )

        valor = valor.strip()

        if valor.startswith(
            "//"
        ):

            valor = (
                "https:"
                + valor
            )

        url = urljoin(
            base_url,
            valor,
        )

        if imagem_valida(
            url
        ):
            return url

    return None


def extrair_imagem_card(
    bloco,
    base_url
):

    if not bloco:
        return None

    # Primeiro procura imagens próximas
    imagens = bloco.select(
        "img"
    )

    for img in imagens:

        url = extrair_imagem_elemento(
            img,
            base_url,
        )

        if url:
            return url


    # Depois procura elementos com background
    elementos = bloco.select(
        "[style*='background-image']"
    )

    for elemento in elementos:

        style = elemento.get(
            "style",
            "",
        )

        match = re.search(
            r"url\(['\"]?(.*?)['\"]?\)",
            style,
            flags=re.I,
        )

        if not match:
            continue

        url = urljoin(
            base_url,
            match.group(1),
        )

        if imagem_valida(
            url
        ):
            return url

    return None


def extrair_og_image(
    soup,
    base_url
):

    if not soup:
        return None

    meta = soup.select_one(
        'meta[property="og:image"]'
    )

    if not meta:

        meta = soup.select_one(
            'meta[name="twitter:image"]'
        )

    if not meta:
        return None

    valor = meta.get(
        "content"
    )

    if not valor:
        return None

    url = urljoin(
        base_url,
        valor,
    )

    if imagem_valida(
        url
    ):
        return url

    return None


# ============================================================
# PRODUTO PADRÃO
# ============================================================

def criar_oferta(
    loja,
    titulo,
    preco,
    url,
    imagem=None,
):

    if (
        not titulo
        or preco is None
    ):
        return None

    marca = detectar_marca(
        titulo
    )

    if not marca:
        return None

    modelo = normalizar_modelo(
        titulo
    )

    if not modelo:
        return None

    return {

        "loja": loja,

        "titulo": titulo.strip(),

        "marca": marca,

        "modelo": modelo,

        "preco": round(
            float(preco),
            2,
        ),

        "url": limpar_url(
            url
        ),

        "imagem": (
            limpar_url(imagem)
            if imagem
            else None
        ),

        "timestamp": int(
            time.time()
        ),
    }


# ============================================================
# HTTP
# ============================================================

def requisitar(
    url
):

    try:

        resposta = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT,
            allow_redirects=True,
        )

        if resposta.status_code != 200:

            log(
                f"HTTP "
                f"{resposta.status_code}: "
                f"{url}"
            )

            return None

        return resposta.text

    except Exception as erro:

        log(
            f"Erro HTTP "
            f"{url}: {erro}"
        )

        return None


# ============================================================
# LINK DIRETO DO PRODUTO
# ============================================================

def escolher_link_produto(
    bloco,
    loja,
    url_base,
):

    if not bloco:
        return None

    candidatos = bloco.select(
        "a[href]"
    )

    if not candidatos:
        return None

    bloqueados = [

        "/login",

        "/cadastro",

        "/account",

        "/conta",

        "/ajuda",

        "/atendimento",

        "/busca",

        "/search",

        "/ofertas",

        "/categoria",

        "/categorias",

        "/departamento",

        "/departamentos",

        "/home",

        "/sair",

        "javascript:",

        "#",
    ]

    candidatos_avaliados = []


    for a in candidatos:

        href = (
            a.get(
                "href",
                ""
            )
            .strip()
        )

        if not href:
            continue

        href_lower = (
            href.lower()
        )

        if any(
            item in href_lower
            for item in bloqueados
        ):
            continue

        link = urljoin(
            url_base,
            href,
        )

        if not link_valido(
            link
        ):
            continue

        texto = a.get_text(
            " ",
            strip=True,
        )

        score = 0


        # ----------------------------------------------------
        # TEXTO
        # ----------------------------------------------------

        if len(texto) >= 15:
            score += 2

        if len(texto) >= 30:
            score += 1


        # ----------------------------------------------------
        # LOJAS
        # ----------------------------------------------------

        if loja == "Amazon":

            if (
                "/dp/"
                in link.lower()
            ):
                score += 20

            if (
                "/gp/product/"
                in link.lower()
            ):
                score += 20


        elif loja == "Mercado Livre":

            if (
                "/mlb-"
                in link.lower()
            ):
                score += 20

            if (
                "produto.mercadolivre"
                in link.lower()
            ):
                score += 15


        elif loja == "Shopee":

            if (
                "/product/"
                in link.lower()
            ):
                score += 20

            if (
                "/universal-link/"
                in link.lower()
            ):
                score += 10


        elif loja == "Magazine Luiza":

            if (
                "/p/"
                in link.lower()
            ):
                score += 20

            if (
                "/produto/"
                in link.lower()
            ):
                score += 15


        elif loja == "Casas Bahia":

            if (
                "/p/"
                in link.lower()
            ):
                score += 20

            if (
                "/produto/"
                in link.lower()
            ):
                score += 15


        elif loja == "KaBuM":

            if (
                "/produto/"
                in link.lower()
            ):
                score += 20


        # ----------------------------------------------------
        # URL LONGA
        # ----------------------------------------------------

        if len(link) > 60:
            score += 1


        candidatos_avaliados.append(
            (
                score,
                link,
            )
        )


    if not candidatos_avaliados:
        return None


    candidatos_avaliados.sort(
        key=lambda x: x[0],
        reverse=True,
    )


    return candidatos_avaliados[0][1]


# ============================================================
# AMAZON
# ============================================================

def buscar_amazon(
    busca
):

    url = url_amazon(
        busca
    )

    html = requisitar(
        url
    )

    if not html:
        return []

    soup = BeautifulSoup(
        html,
        "lxml",
    )

    ofertas = []


    itens = soup.select(
        '[data-component-type="s-search-result"]'
    )


    for item in itens:

        try:

            titulo_el = item.select_one(
                "h2 span"
            )

            preco_el = (
                item.select_one(
                    ".a-price .a-offscreen"
                )
                or item.select_one(
                    ".a-price-whole"
                )
            )

            link_el = item.select_one(
                "h2 a"
            )

            imagem_el = item.select_one(
                "img.s-image"
            )

            if (
                not titulo_el
                or not preco_el
                or not link_el
            ):
                continue


            titulo = titulo_el.get_text(
                " ",
                strip=True,
            )


            preco = converter_preco(
                preco_el.get_text(
                    " ",
                    strip=True,
                )
            )


            if preco is None:

                preco = converter_preco(
                    item.get_text(
                        " ",
                        strip=True,
                    )
                )


            href = link_el.get(
                "href",
                "",
            )

            if not href:
                continue


            link = urljoin(
                "https://www.amazon.com.br",
                href,
            )


            if not link_valido(
                link
            ):
                continue


            imagem = (
                extrair_imagem_elemento(
                    imagem_el,
                    "https://www.amazon.com.br",
                )
                if imagem_el
                else None
            )


            oferta = criar_oferta(
                "Amazon",
                titulo,
                preco,
                link,
                imagem,
            )


            if oferta:

                ofertas.append(
                    oferta
                )


        except Exception:

            continue


    return ofertas


# ============================================================
# MERCADO LIVRE
# ============================================================

def buscar_ml(
    busca
):

    url = url_ml(
        busca
    )

    html = requisitar(
        url
    )

    if not html:
        return []

    soup = BeautifulSoup(
        html,
        "lxml",
    )

    ofertas = []


    itens = soup.select(
        "li.ui-search-layout__item"
    )


    for item in itens:

        try:

            titulo_el = (

                item.select_one(
                    "a.poly-component__title"
                )

                or item.select_one(
                    ".ui-search-item__title"
                )

                or item.select_one(
                    "h2"
                )
            )


            preco_el = (

                item.select_one(
                    ".andes-money-amount__fraction"
                )

                or item.select_one(
                    ".ui-search-price__part "
                    ".andes-money-amount__fraction"
                )
            )


            if not titulo_el:
                continue


            titulo = titulo_el.get_text(
                " ",
                strip=True,
            )


            preco = None


            if preco_el:

                preco = converter_preco(
                    preco_el.get_text(
                        " ",
                        strip=True,
                    )
                )


            if preco is None:

                preco = converter_preco(
                    item.get_text(
                        " ",
                        strip=True,
                    )
                )


            link = escolher_link_produto(
                item,
                "Mercado Livre",
                "https://lista.mercadolivre.com.br",
            )


            if not link:
                continue


            imagem = extrair_imagem_card(
                item,
                "https://lista.mercadolivre.com.br",
            )


            oferta = criar_oferta(
                "Mercado Livre",
                titulo,
                preco,
                link,
                imagem,
            )


            if oferta:

                ofertas.append(
                    oferta
                )


        except Exception:

            continue


    return ofertas


# ============================================================
# SHOPEE
# ============================================================

def buscar_shopee(
    busca
):

    url = url_shopee(
        busca
    )

    html = requisitar(
        url
    )

    if not html:
        return []

    soup = BeautifulSoup(
        html,
        "lxml",
    )

    ofertas = []


    # --------------------------------------------------------
    # PRIMEIRA TENTATIVA:
    # cards com links
    # --------------------------------------------------------

    links = soup.select(
        "a[href]"
    )


    vistos = set()


    for link_el in links:

        try:

            href = link_el.get(
                "href",
                "",
            )

            if not href:
                continue


            link = urljoin(
                "https://shopee.com.br",
                href,
            )


            if (
                "/product/"
                not in link.lower()
                and "/universal-link/"
                not in link.lower()
            ):
                continue


            texto = link_el.get_text(
                " ",
                strip=True,
            )


            if len(texto) < 8:
                continue


            preco = converter_preco(
                texto
            )


            if preco is None:

                continue


            if not detectar_marca(
                texto
            ):
                continue


            chave = (
                link
                + "|"
                + texto[:100]
            )


            if chave in vistos:
                continue


            vistos.add(
                chave
            )


            imagem = extrair_imagem_card(
                link_el,
                "https://shopee.com.br",
            )


            titulo = texto[:220]


            oferta = criar_oferta(
                "Shopee",
                titulo,
                preco,
                link,
                imagem,
            )


            if oferta:

                ofertas.append(
                    oferta
                )


        except Exception:

            continue


    return ofertas


# ============================================================
# LOJAS GENÉRICAS
# ============================================================

def buscar_loja_generica(
    loja,
    busca,
    url,
):

    html = requisitar(
        url
    )

    if not html:
        return []

    soup = BeautifulSoup(
        html,
        "lxml",
    )

    ofertas = []


    candidatos = soup.select(
        "article, li, div"
    )


    limite = 500


    for bloco in candidatos:

        if len(ofertas) >= limite:
            break


        try:

            texto = bloco.get_text(
                " ",
                strip=True,
            )


            if not texto:
                continue


            if "R$" not in texto:
                continue


            if len(texto) < 20:
                continue


            if len(texto) > 1000:
                continue


            if not detectar_marca(
                texto
            ):
                continue


            preco = converter_preco(
                texto
            )


            if preco is None:
                continue


            if (
                preco < 200
                or preco > 100000
            ):
                continue


            link = escolher_link_produto(
                bloco,
                loja,
                url,
            )


            if not link:
                continue


            imagem = extrair_imagem_card(
                bloco,
                url,
            )


            titulo_el = (

                bloco.select_one(
                    "h1"
                )

                or bloco.select_one(
                    "h2"
                )

                or bloco.select_one(
                    "h3"
                )

                or bloco.select_one(
                    "[class*='title']"
                )

                or bloco.select_one(
                    "[class*='name']"
                )
            )


            if titulo_el:

                titulo = titulo_el.get_text(
                    " ",
                    strip=True,
                )

            else:

                titulo = texto[:300]


            oferta = criar_oferta(
                loja,
                titulo,
                preco,
                link,
                imagem,
            )


            if oferta:

                ofertas.append(
                    oferta
                )


        except Exception:

            continue


    return ofertas


# ============================================================
# BUSCAR TODAS AS LOJAS
# ============================================================

def buscar_todas_as_lojas():

    ofertas = []


    for marca, buscas in MARCAS.items():

        for busca in buscas:

            log(
                f"Buscando: {busca}"
            )


            funcoes = [

                (
                    "Amazon",
                    buscar_amazon,
                ),

                (
                    "Mercado Livre",
                    buscar_ml,
                ),

                (
                    "Shopee",
                    buscar_shopee,
                ),

                (
                    "Magazine Luiza",
                    lambda q:
                    buscar_loja_generica(
                        "Magazine Luiza",
                        q,
                        url_magalu(q),
                    ),
                ),

                (
                    "Casas Bahia",
                    lambda q:
                    buscar_loja_generica(
                        "Casas Bahia",
                        q,
                        url_casas_bahia(q),
                    ),
                ),

                (
                    "KaBuM",
                    lambda q:
                    buscar_loja_generica(
                        "KaBuM",
                        q,
                        url_kabum(q),
                    ),
                ),
            ]


            for loja, funcao in funcoes:

                try:

                    encontrados = funcao(
                        busca
                    )


                    if encontrados:

                        log(
                            f"{loja}: "
                            f"{len(encontrados)} "
                            f"ofertas"
                        )


                    ofertas.extend(
                        encontrados
                    )


                except Exception as erro:

                    log(
                        f"Erro {loja}: "
                        f"{erro}"
                    )


    return ofertas


# ============================================================
# DEDUPLICAÇÃO
# ============================================================

def chave_oferta(
    oferta
):

    return (

        normalizar_texto(
            oferta.get(
                "loja",
                "",
            )
        ),

        normalizar_texto(
            oferta.get(
                "modelo",
                "",
            )
        ),

        round(
            float(
                oferta.get(
                    "preco",
                    0,
                )
            ),
            2,
        ),

        normalizar_texto(
            oferta.get(
                "url",
                "",
            )
        ),
    )


def deduplicar_ofertas(
    ofertas
):

    resultado = []

    vistos = set()


    for oferta in ofertas:

        chave = chave_oferta(
            oferta
        )


        if chave in vistos:
            continue


        vistos.add(
            chave
        )

        resultado.append(
            oferta
        )


    return resultado


# ============================================================
# AGRUPAMENTO
# ============================================================

def agrupar_por_modelo(
    ofertas
):

    grupos = {}


    for oferta in ofertas:

        modelo = oferta.get(
            "modelo"
        )


        if not modelo:
            continue


        chave = normalizar_texto(
            modelo
        )


        grupos.setdefault(
            chave,
            [],
        ).append(
            oferta
        )


    return grupos


# ============================================================
# REFERÊNCIA
# ============================================================

def calcular_referencia(
    grupo
):

    precos = [

        float(
            item["preco"]
        )

        for item in grupo

        if item.get(
            "preco"
        ) is not None

        and float(
            item["preco"]
        ) > 0
    ]


    if len(precos) < 2:
        return None


    return statistics.median(
        precos
    )


# ============================================================
# OPORTUNIDADES
# ============================================================

def encontrar_ofertas_desconto(
    ofertas
):

    grupos = agrupar_por_modelo(
        ofertas
    )

    oportunidades = []


    for _, grupo in grupos.items():

        referencia = calcular_referencia(
            grupo
        )


        if referencia is None:
            continue


        for oferta in grupo:

            preco = float(
                oferta["preco"]
            )


            desconto = (
                1
                - (
                    preco
                    / referencia
                )
            )


            if (
                desconto
                >= DESCONTO_MINIMO
            ):

                item = dict(
                    oferta
                )


                item["referencia"] = round(
                    referencia,
                    2,
                )


                item["desconto"] = round(
                    desconto * 100,
                    1,
                )


                oportunidades.append(
                    item
                )


    oportunidades.sort(
        key=lambda x: (
            -x["desconto"],
            x["preco"],
        )
    )


    return oportunidades


# ============================================================
# LINKS DE AFILIADO
# ============================================================

def link_amazon(
    oferta
):

    url = limpar_url(
        oferta.get(
            "url"
        )
    )


    if not url:

        return url_amazon(
            oferta.get(
                "titulo",
                "",
            )
        )


    # Remove tag antiga
    url = re.sub(
        r"([?&])tag=[^&]+",
        "",
        url,
        flags=re.I,
    )


    # Limpa ? ou & sobrando
    url = url.rstrip(
        "?&"
    )


    separador = (
        "&"
        if "?" in url
        else "?"
    )


    return (
        url
        + separador
        + "tag="
        + quote(
            TAG_AMAZON
        )
    )


def link_mercado_livre(
    oferta
):

    url = limpar_url(
        oferta.get(
            "url"
        )
    )


    return (
        url
        or ML_AFILIADO
    )


def link_shopee(
    oferta
):

    url = limpar_url(
        oferta.get(
            "url"
        )
    )


    return (
        url
        or SHOPEE_AFILIADO
    )


# ============================================================
# BOTÕES
# ============================================================

def montar_botoes(
    oferta
):

    url_original = limpar_url(
        oferta.get(
            "url"
        )
    )


    if not url_original:
        return []


    loja = oferta.get(
        "loja",
        "",
    )


    botoes = []


    # --------------------------------------------------------
    # BOTÃO PRINCIPAL
    # --------------------------------------------------------

    if loja == "Amazon":

        botoes.append(
            [
                {
                    "text":
                    "🛒 COMPRAR OFERTA",
                    "url":
                    link_amazon(
                        oferta
                    ),
                }
            ]
        )

    else:

        botoes.append(
            [
                {
                    "text":
                    "🛒 ABRIR OFERTA",
                    "url":
                    url_original,
                }
            ]
        )


    # --------------------------------------------------------
    # AFILIADOS
    # --------------------------------------------------------

    if loja == "Mercado Livre":

        botoes.append(
            [
                {
                    "text":
                    "🟡 Link afiliado ML",
                    "url":
                    ML_AFILIADO,
                }
            ]
        )


    elif loja == "Shopee":

        botoes.append(
            [
                {
                    "text":
                    "🟠 Link afiliado Shopee",
                    "url":
                    SHOPEE_AFILIADO,
                }
            ]
        )


    return botoes


# ============================================================
# MENSAGEM
# ============================================================

def montar_mensagem(
    oferta
):

    loja = oferta.get(
        "loja",
        "N/D",
    )

    modelo = oferta.get(
        "modelo",
        "Produto",
    )

    preco = oferta.get(
        "preco"
    )

    referencia = oferta.get(
        "referencia"
    )

    desconto = oferta.get(
        "desconto",
        0,
    )


    texto = (

        "🔥 <b>OFERTA ENCONTRADA!</b>\n\n"

        f"📱 <b>{modelo}</b>\n"

        f"🏪 {loja}\n"

        f"💰 <b>{moeda(preco)}</b>\n"

        f"📊 Referência: "
        f"{moeda(referencia)}\n"

        f"📉 Desconto: "
        f"<b>{desconto:.1f}%</b>\n\n"

        "👇 <b>Produto encontrado "
        "pelo Radar</b>"
    )


    return texto


# ============================================================
# TELEGRAM - ENVIO DE TEXTO
# ============================================================

def telegram_enviar_texto(
    texto,
    botoes=None,
):

    if not TELEGRAM_TOKEN:

        log(
            "TELEGRAM_TOKEN não configurado."
        )

        return False


    if not CHAT_ID:

        log(
            "CHAT_ID não configurado."
        )

        return False


    url = (
        "https://api.telegram.org/bot"
        + TELEGRAM_TOKEN
        + "/sendMessage"
    )


    dados = {

        "chat_id":
        CHAT_ID,

        "text":
        texto,

        "parse_mode":
        "HTML",

        "disable_web_page_preview":
        False,
    }


    if botoes:

        dados[
            "reply_markup"
        ] = json.dumps(
            {
                "inline_keyboard":
                botoes
            },
            ensure_ascii=False,
        )


    try:

        resposta = requests.post(
            url,
            data=dados,
            timeout=20,
        )


        if resposta.status_code != 200:

            log(
                "Telegram HTTP "
                f"{resposta.status_code}: "
                f"{resposta.text[:500]}"
            )

            return False


        retorno = resposta.json()


        if not retorno.get(
            "ok"
        ):

            log(
                f"Telegram erro: "
                f"{retorno}"
            )

            return False


        return True


    except Exception as erro:

        log(
            f"Erro Telegram: "
            f"{erro}"
        )

        return False


# ============================================================
# TELEGRAM - FOTO + BOTÃO
# ============================================================

def telegram_enviar_foto(
    foto,
    legenda,
    botoes=None,
):

    if not TELEGRAM_TOKEN:

        log(
            "TELEGRAM_TOKEN não configurado."
        )

        return False


    if not CHAT_ID:

        log(
            "CHAT_ID não configurado."
        )

        return False


    if not imagem_valida(
        foto
    ):

        return False


    url = (
        "https://api.telegram.org/bot"
        + TELEGRAM_TOKEN
        + "/sendPhoto"
    )


    dados = {

        "chat_id":
        CHAT_ID,

        "photo":
        foto,

        "caption":
        legenda,

        "parse_mode":
        "HTML",

        "disable_notification":
        False,
    }


    if botoes:

        dados[
            "reply_markup"
        ] = json.dumps(
            {
                "inline_keyboard":
                botoes
            },
            ensure_ascii=False,
        )


    try:

        resposta = requests.post(
            url,
            data=dados,
            timeout=30,
        )


        if resposta.status_code != 200:

            log(
                "Telegram sendPhoto HTTP "
                f"{resposta.status_code}: "
                f"{resposta.text[:500]}"
            )

            return False


        retorno = resposta.json()


        if not retorno.get(
            "ok"
        ):

            log(
                "Telegram sendPhoto erro: "
                f"{retorno}"
            )

            return False


        return True


    except Exception as erro:

        log(
            f"Erro Telegram foto: "
            f"{erro}"
        )

        return False


# ============================================================
# TELEGRAM - ENVIO INTELIGENTE
# ============================================================

def telegram_enviar_oferta(
    oferta
):

    mensagem = montar_mensagem(
        oferta
    )

    botoes = montar_botoes(
        oferta
    )

    imagem = limpar_url(
        oferta.get(
            "imagem"
        )
    )


    # --------------------------------------------------------
    # PRIMEIRO TENTA FOTO
    # --------------------------------------------------------

    if imagem:

        sucesso = telegram_enviar_foto(
            imagem,
            mensagem,
            botoes,
        )


        if sucesso:

            log(
                "Oferta enviada com FOTO: "
                f"{oferta.get('modelo')} | "
                f"{oferta.get('loja')}"
            )

            return True


        log(
            "Foto falhou. "
            "Tentando mensagem normal."
        )


    # --------------------------------------------------------
    # FALLBACK
    # --------------------------------------------------------

    sucesso = telegram_enviar_texto(
        mensagem,
        botoes,
    )


    if sucesso:

        log(
            "Oferta enviada sem foto: "
            f"{oferta.get('modelo')} | "
            f"{oferta.get('loja')}"
        )


    return sucesso


# ============================================================
# ANTI-SPAM
# ============================================================

def chave_alerta(
    oferta
):

    return (

        normalizar_texto(
            oferta.get(
                "modelo",
                "",
            )
        )

        + "|"

        + normalizar_texto(
            oferta.get(
                "loja",
                "",
            )
        )

        + "|"

        + str(
            round(
                float(
                    oferta.get(
                        "preco",
                        0,
                    )
                ),
                2,
            )
        )
    )


def pode_enviar_alerta(
    oferta,
    alertas,
):

    chave = chave_alerta(
        oferta
    )

    agora = int(
        time.time()
    )


    ultimo = alertas.get(
        chave
    )


    if ultimo:

        if (
            agora
            - int(ultimo)
            < 12 * 60 * 60
        ):

            return False


    alertas[chave] = agora


    return True


# ============================================================
# LIMPEZA DOS ALERTAS ANTIGOS
# ============================================================

def limpar_alertas_antigos(
    alertas
):

    agora = int(
        time.time()
    )

    limite = (
        7 * 24 * 60 * 60
    )


    resultado = {}


    for chave, timestamp in alertas.items():

        try:

            if (
                agora
                - int(timestamp)
                <= limite
            ):

                resultado[
                    chave
                ] = timestamp

        except Exception:

            continue


    return resultado


# ============================================================
# CICLO
# ============================================================

def executar_ciclo():

    inicio = time.time()


    with LOCK:

        ULTIMO_CICLO[
            "inicio"
        ] = time.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        ULTIMO_CICLO[
            "erro"
        ] = None

        ULTIMO_CICLO[
            "produtos"
        ] = 0

        ULTIMO_CICLO[
            "ofertas"
        ] = 0

        ULTIMO_CICLO[
            "alertas"
        ] = 0


    try:

        log(
            "=" * 60
        )

        log(
            f"{APP_VERSION} - "
            "INICIANDO CICLO"
        )


        # ----------------------------------------------------
        # BUSCA
        # ----------------------------------------------------

        ofertas = (
            buscar_todas_as_lojas()
        )


        log(
            f"Busca bruta: "
            f"{len(ofertas)} ofertas"
        )


        # ----------------------------------------------------
        # DEDUPLICA
        # ----------------------------------------------------

        ofertas = (
            deduplicar_ofertas(
                ofertas
            )
        )


        log(
            f"Após deduplicação: "
            f"{len(ofertas)} ofertas"
        )


        # ----------------------------------------------------
        # OPORTUNIDADES
        # ----------------------------------------------------

        oportunidades = (
            encontrar_ofertas_desconto(
                ofertas
            )
        )


        log(
            f"Oportunidades: "
            f"{len(oportunidades)}"
        )


        # ----------------------------------------------------
        # HISTÓRICO
        # ----------------------------------------------------

        historico = carregar_json(
            ARQUIVO_HISTORICO,
            [],
        )


        alertas = carregar_json(
            ARQUIVO_ALERTAS,
            {},
        )


        if not isinstance(
            historico,
            list
        ):

            historico = []


        if not isinstance(
            alertas,
            dict
        ):

            alertas = {}


        # ----------------------------------------------------
        # SALVA HISTÓRICO
        # ----------------------------------------------------

        historico.extend(

            [

                {
                    "timestamp":
                    item.get(
                        "timestamp"
                    ),

                    "loja":
                    item.get(
                        "loja"
                    ),

                    "modelo":
                    item.get(
                        "modelo"
                    ),

                    "preco":
                    item.get(
                        "preco"
                    ),

                    "url":
                    item.get(
                        "url"
                    ),

                    "imagem":
                    item.get(
                        "imagem"
                    ),
                }

                for item in ofertas
            ]
        )


        if len(
            historico
        ) > 10000:

            historico = (
                historico[-10000:]
            )


        salvar_json(
            ARQUIVO_HISTORICO,
            historico,
        )


        # ----------------------------------------------------
        # LIMPA ALERTAS
        # ----------------------------------------------------

        alertas = (
            limpar_alertas_antigos(
                alertas
            )
        )


        # ----------------------------------------------------
        # ENVIA
        # ----------------------------------------------------

        enviados = 0


        for oferta in oportunidades:

            if not pode_enviar_alerta(
                oferta,
                alertas,
            ):
                continue


            sucesso = (
                telegram_enviar_oferta(
                    oferta
                )
            )


            if sucesso:

                enviados += 1


            time.sleep(
                1
            )


        # ----------------------------------------------------
        # SALVA ALERTAS
        # ----------------------------------------------------

        salvar_json(
            ARQUIVO_ALERTAS,
            alertas,
        )


        # ----------------------------------------------------
        # FINAL
        # ----------------------------------------------------

        fim = time.time()


        modelos = set(

            item["modelo"]

            for item in ofertas

            if item.get(
                "modelo"
            )
        )


        with LOCK:

            ULTIMO_CICLO[
                "fim"
            ] = time.strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            ULTIMO_CICLO[
                "produtos"
            ] = len(
                modelos
            )

            ULTIMO_CICLO[
                "ofertas"
            ] = len(
                ofertas
            )

            ULTIMO_CICLO[
                "alertas"
            ] = enviados


        log(
            f"Ciclo finalizado em "
            f"{fim - inicio:.1f}s | "
            f"ofertas={len(ofertas)} | "
            f"oportunidades="
            f"{len(oportunidades)} | "
            f"alertas={enviados}"
        )


    except Exception as erro:

        log(
            "ERRO NO CICLO:"
        )

        log(
            traceback.format_exc()
        )


        with LOCK:

            ULTIMO_CICLO[
                "erro"
            ] = str(
                erro
            )


# ============================================================
# THREAD
# ============================================================

def radar_loop():

    log(
        f"{APP_VERSION} - "
        "thread do radar iniciada."
    )


    while True:

        try:

            executar_ciclo()


        except Exception:

            log(
                traceback.format_exc()
            )


        log(
            f"Próximo ciclo em "
            f"{INTERVALO_CICLO}s."
        )


        time.sleep(
            INTERVALO_CICLO
        )


# ============================================================
# FLASK
# ============================================================

@app.route("/")
def home():

    return (
        f"{APP_VERSION} ON"
    )


@app.route("/health")
def health():

    return {

        "status":
        "ok",

        "version":
        APP_VERSION,
    }


@app.route("/status")
def status():

    with LOCK:

        dados = dict(
            ULTIMO_CICLO
        )


    return {

        "version":
        APP_VERSION,

        "intervalo_segundos":
        INTERVALO_CICLO,

        "desconto_minimo":
        DESCONTO_MINIMO,

        "lojas":
        LOJAS,

        "marcas":
        list(
            MARCAS.keys()
        ),

        "telegram_configurado":
        bool(
            TELEGRAM_TOKEN
            and CHAT_ID
        ),

        "afiliado_amazon":
        bool(
            TAG_AMAZON
        ),

        "ultimo_ciclo":
        dados,
    }


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    log(
        "=" * 60
    )


    log(
        f"🚀 {APP_VERSION}"
    )


    log(
        "🚀 Servidor iniciando..."
    )


    log(
        f"🚀 PORT={PORT}"
    )


    log(
        f"🚀 Intervalo="
        f"{INTERVALO_CICLO}s"
    )


    log(
        "🚀 Desconto mínimo="
        f"{DESCONTO_MINIMO * 100:.0f}%"
    )


    log(
        "🚀 Marcas: "
        + ", ".join(
            MARCAS.keys()
        )
    )


    log(
        "🚀 Lojas: "
        + ", ".join(
            LOJAS
        )
    )


    log(
        "🚀 Telegram configurado: "
        + (
            "SIM"
            if TELEGRAM_TOKEN
            and CHAT_ID
            else "NÃO"
        )
    )


    log(
        "🚀 Afiliado Amazon: "
        + TAG_AMAZON
    )


    thread = threading.Thread(
        target=radar_loop,
        daemon=True,
    )


    thread.start()


    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False,
        use_reloader=False,
        threaded=True,
    )
