import os
import re
import json
import time
import threading
import traceback
import statistics
import unicodedata
from urllib.parse import quote, urljoin

import requests
from flask import Flask
from bs4 import BeautifulSoup


# ============================================================
# PRICE RADAR V6.1
# Celulares por MARCA
# Amazon + Mercado Livre + Shopee + Magalu + Casas Bahia + KaBuM
# Alerta somente quando preço <= 80% da referência comparável
# Telegram via Bot API HTTP
# ============================================================

APP_VERSION = "PRICE RADAR V6.1"

PORT = int(os.getenv("PORT", "10000"))

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
    os.getenv("INTERVALO_CICLO", "7200")
)

DESCONTO_MINIMO = float(
    os.getenv("DESCONTO_MINIMO", "0.20")
)

TIMEOUT = int(
    os.getenv("REQUEST_TIMEOUT", "20")
)

ARQUIVO_HISTORICO = "historico_precos.json"
ARQUIVO_ALERTAS = "alertas_enviados.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}


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


LOJAS = [
    "Amazon",
    "Mercado Livre",
    "Shopee",
    "Magazine Luiza",
    "Casas Bahia",
    "KaBuM",
]


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

def carregar_json(caminho, padrao):
    try:
        if not os.path.exists(caminho):
            return padrao

        with open(
            caminho,
            "r",
            encoding="utf-8",
        ) as arquivo:
            return json.load(arquivo)

    except Exception as erro:
        log(f"Erro lendo {caminho}: {erro}")
        return padrao


def salvar_json(caminho, dados):
    try:
        temporario = caminho + ".tmp"

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
# TEXTO / PREÇO
# ============================================================

def normalizar_texto(texto):
    texto = str(texto or "")

    texto = unicodedata.normalize(
        "NFKD",
        texto,
    )

    texto = "".join(
        c for c in texto
        if not unicodedata.combining(c)
    )

    texto = texto.lower()

    texto = re.sub(
        r"\s+",
        " ",
        texto,
    ).strip()

    return texto


def converter_preco(valor):
    if valor is None:
        return None

    texto = str(valor).strip()

    texto = texto.replace(
        "\xa0",
        " ",
    )

    padroes = [
        r"R\$\s*([\d.]+,\d{2})",
        r"R\$\s*([\d]+,\d{2})",
        r"(?<!\d)([\d.]+,\d{2})(?!\d)",
    ]

    for padrao in padroes:
        resultado = re.search(
            padrao,
            texto,
            flags=re.I,
        )

        if not resultado:
            continue

        numero = resultado.group(1)

        numero = numero.replace(
            ".",
            "",
        ).replace(
            ",",
            ".",
        )

        try:
            preco = float(numero)

            if 100 <= preco <= 100000:
                return preco

        except ValueError:
            pass

    return None


def moeda(valor):
    if valor is None:
        return "N/D"

    texto = f"{valor:,.2f}"

    texto = texto.replace(
        ",",
        "X",
    ).replace(
        ".",
        ",",
    ).replace(
        "X",
        ".",
    )

    return f"R$ {texto}"


# ============================================================
# NORMALIZAÇÃO DO MODELO
# ============================================================

def extrair_capacidade(texto):
    texto = normalizar_texto(texto)

    encontrados = re.findall(
        r"(?<!\d)(32|64|128|256|512|1024)\s*gb\b",
        texto,
    )

    if encontrados:
        return f"{encontrados[0]}GB"

    encontrados_tb = re.findall(
        r"(?<!\d)(1|2)\s*tb\b",
        texto,
    )

    if encontrados_tb:
        return f"{encontrados_tb[0]}TB"

    return ""


