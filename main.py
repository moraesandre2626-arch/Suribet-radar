import os, time, threading, requests
from flask import Flask
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
ODDS_API_KEY = os.getenv("ODDS_API_KEY")
app = Flask(__name__)
@app.route('/')
def home(): return "Surebet 1% ON"
def send(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except: pass
def bot_loop():
    time.sleep(5)
    send("✅ *Radar TURBINADO! Caçando surebets >1%*\n\n🎯 Todas as casas\n💰 Lucro mínimo: 1%\n⏳ Analisando jogos agora...")
    while True:
        try:
            if not ODDS_API_KEY: time.sleep(60); continue
            sports = ["soccer_brazil_campeonato", "soccer_epl", "soccer_spain_la_liga", "soccer_uefa_champs_league"]
            for sport in sports:
                url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/?apiKey={ODDS_API_KEY}&regions=eu,us,br&markets=h2h&oddsFormat=decimal"
                r = requests.get(url, timeout=15).json()
                if not isinstance(r, list): continue
                for game in r[:10]:
                    best = {}; books = {}
                    for book in game.get("bookmakers", []):
                        for m in book.get("markets", []):
                            for o in m.get("outcomes", []):
                                name = o["name"]; price = o["price"]
                                if name not in best or price > best[name]:
                                    best[name] = price; books[name] = book["title"]
                    if len(best) < 2: continue
                    inv = sum(1/o for o in best.values())
                    if inv < 0.99:
                        profit = (1 - inv) * 100
                        msg = f"🚨 *SUREBET {profit:.2f}%* 🚨\n\n⚽ {game.get('home_team')} vs {game.get('away_team')}\n🏆 {sport}\n\n"
                        for k,v in best.items(): msg += f"{k}: {v} @ {books[k]}\n"
                        msg += f"\n💰 Lucro: {profit:.2f}%"
                        send(msg)
                time.sleep(2)
            print("Ciclo ok, esperando 5 min")
            time.sleep(300)
        except Exception as e:
            print(f"Erro: {e}"); time.sleep(60)
threading.Thread(target=bot_loop, daemon=True).start()
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
