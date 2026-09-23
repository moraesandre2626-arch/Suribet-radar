import os
import time
import threading
import requests
from flask import Flask
from datetime import datetime, timezone

# ============================================================
# SUREBET TURBO V4
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
ODDS_API_KEY = os.getenv("ODDS_API_KEY")

ODDS_REGION = os.getenv("ODDS_REGION", "br")

# Banca usada somente para calcular a divisão
BANCA = 100.00

# Intervalo entre os ciclos
INTERVALO_CICLO = 60

# Só alerta quando a soma das inversas for menor que 0.99
# Isso representa margem matemática superior a aproximadamente 1%
INVERSA_MAX = 0.99

# Para o robô não gastar a cota até zerar
CREDITOS_MINIMOS = 5

# Memória máxima de jogos já alertados
MAX_ALERTAS_MEMORIA = 3000

# Timeout das consultas
TIMEOUT_API = 20

# ============================================================
# CONTROLE
# ============================================================

CREDITOS_RESTANTES = None
CREDITOS_USADOS = None
CUSTO_ULTIMA_CHAMADA = None

alertas_enviados = set()

robo_iniciado = False

ultima_consulta = None
ultimo_status = "Aguardando primeira consulta"

total_jogos_consultados = 0
total_surebets = 0
total_erros_api = 0


# ============================================================
# FLASK
# ============================================================

app = Flask(__name__)


@app.route("/")
def home():

    restante = (
        CREDITOS_RESTANTES
        if CREDITOS_RESTANTES is not None
        else "desconhecido"
    )

    return (
        "<h2>SUREBET TURBO V4 ON</h2>"
        f"<b>Créditos restantes:</b> {restante}<br>"
        f"<b>Créditos usados:</b> "
        f"{CREDITOS_USADOS if CREDITOS_USADOS is not None else 'desconhecido'}<br>"
        f"<b>Última chamada:</b> "
        f"{CUSTO_ULTIMA_CHAMADA if CUSTO_ULTIMA_CHAMADA is not None else 'desconhecido'}<br>"
        f"<b>Região:</b> {ODDS_REGION}<br>"
        f"<b>Intervalo:</b> {INTERVALO_CICLO}s<br>"
        f"<b>Última consulta:</b> "
        f"{ultima_consulta or 'nenhuma'}<br>"
        f"<b>Jogos:</b> {total_jogos_consultados}<br>"
        f"<b>Surebets:</b> {total_surebets}<br>"
        f"<b>Erros API:</b> {total_erros_api}<br>"
        f"<b>Alertas na memória:</b> {len(alertas_enviados)}<br>"
        f"<b>Status:</b> {ultimo_status}"
    )


@app.route("/teste")
def teste():

    enviado = send(
        "🧪 <b>TESTE OK</b>\n\n"
        "🚀 Surebet TURBO V4 está funcionando."
    )

    if enviado:
        return "Teste enviado para o Telegram."

    return "Erro ao enviar teste."


# ============================================================
# TELEGRAM
# ============================================================

def send(msg):

    if not BOT_TOKEN or not CHAT_ID:

        print("❌ BOT_TOKEN ou CHAT_ID não configurado.")

        return False

    try:

        url = (
            f"https://api.telegram.org/"
            f"bot{BOT_TOKEN}/sendMessage"
        )

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

            print(
                "❌ Erro Telegram:",
                response.text[:500]
            )

            return False

        print("📲 Telegram: mensagem enviada.")

        return True

    except Exception as e:

        print("❌ Erro Telegram:", e)

        return False


# ============================================================
# ESPORTES
# ============================================================

SPORTS = [

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

    {
        "key": "volleyball_usa_pvl",
        "nome": "Vôlei",
        "tipo": "other"
    }
]


# ============================================================
# MEMÓRIA
# ============================================================

def limpar_memoria():

    global alertas_enviados

    if len(alertas_enviados) <= MAX_ALERTAS_MEMORIA:
        return

    lista = list(alertas_enviados)

    alertas_enviados = set(
        lista[-1500:]
    )

    print(
        "🧹 Memória de alertas reduzida."
    )


# ============================================================
# ID DO JOGO
# ============================================================