def normalizar_modelo(titulo):
    texto = normalizar_texto(titulo)

    capacidade = extrair_capacidade(texto)

    modelo = ""

    # Apple
    match = re.search(
        r"\biphone\s*(\d{1,2}(?:\s*(?:pro max|pro|plus|mini|e))?)",
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

    # Samsung
    if not modelo:
        match = re.search(
            r"\bgalaxy\s+"
            r"([asmzf]\s*\d{1,3}"
            r"(?:\s*(?:5g|4g|fe|ultra|plus|\+))*)",
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

    # Motorola
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

    # Xiaomi / Redmi / Poco
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

    if not modelo:
        modelo = normalizar_texto(titulo)

    if capacidade:
        return f"{modelo} {capacidade}".strip()

    return modelo.strip()


def detectar_marca(titulo):
    texto = normalizar_texto(titulo)

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

def url_amazon(busca):
    return (
        "https://www.amazon.com.br/s?k="
        + quote(busca)
        + f"&tag={quote(TAG_AMAZON)}"
    )


def url_ml(busca):
    return (
        "https://lista.mercadolivre.com.br/"
        + quote(busca)
    )


def url_shopee(busca):
    return (
        "https://shopee.com.br/search?keyword="
        + quote(busca)
    )


def url_magalu(busca):
    return (
        "https://www.magazineluiza.com.br/"
        "?s="
        + quote(busca)
    )


def url_casas_bahia(busca):
    return (
        "https://www.casasbahia.com.br/"
        "busca/"
        + quote(busca)
    )


def url_kabum(busca):
    return (
        "https://www.kabum.com.br/"
        "busca/"
        + quote(busca)
    )


# ============================================================
# HTTP
# ============================================================

def requisitar(url):
    try:
        resposta = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT,
        )

        if resposta.status_code != 200:
            log(
                f"HTTP {resposta.status_code}: {url}"
            )
            return None

        return resposta.text

    except Exception as erro:
        log(
            f"Erro HTTP {url}: {erro}"
        )
        return None


# ============================================================
# RESULTADO PADRÃO
# ============================================================

def criar_oferta(
    loja,
    titulo,
    preco,
    url,
):
    if not titulo or preco is None:
        return None

    marca = detectar_marca(titulo)

    if not marca:
        return None

    modelo = normalizar_modelo(titulo)

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
        "url": url,
        "timestamp": int(time.time()),
    }


# ============================================================
# AMAZON
# ============================================================

def buscar_amazon(busca):
    url = url_amazon(busca)
    html = requisitar(url)

    if not html:
        return []

    soup = BeautifulSoup(
        html,
        "lxml",
    )

    ofertas = []

    for item in soup.select(
        '[data-component-type="s-search-result"]'
    ):
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

            if not titulo_el or not preco_el:
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

            link = None

            if link_el and link_el.get("href"):
                link = urljoin(
                    "https://www.amazon.com.br",
                    link_el["href"],
                )

            if not link:
                link = url

            oferta = criar_oferta(
                "Amazon",
                titulo,
                preco,
                link,
            )

            if oferta:
                ofertas.append(oferta)

        except Exception:
            continue

    return ofertas


# ============================================================
# MERCADO LIVRE
# ============================================================

