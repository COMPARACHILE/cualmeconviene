/* ¿Cuál me conviene? — piezas del rediseño del 19-10-2026 (sin dependencias).
   Se carga en <head> SIN defer, antes del código de cada página, porque las páginas arman sus tarjetas
   con CMC.tarjeta apenas leen los datos. Nada aquí toca el DOM al cargarse: CMC.filtros y CMC.guia
   se llaman desde cada página cuando el documento ya está listo (DOMContentLoaded). */
/* =====================================================================================
   Rediseño 19-10-2026: tarjeta compacta, sello del puma, filtros en panel y asistente.
   Cada página usa estas piezas con window.CMC (tarjeta, sello, pago, nota, filtros, guia).
   ===================================================================================== */
(() => {
  const D = document;
  const CMC = window.CMC = window.CMC || {};
  const fmt = n => '$' + Math.round(n).toLocaleString('es-CL');
  const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const PUMA = '/assets/puma-sello.webp';
  const reduce = matchMedia('(prefers-reduced-motion: reduce)');
  const fire = (el, t) => el && el.dispatchEvent(new Event(t, { bubbles: true }));
  CMC.fmt = fmt; CMC.esc = esc;

  /* Monto corto: $500 mil, $1,2 M */
  CMC.corto = n => n >= 1e6 ? '$' + (n / 1e6).toLocaleString('es-CL', { maximumFractionDigits: 1 }) + ' M' : '$' + Math.round(n / 1000) + ' mil';

  /* Medio de pago del precio: etiqueta corta en vez de asterisco */
  CMC.pago = o => !o || !o.c ? '' : `<span class="pago" title="${esc(o.note || 'Precio con un medio de pago de la tienda')}">${/transfer/i.test(o.note || '') ? 'transferencia' : 'con tarjeta'}</span>`;

  /* Sello del puma: solo para el mejor calidad-precio de cada grupo */
  CMC.sello = extra => `<span class="sello"><img src="${PUMA}" alt="" width="26" height="26" decoding="async"><span>Elegido por el puma${extra ? `<small>${esc(extra)}</small>` : ''}</span></span>`;

  /* Nota de potencia de 1 a 10: el puesto del equipo entre todos los del sitio (10 = de los más potentes) */
  CMC.escala = vals => {
    const s = vals.filter(v => v > 0).sort((a, b) => a - b);
    return v => {
      if (!(v > 0) || !s.length) return 0;
      let lo = 0, hi = s.length;
      while (lo < hi) { const m = (lo + hi) >> 1; if (s[m] <= v) lo = m + 1; else hi = m; }
      return Math.max(1, Math.min(10, Math.ceil(lo / s.length * 10)));
    };
  };
  CMC.nota = (n, que) => !n ? '' : `<span class="nota" title="${esc(que || 'Potencia comparada con los demás equipos del sitio')}"><span>Potencia</span><span class="nota-b" aria-hidden="true"><i style="width:${n * 10}%"></i></span><span><b>${n}</b>/10</span></span>`;

  /* Tarjeta compacta, igual en las cuatro categorías */
  CMC.tarjeta = e => {
    const os = e.os, b = os[0], hi = os[os.length - 1], T = e.tiendas;
    const nom = s => (T[s] || { name: s }).name, col = s => (T[s] || {}).color || '#888';
    const multi = os.length > 1;
    const empate = os.filter(o => o.p === b.p).length;
    const donde = !multi ? `Solo en ${nom(b.s)}`
      : hi.p === b.p ? `Mismo precio en ${os.length} tiendas`
      : `${nom(b.s)}${empate > 1 ? ' y ' + (empate - 1) + ' más' : ''} · ${os.length} tiendas`;
    const ir = `class="offer c3-ir" data-id="${esc(e.dataId)}" data-store="${b.s}" href="${esc(b.url)}" target="_blank" rel="noopener nofollow sponsored"`;
    const fila = o => `<li><a class="offer${o.p === b.p ? ' best' : ''}" data-id="${esc(e.dataId)}" data-store="${o.s}" href="${esc(o.url)}" target="_blank" rel="noopener nofollow sponsored"><i class="dot" style="background:${col(o.s)}"></i><span class="oname">${nom(o.s)}${o.note || o.seller ? `<small>${esc([o.note, o.seller].filter(Boolean).join(' · '))}</small>` : ''}</span><span class="oprice">${fmt(o.p)}${o.p > b.p ? `<small>+${fmt(o.p - b.p)}</small>` : ''}</span></a></li>`;
    return `<article class="c3${e.sello ? ' elegido' : ''}"${e.anchor ? ` id="${esc(e.anchor)}"` : ''}>
      <a class="c3-foto pvA" href="${esc(e.ficha)}" tabindex="-1" aria-hidden="true">${e.art}</a>
      <div class="c3-info">
        ${e.sello ? CMC.sello(e.sello === true ? '' : e.sello) : ''}
        ${e.tags && e.tags.length ? `<p class="c3-tags">${e.tags.join('')}</p>` : ''}
        <h3><a class="aFicha" href="${esc(e.ficha)}">${esc(e.nombre)}</a></h3>
        <p class="c3-spec">${esc(e.spec)}</p>
        ${e.nota || ''}
        <p class="c3-precio"><span class="price">${fmt(b.p)}</span>${CMC.pago(b)}</p>
        <p class="c3-donde"><i class="dot" style="background:${col(b.s)}"></i>${esc(donde)}</p>
        ${multi && hi.p > b.p ? `<p class="c3-ahorro">Ahorras ${fmt(hi.p - b.p)}</p>` : ''}
        <div class="c3-acc"><a ${ir}>Ir a ${nom(b.s)}</a>${multi ? `<button type="button" class="c3-ver" aria-expanded="false">${os.length} precios</button>` : ''}</div>
        ${multi ? `<ul class="c3-tiendas" hidden aria-label="Precio en cada tienda">${os.map(fila).join('')}</ul>` : ''}
        ${e.extra || ''}
      </div></article>`;
  };
  D.addEventListener('click', ev => {
    const v = ev.target.closest('.c3-ver');
    if (!v) return;
    const ul = v.closest('article').querySelector('.c3-tiendas');
    const abrir = ul.hidden;
    ul.hidden = !abrir; v.setAttribute('aria-expanded', String(abrir));
  });

  /* Fotos: cuadro gris hasta que cargan */
  const ok = im => { if (im.complete && im.naturalWidth) im.classList.add('ok'); };
  D.addEventListener('load', ev => { if (ev.target.tagName === 'IMG' && ev.target.classList.contains('foto')) ev.target.classList.add('ok'); }, true);
  const marcaFotos = () => D.querySelectorAll('img.foto:not(.ok)').forEach(ok);
  marcaFotos(); setTimeout(marcaFotos, 800);

  /* Precio: mover los dos puntos sin que se crucen */
  CMC.rango = (a, b) => {
    const lo = D.getElementById('budgetMin'), hi = D.getElementById('budget');
    if (!lo || !hi) return;
    const max = +hi.max;
    lo.value = 0; fire(lo, 'input');
    hi.value = b == null || b > max ? max : b; fire(hi, 'input');
    lo.value = Math.min(a || 0, +hi.value); fire(lo, 'input');
    fire(hi, 'change');
  };
  CMC.marcar = sel => { const i = D.querySelector(sel); if (i && !i.checked) { i.checked = true; fire(i, 'change'); } };
  CMC.pulsar = sel => { const b = D.querySelector(sel); if (b) b.click(); };
  CMC.elegir = (sel, v) => { const s = D.querySelector(sel); if (s) { s.value = v; fire(s, 'change'); } };

  /* ---------- Barra fija "Filtros | Ordenar", panel a pantalla completa y filtros activos ---------- */
  CMC.filtros = cfg => {
    const panel = D.getElementById('panel'), res = D.getElementById('compara'), count = D.getElementById('count');
    if (!panel || !res || !count) return;
    const noun = cfg.noun || 'equipos', uno = cfg.uno || 'equipo';
    const lo = D.getElementById('budgetMin'), hi = D.getElementById('budget');
    const sortSel = D.getElementById('sortF');

    // Rangos de precio en botones
    const rW = panel.querySelector('[data-rangos]');
    let rangos = [];
    if (rW && hi) {
      rangos = rW.dataset.rangos.split(',').map(x => { const [a, b] = x.split('-'); return [+a || 0, b ? +b : null]; });
      rW.innerHTML = rangos.map(([a, b], i) => `<button type="button" data-r="${i}" aria-pressed="false">${!a ? 'Hasta ' + CMC.corto(b) : !b ? 'Más de ' + CMC.corto(a) : CMC.corto(a).replace(' mil', '') + ' a ' + CMC.corto(b)}</button>`).join('');
      rW.addEventListener('click', ev => {
        const bt = ev.target.closest('[data-r]'); if (!bt) return;
        const [a, b] = rangos[+bt.dataset.r];
        if (bt.getAttribute('aria-pressed') === 'true') CMC.rango(0, null); else CMC.rango(a, b);
      });
    }
    const rangoTxt = () => {
      const a = +lo.value, b = +hi.value, max = +hi.max;
      return a && b < max ? CMC.corto(a) + ' a ' + CMC.corto(b) : a ? 'Desde ' + CMC.corto(a) : 'Hasta ' + CMC.corto(b);
    };

    // "Más filtros": lo avanzado queda plegado
    const adv = cfg.avanzado && D.getElementById(cfg.avanzado);
    if (adv) {
      const mb = D.createElement('button');
      mb.type = 'button'; mb.className = 'masF'; mb.setAttribute('aria-expanded', 'false'); mb.setAttribute('aria-controls', adv.id);
      mb.textContent = 'Más filtros';
      adv.before(mb); adv.hidden = true;
      mb.addEventListener('click', () => { adv.hidden = !adv.hidden; mb.setAttribute('aria-expanded', String(!adv.hidden)); });
    }

    // Barra
    const bar = D.createElement('div'); bar.className = 'fbar';
    bar.innerHTML = `<button type="button" class="fbar-btn" aria-haspopup="dialog" aria-controls="panel"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M7 12h10M10 18h4"/></svg>Filtros<b></b></button><p class="fbar-n" aria-live="polite"></p>`;
    if (sortSel) {
      const lab = D.createElement('label'); lab.className = 'fbar-orden';
      lab.innerHTML = '<span class="sr">Ordenar por</span>';
      lab.append(sortSel); bar.append(lab);
    }
    const act = D.createElement('div'); act.className = 'activos'; act.setAttribute('aria-label', 'Filtros activos');
    res.prepend(act); res.prepend(bar);

    // Panel: cabecera y pie solo en el celular
    const body = D.createElement('div'); body.className = 'sheet-body';
    while (panel.firstChild) body.append(panel.firstChild);
    const head = D.createElement('div'); head.className = 'sheet-hd';
    head.innerHTML = '<p>Filtros</p><button type="button" class="sheet-x" aria-label="Cerrar filtros">✕</button>';
    const foot = D.createElement('div'); foot.className = 'sheet-ft';
    foot.innerHTML = '<button type="button" class="sheet-limpiar">Limpiar</button><button type="button" class="sheet-ver">Ver resultados</button>';
    panel.append(head, body, foot);
    panel.classList.add('sheet');
    const btn = bar.querySelector('.fbar-btn');
    const mq = matchMedia('(max-width: 959px)');
    const abrir = () => {
      panel.classList.add('open'); D.documentElement.classList.add('sheet-on');
      panel.setAttribute('role', 'dialog'); panel.setAttribute('aria-modal', 'true'); panel.setAttribute('aria-label', 'Filtros');
      btn.setAttribute('aria-expanded', 'true');
      head.querySelector('.sheet-x').focus();
    };
    const cerrar = () => {
      if (!panel.classList.contains('open')) return;
      panel.classList.remove('open'); D.documentElement.classList.remove('sheet-on');
      ['role', 'aria-modal', 'aria-label'].forEach(a => panel.removeAttribute(a));
      btn.setAttribute('aria-expanded', 'false');
      const y = res.getBoundingClientRect().top + scrollY - 4;
      if (Math.abs(scrollY - y) > 40) scrollTo({ top: y, behavior: 'auto' });
      btn.focus({ preventScroll: true });
    };
    CMC.cerrarFiltros = cerrar;
    btn.addEventListener('click', abrir);
    head.querySelector('.sheet-x').addEventListener('click', cerrar);
    foot.querySelector('.sheet-ver').addEventListener('click', cerrar);
    foot.querySelector('.sheet-limpiar').addEventListener('click', () => { const r = D.getElementById('resetAll'); if (r) r.click(); });
    panel.addEventListener('keydown', ev => {
      if (!panel.classList.contains('open')) return;
      if (ev.key === 'Escape') { ev.preventDefault(); cerrar(); return; }
      if (ev.key !== 'Tab') return;
      const f = [...panel.querySelectorAll('button, input, select, summary, a[href]')].filter(x => x.offsetParent !== null && !x.disabled);
      if (!f.length) return;
      if (ev.shiftKey && D.activeElement === f[0]) { ev.preventDefault(); f[f.length - 1].focus(); }
      else if (!ev.shiftKey && D.activeElement === f[f.length - 1]) { ev.preventDefault(); f[0].focus(); }
    });
    mq.addEventListener('change', () => { if (!mq.matches) cerrar(); });

    // Filtros activos como etiquetas que se quitan con un toque
    const defs = new Map();
    panel.querySelectorAll('select').forEach(s => defs.set(s, s.value));
    const texto = i => {
      const sp = i.closest('label') && i.closest('label').querySelector('span');
      return sp ? (sp.firstChild ? sp.firstChild.textContent : sp.textContent).trim() : i.value;
    };
    const lista = () => {
      const out = [];
      const cat = count.querySelector('.catChip');
      if (cat) out.push([cat.textContent.replace('✕', '').trim(), () => cat.click()]);
      panel.querySelectorAll('input[type=checkbox]:checked').forEach(i => out.push([texto(i), () => { i.checked = false; fire(i, 'change'); }]));
      panel.querySelectorAll('input[type=radio]:checked').forEach(i => {
        if (i.defaultChecked) return;
        const d = [...panel.querySelectorAll(`input[type=radio][name="${i.name}"]`)].find(x => x.defaultChecked);
        out.push([texto(i), () => { if (d) { d.checked = true; fire(d, 'change'); } }]);
      });
      panel.querySelectorAll('.seg').forEach(g => {
        const bs = [...g.querySelectorAll('button')], on = bs.find(x => x.getAttribute('aria-pressed') === 'true');
        if (on && on !== bs[0]) out.push([on.textContent.trim(), () => bs[0].click()]);
      });
      panel.querySelectorAll('select').forEach(s => {
        if (s.value === defs.get(s)) return;
        const lab = s.labels && s.labels[0] ? s.labels[0].textContent.trim() + ': ' : '';
        out.push([lab + s.options[s.selectedIndex].text, () => { s.value = defs.get(s); fire(s, 'change'); }]);
      });
      if (lo && hi && (+lo.value > 0 || +hi.value < +hi.max)) out.push([rangoTxt(), () => CMC.rango(0, null)]);
      const q = D.getElementById('q');
      if (q && q.value.trim()) out.push([`"${q.value.trim()}"`, () => { q.value = ''; fire(q, 'input'); }]);
      return out;
    };
    let quitar = [];
    act.addEventListener('click', ev => { const b = ev.target.closest('button[data-i]'); if (b && quitar[+b.dataset.i]) quitar[+b.dataset.i](); });
    const pinta = () => {
      const l = lista();
      quitar = l.map(x => x[1]);
      act.innerHTML = l.map((x, i) => `<button type="button" data-i="${i}" aria-label="Quitar ${esc(x[0])}">${esc(x[0])}</button>`).join('');
      const nb = l.filter(x => !/^"/.test(x[0])).length;
      btn.querySelector('b').textContent = nb ? nb : '';
      const m = (count.querySelector('b') || count).textContent.replace(/\D/g, '');
      const n = +m || 0;
      bar.querySelector('.fbar-n').innerHTML = `<b>${n}</b><span> ${n === 1 ? uno : noun}</span>`;
      foot.querySelector('.sheet-ver').textContent = n ? `Ver ${n} ${n === 1 ? uno : noun}` : 'Sin resultados: cambia los filtros';
      if (rW && hi) rW.querySelectorAll('[data-r]').forEach(bt => {
        const [a, b] = rangos[+bt.dataset.r];
        bt.setAttribute('aria-pressed', String(+lo.value === a && +hi.value === (b == null ? +hi.max : Math.min(b, +hi.max))));
      });
    };
    new MutationObserver(pinta).observe(count, { childList: true, subtree: true, characterData: true });
    pinta();
    CMC.pintaFiltros = pinta;
  };

  /* ---------- Asistente "Ayúdame a elegir": tres preguntas, una por pantalla ---------- */
  CMC.guia = cfg => {
    const box = D.createElement('div');
    box.className = 'guia'; box.hidden = true;
    box.setAttribute('role', 'dialog'); box.setAttribute('aria-modal', 'true'); box.setAttribute('aria-labelledby', 'guiaQ');
    box.innerHTML = `<div class="guia-box"><div class="guia-top"><div class="guia-paso" aria-hidden="true"></div><button type="button" class="guia-x" aria-label="Cerrar">✕</button></div>
      <div class="guia-q"><img src="${PUMA}" alt="" width="56" height="56"><h2 id="guiaQ"></h2></div>
      <div class="guia-ops"></div>
      <div class="guia-pie"><button type="button" class="guia-atras">← Atrás</button><button type="button" class="guia-igual">Me da igual</button></div></div>`;
    D.body.append(box);
    let paso = 0, resp = [], origen = null;
    const P = cfg.pasos;
    const pinta = () => {
      const p = P[paso];
      box.querySelector('.guia-paso').innerHTML = P.map((_, i) => `<i class="${i <= paso ? 'on' : ''}"></i>`).join('');
      box.querySelector('#guiaQ').textContent = p.q;
      box.querySelector('.guia-ops').innerHTML = p.ops.map((o, i) => `<button type="button" data-o="${i}">${esc(o.t)}${o.d ? `<small>${esc(o.d)}</small>` : ''}</button>`).join('');
      box.querySelector('.guia-atras').style.visibility = paso === 0 ? 'hidden' : 'visible';
      const f = box.querySelector('.guia-ops button'); if (f) f.focus();
    };
    const cerrar = () => { box.hidden = true; D.documentElement.classList.remove('sheet-on'); if (origen) origen.focus({ preventScroll: true }); };
    const termina = () => {
      cerrar();
      if (cfg.antes) cfg.antes();
      resp.forEach(r => { if (r && r.a) r.a(); });
      if (cfg.despues) cfg.despues(resp);
      const res = D.getElementById('compara');
      if (res) setTimeout(() => res.scrollIntoView({ behavior: reduce.matches ? 'auto' : 'smooth', block: 'start' }), 60);
    };
    const sigue = r => { resp[paso] = r; if (paso < P.length - 1) { paso++; pinta(); } else termina(); };
    box.querySelector('.guia-ops').addEventListener('click', ev => { const b = ev.target.closest('[data-o]'); if (b) sigue(P[paso].ops[+b.dataset.o]); });
    box.querySelector('.guia-igual').addEventListener('click', () => sigue(null));
    box.querySelector('.guia-atras').addEventListener('click', () => { if (paso) { paso--; pinta(); } });
    box.querySelector('.guia-x').addEventListener('click', cerrar);
    box.addEventListener('click', ev => { if (ev.target === box) cerrar(); });
    box.addEventListener('keydown', ev => {
      if (ev.key === 'Escape') { ev.preventDefault(); cerrar(); return; }
      if (ev.key !== 'Tab') return;
      const f = [...box.querySelectorAll('button')].filter(x => !x.hidden);
      if (ev.shiftKey && D.activeElement === f[0]) { ev.preventDefault(); f[f.length - 1].focus(); }
      else if (!ev.shiftKey && D.activeElement === f[f.length - 1]) { ev.preventDefault(); f[0].focus(); }
    });
    const abrir = b => { origen = b || null; paso = 0; resp = []; if (CMC.cerrarFiltros) CMC.cerrarFiltros(); box.hidden = false; D.documentElement.classList.add('sheet-on'); pinta(); };
    D.addEventListener('click', ev => { const b = ev.target.closest('[data-guia]'); if (b) { ev.preventDefault(); abrir(b); } });
    CMC.abrirGuia = abrir;
    if (/[?&]guia=1/.test(location.search)) setTimeout(() => abrir(), 300);
  };
})();
