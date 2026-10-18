/* Lector de fotos para ¿Cuál me conviene?
   Se pega en la consola (javascript_tool) de una pestaña abierta en la tienda que corresponde,
   igual que leer_precios.js. Solo lee la imagen pública del producto (og:image o JSON-LD).
   Uso: RUTAS = [[id, ruta], ...] que imprime "python3 herramientas/imagenes.py lista"
        await fotos(RUTAS)   ->  '[["id","https://...jpg"], ...]'  (o el motivo del error)
   Después: guardar el resultado en resultados/fotos-<tienda>.json y correr
        python3 herramientas/imagenes.py aplicar resultados/   */

function _foto(h) {
  const meta = h.match(/<meta[^>]+property=["']og:image(?::secure_url)?["'][^>]*>/i);
  if (meta) {
    const c = meta[0].match(/content=["']([^"']+)["']/i);
    if (c && /^https?:\/\//.test(c[1].replace(/&amp;/g, '&'))) return c[1].replace(/&amp;/g, '&');
  }
  for (const m of h.matchAll(/<script[^>]+application\/ld\+json[^>]*>([\s\S]*?)<\/script>/gi)) {
    try {
      const walk = x => {
        if (!x || typeof x !== 'object') return null;
        if (Array.isArray(x)) { for (const y of x) { const r = walk(y); if (r) return r; } return null; }
        if (/Product/.test(x['@type']) && x.image) {
          const im = Array.isArray(x.image) ? x.image[0] : x.image;
          return typeof im === 'string' ? im : im && (im.url || im.contentUrl);
        }
        for (const k in x) { const r = walk(x[k]); if (r) return r; }
        return null;
      };
      const r = walk(JSON.parse(m[1]));
      if (r) return r;
    } catch (e) { /* JSON-LD roto: seguir */ }
  }
  const img = h.match(/<meta[^>]+name=["']twitter:image["'][^>]*content=["']([^"']+)["']/i);
  return img ? img[1] : null;
}

async function fotos(rutas, grupo = 6) {
  const out = [];
  for (let i = 0; i < rutas.length; i += grupo) {
    await Promise.all(rutas.slice(i, i + grupo).map(async ([id, u]) => {
      try {
        const r = await fetch(u);
        if (!r.ok) { out.push([id, 'error ' + r.status]); return; }
        const f = _foto(await r.text());
        out.push([id, f ? new URL(f, location.href).href : 'sin foto']);
      } catch (err) { out.push([id, String(err).slice(0, 40)]); }
    }));
  }
  return JSON.stringify(out);
}