def gerar_id_jogo(game):

    game_id = game.get("id")

    if game_id:
        return str(game_id)

    home = game.get(
        "home_team",
        ""
    )

    away = game.get(
        "away_team",
        ""
    )

    commence = game.get(
        "commence_time",
        ""
    )

    return (
        f"{home}|{away}|{commence}"
    )


# ============================================================
# MELHORES ODDS
# ============================================================

def obter_melhores_odds(game):

    best = {}
    books = {}

    for bookmaker in game.get(
        "bookmakers",
        []
    ):

        bookmaker_name = bookmaker.get(
            "title",
            "Casa desconhecida"
        )

        for market in bookmaker.get(
            "markets",
            []
        ):

            if market.get("key") != "h2h":
                continue

            for outcome in market.get(
                "outcomes",
                []
            ):

                name = outcome.get("name")
                price = outcome.get("price")

                if not name:
                    continue

                if price is None:
                    continue

                try:

                    price = float(price)

                except Exception:

                    continue

                if price <= 1:
                    continue

                if (
                    name not in best
                    or price > best[name]
                ):

                    best[name] = price
                    books[name] = bookmaker_name

    return best, books


# ============================================================
# VALIDAR MERCADO
# ============================================================

def verificar_mercado(
    game,
    best,
    is_soccer
):

    if is_soccer:

        home = game.get("home_team")
        away = game.get("away_team")

        if not home or not away:
            return False

        nomes = set(best.keys())

        # Precisa existir odd para o mandante
        if home not in nomes:
            return False

        # Precisa existir odd para o visitante
        if away not in nomes:
            return False

        # Procurar empate
        empate = None

        for nome in nomes:

            if nome.lower() in (
                "draw",
                "empate"
            ):

                empate = nome

                break

        if empate is None:
            return False

        # Futebol precisa ter exatamente 3 resultados
        if len(best) != 3:
            return False

        return True

    # Outros esportes precisam ter 2 resultados
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

    # Não existe arbitragem válida
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
        "lucro_percentual": lucro_percentual,
        "stakes": stakes
    }


# ============================================================
# TEMPO ATÉ O JOGO
# ============================================================

def minutos_ate_jogo(game):

    commence = game.get(
        "commence_time"
    )

    if not commence:
        return "?"

    try:

        data = datetime.fromisoformat(
            commence.replace(
                "Z",
                "+00:00"
            )
        )

        agora = datetime.now(
            timezone.utc
        )

        minutos = int(
            (
                data - agora
            ).total_seconds()
            / 60
        )

        if minutos < 0:
            return "já começou"

        return minutos

    except Exception:

        return "?"


# ============================================================
# MENSAGEM TELEGRAM
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

        tipo = (
            "⚽ FUTEBOL — 3 RESULTADOS"
        )

    else:

        tipo = (
            "🏆 2 RESULTADOS"
        )

    home = game.get(
        "home_team",
        "?"
    )

    away = game.get(
        "away_team",
        "?"
    )

    lucro_pct = resultado[
        "lucro_percentual"
    ]

    retorno = resultado[
        "retorno"
    ]

    lucro = resultado[
        "lucro"
    ]

    texto = ""

    texto += (
        "🚨 <b>SUREBET TURBO V4</b> 🚨\n\n"
    )

    texto += (
        f"<b>{tipo}</b>\n"
    )

    texto += (
        f"💰 Margem matemática: "
        f"<b>{lucro_pct:.2f}%</b>\n"
    )

    texto += (
        f"⏰ Começa em: "
        f"<b>{minutos} min</b>\n"
    )

    texto += (
        f"🏆 Esporte: "
        f"<b>{sport_nome}</b>\n\n"
    )

    texto += (
        f"⚽ <b>{home} x {away}</b>\n\n"
    )

    texto += (
        "💵 <b>DIVISÃO DA BANCA — R$100</b>\n\n"
    )

    for resultado_nome, odd in best.items():

        stake = resultado[
            "stakes"
        ][resultado_nome]

        bookmaker = books.get(
            resultado_nome,
            "Casa"
        )

        texto += (
            f"👉 <b>{resultado_nome}</b>\n"
            f"R${stake:.2f} @ "
            f"<b>{odd:.2f}</b>\n"
            f"🏠 {bookmaker}\n\n"
        )

    texto +=
