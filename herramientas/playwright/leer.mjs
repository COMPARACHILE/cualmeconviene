/* Lectura automática de precios con Playwright (piloto, 13-11-2026).
   Hace lo mismo que pegar correr.js en la consola de la tienda: abre la página de partida, corre __RUN,
   espera JOB.done y guarda JOB.diff como <tienda>.txt (y JOB.cupones como <tienda>.cup) en la carpeta de salida.
   Después se aplica igual que siempre: python3 herramientas/precios.py aplicar <carpeta>

   Uso:  node herramientas/playwright/leer.mjs <carpeta> tienda1 tienda2 ...
         (sin tiendas: todas las de PARTIDA)
   Requiere: npm i playwright  y  npx playwright install chromium */
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
const idsPC = RUTAS.pcfactory.map(r => r.split('/').pop());
for (let k = 0, n = 1; k < idsPC.length; k += 48, n++)
  PARTIDA['pcfactory-' + n] = ['https://www.pcfactory.cl/busqueda?productos=' + idsPC.slice(k, k + 48).join(',') + '&size=48', 'listado'];
const PCF = Object.keys(PARTIDA).filter(t => t.startsWith('pcfactory-'));
const GH = 'https://raw.githubusercontent.com/COMPARACHILE/cualmeconviene/' + (process.env.CMC_RAMA || 'main') + '/herramientas/correr.js';
const MAX_MIN = Number(process.env.CMC_MAX_MIN || 40);

const [carpeta, ...pedidas] = process.argv.slice(2);
if (!carpeta) { console.error('Uso: node leer.mjs <carpeta> [tiendas...]'); process.exit(2); }
fs.mkdirSync(carpeta, { recursive: true });
const tiendas = (pedidas.length ? pedidas : Object.keys(PARTIDA)).flatMap(t => t === 'pcfactory' ? PCF : [t]);

const browser = await chromium.launch({ headless: process.env.CMC_VER ? false : true });
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
    const job = await page.evaluate(() => ({ diff: JOB.diff, cupones: JOB.cupones, resumen: JOB.resumen, err: JOB.err, seg: JOB.seg }));
    if (job.err) return { t, err: job.err };
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
