import os
import time
import threading
import requests
from flask import Flask
from datetime import datetime, timezone

# =========================================================
# CONFIGURAÇÃO
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
ODDS_API_KEY = os.getenv("ODDS_API_KEY")

BANCA = 100.00

# Só considera jogos que começam dentro deste período
HORAS_MAX = 3

# Intervalo entre ciclos
INTERVALO_CICLO = 900  # 15 minutos

# Surebet mínima
# 0.99 = exige pelo menos aproximadamente 1% de margem matemática
INVERSA_MAX = 0.99

# Quantidade máxima de alertas guardados em memória
MAX_ALERTAS_MEMORIA = 2000


# =========================================================
# FLASK
# =========================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "Surebet TURBO V2 ON"


@app.route("/teste")
def teste():
    send("🧪 *TESTE OK*\n\nSurebet TURBO V2 está funcionando.")
    return "Teste enviado"


# =========================================================
# TELEGRAM
# =========================================================

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
                "parse_mode": "Markdown"
            },
            timeout=10
        )

        if response.status_code != 200:
            print("Erro Telegram:", response.text)
            return False

        return True

    except Exception as e:
        print("Erro ao enviar Telegram:", e)
        return False


# =========================================================
# ESPORTES
# =========================================================

SPORTS = [
    # FUTEBOL
    "soccer_brazil_campeonato",
    "soccer_epl",
    "soccer_spain_la_liga",
    "soccer_uefa_champs_league",

    # BASQUETE
    "basketball_nba",
    "basketball_euroleague",

    # TÊNIS
    "tennis_atp_french_open",
    "tennis_wta_french_open",

    # VÔLEI
    "volleyball_usa_pvl"
]


# =========================================================
# MEMÓRIA ANTI-DUPLICAÇÃO
# =========================================================

alertas_enviados = set()


def limpar_memoria():
    global alertas_enviados

    if len(alertas_enviados) > MAX_ALERTAS_MEMORIA:
        lista = list(alertas_enviados)

        # mantém os mais recentes aproximadamente
        alertas_enviados = set(lista[-1000:])


# =========================================================
# IDENTIFICAÇÃO DO JOGO
# =========================================================

def gerar_id_jogo(game):
    """
    Cria um identificador único para evitar que
    o mesmo jogo seja enviado repetidamente.
    """

    game_id = game.get("id")

    if game_id:
        return str(game_id)

    home = game.get("home_team", "")
    away = game.get("away_team", "")
    commence = game.get("commence_time", "")

    return f"{home}|{away}|{commence}"


# =========================================================
# OBTÉM MELHORES ODDS
# =========================================================

def obter_melhores_odds(game):

    best = {}
    books = {}

    for bookmaker in game.get("bookmakers", []):

        bookmaker_name = bookmaker.get("title", "Casa desconhecida")

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
                except:
                    continue

                if price <= 1:
                    continue

                if name not in best or price > best[name]:
                    best[name] = price
                    books[name] = bookmaker_name

    return best, books


# =========================================================
# VERIFICA RESULTADOS
# =========================================================

def verificar_mercado(game, best, is_soccer):

    if is_soccer:

        home = game.get("home_team")
        away = game.get("away_team")

        if not home or not away:
            return False

        # Futebol precisa obrigatoriamente de:
        # Casa + Empate + Fora

        nomes = set(best.keys())

        if home not in nomes:
            return False

        if away not in nomes:
            return False

        empate = None

        for nome in nomes:
            if nome.lower() in ["draw", "empate"]:
                empate = nome
                break

        if empate is None:
            return False

        # Exatamente 3 resultados
        if len(best) != 3:
            return False

        return True

    else:

        # Outros esportes precisam de exatamente
        # dois resultados.

        if len(best) != 2:
            return False

        return True


# =========================================================
# CÁLCULO DA SUREBET
# =========================================================

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

    lucro_percentual = (lucro / BANCA) * 100

    stakes = {}

    for resultado, odd in best.items():

        stake = (BANCA / odd) / inversa

        stakes[resultado] = stake

    return {
        "inversa": inversa,
        "retorno": retorno,
        "lucro": lucro,
        "lucro_percentual": lucro_percentual,
        "stakes": stakes
    }


# =========================================================
# FORMATAÇÃO DA MENSAGEM
# =========================================================

