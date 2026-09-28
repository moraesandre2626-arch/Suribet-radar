import os
import re
import json
import asyncio
import time
import html
import requests

from fastapi import FastAPI
from datetime import datetime

# ============================================================
# PRICE RADAR V4
# Samsung + Motorola + Apple
# Amazon + Magalu + Mercado Livre + AliExpress + Shopee
#
# O robô pesquisa POR MARCA e descobre os celulares encontrados.
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

AMAZON_TAG = os.getenv("AMAZON_TAG", "achadossm-20")

INTERVALO = int(os.getenv("INTERVALO_MS", "900000")) / 1000

# Queda mínima para gerar alerta
QUEDA_MINIMA = float(os.getenv("QUEDA_MINIMA", "5"))

# Máximo de produtos por marca/loja
MAX_PRODUTOS_POR_LOJA = int(
    os.getenv("MAX_PRODUTOS_POR_LOJA", "20")
)

# Arquivo de histórico
HISTORICO_FILE = "historico.json"

# ============================================================
# MARCAS
# ============================================================

MARCAS = [
    "Samsung",
    "Motorola",
    "Apple"
]

# ============================================================
# URLs DE BUSCA
# ============================================================

LOJAS = {
    "Amazon": {
        "url": "https://www.amazon.com.br/s?k={query}",
    },

    "Magalu": {
        "url": "https://www.magazineluiza.com.br/busca/{query}/",
    },

    "Mercado Livre": {
        "url": "https://lista.mercadolivre.com.br/{query}",
    },

    "AliExpress": {
        "url": "https://pt.aliexpress.com/w/wholesale-{query}.html",
    },

    "Shopee": {
        "url": "https://shopee.com.br/search?keyword={query}",
    }
}

# ============================================================
# HEADERS
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Connection": "keep-alive"
}

# ============================================================
# APP
# ============================================================

app = FastAPI()

# ============================================================
# HISTÓRICO
# ============================================================

historico = {}


def carregar_historico():
    global historico

    try:
        if os.path.exists(HISTORICO_FILE):

            with open(
                HISTORICO_FILE,
                "r",
                encoding="utf-8"
            ) as f:

                historico = json.load(f)

                if not isinstance(historico, dict):
                    historico = {}

    except Exception as e:
        print("Erro carregando histórico:", e)
        historico = {}


