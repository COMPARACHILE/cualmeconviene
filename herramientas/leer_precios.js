/* Lector de precios para la actualización diaria de ¿Cuál me conviene?
   Se pega en la consola (javascript_tool) de una pestaña abierta en la tienda que corresponde.
   Uso (RUTAS = la lista que imprime "python3 herramientas/precios.py lista" para esa tienda):
     1) Pega este archivo completo una vez por pestaña.
     2) await leer('falabella', RUTAS)        // fichas una por una (falabella, paris, ripley, movistar)
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
    if (pr.internetPrice) return { p: pr.internetPrice, c: 0, n: 'Precio Internet' };
    if (pr.eventPrice) return { p: pr.eventPrice, c: 0, n: 'Precio Internet' };  // precio de evento (Cyber, etc.): es el que paga cualquiera
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
  movistar(h) {
    if (/schema.org\/OutOfStock/.test(h)) return { e: 'sin stock' };
    const p = _num((h.match(/"price"\s*:\s*"?(\d{4,})/) || [])[1]);
    return p ? { p, c: 0 } : { e: 'sin precio' };
  }
};

/* Tiendas oficiales de las marcas (26-10-2026). La mayoría publica el precio en los datos para Google (JSON-LD
   "Product" con "offers"): se lee igual en todas. Las tiendas hechas con VTEX se leen desde su catálogo público
   (/api/catalog_system/pub/products/search/<producto>/p), que dice precio y unidades disponibles. */
function _ldOferta(h) {
  for (const m of h.matchAll(/<script[^>]+application\/ld\+json[^>]*>([\s\S]*?)<\/script>/gi)) {
    let j; try { j = JSON.parse(m[1].trim()); } catch (e) { continue; }
    let hit = null;
    const walk = x => {
      if (hit || !x || typeof x !== 'object') return;
      if (Array.isArray(x)) { x.forEach(walk); return; }
      if ([].concat(x['@type'] || []).includes('Product') && x.offers) { hit = x; return; }
      for (const k in x) walk(x[k]);
    };
    walk(j);
    if (!hit) continue;
    let of = [].concat(hit.offers)[0] || {};
    if (of.offers) of = Object.assign({}, of, [].concat(of.offers)[0] || {});
    const n = v => {
      if (typeof v === 'number') return Math.round(v);
      const t = String(v || '').trim();
      return /^\d+(\.\d+)?$/.test(t) ? Math.round(parseFloat(t)) : _num(t.replace(/,\d{1,2}$/, ''));
    };
    const p = n(of.price) || n(of.lowPrice);
    if (/OutOfStock|SoldOut|Discontinued/i.test(String(of.availability || ''))) return { e: 'sin stock' };
    return p ? { p, c: 0, n: '' } : { e: 'sin precio' };
  }
  // Sin JSON-LD: etiqueta "product:price:amount" (Magento, Jumpseller y otras)
  const mp = h.match(/<meta[^>]+property=["']product:price:amount["'][^>]*content=["']([\d.,]+)["']/i) || h.match(/<meta[^>]+content=["']([\d.,]+)["'][^>]*property=["']product:price:amount["']/i);
  if (mp) {
    if (/product:availability["'][^>]*content=["'](out of stock|oos)|class="stock unavailable|out-of-stock/i.test(h)) return { e: 'sin stock' };
    const p = /^\d+(\.\d+)?$/.test(mp[1]) ? Math.round(parseFloat(mp[1])) : _num(mp[1].replace(/,\d{1,2}$/, ''));
    return p ? { p, c: 0, n: '' } : { e: 'sin precio' };
  }
  return { e: 'sin datos' };
}
async function _vtex(u) {
  const r = await fetch('/api/catalog_system/pub/products/search' + u.replace(/[?#].*$/, ''));
  if (!r.ok) return { e: 'error ' + r.status };
  const j = await r.json();
  if (!j.length) return { e: 'error 404' };
  const ofs = j[0].items.flatMap(it => it.sellers.map(s => s.commertialOffer)).filter(o => o.AvailableQuantity > 0 && o.Price > 0);
  if (!ofs.length) return { e: 'sin stock' };
  return { p: Math.min(...ofs.map(o => Math.round(o.Price))), c: 0, n: '' };
}
// Tienda oficial -> forma de leerla. Abrir la portada de cada una (precios.py lista) y llamar a leer('<tienda>', RUTAS).
const OFICIALES = { samsung: 'ld', lg: 'ld', midea: 'vtex', electrolux: 'vtex', mademsa: 'vtex', fensa: 'vtex', dyson: 'vtex', thomas: 'ld', ursus: 'ld' };
for (const [t, k] of Object.entries(OFICIALES)) if (k === 'ld') LECTORES[t] = _ldOferta;

const _corto = (i, r) => r.e ? [i, 0, 0, r.e] : [i, r.p, r.c ? 1 : 0, r.x || 0];
async function leer(tienda, rutas, grupo = 6) {
  const out = [];
  for (let i = 0; i < rutas.length; i += grupo) {
    await Promise.all(rutas.slice(i, i + grupo).map(async (u, k) => {
      const j = i + k;
      try {
        if (OFICIALES[tienda] === 'vtex') { out.push(_corto(j, await _vtex(u))); return; }
        const r = await fetch(u);
        if (!r.ok) { out.push([j, 0, 0, 'error ' + r.status]); return; }
        out.push(_corto(j, LECTORES[tienda](await r.text(), u)));
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
  const p = url.replace(/^[a-z]+:\/\/[^/]+/i, '').split(/[?#]/)[0];
  return s === 'pcfactory' ? '/producto/' + p.split('/producto/')[1].split('-')[0] : p;
};
async function publicados(tienda, rutas) {
  const hojas = [['notebooks.html', 'const NOTEBOOKS = ', '\n];'], ['celulares.html', 'const PHONES = ', ';\n'],
    ['tablets.html', 'const EQUIPOS = ', ';\n'], ['televisores.html', 'const EQUIPOS = ', ';\n'], ['consolas.html', 'const EQUIPOS = ', ';\n']];
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
