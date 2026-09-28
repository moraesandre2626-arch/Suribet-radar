// ============================================================
// PRICE RADAR V2 - 3 MARCAS (Samsung, Motorola, Apple)
// Amazon + Magalu + Mercado Livre + AliExpress
// Com afiliado + histórico salvo
// ============================================================

const express = require("express");
const axios = require("axios");
const cheerio = require("cheerio");
const fs = require("fs");

const app = express();
const PORT = process.env.PORT || 10000;

// --- COLOQUE SUAS CHAVES NO RENDER ---
const BOT_TOKEN = process.env.BOT_TOKEN;
const CHAT_ID = process.env.CHAT_ID;

// SEUS CÓDIGOS DE AFILIADO - TROQUE AQUI
const AFILIADOS = {
  amazon: process.env.AMAZON_TAG || "seucodigo-20", // ex: meuradar-20
  magalu: process.env.MAGALU_ID || "seu_id_magalu",
  aliexpress: process.env.ALI_ID || "seu_id_ali",
};

const INTERVALO = Number(process.env.INTERVALO_MS || 900000); // 15 min
const QUEDA_MINIMA = Number(process.env.QUEDA_MINIMA || 5);

// ------------------------------------------------------------
// PRODUTOS - TROQUE OS LINKS PELOS LINKS REAIS DOS APPS
// Pegue o link do PRODUTO, não da busca
// ------------------------------------------------------------
let produtos = [
  {
    id: "a07",
    nome: "Samsung Galaxy A07 128GB",
    marca: "SAMSUNG",
    urls: [
      "https://www.amazon.com.br/dp/B0DXXXXXXX", // TROQUE
      "https://www.magazineluiza.com.br/smartphone-samsung-galaxy-a07-128gb/p/238543200", // TROQUE
      "https://www.mercadolivre.com.br/p/MLB12345678", // TROQUE
      "https://pt.aliexpress.com/item/100500XXXXX.html" // TROQUE
    ]
  },
  {
    id: "a56",
    nome: "Samsung Galaxy A56 128GB",
    marca: "SAMSUNG",
    urls: [
      "https://www.amazon.com.br/dp/B0DYYYYYYY",
      "https://www.magazineluiza.com.br/smartphone-samsung-galaxy-a56-128gb/p/238543201",
      "https://www.mercadolivre.com.br/p/MLB12345679",
      "https://pt.aliexpress.com/item/100500YYYYY.html"
    ]
  },
  {
    id: "moto-g06",
    nome: "Motorola Moto G06 128GB",
    marca: "MOTOROLA",
    urls: [
      "https://www.amazon.com.br/dp/B0DZZZZZZZ",
      "https://www.magazineluiza.com.br/smartphone-motorola-moto-g06-128gb/p/238543202",
      "https://www.mercadolivre.com.br/p/MLB12345680",
      "https://pt.aliexpress.com/item/100500ZZZZZ.html"
    ]
  },
  {
    id: "iphone17",
    nome: "iPhone 17 128GB",
    marca: "APPLE",
    urls: [
      "https://www.amazon.com.br/dp/B0DAAAAAAA",
      "https://www.magazineluiza.com.br/iphone-17-128gb/p/238543203",
      "https://www.mercadolivre.com.br/p/MLB12345681",
      "https://pt.aliexpress.com/item/100500AAAAA.html"
    ]
  }
];

// --- PERSISTÊNCIA (Não apaga no Render) ---
let historico = {};
try {
  if (fs.existsSync("./historico.json")) {
    historico = JSON.parse(fs.readFileSync("./historico.json", "utf8"));
  }
} catch(e){ historico = {} }
const ultimoAlerta = {};
function salvarHistorico() {
  try { fs.writeFileSync("./historico.json", JSON.stringify(historico, null, 2)); } catch(e){}
}

const HEADERS = {
  "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
  "Accept-Language": "pt-BR,pt;q=0.9",
  "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
};

async function enviarTelegram(mensagem) {
  if (!BOT_TOKEN || !CHAT_ID) { console.log("Telegram não configurado"); return false; }
  try {
    await axios.post(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
      chat_id: CHAT_ID, text: mensagem, parse_mode: "HTML", disable_web_page_preview: false
    });
    return true;
  } catch (erro) {
    console.error("Erro Telegram:", erro.response?.data || erro.message);
    return false;
  }
}

function identificarLoja(url) {
  const u = url.toLowerCase();
  if (u.includes("amazon.com")) return "Amazon";
  if (u.includes("magazineluiza.com") || u.includes("magalu.com")) return "Magalu";
  if (u.includes("mercadolivre.com") || u.includes("mercadolibre.com")) return "Mercado Livre";
  if (u.includes("aliexpress.com")) return "AliExpress";
  return "Outra loja";
}

function transformarAfiliado(url) {
  try {
    if (url.toLowerCase().includes("amazon.com")) {
      const sep = url.includes("?") ? "&" : "?";
      if (url.includes("tag=")) return url;
      return `${url}${sep}tag=${AFILIADOS.amazon}`;
    }
    // Magalu e Ali você pode colocar seu link direto nos produtos, mas aqui garante
    return url;
  } catch(e){ return url; }
}

function limparPreco(valor) {
  if (!valor) return null;
  let texto = String(valor).replace(/\s/g, "").replace(/R\$/gi, "").replace(/[^\d.,]/g, "");
  if (!texto) return null;
  if (texto.includes(".") && texto.includes(",")) texto = texto.replace(/\./g, "").replace(",", ".");
  else if (texto.includes(",")) texto = texto.replace(",", ".");
  const numero = parseFloat(texto);
  if (!Number.isFinite(numero) || numero < 100 || numero > 20000) return null;
  return numero;
}

function extrairPrecos(texto) {
  const encontrados = [];
  const regex = /R\$\s?\d{1,3}(?:\.\d{3})*(?:,\d{2})?/gi;
  const matches = texto.match(regex) || [];
  for (const match of matches) {
    const preco = limparPreco(match);
    if (preco !== null) encontrados.push(preco);
  }
  return encontrados;
}

function escolherMelhorPreco(precos) {
  const validos = precos.filter(p => Number.isFinite(p) && p >= 100 && p <= 20000);
  if (!validos.length) return null;
  return Math.min(...validos);
}

async function baixarPagina(url) {
  try {
    const r = await axios.get(url, { headers: HEADERS, timeout: 20000, maxRedirects: 5 });
    return r.data;
  } catch (erro) {
    console.error(`Erro ${url}:
