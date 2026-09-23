import os
import time
import threading
import requests
from flask import Flask
from datetime import datetime, timezone

# ============================================================
# CONFIGURAÇÕES
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
ODDS_API_KEY = os.getenv("ODDS_API_KEY")

# Região dos bookmakers.
# BR = bookmakers da região brasileira.
# Pode mudar para eu se quiser testar bookmakers europeias.
ODDS_REGION = os.getenv("ODDS_REGION", "br")

# Banca usada apenas para calcular a divisão da surebet
BANCA = 100.00

# Só procurar jogos que começam nas próximas X horas
HORAS_MAX = 3

# 2 horas entre cada consulta
INTERVALO_CICLO = 7200

# Lucro mínimo aproximado
# 0.99 de inversa gera pouco mais de 1% de lucro teórico
INVERSA_MAX = 0.99

# Proteção: se chegar nesse nível, o robô para de fazer consultas
CREDITOS_MINIMOS = 5

# Memória máxima dos alertas
MAX_ALERTAS_MEMORIA = 3000

# ============================================================
# FLASK
# ============================================================

app = Flask(__name__)

@app.route("/")
def home():
    restante = CREDITOS_RESTANTES if CREDITOS_RESTANTES is not None else "desconhecido"

    return (
        "SUREBET TURBO V3 ON<br>"
        f"Créditos restantes: {restante}<br>"
        f"Região: {ODDS_REGION}<br>"
        f"Próxima consulta: rotação automática"
    )


@app.route("/teste")
def teste():
    enviado = send(
        "🧪 <b>TESTE OK</b>\n\n"
        "Surebet TURBO V3 está funcionando corretamente."
    )

    if enviado:
        return "Teste enviado para o Telegram."
    return "Erro ao enviar teste."


# ============================================================
# TELEGRAM
# ============================================================

def send(msg):
    if not BOT_TOKEN or not CHAT_ID:
        print("BOT_TOKEN ou CHAT_ID não configurado.")
        return False

    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

        response = requests.post(
            url,
            data={
                "chat_id": CHAT_ID,
                "text": msg,
                "parse_mode": "HTML"
            },
            timeout=15
        )

        if response.status_code != 200:
            print("Erro Telegram:", response.text)
            return False

        return True

    except Exception as e:
        print("Erro ao enviar Telegram:", e)
        return False


# ============================================================
# ESPORTES
# ============================================================

# Prioridade:
# 1º futebol
# 2º basquete
# 3º tênis
# 4º vôlei

SPORTS = [
    # FUTEBOL
    {
        "key": "soccer_brazil_campeonato",
        "nome": "Brasileirão",
        "tipo": "soccer"
    },
    {
        "key": "soccer_epl",
        "nome": "Premier League",
        "tipo": "soccer"
    },
    {
        "key": "soccer_spain_la_liga",
        "nome": "La Liga",
        "tipo": "soccer"
    },
    {
        "key": "soccer_uefa_champs_league",
        "nome": "Champions League",
        "tipo": "soccer"
    },

    # BASQUETE
    {
        "key": "basketball_nba",
        "nome": "NBA",
        "tipo": "other"
    },
    {
        "key": "basketball_euroleague",
        "nome": "EuroLeague",
        "tipo": "other"
    },

    # TÊNIS
    {
        "key": "tennis_atp_french_open",
        "nome": "ATP",
        "tipo": "other"
    },
    {
        "key": "tennis_wta_french_open",
        "nome": "WTA",
        "tipo": "other"
    },

    # VÔLEI
    {
        "key": "volleyball_usa_pvl",
        "nome": "Vôlei",
        "tipo": "other"
    }
]


# ============================================================
# CONTROLE DE CRÉDITOS
# ============================================================

CREDITOS_RESTANTES = None
CREDITOS_USADOS = None
CUSTO_ULTIMA_CHAMADA = None

# Quantas vezes cada esporte foi consultado
CONTADOR_ESPORTES = {}

# ============================================================
# MEMÓRIA DOS ALERTAS
# ============================================================

alertas_enviados = set()


def limpar_memoria():

    global alertas_enviados

    if len(alertas_enviados) > MAX_ALERTAS_MEMORIA:

        lista = list(alertas_enviados)

        alertas_enviados = set(
            lista[-1500:]
        )


# ============================================================
# ID DO JOGO
# ============================================================

def gerar_id_jogo(game):

    game_id = game.get("id")

    if game_id:
        return str(game_id)

    home = game.get("home_team", "")
    away = game.get("away_team", "")
    commence = game.get("commence_time", "")

    return f"{home}|{away}|{commence}"


