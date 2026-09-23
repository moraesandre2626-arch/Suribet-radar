import os, time, threading, requests
from flask import Flask
from datetime import datetime, timezone

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
ODDS_API_KEY = os.getenv("ODDS_API_KEY")

app = Flask(__name__)
@app.route('/')
def home(): return "Surebet CALC ON"

def send(msg):
    try:
        url = "https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def bot_loop():
    time.sleep(5)
    send("✅ *Radar COM CALCULADORA ATIVADO!*\n\n💰 Banca padrão: R$100\n⏰ Só jogos até 3h\n🔄 A cada 15 min")
    while True:
        try:
            if not ODDS_API_KEY:
                time.sleep(60); continue
            sports = ["soccer_brazil_campeonato","soccer_epl","soccer_spain_la_liga","soccer_uefa_champs_league"]
            for sport in sports:
                base = "https://api.the-odds-api.com/v4/sports/"
                full_url = base + sport + "/odds/?apiKey=" + ODDS_API_KEY + "&regions=eu,us,br&markets=h2h&oddsFormat=decimal"
                r = requests.get(full_url, timeout=15).json()
                if not isinstance(r, list): continue
                for game in r:
                    try:
                        ct = game.get("commence_time")
                        commence = datetime.fromisoformat(ct.replace("Z", "+00:00"))
                        now = datetime.now(timezone.utc)
                        diff = (commence - now).total_seconds() / 3600
                        if diff < 0 or diff > 3: continue
                    except: continue

                    best = {}; books = {}
                    for book in game.get("bookmakers", []):
                        for m in book.get("markets", []):
                            for o in m.get("outcomes", []):
                                name = o["name"]; price = o["price"]
                                if name not in best or price > best[name]:
                                    best[name] = price; books[name] = book["title"]
                    if len(best) < 2: continue
                    inv = sum(1/x for x in best.values())
                    if inv < 0.99:
                        profit = (1 - inv) * 100
                        mins = int(diff * 60)
                        BANCA = 100.0
                        txt = "🚨 *SUREBET " + f"{profit:.2f}" + "% - " + str(mins) + " MIN* 🚨\n\n"
                        txt += game.get('home_team') + " vs " + game.get('away_team') + "\n\n"
                        
                        # CALCULO DA DIVISAO
                        txt += "💵 *DIVISÃO BANCA R$100:*\n"
                        for k,v in best.items():
                            stake = (BANCA / v) / inv
                            retorno = stake * v
                            txt += f"👉 {k}: R${stake:.2f} @ {v} ({books[k]})\n"
                        
                        lucro = BANCA / inv - BANCA
                        txt += f"\n✅ Retorno: R${BANCA/inv:.2f}\n"
                        txt += f"💰 *LUCRO GARANTIDO: R${lucro:.2f} ({profit:.2f}%)*\n"
                        txt += f"\n⚡ Começa em {mins} min - APOSTA AGORA!"
                        send(txt)
                time.sleep(2)
            print("Ciclo calc ok")
            time.sleep(900)
        except Exception as e:
            print(e); time.sleep(60)

threading.Thread(target=bot_loop, daemon=True).start()
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
