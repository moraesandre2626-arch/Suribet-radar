import os
import requests
from bs4 import BeautifulSoup
import telegram
from telegram.constants import ParseMode
import asyncio
import threading
import time
import hashlib
import json
from flask import Flask

# ============================================================
# ACHADOS CELULARES AMAZON - V4
# ============================================================
# Busca ofertas de celulares na Amazon Brasil
# Link de afiliado automático
# Tag Amazon: suribet06-20
# Telegram
# Anti-repetição
# Histórico local
# Render / Flask
# ============================================================

app = Flask(__name__)

@app.route('/')
def home():
    return {
        "status": "Achados Celulares Amazon V4 ONLINE",
        "bot": "Ativo",
        "loja": "Amazon"
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

# Sua tag de afiliado Amazon
TAG = (
    os.getenv("TAG_AMAZON")
    or os.getenv("TAG_AM")
    or "suribet06-20"
)

# Intervalo entre ciclos
INTERVALO_CICLO = 7200  # 2 horas

# Arquivo de histórico
HISTORICO_FILE = "historico_amazon.json"


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
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/139.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9"
}


# ============================================================
# HISTÓRICO
# ============================================================

def carregar_historico():

    try:
        if os.path.exists(HISTORICO_FILE):

            with open(
                HISTORICO_FILE,
                "r",
                encoding="utf-8"
            ) as f:

                return json.load(f)

    except Exception as e:
        print("Erro ao carregar histórico:", e)

    return {}


def salvar_historico(historico):

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
        print("Erro ao salvar histórico:", e)


# ============================================================
# ID DO PRODUTO
# ============================================================

def gerar_id(titulo, link):

    base = f"{titulo}|{link}"

    return hashlib.md5(
        base.encode("utf-8")
    ).hexdigest()


# ============================================================
# LIMPAR PREÇO
# ============================================================

def limpar_preco(preco):

    if not preco:
        return "Ver preço"

    preco = preco.strip()

    preco = (
        preco
        .replace("\n", " ")
        .replace("  ", " ")
    )

    return preco


# ============================================================
# BUSCAR AMAZON
# ============================================================

def buscar_oferta(busca):

    url_busca = (
        "https://www.amazon.com.br/s?k="
        + requests.utils.quote(busca)
    )

    print(f"🔎 Procurando: {busca}")

    try:

        resposta = requests.get(
            url_busca,
            headers=HEADERS,
            timeout=20
        )

        if resposta.status_code != 200:

            print(
                f"Amazon retornou HTTP "
                f"{resposta.status_code}"
            )

            return None

        soup = BeautifulSoup(
            resposta.text,
            "lxml"
        )

        itens = soup.select(
            '[data-component-type="s-search-result"]'
        )

        if not itens:

            print(
                f"❌ Nenhum resultado: {busca}"
            )

            return None

        # Procurar até alguns resultados
        # para evitar pegar item patrocinado
        # ou resultado sem preço.

        for item in itens[:8]:

            titulo_tag = item.select_one("h2")

            if not titulo_tag:
                continue

            titulo = titulo_tag.get_text(
                " ",
                strip=True
            )

            link_tag = item.select_one(
                "h2 a"
            )

            if not link_tag:
                continue

            link_rel = link_tag.get(
                "href",
                ""
            )

            if not link_rel:
                continue

            # Remove parâmetros antigos
            link_rel = link_rel.split("?")[0]

            link = (
                "https://www.amazon.com.br"
                + link_rel
                + f"?tag={TAG}"
            )

            preco_tag = item.select_one(
                ".a-price .a-offscreen"
            )

            preco = (
                limpar_preco(
                    preco_tag.get_text(
                        strip=True
                    )
                )
                if preco_tag
                else "Ver preço"
            )

            imagem_tag = item.select_one(
                "img.s-image"
            )

            imagem = (
                imagem_tag.get("src")
                if imagem_tag
                else None
            )

            produto = {
                "busca": busca,
                "titulo": titulo[:150],
                "preco": preco,
                "link": link,
                "img": imagem
            }

            print(
                f"✅ Encontrado: {titulo[:70]}"
            )

            return produto

        print(
            f"❌ Nenhum produto válido: {busca}"
        )

        return None

    except Exception as e:

        print(
            f"❌ Erro Amazon ({busca}): {e}"
        )

        return None


# ============================================================
# VERIFICAR REPETIÇÃO
# ============================================================

def produto_novo(produto, historico):

    produto_id = gerar_id(
        produto["titulo"],
        produto["link"]
    )

    if produto_id in historico:

        return False, produto_id

    return True, produto_id


# ============================================================
# REGISTRAR PRODUTO
# ============================================================

def registrar_produto(
    produto,
    produto_id,
    historico
):

    historico[produto_id] = {
        "titulo": produto["titulo"],
        "preco": produto["preco"],
        "link": produto["link"],
        "busca": produto["busca"],
        "timestamp": time.time()
    }

    # Limita histórico
    if len(historico) > 1000:

        historico = dict(
            list(historico.items())[-800:]
        )

    salvar_historico(historico)

    return historico


