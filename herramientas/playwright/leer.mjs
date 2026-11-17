/* Lectura automática de precios con Playwright (piloto, 13-11-2026).
   Hace lo mismo que pegar correr.js en la consola de la tienda: abre la página de partida, corre __RUN,
   espera JOB.done y guarda JOB.diff como <tienda>.txt (y JOB.cupones como <tienda>.cup) en la carpeta de salida.
   Después se aplica igual que siempre: python3 herramientas/precios.py aplicar <carpeta>

   Uso:  node herramientas/playwright/leer.mjs <carpeta> tienda1 tienda2 ...
         (sin tiendas: todas las de PARTIDA)
   Requiere: npm i playwright  y  npx playwright install chromium (o CMC_CANAL=chrome para usar el Chrome instalado) */
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

// Dónde abrir cada tienda y en qué modo. Las pesadas se leen desde /robots.txt (no se congela la pestaña).
const PORTADA_CLARO = 'https://tienda.clarochile.cl/CategoryDisplay?ddkey=ProductListingView&fromPage=catalogEntryList&facet_2=ads_f12001_ntk_cs%253A%2522itemShow%2522&facet_1=ads_f11503_ntk_cs%253A%2522Liberados%2522&urlRequestType=Base&categoryId=3074457345616686668&catalogId=10052&resultType=products&showResultsPage=true&pageView=grid&beginIndex=0&pageSize=200&facetName_2=itemShow&facetName_1=Liberados&langId=-5&storeId=10151';
const PARTIDA = {
  hp: ['https://www.hp.com/robots.txt', 'leer'],
  samsung: ['https://www.samsung.com/cl/', 'leer'],
  xiaomi: ['https://www.mi.com/cl/', 'leer'],
  lg: ['https://www.lg.com/cl/', 'leer'],
  apple: ['https://www.apple.com/cl/shop', 'leer'],
  nespresso: ['https://www.nespresso.com/cl/es', 'leer'],
  dolcegusto: ['https://www.dolce-gusto.cl/robots.txt', 'leer'],
  sindelen: ['https://www.sindelen.cl/', 'leer'],
  sodimac: ['https://www.sodimac.cl/sodimac-cl', 'leer'],
  easy: ['https://www.easy.cl/', 'leer'],
  movistar: ['https://catalogo.movistar.cl/tienda/', 'leer'],
  entel: ['https://miportal.entel.cl/personas/catalogo/celulares', 'entel'],
  falabella: ['https://www.falabella.com/robots.txt', 'leer'],
  paris: ['https://www.paris.cl/robots.txt', 'leer'],
  ripley: ['https://simple.ripley.cl/robots.txt', 'leer'],
  wom: ['https://store.wom.cl/equipos/?modalidad-de-compra=prepago', 'wom'],
  claro: [PORTADA_CLARO, 'claro'],
};
// PCFactory: tandas de 48 equipos (pcfactory-1, -2...) con &size=48, igual que precios.py lista
const RUTAS = JSON.parse(fs.readFileSync(new URL('../rutas.json', import.meta.url)));
let NOMBRES = {};  // {tienda: {ruta: nombre}} (precios.py rutas): para buscar el enlace nuevo de una ficha que ya no existe
try { NOMBRES = JSON.parse(fs.readFileSync(new URL('../nombres.json', import.meta.url))); } catch (e) {}
const idsPC = RUTAS.pcfactory.map(r => r.split('/').pop());
for (let k = 0, n = 1; k < idsPC.length; k += 48, n++)
  PARTIDA['pcfactory-' + n] = ['https://www.pcfactory.cl/busqueda?productos=' + idsPC.slice(k, k + 48).join(',') + '&size=48', 'listado'];
const PCF = Object.keys(PARTIDA).filter(t => t.startsWith('pcfactory-'));
const GH = 'https://raw.githubusercontent.com/COMPARACHILE/cualmeconviene/' + (process.env.CMC_RAMA || 'main') + '/herramientas/correr.js';
const GH_LECTOR = GH.replace('correr.js', 'leer_precios.js');
const ORIGEN = { hp: 'https://www.hp.com', samsung: 'https://www.samsung.com', xiaomi: 'https://www.mi.com', lg: 'https://www.lg.com',
  apple: 'https://www.apple.com', nespresso: 'https://www.nespresso.com', dolcegusto: 'https://www.dolce-gusto.cl', sindelen: 'https://www.sindelen.cl',
  sodimac: 'https://www.sodimac.cl', easy: 'https://www.easy.cl', movistar: 'https://catalogo.movistar.cl', falabella: 'https://www.falabella.com',
  paris: 'https://www.paris.cl', ripley: 'https://simple.ripley.cl' };
