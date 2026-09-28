import os, re, json, time, asyncio
from fastapi import FastAPI
import requests
from bs4 import BeautifulSoup

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
AMAZON_TAG = os.getenv("AMAZON_TAG", "seucodigo-20")
INTERVALO = int(os.getenv("INTERVALO_MS", "900000")) / 1000
QUEDA_MINIMA = float(os.getenv("QUEDA_MINIMA", "5"))

# COLOQUE SEUS LINKS REAIS AQUI - pegue dos 4 apps da sua foto
produtos = [
    {
        "id": "a07",
        "nome": "Samsung Galaxy A07 128GB",
        "marca": "SAMSUNG",
        "urls": [
            "https://www.amazon.com.br/dp/B0DXXXXXXX",
            "https://www.magazineluiza.com.br/smartphone-samsung-galaxy-a07-128gb/p/238543200",
            "https://lista.mercadolivre.com.br/samsung-galaxy-a07-128gb",
            "https://pt.aliexpress.com/item/100500XXXXX.html"
        ]
    },
    {
        "id": "a56",
        "nome": "Samsung Galaxy A56 128GB",
        "marca": "SAMSUNG",
        "urls": [
            "https://www.amazon.com.br/dp/B0DYYYYYYY",
        ]
    },
    {
        "id": "moto-g06",
        "nome": "Moto G06 128GB",
        "marca": "MOTOROLA",
        "urls": [
            "https://www.amazon.com.br/dp/B0DZZZZZZZ",
        ]
    },
    {
        "id": "iphone17",
        "nome": "iPhone 17 128GB",
        "marca": "APPLE",
        "urls": [
            "https://www.amazon.com.br/dp/B0DAAAAAAA",
        ]
    }
]

historico = {}
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/121.0.0.0 Safari/537.36"}

def enviar_telegram(msg):
    if not BOT_TOKEN or not CHAT_ID: return False
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        r = requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"})
        return r.status_code == 200
    except: return False

def limpar_preco(t):
    t = re.sub(r"[^\d.,]", "", str(t).replace("R$", ""))
    if "." in t and "," in t: t = t.replace(".", "").replace(",", ".")
    elif "," in t: t = t.replace(",", ".")
    try:
        v = float(t)
        return v if 100 <= v <= 20000 else None
    except: return None

def transformar_afiliado(url):
    if "amazon.com" in url.lower() and "tag=" not in url:
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}tag={AMAZON_TAG}"
    return url

def consultar_url(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        precos = []
        for m in re.findall(r"R\$\s?\d{1,3}(?:\.\d{3})*(?:,\d{2})?", r.text):
            p = limpar_preco(m)
            if p: precos.append(p)
        if not precos: return None
        menor = min(precos)
        loja = "Amazon" if "amazon" in url else "Magalu" if "magalu" in url else "Mercado Livre" if "mercado" in url else "AliExpress" if "aliexpress" in url else "Loja"
        return {"loja": loja, "preco": menor, "url": transformar_afiliado(url)}
    except: return None

app = FastAPI()
@app.get("/")
def home(): return {"status": "Price Radar V2 ONLINE", "produtos": len(produtos)}
@app.get("/teste")
def teste():
    ok = enviar_telegram("🤖 <b>Price Radar V2</b>\n✅ Telegram conectado! 3 Marcas ativas.")
    return {"telegram": "OK" if ok else "ERRO"}
@app.get("/scan")
def scan():
    for p in produtos:
        for url in p["urls"]:
            res = consultar_url(url)
            if not res: continue
            chave = f"{p['id']}:{res['loja']}"
            anterior = historico.get(chave)
            if not anterior:
                historico[chave] = res["preco"]
            else:
                queda = ((anterior - res["preco"])/anterior)*100 if anterior>0 else 0
                if queda >= QUEDA_MINIMA:
                    msg = f"🔥 <b>QUEDA!</b>\n\n📱 {p['nome']}\n🏪 {res['loja']}\nAntes: R$ {anterior:.2f}\nAgora: R$ {res['preco']:.2f}\nQueda: {queda:.1f}%\n\n🔗 <a href='{res['url']}'>VER OFERTA</a>"
                    enviar_telegram(msg)
                historico[chave] = res["preco"]
            time.sleep(2)
    return {"status": "scan feito", "historico": historico}
import uvicorn
if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