# ============================================================
# MELHORES ODDS
# ============================================================

def obter_melhores_odds(game):

    best = {}
    books = {}

    for bookmaker in game.get("bookmakers", []):

        bookmaker_name = bookmaker.get(
            "title",
            "Casa desconhecida"
        )

        for market in bookmaker.get("markets", []):

            if market.get("key") != "h2h":
                continue

            for outcome in market.get("outcomes", []):

                name = outcome.get("name")
                price = outcome.get("price")

                if not name or price is None:
                    continue

                try:
                    price = float(price)
                except Exception:
                    continue

                if price <= 1:
                    continue

                if name not in best or price > best[name]:

                    best[name] = price
                    books[name] = bookmaker_name

    return best, books


# ============================================================
# VALIDAR MERCADO
# ============================================================

def verificar_mercado(game, best, is_soccer):

    if is_soccer:

        home = game.get("home_team")
        away = game.get("away_team")

        if not home or not away:
            return False

        nomes = set(best.keys())

        # Casa
        if home not in nomes:
            return False

        # Fora
        if away not in nomes:
            return False

        # Procurar empate
        empate = None

        for nome in nomes:

            if nome.lower() in [
                "draw",
                "empate"
            ]:
                empate = nome
                break

        if empate is None:
            return False

        # Futebol precisa ter exatamente:
        # CASA + EMPATE + FORA
        if len(best) != 3:
            return False

        return True

    else:

        # Outros esportes:
        # precisa ter 2 resultados
        if len(best) != 2:
            return False

        return True


# ============================================================
# CALCULAR SUREBET
# ============================================================

def calcular_surebet(best):

    if not best:
        return None

    inversa = 0.0

    for odd in best.values():
        inversa += 1.0 / odd

    # Se não houver lucro mínimo, ignora
    if inversa >= INVERSA_MAX:
        return None

    retorno = BANCA / inversa

    lucro = retorno - BANCA

    lucro_percentual = (
        lucro / BANCA
    ) * 100

    stakes = {}

    for resultado, odd in best.items():

        stake = (
            (BANCA / odd)
            / inversa
        )

        stakes[resultado] = stake

    return {
        "inversa": inversa,
        "retorno": retorno,
        "lucro": lucro,
        "lucro_percentual":
    stakes = {}

    for resultado, odd in best.items():

        stake = (
            (BANCA / odd)
            / inversa
        )

        stakes[resultado] = stake

    return {
        "inversa": inversa,
        "retorno": retorno,
        "lucro": lucro,
        "lucro_percentual": lucro_percentual,
        "stakes": stakes
    }


# ============================================================
# MENSAGEM
# ============================================================

def montar_mensagem(
    game,
    sport_nome,
    best,
    books,
    resultado,
    is_soccer,
    minutos
):

    if is_soccer:
        tipo = "⚽ FUTEBOL — 3 RESULTADOS"
    else:
        tipo = "🏆 2 RESULTADOS"

    lucro_pct = resultado["lucro_percentual"]
    retorno = resultado["retorno"]
    lucro = resultado["lucro"]

    home = game.get("home_team", "?")
    away = game.get("away_team", "?")

    texto = ""

    texto += "🚨 <b>SUREBET TURBO V3</b> 🚨\n\n"
    texto += f"<b>{tipo}</b>\n"
    texto += f"💰 Margem matemática: <b>{lucro_pct:.2f}%</b>\n"
    texto += f"⏰ Começa em: <b>{minutos} min</b>\n\n"
    texto += f"⚽ <b>{home} x {away}</b>\n\n"

    texto += "💵 <b>DIVISÃO DA BANCA — R$100</b>\n\n"

    for resultado_nome, odd in best.items():

        stake = resultado["stakes"][resultado_nome]

        bookmaker = books.get(
            resultado_nome,
            "Casa"
        )

        texto += (
            f"👉 <b>{resultado_nome}</b>\n"
            f"R${stake:.2f} @ <b>{odd:.2f}</b>\n"
            f"🏠 {bookmaker}\n\n"
        )

    texto += "━━━━━━━━━━━━━━━━\n"
    texto += f"💰 Retorno: <b>R${retorno:.2f}</b>\n"
    texto += f"📈 Lucro teórico: <b>R${lucro:.2f}</b>\n"
    texto += "━━━━━━━━━━━━━━━━\n\n"
    texto += "⚠️ Odds podem mudar antes da confirmação.\n"
    texto += "⚠️ Confira as odds nas casas antes de apostar."

    return texto
