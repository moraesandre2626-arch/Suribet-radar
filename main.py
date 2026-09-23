import os
import time
import threading
import requests
from flask import Flask
from datetime import datetime, timezone

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
ODDS_API_KEY = os.getenv("ODDS_API_KEY")
ODDS_REGION = os.getenv("ODDS_REGION", "br")

BANCA = 100.0
INTERVALO_CICLO = 60
INVERSA_MAX = 0.99
CREDITOS_MINIMOS = 5
MAX_ALERTAS_MEMORIA = 3000
TIMEOUT_API = 20

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

app = Flask(__name__)


@app.route("/")
def home():
    return (
        "<h2>SUREBET TURBO V4 ON</h2>"
        f"<b>Créditos restantes:</b> "
        f"{CREDITOS_RESTANTES if CREDITOS_RESTANTES is not None else 'desconhecido'}<br>"
        f"<b>Créditos usados:</b> "
        f"{CREDITOS_USADOS if CREDITOS_USADOS is not None else 'desconhecido'}<br>"
        f"<b>Última chamada:</b> "
        f"{CUSTO_ULTIMA_CHAMADA if CUSTO_ULTIMA_CHAMADA is not None else 'desconhecido'}<br>"
        f"<b>Região:</b> {ODDS_REGION}<br>"
        f"<b>Intervalo:</b> {INTERVALO_CICLO}s<br>"
        f"<b>Última consulta:</b> {ultima_consulta or 'nenhuma'}<br>"
        f"<b>Jogos:</b> {total_jogos_consultados}<br>"
        f"<b>Surebets:</b> {total_surebets}<br>"
        f"<b>Erros API:</b> {total_erros_api}<br>"
        f"<b>Alertas:</b> {len(alertas_enviados)}<br>"
        f"<b>Status:</b> {ultimo_status}"
    )


@app.route("/teste")
def teste():
    if send(
        "🧪 <b>TESTE OK</b>\n\n"
        "🚀 Surebet TURBO V4 está funcionando."
    ):
        return "Teste enviado para o Telegram."

    return "Erro ao enviar teste."


def send(msg):
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ BOT_TOKEN ou CHAT_ID não configurado.")
        return False

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
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
        print(f"❌ Erro Telegram: {e}")
        return False


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


def limpar_memoria():
    global alertas_enviados

    if len(alertas_enviados) > MAX_ALERTAS_MEMORIA:
        alertas_enviados = set(
            list(alertas_enviados)[-1500:]
        )
        print("🧹 Memória de alertas reduzida.")


def gerar_id_jogo(game):
    if game.get("id"):
        return str(game["id"])

    return (
        f"{game.get('home_team', '')}|"
        f"{game.get('away_team', '')}|"
        f"{game.get('commence_time', '')}"
    )


def obter_melhores_odds(game):
    best = {}
    books = {}

    for bookmaker in game.get("bookmakers", []):

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

                if not name or price is None:
                    continue

                try:
                    price = float(price)
                except (TypeError, ValueError):
                    continue

                if price > 1 and (
                    name not in best
                    or price > best[name]
                ):
                    best[name] = price
                    books[name] = bookmaker_name

    return best, books


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

        empate = any(
            nome.lower() in (
                "draw",
                "empate"
            )
            for nome in nomes
        )

        return empate and len(best) == 3

    return len(best) == 2


def calcular_surebet(best):

    if not best:
        return None

    inversa = sum(
        1.0 / odd
        for odd in best.values()
    )

    if inversa >= INVERSA_MAX:
        return None

    retorno = BANCA / inversa
    lucro = retorno - BANCA

    stakes = {}

    for resultado, odd in best.items():
        stakes[resultado] = (
            (BANCA / odd)
            / inversa
        )

    return {
        "inversa": inversa,
        "retorno": retorno,
        "lucro": lucro,
        "lucro_percentual": (
            lucro / BANCA
        ) * 100,
        "stakes": stakes
    }


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

        minutos = int(
            (
                data
                - datetime.now(timezone.utc)
            ).total_seconds()
            / 60
        )

        if minutos < 0:
            return "já começou"

        return minutos

    except Exception:
        return "?"