# ============================================================
# MONTAR MENSAGEM
# ============================================================

def montar_mensagem(produto):

    return (
        "⚡ *ACHADO DE CELULAR*\n\n"
        f"📱 *{produto['titulo']}*\n\n"
        f"💰 *Preço: {produto['preco']}*\n\n"
        "🛒 *COMPRE NA AMAZON:*\n"
        f"{produto['link']}\n\n"
        "⏰ Confira o preço antes de comprar!"
    )


# ============================================================
# ENVIAR TELEGRAM
# ============================================================

async def enviar_produto(bot, produto):

    texto = montar_mensagem(produto)

    try:

        if produto.get("img"):

            await bot.send_photo(
                chat_id=CHAT_ID,
                photo=produto["img"],
                caption=texto,
                parse_mode=ParseMode.MARKDOWN
            )

        else:

            await bot.send_message(
                chat_id=CHAT_ID,
                text=texto,
                parse_mode=ParseMode.MARKDOWN
            )

        print(
            "📨 Oferta enviada para Telegram"
        )

        return True

    except Exception as e:

        print(
            "Erro ao enviar oferta:",
            e
        )

        try:

            await bot.send_message(
                chat_id=CHAT_ID,
                text=texto,
                parse_mode=ParseMode.MARKDOWN
            )

            return True

        except Exception as e2:

            print(
                "Falha no envio alternativo:",
                e2
            )

            return False


# ============================================================
# CICLO DE BUSCA
# ============================================================

async def executar_ciclo(bot):

    historico = carregar_historico()

    encontrados = 0
    enviados = 0

    print("")
    print("=" * 60)
    print("🚀 NOVO CICLO DE BUSCA")
    print("=" * 60)

    for busca in BUSCAS:

        try:

            produto = buscar_oferta(busca)

            if not produto:
                continue

            encontrados += 1

            novo, produto_id = produto_novo(
                produto,
                historico
            )

            if not novo:

                print(
                    f"⏭️ Já enviado: "
                    f"{produto['titulo'][:60]}"
                )

                continue

            historico = registrar_produto(
                produto,
                produto_id,
                historico
            )

            enviado = await enviar_produto(
                bot,
                produto
            )

            if enviado:

                enviados += 1

            # Pequena pausa entre buscas
            await asyncio.sleep(5)

        except Exception as e:

            print(
                f"Erro processando {busca}:",
                e
            )

    print("")
    print(
        f"📊 Encontrados: {encontrados}"
    )

    print(
        f"📨 Enviados: {enviados}"
    )

    print(
        f"🗂️ Histórico: {len(historico)}"
    )

    print("=" * 60)
    print("")


# ============================================================
# LOOP PRINCIPAL
# ============================================================

async def bot_loop():

    if not TOKEN:

        print(
            "❌ ERRO: TOKEN DO TELEGRAM NÃO CONFIGURADO"
        )

        return

    if not CHAT_ID:

        print(
            "❌ ERRO: CHAT_ID NÃO CONFIGURADO"
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
        "📱 ACHADOS CELULARES AMAZON V4"
    )
    print(
        "=========================================="
    )
    print(
        f"🏷️ Tag afiliado: {TAG}"
    )
    print(
        f"🔎 Modelos monitorados: {len(BUSCAS)}"
    )
    print(
        f"⏱️ Intervalo: {INTERVALO_CICLO}s"
    )
    print(
        "=========================================="
    )

    # Mensagem inicial
    try:

        await bot.send_message(
            chat_id=CHAT_ID,
            text=(
                "🚀 *ACHADOS CELULARES V4 ATIVADO!*\n\n"
                "📱 Monitoramento da Amazon iniciado.\n"
                f"🔎 {len(BUSCAS)} modelos monitorados.\n"
                "🏷️ Links com afiliado automático.\n\n"
                "⚡ O radar está procurando ofertas..."
            ),
            parse_mode=ParseMode.MARKDOWN
        )

    except Exception as e:

        print(
            "Erro mensagem inicial:",
            e
        )

    # Loop infinito
    while True:

        try:

            await executar_ciclo(bot)

        except Exception as e:

            print(
                "❌ Erro no ciclo:",
                e
            )

        print(
            f"😴 Aguardando "
            f"{INTERVALO_CICLO // 3600} horas..."
        )

        await asyncio.sleep(
            INTERVALO_CICLO
        )


# ============================================================
# THREAD DO BOT
# ============================================================

def start_bot():

    try:

        asyncio.run(
            bot_loop()
        )

    except Exception as e:

        print(
            "Erro fatal no bot:",
            e
        )


# ============================================================
# SERVIDOR FLASK
# ============================================================

def run_web():

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    thread = threading.Thread(
        target=start_bot,
        daemon=True
    )

    thread.start()

    run_web()
