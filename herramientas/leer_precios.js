/* Lector de precios para la actualización diaria de ¿Cuál me conviene?
   Se pega en la consola (javascript_tool) de una pestaña abierta en la tienda que corresponde.
   Uso (RUTAS = la lista que imprime "python3 herramientas/precios.py lista" para esa tienda):
     1) Pega este archivo completo una vez por pestaña.
     2) await leer('falabella', RUTAS)        // fichas una por una (falabella, paris, ripley, movistar y las
                                            // tiendas oficiales: samsung, lg, xiaomi, apple, hp, nespresso, dolcegusto)
        await leerEntel(RUTAS)               // entel: abre cada ficha en un iframe y lee el precio dibujado
        leerListado('claro', RUTAS)          // claro y pcfactory leen un listado ya abierto
        await leerWom(RUTAS)                 // wom: recorre las páginas del listado
   Claro bloquea fetch a GitHub: ahí hay que pegar el archivo y las RUTAS a mano.
   PCFactory: "precios.py lista" da varios enlaces (48 equipos c/u); se lee cada uno y se guarda
   como pcfactory-1.json, pcfactory-2.json... "aplicar" los junta.
   Devuelve un texto JSON corto: [[i, precio, c, extra], ...] donde i es la posición en RUTAS,
   c = 1 si el precio pide tarjeta o transferencia, y extra es el precio sin tarjeta (Ripley),
   el de otros medios (PCFactory) o el motivo del error cuando precio = 0.
   Solo lee precios públicos. No usar en Mercado Libre. */

const _num = s => s == null ? null : +String(s).replace(/[^\d]/g, '') || null;
const _fmt = n => '$' + n.toLocaleString('es-CL');

