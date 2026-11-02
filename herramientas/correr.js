/* Corre la lectura de una tienda en segundo plano y deja el resultado en window.JOB (01-11-2026).
   En la pestaña de la tienda:
     (0, eval)(await (await fetch('https://raw.githubusercontent.com/COMPARACHILE/cualmeconviene/main/herramientas/correr.js?' + Date.now())).text());
     __RUN('falabella', 'leer')      // modo: leer | entel | wom | listado ('pcfactory-2' para la tanda 2 de PCFactory)
   Luego se consulta JOB (fase, resumen) hasta que JOB.done. JOB.diff es lo que cambió (formato de cambios()),
   se guarda como <tienda>.txt y se aplica con "python3 herramientas/precios.py aplicar <carpeta>".
   JOB.cupones (Falabella y Paris) se guarda como <tienda>.cup en la misma carpeta.
   Los errores 403/429/5xx y de red se reintentan solos (hasta 6 vueltas, más lentas cada vez). */
window.__RUN = function (T, MODO) {
  const GH = 'https://raw.githubusercontent.com/COMPARACHILE/cualmeconviene/main/';
  window.JOB = { t: T, done: false, fase: 'cargando', ini: Date.now() };
  (async () => {
    try {
      const s = await (await fetch(GH + 'herramientas/leer_precios.js?' + Date.now(), { cache: 'no-store' })).text();
      (0, eval)(s + '\n;window.__L={leer,leerEntel,leerWom,leerListado,cambios,CUPONES};');
      const R = (await (await fetch(GH + 'herramientas/rutas.json?' + Date.now(), { cache: 'no-store' })).json())[T.split('-')[0]];
      JOB.n = R.length; JOB.fase = 'leyendo';
      let raw;
      if (MODO === 'entel') raw = await __L.leerEntel(R);
      else if (MODO === 'wom') raw = await __L.leerWom(R);
      else if (MODO === 'listado') raw = __L.leerListado(T.split('-')[0], R);
      else raw = await __L.leer(T, R);
      const res = JSON.parse(raw);
      const malo = r => !r[1] && /error (403|429|5\d\d)|Failed|TypeError|NetworkError|abort|timeout|timed out/i.test(String(r[3]));
      const sleep = ms => new Promise(r => setTimeout(r, ms));
      if (MODO === 'leer') {
        for (let vuelta = 0; vuelta < 6 && res.some(malo); vuelta++) {
          JOB.fase = 'reintento ' + (vuelta + 1) + ' (' + res.filter(malo).length + ')';
          await sleep(vuelta ? 15000 : 3000);
          for (const r of res.filter(malo)) {
            const otra = JSON.parse(await __L.leer(T, [R[r[0]]], 1))[0];
            r[1] = otra[1]; r[2] = otra[2]; r[3] = otra[3];
            await sleep(500 + 500 * vuelta);
          }
        }
      }
      JOB.res = res;
      try { localStorage.setItem('cmc_raw_' + T, JSON.stringify(res)); } catch (e) {}
      JOB.fase = 'comparando';
      let solo;
      if (T.startsWith('pcfactory')) {  // solo los equipos de esta tanda (los demás no están en el listado abierto)
        const ids = (new URLSearchParams(location.search).get('productos') || '').split(',');
        solo = new Set(R.map((u, i) => ids.includes(u.split('/').pop()) ? i : -1).filter(i => i >= 0));
        JOB.tanda = solo.size;
      }
      JOB.diff = await __L.cambios(T.split('-')[0], R, res, solo);
      const vistos = solo ? res.filter(r => solo.has(r[0])) : res;
      JOB.resumen = { total: vistos.length, conPrecio: vistos.filter(r => r[1]).length,
        errores: vistos.filter(r => !r[1]).reduce((a, r) => (a[r[3]] = (a[r[3]] || 0) + 1, a), {}) };
      // Cupones: t = {etiqueta: [i...]} y b = {i: precio sin tarjeta} (Paris); g = {"código|etiqueta|vence": {i: precio sin tarjeta}} (Falabella)
      if (T === 'falabella' || T === 'paris') {
        const cup = { t: {}, g: {}, b: {} };
        R.forEach((u, i) => {
          const q = __L.CUPONES[u]; if (!q) return;
          (q.t || []).forEach(t => (cup.t[t] = cup.t[t] || []).push(i));
          if (q.t && q.b) cup.b[i] = q.b;
          if (q.c) { const k = [q.c, q.l, q.v].join('|'); (cup.g[k] = cup.g[k] || {})[i] = q.b; }
        });
        JOB.cupones = JSON.stringify(cup);
      }
      JOB.fase = 'listo'; JOB.done = true; JOB.seg = Math.round((Date.now() - JOB.ini) / 1000);
    } catch (e) { JOB.err = String(e && e.stack || e).slice(0, 400); JOB.done = true; }
  })();
  return 'iniciado ' + T;
};
