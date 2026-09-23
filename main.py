import os, time, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

def send(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg}, timeout=10)
        print(f"Enviado: {msg}")
    except Exception as e:
        print(f"Erro send: {e}")

def bot_loop():
    if not BOT_TOKEN or not CHAT_ID:
        print("ERRO: BOT_TOKEN ou CHAT_ID faltando!")
        return
    send("✅ *Suribet Radar LIGADO no Render!*")
    while True:
        try:
            print("Verificando surebets...")
            # AQUI VAI SUA LOGICA DE SUREBET DEPOIS
            time.sleep(60)
        except Exception as e:
            print(f"Erro loop: {e}")
            time.sleep(10)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot online!")

# Inicia o bot em segundo plano
threading.Thread(target=bot_loop, daemon=True).start()

# Inicia servidor web que o Render exige
port = int(os.environ.get("PORT", 10000))
print(f"Servidor web na porta {port}")
HTTPServer(("0.0.0.0", port), Handler).serve_forever()
