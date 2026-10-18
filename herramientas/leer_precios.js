/* Lector de precios para la actualización diaria de ¿Cuál me conviene?
   Se pega en la consola (javascript_tool) de una pestaña abierta en la tienda que corresponde.
   Uso (RUTAS = la lista que imprime "python3 herramientas/precios.py lista" para esa tienda):
     1) Pega este archivo completo una vez por pestaña.
     2) await leer('falabella', RUTAS)        // fichas una por una
        leerListado('claro', RUTAS)          // claro, wom y pcfactory leen un listado ya abierto
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
    const sku = u.split('/').pop();
    const v = (pd.variants || []).find(x => x.id === sku) || pd.variants[0];
    const pr = Object.fromEntries((v.prices || []).map(p => [p.type, _num((p.price || [])[0])]));
    if (v.isPurchaseable === false) return { e: 'sin stock' };
    if (pr.cmrPrice) return { p: pr.cmrPrice, c: 1, n: 'Con tarjeta CMR' };
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
    const p = _num((h.match(/"offers"\s*:\s*\{[\s\S]{0,300}?"price"\s*:\s*"?([\d.]+)/) || [])[1]);
    return p ? { p, c: 0, n: 'Precio oferta online Entel (solo equipo)' } : { e: 'sin precio' };
  },
  movistar(h) {
    if (/schema.org\/OutOfStock/.test(h)) return { e: 'sin stock' };
    const p = _num((h.match(/"price"\s*:\s*"?(\d{4,})/) || [])[1]);
    return p ? { p, c: 0 } : { e: 'sin precio' };
  }
};

const _corto = (i, r) => r.e ? [i, 0, 0, r.e] : [i, r.p, r.c ? 1 : 0, r.x || 0];
async function leer(tienda, rutas, grupo = 6) {
  const out = [];
  for (let i = 0; i < rutas.length; i += grupo) {
    await Promise.all(rutas.slice(i, i + grupo).map(async (u, k) => {
      const j = i + k;
      try {
        const r = await fetch(u);
        if (!r.ok) { out.push([j, 0, 0, 'error ' + r.status]); return; }
        out.push(_corto(j, LECTORES[tienda](await r.text(), u)));
      } catch (err) { out.push([j, 0, 0, String(err).slice(0, 40)]); }
    }));
  }
  return JSON.stringify(out.sort((a, b) => a[0] - b[0]));
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