def salvar_historico():

    try:

        with open(
            HISTORICO_FILE,
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
        print("Erro salvando histórico:", e)


# ============================================================
# TELEGRAM
# ============================================================

def enviar_telegram(msg):

    if not BOT_TOKEN or not CHAT_ID:
        print("BOT_TOKEN ou CHAT_ID não configurado.")
        return False

    try:

        url = (
            f"https://api.telegram.org/"
            f"bot{BOT_TOKEN}/sendMessage"
        )

        payload = {
            "chat_id": CHAT_ID,
            "text": msg,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }

        r = requests.post(
            url,
            json=payload,
            timeout=15
        )

        print(
            "Telegram:",
            r.status_code,
            r.text[:200]
        )

        return r.ok

    except Exception as e:

        print("Erro Telegram:", e)
        return False


# ============================================================
# LIMPEZA DE TEXTO
# ============================================================

def limpar_texto(texto):

    if not texto:
        return ""

    texto = html.unescape(str(texto))

    texto = re.sub(
        r"<[^>]+>",
        " ",
        texto
    )

    texto = re.sub(
        r"\s+",
        " ",
        texto
    )

    return texto.strip()


# ============================================================
# PREÇO
# ============================================================

def limpar_preco(valor):

    if valor is None:
        return None

    texto = str(valor)

    texto = texto.replace(
        "\xa0",
        " "
    )

    # R$ 1.299,90
    encontrados = re.findall(
        r"\d{1,3}(?:\.\d{3})*(?:,\d{2})?",
        texto
    )

    if not encontrados:
        return None

    # normalmente o primeiro preço encontrado
    numero = encontrados[0]

    try:

        if "," in numero:

            numero = numero.replace(
                ".",
                ""
            )

            numero = numero.replace(
                ",",
                "."
            )

        else:

            # Ex: 1299
            numero = numero.replace(
                ".",
                ""
            )

        preco = float(numero)

        if 100 <= preco <= 30000:
            return preco

    except Exception:
        pass

    return None


# ============================================================
# NORMALIZAÇÃO DE NOME
# ============================================================

def normalizar_nome(nome):

    nome = limpar_texto(nome)

    nome = re.sub(
        r"\s+",
        " ",
        nome
    )

    return nome.strip()


# ============================================================
# VERIFICA SE É CELULAR
# ============================================================

def parece_celular(nome):

    texto = nome.lower()

    palavras_excluir = [
        "capa",
        "case",
        "película",
        "pelicula",
        "capinha",
        "carregador",
        "cabo",
        "fone",
        "fones",
        "suporte",
        "vidro",
        "bateria",
        "película",
        "adaptador",
        "smartwatch",
        "relógio",
        "relogio",
        "controle",
        "tripé",
        "tripe",
        "adesivo",
        "bolsa"
    ]

    for palavra in palavras_excluir:

        if palavra in texto:
            return False

    marcas = [
        "samsung",
        "galaxy",
        "motorola",
        "moto ",
        "iphone",
        "apple"
    ]

    return any(
        marca in texto
        for marca in marcas
    )


# ============================================================
# DETECTA MODELO
# ============================================================

def detectar_modelo(nome, marca):

    texto = normalizar_nome(nome)

    # --------------------------------------------------------
    # Samsung
    # --------------------------------------------------------

    if marca.lower() == "samsung":

        padroes = [

            r"(Galaxy\s+A\d+\s*(?:5G)?\s*(?:\d+\s*GB)?)",

            r"(Galaxy\s+S\d+\s*(?:Ultra|Plus|\+|FE)?\s*(?:5G)?\s*(?:\d+\s*GB)?)",

            r"(Galaxy\s+M\d+\s*(?:5G)?\s*(?:\d+\s*GB)?)",

            r"(Galaxy\s+Z\s*(?:Flip|Fold)\s*\d+\s*(?:\d+\s*GB)?)",

        ]

        for padrao in padroes:

            match = re.search(
                padrao,
                texto,
                re.IGNORECASE
            )

            if match:
                return match.group(1)

    # --------------------------------------------------------
    # Motorola
    # --------------------------------------------------------

    if marca.lower() == "motorola":

        padroes = [

            r"(Moto\s+G\d+\s*(?:Power|Play|Plus|Fusion|Edge)?\s*(?:5G)?\s*(?:\d+\s*GB)?)",

            r"(Moto\s+G\s*(?:Stylus)?\s*\d+\s*(?:5G)?\s*(?:\d+\s*GB)?)",

            r"(Motorola\s+Edge\s+\d+\s*(?:Pro|Fusion|Ultra)?\s*(?:5G)?\s*(?:\d+\s*GB)?)",

            r"(Motorola\s+Razr\s+\d+\s*(?:Ultra)?\s*(?:5G)?)",

        ]

        for padrao in padroes:

            match = re.search(
                padrao,
                texto,
                re.IGNORECASE
            )

            if match:
                return match.group(1)

    # --------------------------------------------------------
    # Apple
    # --------------------------------------------------------

    if marca.lower() == "apple":

        padroes = [

            r"(iPhone\s+\d+\s*(?:Pro\s*Max|Pro|Plus)?\s*(?:\d+\s*GB|\d+\s*TB)?)",

            r"(iPhone\s+SE\s*(?:\d+)?\s*(?:\d+\s*GB)?)"

        ]

        for padrao in padroes:

            match = re.search(
                padrao,
                texto,
                re.IGNORECASE
            )

            if match:
                return match.group(1)

    return texto[:120]


# ============================================================
# REQUEST
# ============================================================

def baixar_pagina(url):

    try:

        resposta = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        if resposta.status_code != 200:

            print(
                "HTTP",
                resposta.status_code,
                url
            )

            return None

        return resposta.text

    except Exception as e:

        print(
            "Erro acessando:",
            url,
            e
        )

        return None


# ============================================================
# EXTRATOR GENÉRICO
# ============================================================

def extrair_produtos_generico(
    html_texto,
    marca,
    loja,
    url_busca
):

    if not html_texto:
        return []

    produtos_encontrados = []

    texto = limpar_texto(html_texto)

    # --------------------------------------------------------
    # Estratégia 1:
    # procura blocos contendo marca + preço
    # --------------------------------------------------------

    padrao_preco = re.compile(
        r"R\$\s?\d{1,3}(?:\.\d{3})*(?:,\d{2})?"
    )

    precos = list(
        padrao_preco.finditer(
            html_texto
        )
    )

    for match_preco in precos:

        inicio = max(
            0,
            match_preco.start() - 500
        )

        fim = min(
            len(html_texto),
            match_preco.end() + 500
        )

        bloco = html_texto[
            inicio:fim
        ]

        bloco_texto = limpar_texto(
            bloco
        )

        if marca.lower() not in bloco_texto.lower():
            continue

        preco = limpar_preco(
            match_preco.group(0)
        )

        if not preco:
            continue

        # tenta encontrar nome antes do preço
        palavras = re.findall(
            r"[A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9\s\-\+\(\)\/\.]{10,150}",
            bloco_texto
        )

        nome = None

        for candidato in palavras:

            candidato = normalizar_nome(
                candidato
            )

            if (
                marca.lower() in candidato.lower()
                and parece_celular(candidato)
            ):

                nome = candidato
                break

        if not nome:
            continue

        modelo = detectar_modelo(
            nome,
            marca
        )

        produtos_encontrados.append({
            "marca": marca,
            "modelo": modelo,
            "nome": nome,
            "preco": preco,
            "loja": loja,
            "url": url_busca
        })

    return produtos_encontrados


# ============================================================
# AMAZON
# ============================================================

def consultar_amazon(marca):

    query = requests.utils.quote(
        f"{marca} celular smartphone"
    )

    url = (
        LOJAS["Amazon"]["url"]
        .format(query=query)
    )

    if "tag=" not in url:

        url += (
            "&" if "?" in url else "?"
        )

        url += f"tag={AMAZON_TAG}"

    pagina = baixar_pagina(url)

    return extrair_produtos_generico(
        pagina,
        marca,
        "Amazon",
        url
    )


# ============================================================
# MAGALU
# ============================================================

def consultar_magalu(marca):

    query = requests.utils.quote(
        f"{marca} celular"
    )

    url = (
        LOJAS["Magalu"]["url"]
        .format(query=query)
    )

    pagina = baixar_pagina(url)

    return extrair_produtos_generico(
        pagina,
        marca,
        "Magalu",
        url
    )


# ============================================================
# MERCADO LIVRE
# ============================================================

def consultar_mercadolivre(marca):

    query = requests.utils.quote(
        f"{marca} celular"
    )

    url = (
        LOJAS["Mercado Livre"]["url"]
        .format(query=query)
    )

    pagina = baixar_pagina(url)

    return extrair_produtos_generico(
        pagina,
        marca,
        "Mercado Livre",
        url
    )


# ============================================================
# ALIEXPRESS
# ============================================================

def consultar_aliexpress(marca):

    query = requests.utils.quote(
        f"{marca} smartphone"
    )

    url = (
        LOJAS["AliExpress"]["url"]
        .format(query=query)
    )

    pagina = baixar_pagina(url)

    return extrair_produtos_generico(
        pagina,
        marca,
        "AliExpress",
        url
    )


# ============================================================
# SHOPEE
# ============================================================

def consultar_shopee(marca):

    query = requests.utils.quote(
        f"{marca} celular"
    )

    url = (
        LOJAS["Shopee"]["url"]
        .format(query=query)
    )

    pagina = baixar_pagina(url)

    return extrair_produtos_generico(
        pagina,
        marca,
        "Shopee",
        url
    )


# ============================================================
# CONSULTAR LOJA
# ============================================================

def consultar_loja(
    loja,
    marca
):

    try:

        if loja == "Amazon":
            return consultar_amazon(marca)

        if loja == "Magalu":
            return consultar_magalu(marca)

        if loja == "Mercado Livre":
            return consultar_mercadolivre(marca)

        if loja == "AliExpress":
            return consultar_aliexpress(marca)

        if loja == "Shopee":
            return consultar_shopee(marca)

    except Exception as e:

        print(
            f"Erro {loja}/{marca}:",
            e
        )

    return []


# ============================================================
# REMOVE DUPLICADOS
# ============================================================

def remover_duplicados(produtos):

    vistos = set()

    resultado = []

    for p in produtos:

        chave = (
            p["marca"].lower(),
            p["modelo"].lower(),
            p["loja"].lower()
        )

        if chave in vistos:
            continue

        vistos.add(chave)

        resultado.append(p)

    return resultado


# ============================================================
# FILTRA E ORDENA
# ============================================================

def preparar_produtos(
    produtos
):

    produtos = [
        p for p in produtos
        if p.get("preco")
        and p["preco"] >= 100
        and parece_celular(
            p.get("nome", "")
        )
    ]

    produtos = remover_duplicados(
        produtos
    )

    produtos.sort(
        key=lambda x: x["preco"]
    )

    return produtos[
        :MAX_PRODUTOS_POR_LOJA
    ]


# ============================================================
# CHAVE DO PRODUTO
# ============================================================

def chave_produto(p):

    marca = p["marca"].lower()

    modelo = p["modelo"].lower()

    loja = p["loja"].lower()

    return (
        f"{marca}|"
        f"{modelo}|"
        f"{loja}"
    )


# ============================================================
# PROCESSA PREÇO
# ============================================================

def processar_preco(p):

    chave = chave_produto(p)

    preco_atual = p["preco"]

    registro = historico.get(
        chave
    )

    anterior = None

    if isinstance(
        registro,
        dict
    ):

        anterior = registro.get(
            "preco"
        )

    elif isinstance(
        registro,
        (int, float)
    ):

        anterior = registro

    # atualiza histórico
    historico[chave] = {
        "preco": preco_atual,
        "nome": p["nome"],
        "modelo": p["modelo"],
        "marca": p["marca"],
        "loja": p["loja"],
        "url": p["url"],
        "atualizado": datetime.now().isoformat()
    }

    # primeira vez
    if not anterior:
        return None

    # preço subiu ou ficou igual
    if preco_atual >= anterior:
        return None

    queda = (
        (anterior - preco_atual)
        / anterior
    ) * 100

    if queda < QUEDA_MINIMA:
        return None

    return {
        **p,
        "anterior": anterior,
        "queda": queda
    }


# ============================================================
# ALERTA
# ============================================================

def montar_alerta(
    p
):

    nome = html.escape(
        p["nome"]
    )

    loja = html.escape(
        p["loja"]
    )

    url = html.escape(
        p["url"],
        quote=True
    )

    msg = (
        "🔥 <b>PRICE RADAR V4</b>\n\n"
        f"📱 <b>{nome}</b>\n"
        f"🏷️ {html.escape(p['marca'])}\n"
        f"🏪 {loja}\n\n"
        f"💰 De: <s>R$ {p['anterior']:.2f}</s>\n"
        f"💸 Agora: <b>R$ {p['preco']:.2f}</b>\n"
        f"📉 Queda: <b>-{p['queda']:.1f}%</b>\n\n"
        f"🔗 <a href='{url}'>VER OFERTA</a>"
    )

    return msg


# ============================================================
# SCAN COMPLETO
# ============================================================

def executar_scan():

    inicio = time.time()

    encontrados = []

    estatisticas = {
        "marcas": 0,
        "lojas": 0,
        "produtos": 0,
        "alertas": 0
    }

    for marca in MARCAS:

        estatisticas["marcas"] += 1

        print(
            f"\n===== {marca.upper()} ====="
        )

        for loja in LOJAS:

            estatisticas["lojas"] += 1

            print(
                f"Consultando {loja}..."
            )

            produtos = consultar_loja(
                loja,
                marca
            )

            produtos = preparar_produtos(
                produtos
            )

            print(
                f"{loja}: "
                f"{len(produtos)} encontrados"
            )

            estatisticas["produtos"] += len(
                produtos
            )

            encontrados.extend(
                produtos
            )

            # pequeno intervalo
            time.sleep(2)

    alertas = []

    for produto in encontrados:

        queda = processar_preco(
            produto
        )

        if queda:

            alertas.append(
                queda
            )

    salvar_historico()

    estatisticas["alertas"] = len(
        alertas
    )

    duracao = time.time() - inicio

    print(
        "\nSCAN FINALIZADO"
    )

    print(
        f"Produtos: {estatisticas['produtos']}"
    )

    print(
        f"Alertas: {estatisticas['alertas']}"
    )

    print(
        f"Tempo: {duracao:.1f}s"
    )

    # envia alertas
    for alerta in alertas:

        enviar_telegram(
            montar_alerta(
                alerta
            )
        )

        time.sleep(2)

    return {
        "estatisticas": estatisticas,
        "alertas": alertas,
        "duracao": duracao
    }


# ============================================================
# LOOP AUTOMÁTICO
# ============================================================

async def loop_radar():

    await asyncio.sleep(10)

    carregar_historico()

    enviar_telegram(
        "🚀 <b>PRICE RADAR V4 LIGADO</b>\n\n"
        "📱 Samsung\n"
        "📱 Motorola\n"
        "📱 Apple\n\n"
        "🏪 Amazon\n"
        "🏪 Magalu\n"
        "🏪 Mercado Livre\n"
        "🏪 AliExpress\n"
        "🏪 Shopee\n\n"
        f"📉 Alerta de queda: {QUEDA_MINIMA:.1f}%\n"
        f"⏰ Intervalo: {int(INTERVALO / 60)} min\n\n"
        "🔎 Pesquisa por MARCA ativada."
    )

    while True:

        try:

            print(
                "\n================================"
            )

            print(
                "PRICE RADAR V4 - NOVO SCAN"
            )

            print(
                "================================"
            )

            await asyncio.to_thread(
                executar_scan
            )

        except Exception as e:

            print(
                "Erro no loop:",
                e
            )

        await asyncio.sleep(
            INTERVALO
        )


# ============================================================
# STARTUP
# ============================================================

@app.on_event(
    "startup"
)
async def startup():

    carregar_historico()

    asyncio.create_task(
        loop_radar()
    )


# ============================================================
# HOME
# ============================================================

@app.get("/")
def home():

    return {
        "status": "Price Radar V4 ONLINE",
        "marcas": MARCAS,
        "lojas": list(LOJAS.keys()),
        "queda_minima": QUEDA_MINIMA,
        "intervalo_min": INTERVALO / 60,
        "produtos_historico": len(
            historico
        )
    }


# ============================================================
# TESTE TELEGRAM
# ============================================================

@app.get("/teste")
def teste():

    ok = enviar_telegram(
        "🤖 <b>Price Radar V4</b>\n\n"
        "✅ Telegram funcionando!\n"
        "🔎 Pesquisa por marca ativada.\n"
        "📱 Samsung + Motorola + Apple\n"
        "🏪 5 lojas configuradas."
    )

    return {
        "telegram": (
            "OK" if ok else "ERRO"
        )
    }


# ============================================================
# SCAN MANUAL
# ============================================================

@app.get("/scan")
async def scan():

    resultado = await asyncio.to_thread(
        executar_scan
    )

    return {
        "scan": "finalizado",
        "resultado": resultado["estatisticas"]
    }


# ============================================================
# STATUS
# ============================================================

@app.get("/status")
def status():

    return {
        "status": "ONLINE",
        "marcas": MARCAS,
        "lojas": list(
            LOJAS.keys()
        ),
        "historico": len(
            historico
        ),
        "queda_minima": (
            f"{QUEDA_MINIMA}%"
        ),
        "intervalo_minutos": (
            INTERVALO / 60
        ),
        "horario": datetime.now().strftime(
            "%d/%m/%Y %H:%M:%S"
        )
    }