// Búsqueda en la tienda (17-11-2026) y forma de las rutas de producto, para reemplazar fichas que ya no existen (error 404/410)
const BUSCAR = {
  easy: [q => 'https://www.easy.cl/search/' + encodeURIComponent(q), /\/p$/],
  ripley: [q => 'https://simple.ripley.cl/search/' + encodeURIComponent(q), /-(mpm)?\d{8,}p?$/],
  paris: [q => 'https://www.paris.cl/search/?q=' + encodeURIComponent(q), /\d{6,}\.html$/],
  falabella: [q => 'https://www.falabella.com/falabella-cl/search?Ntt=' + encodeURIComponent(q), /^\/falabella-cl\/product\/\d+/],
  sodimac: [q => 'https://www.sodimac.cl/sodimac-cl/search?Ntt=' + encodeURIComponent(q), /^\/sodimac-cl\/product\/\d+/],
  hp: [q => 'https://www.hp.com/cl-es/shop/catalogsearch/result/?q=' + encodeURIComponent(q), /^\/cl-es\/shop\/.+\.html$/],
};
const MAX_BUSQUEDAS = Number(process.env.CMC_MAX_BUSQUEDAS || 15);  // por tienda y por vuelta
const MAX_REINTENTOS = Number(process.env.CMC_MAX_REINTENTOS || 60);
const BLOQUEO = /error (403|429|5\d\d)|Failed|TypeError|NetworkError|abort|timeout|timed out/i;
const MAX_MIN = Number(process.env.CMC_MAX_MIN || 40);

const [carpeta, ...pedidas] = process.argv.slice(2);
if (!carpeta) { console.error('Uso: node leer.mjs <carpeta> [tiendas...]'); process.exit(2); }
fs.mkdirSync(carpeta, { recursive: true });
const tiendas = (pedidas.length ? pedidas : Object.keys(PARTIDA)).flatMap(t => t === 'pcfactory' ? PCF : [t]);

// En el PC del dueño se usa su Google Chrome instalado (CMC_CANAL=chrome): Windows bloquea el navegador que baja Playwright.
const browser = await chromium.launch({ headless: process.env.CMC_VER ? false : true, ...(process.env.CMC_CANAL ? { channel: process.env.CMC_CANAL } : {}) });
const ctx = await browser.newContext({
  bypassCSP: true,  // algunas tiendas no dejan cargar scripts de GitHub
  locale: 'es-CL', timezoneId: 'America/Santiago', viewport: { width: 1366, height: 900 },
  userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
});

async function bajarHastaElFinal(page) {
  let alto = 0;
  for (let i = 0; i < 30; i++) {
    const h = await page.evaluate(() => { window.scrollTo(0, document.body.scrollHeight); return document.body.scrollHeight; });
    if (h === alto) break; alto = h; await page.waitForTimeout(2000);
  }
}

// Claro no deja cargar correr.js: se lee el listado ("Ahora Desde $…") y se cruza por el número de 8 dígitos de la ruta.
async function leerClaro(page, t, ini) {
  const L = await page.evaluate(() => {
    const n = s => +String(s || '').replace(/\D/g, ''), o = [];
    document.querySelectorAll('a[href]').forEach(a => {
      if (!/Conoce/.test(a.textContent)) return;
      let c = a; for (let i = 0; i < 6 && !/Ahora/.test(c.innerText); i++) c = c.parentElement;
      const p = n((c.innerText.match(/Ahora Desde\s*\$([\d.]+)/) || [])[1]);
      if (p) o.push([new URL(a.href).pathname, p]);
    });
    return o;
  });
  const num = u => (u.match(/(\d{8})pre/g) || []).pop();
  const m = new Map(L.map(([u, p]) => [num(u), p]));
  const out = RUTAS.claro.map((u, i) => m.has(num(u)) ? [i, m.get(num(u)), 0, 0] : null).filter(Boolean);
  fs.writeFileSync(path.join(carpeta, 'claro.json'), JSON.stringify(out));
  return { t, seg: Math.round((Date.now() - ini) / 1000), resumen: { total: RUTAS.claro.length, conPrecio: out.length, errores: {} }, cambios: out.length };
}

