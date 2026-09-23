import os, time, threading, requests
from flask import Flask
from datetime import datetime, timezone

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
ODDS_API_KEY = os.getenv("ODDS_API_KEY")

app = Flask(__name__)
@app.route('/')
def home(): return "Surebet TURBO ON"

def send(msg):
    try:
        url = "https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def bot_loop():
    time.sleep(5)
    send("✅ *Radar TURBO ATIVADO!*\n\n⚽ Futebol = 3 resultados (com empate)\n🏀 Basquete/Tênis/Vôlei = 2 resultados\n💰 Banca R$100\n⏰ Até 3h")
    while True:
        try:
            if not ODDS_API_KEY: time.sleep(60); continue
            # TURBO: Futebol + Basquete + Tenis
            sports = [
                "soccer_brazil_campeonato","soccer_epl","soccer_spain_la_liga","soccer_uefa_champs_league",
                "basketball_nba","basketball_euroleague",
                "tennis_atp_french_open","tennis_wta_french_open",
                "volleyball_usa_pvl"
            ]
            for sport in sports:
                is_soccer = "soccer" in sport
                full_url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/?apiKey={ODDS_API_KEY}&regions=eu,us,br&markets=h2h&oddsFormat=decimal"
                r = requests.get(full_url, timeout=15).json()
                if not isinstance(r, list): continue
                for game in r:
                    try:
                        ct = game.get("commence_time")
                        commence = datetime.fromisoformat(ct.replace("Z", "+00:00"))
                        diff = (commence - datetime.now(timezone.utc)).total_seconds() / 3600
                        if diff < 0 or diff > 3: continue
                    except: continue

                    best = {}; books = {}
                    for book in game.get("bookmakers", []):
                        for m in book.get("markets", []):
                            for o in m.get("outcomes", []):
                                name = o["name"]; price = o["price"]
                                if name not in best or price > best[name]:
                                    best[name] = price; books[name] = book["title"]
                    
                    # REGRA TURBO
                    if is_soccer:
                        if len(best) != 3: continue # Futebol só com 3
                    else:
                        if len(best) != 2: continue # Outros só com 2
                    
                    inv = sum(1/x for x in best.values())
                    if inv < 0.99:
                        profit = (1 - inv) * 100
                        mins = int(diff * 60)
                        BANCA = 100.0
                        tipo = "FUTEBOL (3)" if is_soccer else "2 RESULTADOS"
                        txt = f"🚨 *SUREBET {tipo} {profit:.2f}% - {mins} MIN* 🚨\n\n"
                        txt += game.get('home_team') + " vs " + game.get('away_team') + f"\n_{sport}_\n\n"
                        txt += "💵 *DIVISÃO BANCA R$100:*\n"
                        for k,v in best.items():
                            stake = (BANCA / v) / inv
                            txt += f"👉 {k}: R${stake:.2f} @ {v} ({books[k]})\n"
                        txt += f"\n✅ Retorno: R${BANCA/inv:.2f} | LUCRO: R${BANCA/inv - BANCA:.2f}\n"
                        txt += "🔒 100% GARANTIDO!"
                        send(txt)
                time.sleep(2)
            print("Ciclo turbo ok")
            time.sleep(900)
        except Exception as e:
            print(e); time.sleep(60)

threading.Thread(target=bot_loop, daemon=True).start()
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
