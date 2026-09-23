import os, time, threading, requests
from flask import Flask
from datetime import datetime, timezone

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
ODDS_API_KEY = os.getenv("ODDS_API_KEY")

app = Flask(__name__)
@app.route('/')
def home(): return "Surebet 3H ON"

def send(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def bot_loop():
    time.sleep(5)
    send("✅ *Radar INTELIGENTE ATIVADO!*\n\n⏰ Filtrando só jogos que começam em até 3h\n💰 Lucro mínimo: 1%\n🔄 Varredura a cada 15 min")
    
    while True:
        try:
            if not ODDS_API_KEY: 
                time.sleep(60)
                continue

            sports = ["soccer_brazil_campeonato", "soccer_epl", "soccer_spain_la_liga", "soccer_uefa_champs_league", "soccer_brazil_serie_b"]
            
            for sport in sports:
                url = f"https://api.the-odds-api.com/v4/sports/{sport