def buscar_ml(busca):
    url = url_ml(busca)
    html = requisitar(url)

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
                    ".ui-search-price__part .andes-money-amount__fraction"
                )
            )

            link_el = (
                item.select_one(
                    "a[href]"
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

            link = (
                link_el.get("href")
                if link_el
                else url
            )

            oferta = criar_oferta(
                "Mercado Livre",
                titulo,
                preco,
                link,
            )

            if oferta:
                ofertas.append(oferta)

        except Exception:
            continue

    return ofertas


# ============================================================
# SHOPEE
# ============================================================

def buscar_shopee(busca):
    url = url_shopee(busca)
    html = requisitar(url)

    if not html:
        return []

    soup = BeautifulSoup(
        html,
        "lxml",
    )

    ofertas = []

    for link_el in soup.select(
        "a[href]"
    ):
        try:
            href = link_el.get("href", "")

            texto = link_el.get_text(
                " ",
                strip=True,
            )

            if len(texto) < 8:
                continue

            if "R$" not in texto:
                continue

            preco = converter_preco(texto)

            if preco is None:
                continue

            titulo = texto

            if len(titulo) > 220:
                titulo = titulo[:220]

            if not detectar_marca(titulo):
                continue

            link = urljoin(
                "https://shopee.com.br",
                href,
            )

            oferta = criar_oferta(
                "Shopee",
                titulo,
                preco,
                link,
            )

            if oferta:
                ofertas.append(oferta)

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
    html = requisitar(url)

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

            if not detectar_marca(texto):
                continue

            preco = converter_preco(texto)

            if preco is None:
                continue

            if preco < 200 or preco > 100000:
                continue

            link_el = bloco.select_one(
                "a[href]"
            )

            if link_el:
                link = urljoin(
                    url,
                    link_el.get("href"),
                )
            else:
                link = url

            titulo = texto[:300]

            oferta = criar_oferta(
                loja,
                titulo,
                preco,
                link,
            )

            if oferta:
                ofertas.append(oferta)

        except Exception:
            continue

    return ofertas


# ============================================================
# BUSCA POR MARCA
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
                    lambda q: buscar_loja_generica(
                        "Magazine Luiza",
                        q,
                        url_magalu(q),
                    ),
                ),
                (
                    "Casas Bahia",
                    lambda q: buscar_loja_generica(
                        "Casas Bahia",
                        q,
                        url_casas_bahia(q),
                    ),
                ),
                (
                    "KaBuM",
                    lambda q: buscar_loja_generica(
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
                            f"{len(encontrados)} ofertas"
                        )

                    ofertas.extend(
                        encontrados
                    )

                except Exception as erro:
                    log(
                        f"Erro {loja}: {erro}"
                    )

    return ofertas


# ============================================================
# DEDUPLICAÇÃO
# ============================================================

def chave_oferta(oferta):
    return (
        normalizar_texto(
            oferta.get("loja", "")
        ),
        normalizar_texto(
            oferta.get("modelo", "")
        ),
        round(
            float(
                oferta.get("preco", 0)
            ),
            2,
        ),
    )


def deduplicar_ofertas(ofertas):
    resultado = []
    vistos = set()

    for oferta in ofertas:
        chave = chave_oferta(oferta)

        if chave in vistos:
            continue

        vistos.add(chave)
        resultado.append(oferta)

    return resultado


# ============================================================
# REFERÊNCIA COMPARÁVEL
# ============================================================

def agrupar_por_modelo(ofertas):
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
        ).append(oferta)

    return grupos


def calcular_referencia(grupo):
    precos = [
        float(
            item["preco"]
        )
        for item in grupo
        if item.get("preco") is not None
        and float(item["preco"]) > 0
    ]

    if len(precos) < 2:
        return None

    return statistics.median(
        precos
    )


def encontrar_ofertas_desconto(ofertas):
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
                item = dict(oferta)

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

def link_amazon(oferta):
    url = oferta.get("url")

    if not url:
        return url_amazon(
            oferta.get(
                "titulo",
                "",
            )
        )

    separador = (
        "&"
        if "?" in url
        else "?"
    )

    if "tag=" in url:
        return url

    return (
        url
        + separador
        + "tag="
        + quote(TAG_AMAZON)
    )


def link_mercado_livre(oferta):
    return ML_AFILIADO


def link_shopee(oferta):
    return SHOPEE_AFILIADO


# ============================================================
# TELEGRAM
# ============================================================

def telegram_enviar(
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
        "chat_id": CHAT_ID,
        "text": texto,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }

    if botoes:
        dados["reply_markup"] = json.dumps(
            {
                "inline_keyboard": botoes
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

        if not retorno.get("ok"):
            log(
                f"Telegram erro: {retorno}"
            )
            return False

        return True

    except Exception as erro:
        log(
            f"Erro Telegram: {erro}"
        )
        return False


# ============================================================
# ANTI-SPAM
# ============================================================

def chave_alerta(oferta):
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
# MENSAGEM
# ============================================================

def montar_mensagem(oferta):
    loja = oferta["loja"]
    modelo = oferta["modelo"]
    preco = oferta["preco"]
    referencia = oferta["referencia"]
    desconto = oferta["desconto"]

    texto = (
        "🔥 <b>OFERTA ENCONTRADA!</b>\n\n"
        f"📱 <b>{modelo}</b>\n"
        f"🏪 {loja}\n"
        f"💰 <b>{moeda(preco)}</b>\n"
        f"📊 Referência: {moeda(referencia)}\n"
        f"📉 Desconto: <b>{desconto:.1f}%</b>\n\n"
        "⚠️ Comparação feita com ofertas "
        "do mesmo modelo/capacidade encontrados "
        "pelo radar."
    )

    return texto


def montar_botoes(oferta):
    url_original = oferta.get(
        "url"
    )

    if not url_original:
        url_original = "#"

    botoes = [
        [
            {
                "text": "🛒 Ver oferta",
                "url": url_original,
            }
        ]
    ]

    loja = oferta.get(
        "loja"
    )

    if loja == "Amazon":
        botoes.append(
            [
                {
                    "text": "🟠 Comprar com afiliado",
                    "url": link_amazon(
                        oferta
                    ),
                }
            ]
        )

    elif loja == "Mercado Livre":
        botoes.append(
            [
                {
                    "text": "🟡 Link afiliado ML",
                    "url": link_mercado_livre(
                        oferta
                    ),
                }
            ]
        )

    elif loja == "Shopee":
        botoes.append(
            [
                {
                    "text": "🟠 Link afiliado Shopee",
                    "url": link_shopee(
                        oferta
                    ),
                }
            ]
        )

    return botoes


# ============================================================
# CICLO DO RADAR
# ============================================================

def executar_ciclo():
    inicio = time.time()

    with LOCK:
        ULTIMO_CICLO["inicio"] = (
            time.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )

        ULTIMO_CICLO["erro"] = None
        ULTIMO_CICLO["produtos"] = 0
        ULTIMO_CICLO["ofertas"] = 0
        ULTIMO_CICLO["alertas"] = 0

    try:
        log("=" * 60)

        log(
            f"{APP_VERSION} - INICIANDO CICLO"
        )

        ofertas = buscar_todas_as_lojas()

        ofertas = deduplicar_ofertas(
            ofertas
        )

        oportunidades = encontrar_ofertas_desconto(
            ofertas
        )

        historico = carregar_json(
            ARQUIVO_HISTORICO,
            [],
        )

        alertas = carregar_json(
            ARQUIVO_ALERTAS,
            {},
        )

        historico.extend(
            [
                {
                    "timestamp": item.get(
                        "timestamp"
                    ),
                    "loja": item.get(
                        "loja"
                    ),
                    "modelo": item.get(
                        "modelo"
                    ),
                    "preco": item.get(
                        "preco"
                    ),
                    "url": item.get(
                        "url"
                    ),
                }
                for item in ofertas
            ]
        )

        if len(historico) > 10000:
            historico = historico[
                -10000:
            ]

        salvar_json(
            ARQUIVO_HISTORICO,
            historico,
        )

        enviados = 0

        for oferta in oportunidades:
            if not pode_enviar_alerta(
                oferta,
                alertas,
            ):
                continue

            mensagem = montar_mensagem(
                oferta
            )

            botoes = montar_botoes(
                oferta
            )

            if telegram_enviar(
                mensagem,
                botoes,
            ):
                enviados += 1

            time.sleep(1)

        salvar_json(
            ARQUIVO_ALERTAS,
            alertas,
        )

        fim = time.time()

        with LOCK:
            ULTIMO_CICLO["fim"] = (
                time.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            )

            ULTIMO_CICLO["produtos"] = (
                len(
                    set(
                        item["modelo"]
                        for item in ofertas
                        if item.get("modelo")
                    )
                )
            )

            ULTIMO_CICLO["ofertas"] = (
                len(ofertas)
            )

            ULTIMO_CICLO["alertas"] = (
                enviados
            )

        log(
            f"Ciclo finalizado em "
            f"{fim - inicio:.1f}s | "
            f"ofertas={len(ofertas)} | "
            f"oportunidades={len(oportunidades)} | "
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
            ULTIMO_CICLO["erro"] = str(
                erro
            )


# ============================================================
# THREAD
# ============================================================

def radar_loop():
    log(
        f"{APP_VERSION} - thread do radar iniciada."
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
        "status": "ok",
        "version": APP_VERSION,
    }


@app.route("/status")
def status():
    with LOCK:
        dados = dict(
            ULTIMO_CICLO
        )

    return {
        "version": APP_VERSION,
        "intervalo_segundos": (
            INTERVALO_CICLO
        ),
        "desconto_minimo": (
            DESCONTO_MINIMO
        ),
        "lojas": LOJAS,
        "marcas": list(
            MARCAS.keys()
        ),
        "ultimo_ciclo": dados,
    }


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    log("=" * 60)

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
        f"🚀 Intervalo={INTERVALO_CICLO}s"
    )

    log(
        f"🚀 Desconto mínimo="
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
