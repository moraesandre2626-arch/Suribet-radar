import os, re, json, asyncio, time, html, requests
from fastapi import FastAPI
from datetime import datetime
from contextlib import asynccontextmanager

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
AMAZON_TAG = os.getenv("AMAZON_TAG", "achadossm-20")
INTERVALO = int(os.getenv("INTERVALO_MS", "900000")) / 1000
QUEDA_MINIMA = float(os.getenv("QUEDA_MINIMA", "5"))
MAX_PRODUTOS_POR_LOJA = 20
HISTORICO_FILE = "historico.json"

MARCAS = ["Samsung", "Motorola", "Apple"]
LOJAS = {
    "Amazon": {"url": "https://www.amazon.com.br/s?k={query}"},
    "Magalu": {"url": "https://www.magazineluiza.com.br/busca/{query}/"},
    "Mercado Livre": {"url": "https://lista.mercadolivre.com.br/{query}"},
    "AliExpress": {"url": "https://pt.aliexpress.com/w/wholesale-{query}.html"},
    "Shopee": {"url": "https://shopee.com.br/search?keyword={query}"}
}
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"}

historico = {}
def carregar_historico():
    global historico
    try:
        if os.path.exists(HISTORICO_FILE):
            with open(HISTORICO_FILE,"r",encoding="utf-8") as f: historico=json.load(f)
    except: historico={}
def salvar_historico():
    try:
        with open(HISTORICO_FILE,"w",encoding="utf-8") as f: json.dump(historico,f,ensure_ascii=False,indent=2)
    except: pass

def enviar_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=15)
    except: pass

def limpar_texto(t):
    if not t: return ""
    t = html.unescape(str(t)); t = re.sub(r"<[^>]+>"," ",t); t = re.sub(r"\s+"," ",t); return t.strip()
def limpar_preco(v):
    if v is None: return None
    encontrados = re.findall(r"\d{1,3}(?:\.\d{3})*(?:,\d{2})?", str(v))
    if not encontrados: return None
    num = encontrados[0].replace(".","").replace(",",".") if "," in encontrados[0] else encontrados[0].replace(".","")
    try:
        preco=float(num)
        return preco if 100 <= preco <= 30000 else None
    except: return None

def parece_celular(nome):
    texto=nome.lower()
    for p in ["capa","case","película","capinha","carregador","cabo","fone","suporte","vidro","relógio","smartwatch","tripé","bolsa"]:
        if p in texto: return False
    return any(m in texto for m in ["samsung","galaxy","motorola","moto ","iphone","apple"])

def baixar_pagina(url):
    try:
        r=requests.get(url,headers=HEADERS,timeout=20)
        return r.text if r.status_code==200 else None
    except: return None

def extrair_produtos_generico(html_texto, marca, loja, url_busca):
    if not html_texto: return []
    produtos=[]
    for m in re.finditer(r"R\$\s?\d{1,3}(?:\.\d{3})*(?:,\d{2})?", html_texto):
        ini=max(0,m.start()-500); fim=min(len(html_texto),m.end()+500)
        bloco=limpar_texto(html_texto[ini:fim])
        if marca.lower() not in bloco.lower(): continue
        preco=limpar_preco(m.group(0))
        if not preco: continue
        palavras=re.findall(r"[A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9\s\-\+\(\)\/\.]{10,150}", bloco)
        nome=None
        for c in palavras:
            if marca.lower() in c.lower() and parece_celular(c): nome=c.strip(); break
        if not nome: continue
        produtos.append({"marca":marca,"modelo":nome[:80],"nome":nome,"preco":preco,"loja":loja,"url":url_busca})
    return produtos

def consultar_loja(loja, marca):
    q=requests.utils.quote(f"{marca} celular")
    url=LOJAS[loja]["url"].format(query=q)
    if loja=="Amazon" and "tag=" not in url: url+=("&" if "?" in url else "?")+f"tag={AMAZON_TAG}"
    pagina=baixar_pagina(url)
    return extrair_produtos_generico(pagina,marca,loja,url)

def processar_preco(p):
    chave=f"{p['marca'].lower()}|{p['modelo'].lower()}|{p['loja'].lower()}"
    anterior=historico.get(chave,{}).get("preco") if isinstance(historico.get(chave),dict) else historico.get(chave)
    historico[chave]={"preco":p["preco"],"nome":p["nome"],"marca":p["marca"],"loja":p["loja"],"url":p["url"],"atualizado":datetime.now().isoformat()}
    if not anterior or p["preco"]>=anterior: return None
    queda=((anterior-p["preco"])/anterior)*100
    return {**p,"anterior":anterior,"queda":queda} if queda>=QUEDA_MINIMA else None

def montar_alerta(p):
    return f"🔥 <b>QUEDA!</b>\n\n📱 {p['nome']}\n🏪 {p['loja']}\n💰 De R$ {p['anterior']:.2f}\n💸 Por R$ {p['preco']:.2f}\n📉 -{p['queda']:.1f}%\n\n🔗 <a href='{p['url']}'>VER OFERTA</a>"

def executar_scan():
    encontrados=[]
    for marca in MARCAS:
        for loja in LOJAS:
            try:
                prods=consultar_loja(loja,marca)
                prods=[p for p in prods if p["preco"]>=100][:MAX_PRODUTOS_POR_LOJA]
                encontrados.extend(prods); time.sleep(2)
            except: pass
    alertas=[]
    for p in encontrados:
        q=processar_preco(p)
        if q: alertas.append(q)
    salvar_historico()
    for a in alertas: enviar_telegram(montar_alerta(a)); time.sleep(1)
    return {"produtos":len(encontrados),"alertas":len(alertas)}

async def loop_radar():
    await asyncio.sleep(10)
    carregar_historico()
    enviar_telegram(f"🚀 <b>RADAR V4 LIGADO</b>\n📱 Samsung, Motorola, Apple\n🏪 5 lojas\n⏰ A cada {int(INTERVALO/60)} min")
    while True:
        try: await asyncio.to_thread(executar_scan)
        except: pass
        await asyncio.sleep(INTERVALO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    carregar_historico()
    asyncio.create_task(loop_radar())
    yield
app=FastAPI(lifespan=lifespan)

@app.get("/")
def home(): return {"status":"Price Radar V4 ONLINE","marcas":MARCAS,"lojas":list(LOJAS.keys()),"historico":len(historico)}
@app.get("/teste")
def teste():
    enviar_telegram("🤖 V4 OK - Telegram funcionando!")
    return {"telegram":"OK"}
@app.get("/scan")
async def scan():
    r=await asyncio.to_thread(executar_scan); return r
@app.get("/status")
def status(): return {"status":"ONLINE","marcas":MARCAS,"lojas":list(LOJAS.keys()),"historico":len(historico),"hora":datetime.now().strftime("%H:%M")}