def montar_mensagem(
    game,
    sport_nome,
    best,
    books,
    resultado,
    is_soccer,
    minutos
):

    tipo = (
        "⚽ FUTEBOL — 3 RESULTADOS"
        if is_soccer
        else "🏆 2 RESULTADOS"
    )

    texto = (
        "🚨 <b>SUREBET TURBO V4</b> 🚨\n\n"
        f"<b>{tipo}</b>\n"
        f"💰 Margem matemática: "
        f"<b>{resultado['lucro_percentual']:.2f}%</b>\n"
        f"⏰ Começa em: "
        f"<b>{minutos} min</b>\n"
        f"🏆 Esporte: "
        f"<b>{sport_nome}</b>\n\n"
        f"⚽ <b>{game.get('home_team', '?')} "
        f"x {game.get('away_team', '?')}</b>\n\n"
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

    texto += (
        "━━━━━━━━━━━━━━━━\n"
        f"💰 Retorno: "
        f"<b>R${resultado['retorno']:.2f}</b>\n"
        f"📈 Lucro teórico: "
        f"<b>R${resultado['lucro']:.2f}</b>\n"
        "━━━━━━━━━━━━━━━━\n\n"
        "⚠️ Odds podem mudar antes da confirmação.\n"
        "⚠️ Confira as odds nas casas antes de apostar."
    )

    return texto


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
            CREDITOS_RESTANTES = int(
                restante
            )
    except (TypeError, ValueError):
        pass

    try:
        if usado is not None:
            CREDITOS_USADOS = int(
                usado
            )
    except (TypeError, ValueError):
        pass

    try:
        if ultimo is not None:
            CUSTO_ULTIMA_CHAMADA = int(
                ultimo
            )
    except (TypeError, ValueError):
        pass

    print(
        "💳 CRÉDITOS | "
        f"restantes={CREDITOS_RESTANTES} | "
        f"usados={CREDITOS_USADOS} | "
        f"última={CUSTO_ULTIMA_CHAMADA}"
    )


def consultar_esporte(sport):

    global total_erros_api

    if not ODDS_API_KEY:
        print(
            "❌ ODDS_API_KEY não configurada."
        )
        return []

    try:

        response = requests.get(
            (
                "https://api.the-odds-api.com/"
                "v4/sports/"
                f"{sport['key']}/odds"
            ),
            params={
                "apiKey": ODDS_API_KEY,
                "regions": ODDS_REGION,
                "markets": "h2h",
                "oddsFormat": "decimal"
            },
            timeout=TIMEOUT_API
        )

        atualizar_creditos(
            response
        )

        if response.status_code != 200:

            total_erros_api += 1

            print(
                f"❌ API {sport['nome']}: "
                f"{response.status_code}"
            )

            print(
                response.text[:500]
            )

            return []

        dados = response.json()

        if not isinstance(
            dados,
            list
        ):
            return []

        print(
            f"📊 {sport['nome']}: "
            f"{len(dados)} jogos recebidos."
        )

        return dados

    except Exception as e:

        total_erros_api += 1

        print(
            f"❌ Erro API "
            f"{sport['nome']}: {e}"
        )

        return []


def processar_esporte(sport):

    global total_jogos_consultados
    global total_surebets

    print(
        f"🔎 Consultando "
        f"{sport['nome']}..."
    )

    jogos = consultar_esporte(
        sport
    )

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

            game_id = gerar_id_jogo(
                game
            )

            if game_id in alertas_enviados:
                continue

            best, books = (
                obter_melhores_odds(
                    game
                )
            )

            if not verificar_mercado(
                game,
                best,
                is_soccer
            ):
                continue

            resultado = (
                calcular_surebet(
                    best
                )
            )

            if not resultado:
                continue

            total_surebets += 1

            mensagem = (
                montar_mensagem(
                    game,
                    sport["nome"],
                    best,
                    books,
                    resultado,
                    is_soccer,
                    minutos_ate_jogo(game)
                )
            )

            if send(mensagem):

                alertas_enviados.add(
                    game_id
                )

                print(
                    "🚨 SUREBET ENVIADA:",
                    game.get("home_team"),
                    "x",
                    game.get("away_team"),
                    "|",
                    f"{resultado['lucro_percentual']:.2f}%"
                )

            limpar_memoria()

        except Exception as e:

            print(
                f"❌ Erro processando jogo: {e}"
            )


def ciclo():

    global ultima_consulta
    global ultimo_status

    print(
        "=========================================="
    )

    print(
        "🚀 NOVO CICLO DO SUREBET TURBO V4"
    )

    print(
        "=========================================="
    )

    ultima_consulta = (
        datetime.now(
            timezone.utc
        ).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )
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
        and
        CREDITOS_RESTANTES
        <= CREDITOS_MINIMOS
    ):

        ultimo_status = (
            "PAUSADO: poucos créditos"
        )

        print(
            "🛑 Poucos créditos restantes."
        )

        return

    ultimo_status = (
        "Consultando odds..."
    )

    for sport in SPORTS:

        if (
            CREDITOS_RESTANTES is not None
            and
            CREDITOS_RESTANTES
            <= CREDITOS_MINIMOS
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
        "=========================================="
    )

    print(
        "✅ CICLO CONCLUÍDO"
    )

    print(
        f"📊 Jogos consultados: "
        f"{total_jogos_consultados}"
    )

    print(
        f"🎯 Surebets encontradas: "
        f"{total_surebets}"
    )

    print(
        f"❌ Erros API: "
        f"{total_erros_api}"
    )

    print(
        f"💳 Créditos restantes: "
        f"{CREDITOS_RESTANTES}"
    )

    print(
        "=========================================="
    )


def iniciar_robo():

    global robo_iniciado

    if robo_iniciado:
        return

    robo_iniciado = True

    print(
        "🤖 THREAD DO ROBÔ INICIADA"
    )

    while True:

        try:

            ciclo()

        except Exception as e:

            print(
                f"❌ Erro geral no ciclo: {e}"
            )

        print(
            f"⏳ Aguardando "
            f"{INTERVALO_CICLO} segundos..."
        )

        time.sleep(
            INTERVALO_CICLO
        )


if __name__ == "__main__":

    print(
        "=========================================="
    )

    print(
        "🚀 SUREBET TURBO V4 INICIANDO"
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

    print(
        f"REGIÃO: {ODDS_REGION}"
    )

    print(
        f"INTERVALO: "
        f"{INTERVALO_CICLO} segundos"
    )

    print(
        "=========================================="
    )

    threading.Thread(
        target=iniciar_robo,
        daemon=True
    ).start()

    app.run(
        host="0.0.0.0",
        port=int(
            os.getenv(
                "PORT",
                "10000"
            )
        )
    )
