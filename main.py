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

ODDS_REGION = os.getenv("ODDS_REGION", "br")

BANCA = 100.00

# Consulta a cada 60 segundos
# Depois podemos ajustar conforme o consumo da API.
INTERVALO_CICLO = 60

# Surebet mínima:
# inversa < 0.99 = margem superior a aproximadamente 1%
INVERSA_MAX = 0.99

# Proteção da cota
CREDITOS_MINIMOS = 5

MAX_ALERTAS_MEMORIA = 3000

# Timeout da API
TIMEOUT_API = 20


# ============================================================
# VARIÁVEIS
# ============================================================

CREDITOS_RESTANTES = None
CREDITOS_USADOS = None
CUSTO_ULTIMA_CHAMADA = None

alertas_enviados = set()

robô_iniciado = False
ultima_consulta = None
ultimo_status = "Aguardando primeira consulta"
total_jogos_consultados = 0
total_surebets = 0

lock = threading.Lock()


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
        "<h2>SUREBET TURBO V3 ON</h2>"
        f"<b>Créditos restantes:</b> {restante}<br>"
        f"<b>Região:</b> {ODDS_REGION}<br>"
        f"<b>Intervalo:</b> {INTERVALO_CICLO}s<br>"
        f"<b>Última consulta:</b> {ultima_consulta or 'nenhuma'}<br>"
        f"<b>Jogos:</b> {total_jogos_consultados}<br>"
        f"<b>Surebets:</b> {total_surebets}<br>"
        f"<b>Status:</b> {ultimo_status}"
    )


@app.route("/teste")
def teste():

    enviado = send(
        "🧪 <b>TESTE OK</b>\n\n"
        "Surebet TURBO V3 está funcionando."
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
                response.text
            )

            return False

        print("📲 Telegram: mensagem enviada.")

        return True

    except Exception as e:

        print(
            "❌ Erro Telegram:",
            e
        )

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

        if home not in nomes:
            return False

        if away not in nomes:
            return False

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

        if len(best) != 3:
            return False

        return True

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

    commence = game.get("commence_time")

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
            (data - agora).total_seconds()
            / 60
        )

        if minutos < 0:
            return "já começou"

        return minutos

    except Exception:

        return "?"


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
        "🚨 <b>SUREBET TURBO V3</b> 🚨\n\n"
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

    texto += "━━━━━━━━━━━━━━━━\n"

    texto += (
        f"💰 Retorno: "
        f"<b>R${retorno:.2f}</b>\n"
    )

    texto += (
        f"📈 Lucro teórico: "
        f"<b>R${lucro:.2f}</b>\n"
    )

    texto += "━━━━━━━━━━━━━━━━\n\n"

    texto += (
        "⚠️ Odds podem mudar antes da confirmação.\n"
        "⚠️ Confira as odds nas casas antes de apostar."
    )

    return texto


# ============================================================
# ATUALIZAR CRÉDITOS
# ============================================================

def atualizar_creditos(response):

    global CREDITOS_RESTANTES
    global CREDITOS_USADOS
    global CUSTO_ULTIMA_CHAMADA

    restante = response.headers.get(
        "x-requests-remaining"
    )

    usado = response.headers.get(
        "x-requests-used"
    )

    ultimo = response.headers.get(
        "x-requests-last"
    )

    try:

        if restante is not None:
            CREDITOS_RESTANTES = int(restante)

    except Exception:
        pass

    try:

        if usado is not None:
            CREDITOS_USADOS = int(usado)

    except Exception:
        pass

    try:

        if ultimo is not None:
            CUSTO_ULTIMA_CHAMADA = int(ultimo)

    except Exception:
        pass

    print(
        "💳 CRÉDITOS | "
        f"restantes={CREDITOS_RESTANTES} | "
        f"usados={CREDITOS_USADOS} | "
        f"última={CUSTO_ULTIMA_CHAMADA}"
    )


# ============================================================
# CONSULTAR ODDS
# ============================================================

def consultar_esporte(sport):

    if not ODDS_API_KEY:

        print("❌ ODDS_API_KEY não configurada.")

        return []

    url = (
        "https://api.the-odds-api.com/v4/sports/"
        f"{sport['key']}/odds"
    )

    params = {
        "apiKey": ODDS_API_KEY,
        "regions": ODDS_REGION,
        "markets": "h2h",
        "oddsFormat": "decimal"
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=TIMEOUT_API
        )

        atualizar_creditos(response)

        if response.status_code != 200:

            print(
                f"❌ API {sport['nome']}: "
                f"{response.status_code}"
            )

            print(response.text[:500])

            return []

        dados = response.json()

        if not isinstance(dados, list):
            return []

        return dados

    except Exception as e:

        print(
            f"❌ Erro API {sport['nome']}:",
            e
        )

        return []