const LECTORES = {
  falabella(h, u) {
    const d = h.match(/<script id="__NEXT_DATA__"[^>]*>([\s\S]*?)<\/script>/);
    if (!d) return { e: 'sin datos' };
    const pd = JSON.parse(d[1]).props.pageProps.productData;
    if (!pd) return { e: 'sin producto' };
    if (!(pd.variants || []).length) return { e: 'sin stock' };  // ficha sin variantes = ya no se vende
    const sku = u.split('/').pop();
    const v = (pd.variants || []).find(x => x.id === sku) || pd.variants[0];
    const pr = Object.fromEntries((v.prices || []).map(p => [p.type, _num((p.price || [])[0])]));
    if (v.isPurchaseable === false) return { e: 'sin stock' };
    if (pr.cmrPrice) return { p: pr.cmrPrice, c: 1, n: 'Con tarjeta CMR' };
    if (pr.eventPrice) return { p: pr.eventPrice, c: 0, n: 'Precio Internet' };
    if (pr.internetPrice) return { p: pr.internetPrice, c: 0, n: 'Precio Internet' };
    if (pr.normalPrice) return { p: pr.normalPrice, c: 0, n: 'Precio Internet' };
    return { e: 'sin precio' };
  },
  paris(h) {
    const ps = [];
    for (const x of h.matchAll(/\$([\d.]{5,})/g)) {
      const pre = h.slice(Math.max(0, x.index - 500), x.index);
      if (!/line-through/.test(pre.slice(pre.lastIndexOf('<')))) ps.push(_num(x[1]));
      if (ps.length >= 2) break;
    }
    if (!ps.length) return { e: 'sin precio' };
    return ps.length >= 2 && ps[0] < ps[1] ? { p: ps[0], c: 1, n: 'Con Tarjeta Cencosud Scotiabank' } : { p: ps[0], c: 0, n: '' };
  },
  ripley(h0) {
    const h = h0.replace(/\\"/g, '"');
    if (/schema.org\/(OutOfStock|SoldOut)/.test(h)) return { e: 'sin stock' };
    const i = h.indexOf('"price":{"master"'); if (i < 0) return { e: 'sin precio' };
    const seg = h.slice(i, i + 600);
    const g = k => _num((seg.match(new RegExp('"' + k + '":\\{[^}]*?"valueNumber":(\\d+)')) || [])[1]);
    const sale = g('sale') || g('master'), rip = g('ripley');
    if (rip && rip < sale) return { p: rip, c: 1, x: sale, n: 'Con tarjeta Ripley · sin tarjeta ' + _fmt(sale) };
    return sale ? { p: sale, c: 0, n: 'Precio Internet' } : { e: 'sin precio' };
  },
  entel(h) {
    // Respaldo: el "price" del JSON-LD a veces es el precio del equipo CON plan (ej. Moto G35 $59.990).
    // Usar leerEntel, que lee el "Precio oferta" que ve el comprador en la ficha.
    const p = _num((h.match(/"offers"\s*:\s*\{[\s\S]{0,300}?"price"\s*:\s*"?([\d.]+)/) || [])[1]);
    return p ? { p, c: 0, n: 'Precio oferta online Entel (solo equipo)' } : { e: 'sin precio' };
  },
  // Tiendas oficiales de cada marca (26-10-2026): precio público de la ficha, sin tarjeta
  samsung: (h, u) => _samsung(h, u), lg: h => _oficial(h), hp: h => _oficial(h), nespresso: h => _oficial(h), dolcegusto: h => _oficial(h),
  apple: (h, u) => _apple(h, u),
  movistar(h) {
    if (/schema.org\/OutOfStock/.test(h)) return { e: 'sin stock' };
    const p = _num((h.match(/"price"\s*:\s*"?(\d{4,})/) || [])[1]);
    return p ? { p, c: 0 } : { e: 'sin precio' };
  }
};

/* Precio escrito como número (938990, "938990.00") o con puntos de miles ("938.990") */
const _precio = v => {
  if (v == null || v === '') return null;
  if (typeof v === 'number') return Math.round(v) || null;
  const t = String(v).replace(/[^\d.,]/g, '');
  if (/^\d{1,3}([.,]\d{3})+$/.test(t)) return +t.replace(/[.,]/g, '') || null;
  return Math.round(parseFloat(t.replace(',', '.'))) || null;
};
const _agotado = a => /OutOfStock|SoldOut|Discontinued|out of stock|agotado/i.test(String(a || ''));
/* Ficha de tienda oficial: 1) JSON-LD (offers), 2) meta product:price:amount, 3) "price"/"inStock" (Nespresso) */
function _oficial(h) {
  const ofertas = [];
  const junta = x => {
    if (!x || typeof x !== 'object') return;
    if (Array.isArray(x)) { x.forEach(junta); return; }
    if (x.offers) [].concat(x.offers).forEach(o => { if (o && typeof o === 'object') ofertas.push(o); });
    if (x['@graph']) junta(x['@graph']);
  };
  for (const m of h.matchAll(/<script[^>]+application\/ld\+json[^>]*>([\s\S]*?)<\/script>/g)) { try { junta(JSON.parse(m[1])); } catch (e) {} }
  const conPrecio = ofertas.map(o => ({ p: _precio(o.price != null ? o.price : o.lowPrice), a: o.availability })).filter(o => o.p > 1000);
  if (conPrecio.length) {
    const hay = conPrecio.filter(o => !_agotado(o.a));
    if (!hay.length) return { e: 'sin stock' };
    return { p: Math.min(...hay.map(o => o.p)), c: 0 };
  }
  const meta = k => (h.match(new RegExp('<meta[^>]+(?:property|name)="' + k + '"[^>]+content="([^"]*)"')) || h.match(new RegExp('<meta[^>]+content="([^"]*)"[^>]+(?:property|name)="' + k + '"')) || [])[1];
  const mp = _precio(meta('product:price:amount'));
  if (mp > 1000) return _agotado(meta('product:availability')) ? { e: 'sin stock' } : { p: mp, c: 0 };
  const np = _precio((h.match(/"price"\s*:\s*"?([\d.]+)/) || [])[1]);
  if (np > 1000) return /"inStock"\s*:\s*false/.test(h) ? { e: 'sin stock' } : { p: np, c: 0 };
  return { e: 'sin precio' };
}
/* Apple: la página de compra trae "products":[{name, price:{fullPrice}}]; ?m= es el comienzo del nombre del modelo */
function _apple(h, u) {
  // La página trae varios bloques "products":[...] (uno por modelo: Pro y Pro Max, 11" y 13"); se juntan todos.
  // Apple escribe "Wi‑Fi" con un guion que no corta (U+2011): se comparan los nombres con guiones y espacios normales.
  const pl = t => String(t).replace(/[\u2010-\u2015]/g, '-').replace(/\s+/g, ' ');
  const m = pl(decodeURIComponent((u.match(/[?&]m=([^&#]+)/) || [])[1] || ''));
  const ps = [];
  for (let i = h.indexOf('"products":['); i >= 0; i = h.indexOf('"products":[', i + 12)) {
    let k = i + 11, n = 0;
    for (; k < h.length; k++) { if (h[k] === '[') n++; else if (h[k] === ']' && !--n) break; }
    try { ps.push(...JSON.parse(h.slice(i + 11, k + 1))); } catch (e) {}
  }
  if (!ps.length) return { e: 'sin datos' };
  const v = ps.filter(x => x && x.name && pl(x.name).startsWith(m)).map(x => _precio(x.price && (x.price.fullPrice || x.price.currentPrice))).filter(Boolean);
  return v.length ? { p: Math.min(...v), c: 0 } : { e: 'sin precio' };
}
/* Xiaomi (mi.com/cl): el precio lo trae su API, no el HTML. Ruta /cl/product/<tag>/?gb=256 (gb solo en celulares y tablets) */
async function _xiaomi(u) {
  const tag = (u.match(/\/product\/([^/?#]+)/) || [])[1], gb = (u.match(/[?&]gb=(\d+)/) || [])[1];
  const r = await fetch('https://go.buy.mi.com/cl/v2/item/productdetail?tag=' + encodeURIComponent(tag), { credentials: 'include' });
  if (!r.ok) return { e: 'error ' + r.status };
  const d = (await r.json()).data;
  const items = ((d && d.item_detail && d.item_detail.spu_list) || []).flatMap(x => x.item_list || []);
  if (!items.length) return { e: 'sin producto' };
  // "8GB+256GB" o "4G RAM 256G ROM": la versión es el número seguido de G o GB (la RAM nunca llega a 64)
  const ok = items.filter(x => !gb || new RegExp('(?:\\+|\\b)\\s*' + gb + '\\s*GB?(?![a-z])', 'i').test(x.item_name));
  if (!ok.length) return { e: 'sin esa versión' };
  const hay = ok.filter(x => x.is_sale !== false && !x.is_out_of_stock);
  if (!hay.length) return { e: 'sin stock' };
  return { p: Math.min(...hay.map(x => _precio(x.price)).filter(Boolean)), c: 0 };
}
const DIRECTOS = { xiaomi: _xiaomi };
/* Samsung: algunas fichas de celulares no traen el precio en el HTML. Ahí se busca el modelo (sm-xxxx al final
   de la ruta) en el buscador de Samsung, que da el precio de oferta y el stock. Se pide una vez por pestaña. */
let _samsungLista = null;
async function _samsung(h, u) {
  const r = _oficial(h);
  if (r.p || r.e === 'sin stock') return r;
  const m = (u.split(/[?#]/)[0].replace(/\/$/, '').split('/').pop().match(/(?:^|-)sm-([a-z0-9]+)$/i) || [])[1];
  if (!m) return r;
  if (!_samsungLista) _samsungLista = (async () => {
    const todos = [];
    for (const t of ['01010000', '01020000']) {
      const j = await (await fetch('https://searchapi.samsung.com/v6/front/b2c/product/finder/newhybris?type=' + t + '&siteCode=cl&start=1&num=200&sort=newest&onlyFilterInfoYN=N&keySummaryYN=N')).json();
      todos.push(...((j.response && j.response.resultData && j.response.resultData.productList) || []).flatMap(p => p.modelList || []));
    }
    return todos;
  })();
  const x = (await _samsungLista).find(y => String(y.modelCode).toUpperCase() === 'SM-' + m.toUpperCase());
  if (!x) return r;
  if (x.stockStatusText && x.stockStatusText !== 'inStock') return { e: 'sin stock' };
  const p = _precio(x.promotionPrice) || _precio(x.price);
  return p ? { p, c: 0 } : r;
}

const _corto = (i, r) => r.e ? [i, 0, 0, r.e] : [i, r.p, r.c ? 1 : 0, r.x || 0];
async function leer(tienda, rutas, grupo = 6) {
  const out = [];
  for (let i = 0; i < rutas.length; i += grupo) {
    await Promise.all(rutas.slice(i, i + grupo).map(async (u, k) => {
      const j = i + k;
      try {
        if (DIRECTOS[tienda]) { out.push(_corto(j, await DIRECTOS[tienda](u))); return; }
        const r = await fetch(u);
        if (!r.ok) { out.push([j, 0, 0, 'error ' + r.status]); return; }
        out.push(_corto(j, await LECTORES[tienda](await r.text(), u)));
      } catch (err) { out.push([j, 0, 0, String(err).slice(0, 40)]); }
    }));
  }
  return JSON.stringify(out.sort((a, b) => a[0] - b[0]));
}

/* Entel arma el precio con JavaScript: cada ficha se abre en un iframe oculto (misma página de Entel)
   y se lee "Precio oferta" (o "Precio General" si no hay oferta) de la opción "Equipo".
   Si la ficha carga sin el bloque de capacidad, el equipo ya no se vende (sin stock). */
async function leerEntel(rutas, grupo = 4) {
  const out = [];
  const uno = (u, i) => new Promise(res => {
    const f = document.createElement('iframe');
    f.style.cssText = 'position:fixed;left:-3000px;top:0;width:1200px;height:900px';
    f.src = u; const t0 = Date.now();
    const tick = () => {
      let txt = ''; try { txt = f.contentDocument.body.innerText; } catch (e) {}
      const p = _num((txt.match(/Precio oferta:\s*\$\s*([\d.]+)/) || txt.match(/Precio General:\s*\$\s*([\d.]+)/) || [])[1]);
      const listo = f.contentDocument && f.contentDocument.readyState === 'complete';
      if (p) { out.push([i, p, 0, 0]); f.remove(); res(); }
      else if (Date.now() - t0 > 20000) { out.push([i, 0, 0, listo && !/Capacidad/.test(txt) ? 'sin stock' : 'sin precio']); f.remove(); res(); }
      else setTimeout(tick, 700);
    };
    document.body.appendChild(f); setTimeout(tick, 2500);
  });
  for (let i = 0; i < rutas.length; i += grupo) await Promise.all(rutas.slice(i, i + grupo).map((u, k) => uno(u, i + k)));
  return JSON.stringify(out.sort((a, b) => a[0] - b[0]));
}

/* WOM muestra 24 equipos por página: lee la página abierta y luego pasa a la 2, 3... */
async function leerWom(rutas) {
  const best = rutas.map((u, i) => [i, 0, 0, 'no está en el listado']);
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const primero = () => (document.querySelector('a[href*="/equipos/"]:not([href$="/equipos/"])') || {}).href;
  const juntar = () => JSON.parse(leerListado('wom', rutas)).forEach(r => { if (r[1] && !best[r[0]][1]) best[r[0]] = r; });
  juntar();
  for (let p = 2; p < 10; p++) {
    const li = document.querySelector('li.rc-pagination-item-' + p); if (!li) break;
    const antes = primero(); (li.querySelector('a') || li).click();
    for (let k = 0; k < 20 && primero() === antes; k++) await sleep(400);
    await sleep(1500); juntar();
  }
  return JSON.stringify(best);
}

/* ---------- Solo lo que cambió (25-10-2026) ----------
   Compara lo leído con lo publicado (las páginas en GitHub) y devuelve solo las diferencias, en un texto corto:
   "i:precio:c:extra;" o "i:E:motivo;". Se guarda como <tienda>.txt y "precios.py aplicar" lo entiende
   (lo que no aparece en el texto queda igual). Así no hay que copiar los 1.200 precios en cada actualización.
     await cambios('falabella', R.falabella, await leer('falabella', R.falabella))
     await cambios('pcfactory', R.pcfactory, leerListado('pcfactory', R.pcfactory), soloEstaTanda)
   La ruta se arma igual que en precios.py (urlparse(url).path), sin volver a codificar tildes ni espacios. */
const _GH = 'https://raw.githubusercontent.com/COMPARACHILE/cualmeconviene/main/';
const _ruta = (s, url) => {
  // Xiaomi y Apple guardan la versión en la ruta (?gb=256, ?m=iPhone 18 Pro 256GB): igual que precios.ruta()
  const p = url.replace(/^[a-z]+:\/\/[^/]+/i, '').split(s === 'xiaomi' || s === 'apple' ? '#' : /[?#]/)[0];
  return s === 'pcfactory' ? '/producto/' + p.split('/producto/')[1].split('-')[0] : p;
};
async function publicados(tienda, rutas) {
  const hojas = [['notebooks.html', 'const NOTEBOOKS = ', '\n];'], ['celulares.html', 'const PHONES = ', ';\n'],
    ['tablets.html', 'const EQUIPOS = ', ';\n'], ['televisores.html', 'const EQUIPOS = ', ';\n'], ['consolas.html', 'const EQUIPOS = ', ';\n'],
    ['lavadoras.html', 'const EQUIPOS = ', ';\n'], ['aspiradoras.html', 'const EQUIPOS = ', ';\n'], ['batidoras.html', 'const EQUIPOS = ', ';\n'], ['cafeteras.html', 'const EQUIPOS = ', ';\n']];
  const pos = new Map(rutas.map((u, i) => [u, i])), exp = rutas.map(() => null);
  for (const [f, a, b] of hojas) {
    const t = await (await fetch(_GH + f, { cache: 'no-store' })).text();
    const i = t.indexOf(a) + a.length, j = t.indexOf(b, i) + (b === '\n];' ? 2 : 0);
    for (const eq of JSON.parse(t.slice(i, j))) for (const o of eq.offers) {
      if (o.s !== tienda) continue;
      const k = pos.get(_ruta(o.s, o.url));
      if (k == null || exp[k]) continue;
      const m = /(?:sin tarjeta|otros medios) \$([\d.]+)/.exec(o.note || '');
      exp[k] = [o.p, o.c ? 1 : 0, m && (tienda === 'ripley' || tienda === 'pcfactory') ? _num(m[1]) : 0, o.x ? 1 : 0];
    }
  }
  return exp;
}
async function cambios(tienda, rutas, res, solo) {
  const exp = await publicados(tienda, rutas), AG = ['sin stock', 'error 404', 'error 410'], out = [];
  for (const [i, p, c, x] of typeof res === 'string' ? JSON.parse(res) : res) {
    if (solo && !solo.has(i)) continue;
    const e = exp[i];
    if (!e) { out.push(i + ':E:no publicado'); continue; }
    if (!p) { if (!(AG.includes(x) && e[3])) out.push(i + ':E:' + x); }
    else if (e[3] || p !== e[0] || c !== e[1] || (x || 0) !== e[2]) out.push(i + ':' + p + ':' + c + ':' + (x || 0));
  }
  return out.join(';') + (out.length ? ';' : '');
}

/* Listados: abrir primero la página indicada y esperar a que cargue.
   claro: https://tienda.clarochile.cl/CategoryDisplay?...facetName_1=Liberados... (ver precios.py)
   wom:   https://store.wom.cl/equipos/?modalidad-de-compra=prepago  (bajar hasta el final para que carguen todos)
   pcfactory: https://www.pcfactory.cl/busqueda?productos=<ids>&size=60 */
function leerListado(tienda, rutas) {
  const out = [];
  if (tienda === 'claro') {
    document.querySelectorAll('a[href]').forEach(a => {
      if (!/Conoce/.test(a.textContent)) return;
      let c = a; for (let i = 0; i < 6 && !/Ahora/.test(c.innerText); i++) c = c.parentElement;
      const p = _num((c.innerText.match(/Ahora Desde\s*\$([\d.]+)/) || [])[1]);
      if (p) out.push({ u: new URL(a.href).pathname, p, c: 0 });
    });
  } else if (tienda === 'wom') {
    // Cada tarjeta es un enlace a /equipos/...; el segundo precio es el de oferta (el primero es el normal)
    document.querySelectorAll('a[href*="/equipos/"]').forEach(a => {
      const u = new URL(a.href).pathname; if (u === '/equipos/' || out.some(r => r.u === u)) return;
      let c = a; for (let i = 0; i < 6 && !/C[aá]mara[\s\S]*\$/.test(c.innerText); i++) c = c.parentElement;
      const ps = (c.innerText.match(/\$[\d.]+/g) || []).map(_num);
      const p = ps.length > 1 ? ps[1] : ps[0];
      if (p) out.push({ u, p, c: 0, n: 'Modalidad Prepago (equipo liberado)' });
    });
  } else if (tienda === 'pcfactory') {
    new Set([...document.querySelectorAll('a[href*="/producto/"]')].map(a => a.href)).forEach(h => {
      const a = [...document.querySelectorAll('a[href]')].find(x => x.href === h);
      let c = a; for (let i = 0; i < 7 && !/\$/.test(c.innerText); i++) c = c.parentElement;
      const ps = (c.innerText.match(/\$[\d.]+/g) || []).map(_num);
      const id = h.split('/producto/')[1].split('-')[0];
      if (ps.length >= 3) out.push({ u: '/producto/' + id, p: ps[1], c: 1, x: ps[2] });
      else if (ps.length === 2) out.push({ u: '/producto/' + id, p: ps[0], c: 1, x: ps[1] });
    });
  }
  const m = new Map(out.map(r => [r.u, r]));
  return JSON.stringify(rutas.map((u, i) => m.has(u) ? _corto(i, m.get(u)) : [i, 0, 0, tienda === 'pcfactory' ? 'sin stock' : 'no está en el listado']));
}