// Samsung: "sin precio" suele ser agotado. Se abre la ficha y se mira el botón visible: solo "Avísame" = sin stock.
async function revisarSamsung(diff) {
  const partes = diff.split(';').filter(Boolean);
  for (let k = 0; k < partes.length; k++) {
    const [i, a, motivo] = partes[k].split(':');
    if (a !== 'E' || motivo !== 'sin precio') continue;
    const page = await ctx.newPage();
    try {
      await page.goto('https://www.samsung.com' + RUTAS.samsung[+i], { waitUntil: 'domcontentloaded', timeout: 60000 });
      await page.waitForTimeout(6000);
      const v = await page.evaluate(() => {
        const vis = re => [...document.querySelectorAll('a,button')].some(b => re.test(b.innerText || '') && b.offsetParent && b.getBoundingClientRect().width);
        return { comprar: vis(/Comprar ahora|Agregar al carro|Añadir al carro/i), avisame: vis(/Av[ií]same/i) };
      });
      if (v.avisame && !v.comprar) partes[k] = i + ':E:sin stock';
      console.log(`[samsung] ${i}: ${v.avisame && !v.comprar ? 'sin stock' : 'se deja sin precio'}`);
    } catch (e) { console.log(`[samsung] ${i}: no se pudo abrir`); }
    finally { await page.close().catch(() => {}); }
  }
  return partes.map(x => x + ';').join('');
}

// Fichas que la lectura rápida (fetch desde la pestaña) no pudo leer por bloqueo (403, 429, 5xx, "Failed to fetch"):
// se abre cada una como una visita normal y se lee con el mismo lector de la tienda (LECTORES de leer_precios.js).
async function reintentarAbriendo(t, filas) {
  const arreglos = [];
  for (const [i] of filas.slice(0, MAX_REINTENTOS)) {
    const u = RUTAS[t][i], page = await ctx.newPage();
    try {
      const r = await page.goto(ORIGEN[t] + u, { waitUntil: 'domcontentloaded', timeout: 60000 });
      const st = r ? r.status() : 0;
      if (st === 404 || st === 410) { arreglos.push([i, 0, 0, 'error ' + st]); continue; }
      await page.waitForTimeout(5000);
      const f = await page.evaluate(async ([gh, t, u]) => {
        if (!window.__LX) (0, eval)(await (await fetch(gh + '?' + Date.now(), { cache: 'no-store' })).text() + '\n;window.__LX={LECTORES,_corto};');
        try { return __LX._corto(0, await __LX.LECTORES[t](document.documentElement.outerHTML, u)); } catch (e) { return [0, 0, 0, 'sin precio']; }
      }, [GH_LECTOR, t, u]);
      f[0] = i; arreglos.push(f);
      console.log(`[${t}] abriendo ${i}: ${f[1] || f[3]}`);
    } catch (e) { console.log(`[${t}] abriendo ${i}: no se pudo (${String(e.message || e).slice(0, 60)})`); }
    finally { await page.close().catch(() => {}); }
    await new Promise(r => setTimeout(r, 1500));
  }
  return arreglos;
}