# ============================================================
# PROCESSAR ESPORTE
# ============================================================

def processar_esporte(sport):

    global total_jogos_consultados
    global total_surebets

    print(
        f"🔎 Consultando {sport['nome']}..."
    )

    jogos = consultar_esporte(sport)

    if not jogos:

        print(
            f"ℹ️ Nenhum jogo retornado: "
            f"{sport['nome']}"
        )

        return

    is_soccer = (
        sport["tipo"] == "soccer"
    )

    for game in jogos:

        total_jogos_consultados += 1

        try:

            game_id = gerar_id_jogo(game)

            if game_id in alertas_enviados:
                continue

            best, books = obter_melhores_odds(game)

            if not verificar_mercado(
                game,
                best,
                is_soccer
            ):
                continue

            resultado = calcular_surebet(best)

            if not resultado:
                continue

            total_surebets += 1

            minutos = minutos_ate_jogo(game)

            mensagem = montar_mensagem(
                game,
                sport["nome"],
                best,
                books,
                resultado,
                is_soccer,
                minutos
            )

            enviado = send(mensagem)

            if enviado:

                alertas_enviados.add(
                    game_id
                )

                print(
                    "🚨 SUREBET ENVIADA:",
                    game.get("home_team"),
                    "x",
                    game.get("away_team"),
                    f"| {resultado['lucro_percentual']:.2f}%"
                )

            limpar_memoria()

        except Exception as e:

            print(
                "❌ Erro processando jogo:",
                e
            )


# ============================================================
# CICLO PRINCIPAL
# ============================================================

def ciclo():

    global ultima_consulta
    global ultimo_status

    print(
        "=========================================="
    )

    print(
        "🚀 NOVO CICLO DO SUREBET TURBO V3"
    )

    print(
        "=========================================="
    )

    ultima_consulta = datetime.now(
        timezone.utc
    ).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )

    if not ODDS_API_KEY:

        ultimo_status = (
            "ERRO: ODDS_API_KEY não configurada"
        )

        print(
            "❌ ODDS_API_KEY não configurada."
        )

        return

    if (
        CREDITOS_RESTANTES is not None
        and CREDITOS_RESTANTES <= CREDITOS_MINIMOS
    ):

        ultimo_status = (
            "PAUSADO: poucos créditos"
        )

        print(
            "🛑 Poucos créditos restantes."
        )

        return

    ultimo_status = "Consultando odds..."

    for sport in SPORTS:

        if (
            CREDITOS_RESTANTES is not None
            and CREDITOS_RESTANTES <= CREDITOS_MINIMOS
        ):

            print(
                "🛑 Limite de créditos atingido."
            )

            break

        processar_esporte(
            sport
        )

    ultimo_status = (
        "Ciclo concluído"
    )

    print(
        "✅ CICLO CONCLUÍDO"
    )


# ============================================================
# THREAD DO ROBÔ
# ============================================================

def iniciar_robo():

    global robô_iniciado

    if robô_iniciado:
        return

    robô_iniciado = True

    print(
        "🤖 THREAD DO ROBÔ INICIADA"
    )

    while True:

        try:

            ciclo()

        except Exception as e:

            print(
                "❌ Erro no ciclo:",
                e
            )

        print(
            f"⏳ Aguardando "
            f"{INTERVALO_CICLO} segundos..."
        )

        time.sleep(
            INTERVALO_CICLO
        )


# ============================================================
# INICIAR
# ============================================================

if __name__ == "__main__":

    print(
        "=========================================="
    )

    print(
        "🚀 SUREBET TURBO V3 INICIANDO"
    )

    print(
        "=========================================="
    )

    print(
        f"BOT_TOKEN: "
        f"{'OK' if BOT_TOKEN else 'NÃO CONFIGURADO'}"
    )

    print(
        f"CHAT_ID: "
        f"{'OK' if CHAT_ID else 'NÃO CONFIGURADO'}"
    )

    print(
        f"ODDS_API_KEY: "
        f"{'OK' if ODDS_API_KEY else 'NÃO CONFIGURADO'}"
    )

    threading.Thread(
        target=iniciar_robo,
        daemon=True
    ).start()

    # Mantém o serviço vivo no Render
    app.run(
        host="0.0.0.0",
        port=int(
            os.getenv(
                "PORT",
                "10000"
            )
        )
    )