def montar_mensagem(
    game,
    sport,
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

    texto += "🚨 *SUREBET TURBO V2* 🚨\n\n"

    texto += f"*{tipo}*\n"
    texto += f"💰 Margem matemática: *{lucro_pct:.2f}%*\n"
    texto += f"⏰ Começa em: *{minutos} min*\n\n"

    texto += f"⚽ *{home} x {away}*\n"
    texto += f"_{sport}_\n\n"

    texto += "💵 *DIVISÃO DA BANCA — R$100:*\n\n"

    for resultado_nome, odd in best.items():

        stake = resultado["stakes"][resultado_nome]
        bookmaker = books.get(resultado_nome, "Casa")

        texto += (
            f"👉 *{resultado_nome}*\n"
            f"R${stake:.2f} @ *{odd:.2f}*\n"
            f"🏠 {bookmaker}\n\n"
        )

    texto += "━━━━━━━━━━━━━━━━\n"

    texto += f"💰 Retorno: *R${retorno:.2f}*\n"
    texto += f"📈 Lucro teórico: *R${lucro:.2f}*\n"

    texto += "━━━━━━━━━━━━━━━━\n\n"

    texto += "⚠️ Odds podem mudar antes da confirmação.\n"
    texto += "⚠️ Verifique as odds nas casas antes de apostar."

    return texto


# =========================================================
# PROCESSAMENTO DE UM ESPORTE
# =========================================================

def processar_esporte(sport):

    is_soccer = "soccer" in sport

    url = (
        f"https://api.the-odds-api.com/v4/sports/"
        f"{sport}/odds/"
        f"?apiKey={ODDS_API_KEY}"
        f"&regions=eu,us,br"
        f"&markets=h2h"
        f"&oddsFormat=decimal"
    )

    try:

        response = requests.get(
            url,
            timeout=20
        )

        if response.status_code != 200:

            print(
                f"[{sport}] API HTTP {response.status_code}: "
                f"{response.text[:300]}"
            )

            return

        try:
            jogos = response.json()
        except:
            print(f"[{sport}] Resposta não é JSON.")
            return

        if not isinstance(jogos, list):
            print(f"[{sport}] Resposta inesperada.")
            return

        print(f"[{sport}] {len(jogos)} jogos encontrados.")

        for game in jogos:

            try:

                # -----------------------------------------
                # HORÁRIO
                # -----------------------------------------

                commence_time = game.get("commence_time")

                if not commence_time:
                    continue

                commence = datetime.fromisoformat(
                    commence_time.replace("Z", "+00:00")
                )

                agora = datetime.now(timezone.utc)

                diferenca = (
                    commence - agora
                ).total_seconds()

                horas = diferenca / 3600

                # jogo já começou
                if horas < 0:
                    continue

                # mais de 3 horas
                if horas > HORAS_MAX:
                    continue

                minutos = int(diferenca / 60)

                # -----------------------------------------
                # ODDS
                # -----------------------------------------

                best, books = obter_melhores_odds(game)

                if not best:
                    continue

                # -----------------------------------------
                # MERCADO
                # -----------------------------------------

                if not verificar_mercado(
                    game,
                    best,
                    is_soccer
                ):
                    continue

                # -----------------------------------------
                # SUREBET
                # -----------------------------------------

                resultado = calcular_surebet(best)

                if not resultado:
                    continue

                # -----------------------------------------
                # ID
                # -----------------------------------------

                game_id = gerar_id_jogo(game)

                # Incluímos as odds na chave.
                # Assim, se as odds mudarem e surgir
                # uma nova oportunidade, o robô poderá
                # alertar novamente.

                odds_key = "|".join(
                    f"{k}:{best[k]:.3f}"
                    for k in sorted(best.keys())
                )

                alerta_id = (
                    f"{game_id}|{odds_key}"
                )

                if alerta_id in alertas_enviados:
                    continue

                # -----------------------------------------
                # ENVIA
                # -----------------------------------------

                mensagem = montar_mensagem(
                    game=game,
                    sport=sport,
                    best=best,
                    books=books,
                    resultado=resultado,
                    is_soccer=is_soccer,
                    minutos=minutos
                )

                enviado = send(mensagem)

                if enviado:

                    alertas_enviados.add(alerta_id)

                    limpar_memoria()

                    print(
                        f"✅ SUREBET ENVIADA: "
                        f"{game.get('home_team')} x "
                        f"{game.get('away_team')} | "
                        f"{resultado['lucro_percentual']:.2f}%"
                    )

            except Exception as e:

                print(
                    f"[{sport}] Erro processando jogo:",
                    e
                )

    except requests.exceptions.Timeout:

        print(f"[{sport}] Timeout na API.")

    except requests.exceptions.RequestException as e:

        print(
            f"[{sport}] Erro de conexão:",
            e
        )

    except Exception as e:

        print(
            f"[{sport}] Erro geral:",
            e
        )


# =========================================================
# LOOP PRINCIPAL
# =========================================================

def bot_loop():

    print("===================================")
    print("   SUREBET TURBO V2 INICIANDO")
    print("===================================")

    time.sleep(5)

    if not BOT_TOKEN:
        print("⚠️ BOT_TOKEN não configurado.")

    if not CHAT_ID:
        print("⚠️ CHAT_ID não configurado.")

    if not ODDS_API_KEY:
        print("⚠️ ODDS_API_KEY não configurado.")

    send(
        "✅ *SUREBET TURBO V2 ATIVADO!*\n\n"
        "⚽ Futebol = Casa / Empate / Fora\n"
        "🏀🎾🏐 Outros = 2 resultados\n"
        "💰 Banca configurada: R$100\n"
        "⏰ Janela: até 3 horas\n"
        "🚫 Anti-duplicação: ON\n"
        "📊 Cálculo automático: ON\n\n"
        "🔎 Radar procurando oportunidades..."
    )

    while True:

        try:

            if not ODDS_API_KEY:

                print(
                    "ODDS_API_KEY ausente. "
                    "Tentando novamente em 60s."
                )

                time.sleep(60)

                continue

            inicio = time.time()

            print("\n===================================")
            print("🔎 INICIANDO NOVO CICLO")
            print(
                datetime.now().strftime(
                    "%d/%m/%Y %H:%M:%S"
                )
            )
            print("===================================")

            for sport in SPORTS:

                processar_esporte(sport)

                # Pequena pausa para não bombardear a API
                time.sleep(2)

            duracao = time.time() - inicio

            print("\n===================================")
            print(
                f"✅ CICLO CONCLUÍDO EM "
                f"{duracao:.1f}s"
            )
            print(
                f"⏳ Próximo ciclo em "
                f"{INTERVALO_CICLO // 60} minutos"
            )
            print("===================================")

            time.sleep(INTERVALO_CICLO)

        except Exception as e:

            print(
                "❌ Erro no loop principal:",
                e
            )

            time.sleep(60)


# =========================================================
# START
# =========================================================

threading.Thread(
    target=bot_loop,
    daemon=True
).start()


if __name__ == "__main__":

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