// Ficha que ya no existe: busca el mismo modelo en la tienda. Solo acepta un resultado que tenga el código del modelo
// (o todas las palabras y números del nombre). Si no hay uno seguro, la oferta queda oculta como sin stock.
const _norm = s => String(s || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/(\d)\.(\d{3})/g, '$1$2');
const _pal = s => _norm(s).split(/[^a-z0-9]+/).filter(Boolean);
const VACIAS = new Set(['con', 'para', 'de', 'del', 'la', 'el', 'en', 'y', 'gb', 'tb', 'lt', 'kg', 'btu', 'cm', 'mm', 'litros', 'pulgadas', 'negro', 'blanco', 'gris', 'plata']);
function claves(nombre, ruta) {
  const codigo = w => /[a-z]/.test(w) && /\d/.test(w) && w.length >= 4 && !/\d{6,}/.test(w) && !/^mk[a-z0-9]{6,}$/.test(w) && !/^mpm/.test(w);
  let cod = _pal(nombre).filter(codigo);
  if (!cod.length) cod = _pal(ruta.split('/').filter(Boolean).slice(-1)[0] || '').filter(codigo);
  return { cod, nums: _pal(nombre).filter(w => /^\d{2,5}$/.test(w)), pal: _pal(nombre).filter(w => w.length >= 2 && !VACIAS.has(w) && !/^\d+$/.test(w)) };
}
function calza(k, texto) {
  const w = _norm(texto), junto = w.replace(/[^a-z0-9]/g, ''), p = new Set(_pal(texto));
  if (!k.nums.every(n => p.has(n) || junto.includes(n))) return false;
  const tiene = k.pal.filter(x => p.has(x) || (x.length >= 4 && junto.includes(x))).length;
  if (k.cod.length) return k.cod.every(c => junto.includes(c)) && tiene >= Math.ceil(k.pal.length * 0.7);  // código del modelo + casi todo el nombre
  return k.pal.length >= 2 && tiene === k.pal.length;
}
async function buscarNuevo(t, ruta) {
  const [url, forma] = BUSCAR[t], nombre = (NOMBRES[t] || {})[ruta];
  if (!nombre) return null;
  const k = claves(nombre, ruta), page = await ctx.newPage();
  try {
    await page.goto(url(nombre.replace(/\s+\d+GB$/, m => m)), { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForTimeout(7000);
    await page.evaluate(() => window.scrollTo(0, 1500)); await page.waitForTimeout(2000);
    const cand = await page.evaluate(() => [...document.querySelectorAll('a[href]')].map(a => {
      let c = a; for (let i = 0; i < 4 && (c.innerText || '').length < 25 && c.parentElement; i++) c = c.parentElement;
      return [a.href, (a.innerText || '') + ' ' + (a.title || '') + ' ' + (c.innerText || '').slice(0, 300)];
    }));
    for (const [href, txt] of cand) {
      let u; try { u = new URL(href); } catch (e) { continue; }
      if (!u.hostname.endsWith(new URL(ORIGEN[t]).hostname.replace(/^www\./, '')) || !forma.test(u.pathname) || u.pathname === ruta) continue;
      if (calza(k, decodeURIComponent(u.pathname).replace(/[-_/]/g, ' ') + ' ' + txt)) return [ruta, u.origin + u.pathname, txt.trim().replace(/\s+/g, ' ').slice(0, 120)];
    }
    return null;
  } catch (e) { return null; }
  finally { await page.close().catch(() => {}); }
}

async function leerTienda(t) {
  const [url, modo] = PARTIDA[t] || [];
  if (!url) return { t, err: 'tienda sin página de partida' };
  const page = await ctx.newPage();
  const ini = Date.now();
  try {
    const r = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
    const estado = r ? r.status() : 0;
    if (estado >= 400) return { t, err: 'la página de partida respondió ' + estado };
    await page.waitForTimeout(modo === 'listado' ? 8000 : 3000);
    if (modo === 'wom' || modo === 'claro') await bajarHastaElFinal(page);
    if (modo === 'claro') return await leerClaro(page, t, ini);
    if (modo === 'listado' && await page.getByText('Siguiente página').count()) console.log(`[${t}] OJO: aparece "Siguiente página"`);
    await page.evaluate(async gh => {
      (0, eval)(await (await fetch(gh + '?' + Date.now(), { cache: 'no-store' })).text());
    }, GH);
    await page.evaluate(([t, m]) => window.__RUN(t, m), [t, modo]);
    let ultima = '';
    while (true) {
      await page.waitForTimeout(10000);
      const j = await page.evaluate(() => ({ fase: JOB.fase, done: JOB.done, err: JOB.err }));
      if (j.fase !== ultima) { console.log(`[${t}] ${j.fase}`); ultima = j.fase; }
      if (j.done) break;
      if (Date.now() - ini > MAX_MIN * 60000) return { t, err: `sin terminar a los ${MAX_MIN} min (fase: ${j.fase})` };
    }
    if (await page.evaluate(() => JOB.err)) return { t, err: await page.evaluate(() => JOB.err) };
    const base = t.split('-')[0];
    // 1) Fichas bloqueadas: se abren una por una como visita normal
    if (modo === 'leer' && ORIGEN[base] && base !== 'sodimac' && base !== 'xiaomi') {  // esas dos se leen por su API, no por la ficha
      const malas = await page.evaluate(re => JOB.res.filter(r => !r[1] && new RegExp(re, 'i').test(String(r[3]))), BLOQUEO.source);
      if (malas.length) {
        console.log(`[${t}] ${malas.length} bloqueadas: se abren una por una`);
        const arr = await reintentarAbriendo(base, malas);
        if (arr.length) await page.evaluate(async ([arr, t]) => {
          for (const f of arr) { const r = JOB.res.find(x => x[0] === f[0]); if (r) r.splice(0, r.length, ...f); }
          const R = (await (await fetch('https://raw.githubusercontent.com/COMPARACHILE/cualmeconviene/main/herramientas/rutas.json?' + Date.now(), { cache: 'no-store' })).json())[t];
          JOB.diff = await __L.cambios(t, R, JOB.res);
          JOB.resumen = { total: JOB.res.length, conPrecio: JOB.res.filter(r => r[1]).length,
            errores: JOB.res.filter(r => !r[1]).reduce((a, r) => (a[r[3]] = (a[r[3]] || 0) + 1, a), {}) };
        }, [arr, base]);
      }
    }
    // 2) Fichas que ya no existen: se busca el mismo modelo en la tienda
    let nuevas = [];
    if (BUSCAR[base]) {
      const muertas = await page.evaluate(() => (JOB.res || []).filter(r => !r[1] && /error 40[14]|error 410/.test(String(r[3]))).map(r => r[0]));
      const orden = muertas.sort(() => Math.random() - 0.5).slice(0, MAX_BUSQUEDAS);  // al azar: en cada vuelta se prueban otras
      for (const i of orden) {
        const n = await buscarNuevo(base, RUTAS[base][i]);
        console.log(`[${t}] buscar ${i}: ${n ? n[1] : 'sin resultado seguro (queda sin stock)'}`);
        if (n) nuevas.push(n);
      }
    }
    const job = await page.evaluate(() => ({ diff: JOB.diff, cupones: JOB.cupones, resumen: JOB.resumen, err: JOB.err, seg: JOB.seg }));
    if (nuevas.length) { fs.writeFileSync(path.join(carpeta, base + '.nuevas'), JSON.stringify(nuevas)); job.resumen.nuevas = nuevas.length; }
    if (t === 'samsung') job.diff = await revisarSamsung(job.diff || '');
    fs.writeFileSync(path.join(carpeta, t + '.txt'), job.diff || '');
    if (job.cupones) fs.writeFileSync(path.join(carpeta, t + '.cup'), job.cupones);
    return { t, seg: job.seg, resumen: job.resumen, cambios: (job.diff || '').split(';').filter(Boolean).length };
  } catch (e) {
    return { t, err: String(e && e.message || e).slice(0, 300) };
  } finally {
    await page.close().catch(() => {});
  }
}

// Máximo 3 tiendas a la vez (más que eso se caen las grandes)
const cola = [...tiendas], resultados = [];
await Promise.all([1, 2, 3].map(async () => {
  while (cola.length) resultados.push(await leerTienda(cola.shift()));
}));
await browser.close();

fs.writeFileSync(path.join(carpeta, 'informe.json'), JSON.stringify(resultados, null, 1));
console.log('\n=== Informe ===');
for (const r of resultados) {
  if (r.err) { console.log(`${r.t}: FALLÓ — ${r.err}`); continue; }
  const { total, conPrecio, errores = {} } = r.resumen;
  console.log(`${r.t}: ${conPrecio}/${total} con precio, ${r.cambios} cambios, ${r.seg}s` +
    (Object.keys(errores).length ? ' | sin precio: ' + JSON.stringify(errores) : ''));
}
