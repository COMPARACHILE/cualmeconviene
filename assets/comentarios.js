/* ¿Cuál me conviene? — Comentarios de cada equipo, avisos de precio por correo y "Mi cuenta".
   Se inicia sesión con Google solo para comentar o pedir avisos: para mirar precios no hace falta cuenta.
   Los comentarios se guardan con la dirección fija de la ficha, así que siguen ahí si el equipo se agota y vuelve. */
(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const fmt = n => '$' + Math.round(n).toLocaleString('es-CL');
  const sec = document.getElementById('comentarios');
  const CLAVE = sec ? sec.dataset.producto : '';
  const NOMBRE = sec ? sec.dataset.nombre : '';
  const btnAv = $('[data-avisame]'), msgAv = $('.avisaMsg');
  const cuentaEl = document.getElementById('miCuenta');
  const usaSesion = sec || btnAv || cuentaEl || document.getElementById('panel');
  if (!usaSesion) return;

  /* ---------- Sesión ---------- */
  let S = { activo: false, clientId: '', usuario: null, aviso: null, listo: false };
  const oyentes = new Set();
  const avisar = () => oyentes.forEach(f => { try { f(S); } catch (e) { console.error(e); } });
  let despuesDeIngresar = null; // lo que la persona quería hacer antes de iniciar sesión

  async function api(url, op = {}) {
    let r;
    try {
      r = await fetch(url, { credentials: 'same-origin', ...op, headers: { 'Content-Type': 'application/json', ...(op.headers || {}) } });
    } catch (_) {
      throw new Error('No hay conexión. Revisa tu internet e inténtalo de nuevo.');
    }
    let d = null;
    try { d = await r.json(); } catch (_) {}
    if (!r.ok) {
      const e = new Error((d && d.error) || 'Algo falló de nuestro lado. Inténtalo de nuevo en un momento.');
      e.status = r.status;
      if (r.status === 401 && S.usuario) { S.usuario = null; S.aviso = null; avisar(); }
      throw e;
    }
    return d;
  }

  let gis = null;
  function cargarGoogle() {
    if (gis) return gis;
    gis = new Promise((ok, mal) => {
      const s = document.createElement('script');
      s.src = 'https://accounts.google.com/gsi/client';
      s.async = true;
      s.onload = () => {
        google.accounts.id.initialize({
          client_id: S.clientId, callback: credencial, ux_mode: 'popup', auto_select: false,
          cancel_on_tap_outside: true, itp_support: true, use_fedcm_for_button: true
        });
        ok();
      };
      s.onerror = () => { gis = null; mal(new Error('google')); };
      document.head.append(s);
    });
    return gis;
  }
  async function botonGoogle(el) {
    if (!el) return;
    el.innerHTML = '<span class="gCarga">Cargando el botón de Google…</span>';
    try {
      await cargarGoogle();
      el.innerHTML = '';
      google.accounts.id.renderButton(el, {
        type: 'standard', theme: 'outline', size: 'large', text: 'continue_with', shape: 'pill', logo_alignment: 'left',
        locale: 'es', width: Math.round(Math.max(220, Math.min(320, el.clientWidth || 300)))
      });
    } catch (_) {
      el.innerHTML = '<p class="loginErr">No se pudo cargar el botón de Google. Si usas un bloqueador de anuncios, permite este sitio y recarga la página.</p>';
    }
  }
  const errorIngreso = m => document.querySelectorAll('.loginErr').forEach(p => { p.textContent = m; });

  async function credencial(resp) {
    errorIngreso('');
    try {
      const d = await api('/api/sesion', { method: 'POST', body: JSON.stringify({ credential: resp.credential, p: CLAVE }) });
      ingresado(d);
    } catch (e) { errorIngreso(e.message); }
  }
  function ingresado(d) {
    S.usuario = d.usuario;
    S.aviso = d.aviso || null;
    const pend = despuesDeIngresar;
    despuesDeIngresar = null;
    avisar();
    if (pend) pend(d);
  }
  async function salir() {
    try { await api('/api/sesion', { method: 'DELETE' }); } catch (_) {}
    try { if (window.google) google.accounts.id.disableAutoSelect(); } catch (_) {}
    S.usuario = null; S.aviso = null;
    avisar();
  }
  async function guardarResumen(si) {
    const d = await api('/api/cuenta', { method: 'POST', body: JSON.stringify({ resumen: !!si }) });
    const antes = S.usuario && S.usuario.decidio;
    S.usuario = d.usuario;
    if (!antes && !cuentaEl) avisar(); // la tarjeta "¿Te avisamos por correo?" ya no hace falta
    return d.usuario;
  }

  /* ---------- Ventana para iniciar sesión (botón "Avísame") ---------- */
  let dlg = null;
  function ventana() {
    if (!dlg) {
      dlg = document.createElement('dialog');
      dlg.className = 'cmcDlg';
      dlg.setAttribute('aria-labelledby', 'cmcDlgT');
      dlg.innerHTML = '<button type="button" class="dlgX" aria-label="Cerrar">&times;</button><div class="dlgIn"></div>';
      dlg.querySelector('.dlgX').addEventListener('click', () => dlg.close());
      dlg.addEventListener('click', e => { if (e.target === dlg) dlg.close(); });
      dlg.addEventListener('close', () => { despuesDeIngresar = null; if (btnAv) btnAv.focus(); });
      document.body.append(dlg);
    }
    return dlg;
  }
  function pedirIngreso(titulo, texto, luego) {
    const d = ventana(), inn = $('.dlgIn', d);
    inn.innerHTML = `<img class="dlgPuma" src="/assets/puma-icono-96.png" alt="" width="56" height="56">
      <h2 id="cmcDlgT">${esc(titulo)}</h2><p>${texto}</p><div class="gBtn"></div><p class="loginErr" aria-live="polite"></p>
      <p class="dlgPriv">Solo recibimos tu nombre, foto y correo de Google. Tu correo no se publica ni se comparte. <a href="/#privacidad">Privacidad</a></p>`;
    despuesDeIngresar = luego;
    if (!d.open) d.showModal();
    botonGoogle($('.gBtn', inn));
  }

  // Después del primer aviso: ofrecer también el resumen diario (una sola vez)
  function pantallaListo(texto) {
    const d = ventana(), inn = $('.dlgIn', d);
    const preguntar = S.usuario && !S.usuario.decidio;
    inn.innerHTML = `<div class="dlgOk" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg></div>
      <h2 id="cmcDlgT">Listo</h2><p>${texto}</p>
      ${preguntar ? `<label class="chk"><input type="checkbox" name="resumen"><span><b>También quiero el resumen diario</b> con las mayores bajadas de precio de todo el sitio (solo los días que haya).</span></label>` : ''}
      <button type="button" class="btnPri dlgFin">Entendido</button>
      <p class="dlgPriv">Cada correo trae un enlace para darte de baja. Puedes cambiarlo cuando quieras en <a href="/mi-cuenta">Mi cuenta</a>.</p>`;
    if (!d.open) d.showModal();
    $('.dlgFin', inn).addEventListener('click', async () => {
      const c = $('input[name=resumen]', inn);
      if (c) { try { await guardarResumen(c.checked); } catch (_) {} }
      d.close();
    });
    $('.dlgFin', inn).focus();
  }

  /* ---------- Botón "Avísame si baja de precio" ---------- */
  const sinStock = () => btnAv && btnAv.hasAttribute('data-sin');
  const textoAviso = a => a && a.precio && !sinStock()
    ? `Te escribiremos a <b>${esc(S.usuario.correo)}</b> si baja de <b>${fmt(a.precio)}</b>.`
    : `Te escribiremos a <b>${esc(S.usuario.correo)}</b> cuando vuelva a tener stock.`;
  function mensajeAviso(html, err) {
    if (!msgAv) return;
    msgAv.hidden = !html;
    msgAv.className = 'avisaMsg' + (err ? ' err' : '');
    msgAv.innerHTML = html;
  }
  function pintarAvisame() {
    if (!btnAv) return;
    btnAv.hidden = !S.activo;
    const on = !!(S.usuario && S.aviso);
    btnAv.classList.toggle('on', on);
    btnAv.setAttribute('aria-pressed', String(on));
    $('span', btnAv).textContent = on
      ? (S.aviso.precio && !sinStock() ? `Siguiendo: te avisamos si baja de ${fmt(S.aviso.precio)}` : 'Siguiendo: te avisamos cuando vuelva')
      : (sinStock() ? 'Avísame cuando vuelva a tener stock' : 'Avísame si baja de precio');
    btnAv.title = on ? 'Toca para dejar de seguir este equipo' : '';
  }
  async function seguir() {
    const d = await api('/api/avisos', { method: 'POST', body: JSON.stringify({ p: CLAVE, nombre: NOMBRE }) });
    S.aviso = d.aviso;
    pintarAvisame();
    return d.aviso;
  }
  if (btnAv) {
    oyentes.add(pintarAvisame);
    btnAv.addEventListener('click', async () => {
      mensajeAviso('');
      if (!S.usuario) {
        pedirIngreso(sinStock() ? 'Te avisamos cuando vuelva' : 'Te avisamos si baja de precio',
          `Inicia sesión con Google y te escribiremos ${sinStock() ? 'cuando el' : 'si el'} <b>${esc(NOMBRE)}</b> ${sinStock() ? 'vuelva a tener stock' : 'baja de precio'}. Solo por este equipo.`,
          async () => {
            try {
              const a = S.aviso || await seguir();
              pantallaListo(textoAviso(a));
            } catch (e) { errorIngreso(e.message); }
          });
        return;
      }
      btnAv.disabled = true;
      try {
        if (S.aviso) {
          await api('/api/avisos?p=' + encodeURIComponent(CLAVE), { method: 'DELETE' });
          S.aviso = null;
          mensajeAviso('Listo, ya no te avisaremos de este equipo.');
        } else {
          const a = await seguir();
          if (!S.usuario.decidio) pantallaListo(textoAviso(a));
          else mensajeAviso(`${textoAviso(a)} <a href="/mi-cuenta">Ver mis avisos</a>`);
        }
      } catch (e) { mensajeAviso(esc(e.message), true); }
      btnAv.disabled = false;
      pintarAvisame();
    });
  }

  /* ---------- Comentarios ---------- */
  const hace = iso => {
    const s = (Date.now() - Date.parse(iso)) / 1000;
    if (s < 60) return 'recién';
    if (s < 3600) return `hace ${Math.floor(s / 60)} min`;
    if (s < 86400) { const h = Math.floor(s / 3600); return `hace ${h} ${h === 1 ? 'hora' : 'horas'}`; }
    const d = Math.floor(s / 86400);
    if (d < 30) return `hace ${d} ${d === 1 ? 'día' : 'días'}`;
    return new Date(iso).toLocaleDateString('es-CL', { day: 'numeric', month: 'short', year: 'numeric' });
  };
  const fechaLarga = iso => new Date(iso).toLocaleString('es-CL', { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  const inicial = n => esc((String(n || '?').trim()[0] || '?').toUpperCase());
  const avatar = (foto, nombre, cls = 'comAv') =>
    `<span class="${cls}" aria-hidden="true"><span>${inicial(nombre)}</span>${foto ? `<img src="${esc(foto)}" alt="" width="40" height="40" loading="lazy" referrerpolicy="no-referrer">` : ''}</span>`;
  const sinFotoRota = raiz => raiz.querySelectorAll('.comAv img, .cuAv img').forEach(i => i.addEventListener('error', () => i.remove(), { once: true }));

  if (sec) {
    const app = $('.comApp', sec), cnt = $('.comN', sec);
    let lista = [], total = 0, mas = false, cargo = false, fallo = false;
    const BORR = 'cmc-borrador:' + CLAVE;
    const leerBorrador = () => { try { return localStorage.getItem(BORR) || ''; } catch (_) { return ''; } };
    const guardarBorrador = t => { try { t ? localStorage.setItem(BORR, t) : localStorage.removeItem(BORR); } catch (_) {} };

    app.innerHTML = `<div class="comArriba"></div><ol class="comLista" aria-label="Comentarios"></ol>
      <div class="comAbajo"><button type="button" class="btnSec comMas" hidden>Ver comentarios anteriores</button></div>
      <p class="comNormas">Comenta con respeto y sobre el equipo. Ocultamos insultos, publicidad y datos personales. <a href="/#privacidad">Normas y privacidad</a></p>`;
    const arriba = $('.comArriba', app), ol = $('.comLista', app), btnMas = $('.comMas', app);

    function item(c) {
      const admin = S.usuario && S.usuario.admin;
      return `<li class="comI${c.oculto ? ' oculto' : ''}" data-id="${c.id}">
        ${avatar(c.foto, c.nombre)}
        <div class="comC">
          <p class="comH"><b>${esc(c.nombre)}</b><time datetime="${esc(c.fecha)}" title="${esc(fechaLarga(c.fecha))}">${esc(hace(c.fecha))}</time>${c.oculto ? '<span class="comTag">Oculto: solo lo ves tú</span>' : ''}</p>
          <p class="comT">${esc(c.texto)}</p>
          ${c.mio || admin ? `<p class="comAcc">${admin ? `<button type="button" class="lnk" data-acc="${c.oculto ? 'mostrar' : 'ocultar'}">${c.oculto ? 'Mostrar' : 'Ocultar'}</button>` : ''}<button type="button" class="lnk" data-acc="borrar">Borrar</button></p>` : ''}
        </div></li>`;
    }
    function pintarLista() {
      cnt.textContent = total ? `(${total})` : '';
      if (fallo && !lista.length) {
        ol.innerHTML = '<li class="comVacio"><p>No pudimos cargar los comentarios.</p><button type="button" class="btnSec" data-reintentar>Intentar de nuevo</button></li>';
      } else if (!lista.length) {
        ol.innerHTML = `<li class="comVacio"><p><b>Todavía nadie comenta este equipo.</b> ¿Lo tienes o lo estás evaluando? Tu experiencia ayuda a otros a decidir.</p></li>`;
      } else {
        ol.innerHTML = lista.map(item).join('');
        sinFotoRota(ol);
      }
      btnMas.hidden = !mas;
    }
    function pintarArriba() {
      const u = S.usuario;
      if (!S.listo) { arriba.innerHTML = ''; return; }
      if (!S.activo) {
        // Mientras el inicio de sesión no esté configurado, la sección no se muestra (salvo que ya tenga comentarios)
        if (cargo && !total) sec.hidden = true;
        arriba.innerHTML = '<p class="comPronto">Por ahora no se pueden publicar comentarios nuevos.</p>';
        return;
      }
      sec.hidden = false;
      if (!u) {
        arriba.innerHTML = `<div class="comLogin">
          <div><p class="comLoginT">¿Qué te pareció este equipo?</p>
          <p class="comLoginS">Inicia sesión con Google para comentar. Mostramos tu nombre y tu foto; tu correo no se publica.</p></div>
          <div class="gBtn"></div><p class="loginErr" aria-live="polite"></p></div>`;
        verCuandoAparezca($('.gBtn', arriba));
        return;
      }
      if (u.bloqueado) {
        arriba.innerHTML = `<p class="comPronto">Tu cuenta no puede publicar comentarios. Si crees que es un error, escríbenos a adictosdigitalesla@gmail.com.</p>${yo(u)}`;
        return;
      }
      arriba.innerHTML = `${!u.decidio ? `<div class="comConsent" role="group" aria-labelledby="ccT">
          <p id="ccT"><b>¿Te avisamos por correo?</b> Elige qué quieres recibir en ${esc(u.correo)}. Puedes cambiarlo cuando quieras.</p>
          ${S.aviso ? '' : `<label class="chk"><input type="checkbox" name="este"><span>Avisarme si baja el precio de este equipo</span></label>`}
          <label class="chk"><input type="checkbox" name="resumen"><span>Resumen diario con las mayores bajadas de precio (solo los días que haya)</span></label>
          <div class="ccBtns"><button type="button" class="btnPri" data-cc="guardar">Guardar mi elección</button><button type="button" class="lnk" data-cc="no">Ahora no</button></div>
          <p class="ccMsg" aria-live="polite"></p></div>` : ''}
        <form class="comNuevo" novalidate>
          ${avatar(u.foto, u.nombre)}
          <div class="comCampo">
            <label for="comTxt">Tu comentario</label>
            <textarea id="comTxt" maxlength="1000" rows="3" placeholder="¿Lo compraste? ¿Qué te pareció, o qué duda tienes?"></textarea>
            <div class="comBar"><span class="comCnt">0/1000</span><button type="submit" class="btnPri comPub">Publicar comentario</button></div>
            <p class="comMsg" aria-live="polite"></p>
          </div>
        </form>${yo(u)}`;
      sinFotoRota(arriba);
      const ta = $('#comTxt', arriba), c = $('.comCnt', arriba), m = $('.comMsg', arriba), pub = $('.comPub', arriba);
      ta.value = leerBorrador();
      c.textContent = ta.value.length + '/1000';
      ta.addEventListener('input', () => { c.textContent = ta.value.length + '/1000'; guardarBorrador(ta.value); if (m.classList.contains('err')) { m.textContent = ''; m.className = 'comMsg'; } });
      $('form', arriba).addEventListener('submit', async e => {
        e.preventDefault();
        const t = ta.value.trim();
        if (t.length < 3) { m.className = 'comMsg err'; m.textContent = 'Escribe al menos unas palabras antes de publicar.'; ta.focus(); return; }
        if (pub.disabled) return;
        pub.disabled = true; pub.textContent = 'Publicando…'; m.textContent = ''; m.className = 'comMsg';
        try {
          const d = await api('/api/comentarios', { method: 'POST', body: JSON.stringify({ p: CLAVE, t }) });
          lista.unshift(d.comentario); total++;
          ta.value = ''; guardarBorrador(''); c.textContent = '0/1000';
          pintarLista();
          m.textContent = '¡Gracias! Tu comentario ya está publicado.';
        } catch (er) { m.className = 'comMsg err'; m.textContent = er.message; }
        pub.disabled = false; pub.textContent = 'Publicar comentario';
      });
    }
    const yo = u => `<p class="comYo">Comentas como <b>${esc(u.nombre)}</b> · <a href="/mi-cuenta">Mi cuenta y avisos</a> · <button type="button" class="lnk" data-salir>Cerrar sesión</button></p>`;

    // El botón de Google se carga solo cuando la sección está cerca de verse
    let io = null;
    function verCuandoAparezca(el) {
      if (!('IntersectionObserver' in window)) return botonGoogle(el);
      if (io) io.disconnect();
      io = new IntersectionObserver(es => es.forEach(x => {
        if (x.isIntersecting) { io.disconnect(); botonGoogle(el); }
      }), { rootMargin: '400px 0px' });
      io.observe(el);
    }

    async function cargar(antes) {
      try {
        const d = await api(`/api/comentarios?p=${encodeURIComponent(CLAVE)}${antes ? '&antes=' + antes : ''}`);
        lista = antes ? lista.concat(d.comentarios) : d.comentarios;
        total = d.total; mas = d.mas; fallo = false;
      } catch (_) { fallo = true; }
      const primera = !cargo;
      cargo = true;
      pintarLista();
      if (primera && S.listo && !S.activo) pintarArriba();
    }

    app.addEventListener('click', async e => {
      const b = e.target.closest('button');
      if (!b) return;
      if (b.hasAttribute('data-salir')) return salir();
      if (b.hasAttribute('data-reintentar')) { b.disabled = true; return cargar(); }
      if (b === btnMas) { b.disabled = true; b.textContent = 'Cargando…'; await cargar(lista[lista.length - 1].id); b.disabled = false; b.textContent = 'Ver comentarios anteriores'; return; }
      if (b.dataset.cc) {
        const box = b.closest('.comConsent'), msg = $('.ccMsg', box);
        b.disabled = true;
        try {
          const este = $('input[name=este]', box), res = $('input[name=resumen]', box);
          if (b.dataset.cc === 'guardar' && este && este.checked) await seguir();
          await guardarResumen(b.dataset.cc === 'guardar' && res.checked);
          pintarArriba();
          const mm = $('.comMsg', arriba);
          if (mm) mm.textContent = b.dataset.cc === 'guardar' ? 'Listo, guardamos tu elección. Puedes cambiarla en Mi cuenta.' : 'Entendido, no te enviaremos correos.';
        } catch (er) { msg.textContent = er.message; b.disabled = false; }
        return;
      }
      const li = b.closest('.comI');
      if (!li || !b.dataset.acc) return;
      const id = +li.dataset.id, acc = b.dataset.acc;
      if (acc === 'borrar' && !b.dataset.seguro) {
        // Confirmación con nombre: el segundo toque borra
        const acc2 = b.parentElement;
        acc2.dataset.antes = acc2.innerHTML;
        acc2.innerHTML = '<span class="comSeguro">¿Borrar este comentario?</span><button type="button" class="lnk peligro" data-acc="borrar" data-seguro="1">Sí, borrar comentario</button><button type="button" class="lnk" data-acc="cancelar">Cancelar</button>';
        $('[data-seguro]', acc2).focus();
        return;
      }
      if (acc === 'cancelar') { const p = b.parentElement; p.innerHTML = p.dataset.antes; return; }
      b.disabled = true;
      try {
        if (acc === 'borrar') {
          await api('/api/comentarios?id=' + id, { method: 'DELETE' });
          const c = lista.find(x => x.id === id);
          lista = lista.filter(x => x.id !== id);
          if (c && !c.oculto) total = Math.max(0, total - 1);
        } else {
          await api('/api/panel', { method: 'POST', body: JSON.stringify({ accion: acc, id }) });
          const c = lista.find(x => x.id === id);
          if (c) { c.oculto = acc === 'ocultar'; total += acc === 'ocultar' ? -1 : 1; }
        }
        pintarLista();
      } catch (er) { b.disabled = false; alert(er.message); }
    });

    oyentes.add(() => { pintarArriba(); if (cargo) pintarLista(); });
    cargar();
  }

  /* ---------- Página "Mi cuenta" ---------- */
  if (cuentaEl) {
    const app = $('.cuentaApp', cuentaEl);
    async function pintarCuenta() {
      if (!S.listo) return;
      if (!S.activo) { app.innerHTML = '<p class="comPronto">Las cuentas aún no están activas. Vuelve pronto.</p>'; return; }
      if (!S.usuario) {
        app.innerHTML = `<div class="comLogin"><div><p class="comLoginT">Inicia sesión para ver tus avisos</p>
          <p class="comLoginS">Aquí ves los equipos que sigues, eliges qué correos recibir y puedes borrar tu cuenta.</p></div>
          <div class="gBtn"></div><p class="loginErr" aria-live="polite"></p></div>`;
        botonGoogle($('.gBtn', app));
        return;
      }
      app.innerHTML = '<p class="comCarga">Cargando tu cuenta…</p>';
      let d;
      try { d = await api('/api/cuenta'); } catch (e) { app.innerHTML = `<p class="comPronto">${esc(e.message)}</p>`; return; }
      const u = d.usuario;
      const filas = d.avisos.map(a => `<li data-p="${esc(a.producto)}">
          <a class="cuEq" href="/${esc(a.producto)}">${esc(a.nombre)}</a>
          <span class="cuHoy">${a.hoy ? `Hoy <b>${fmt(a.hoy)}</b>${a.tienda ? ' en ' + esc(a.tienda) : ''}` : 'Sin stock hoy: te avisamos cuando vuelva'}</span>
          ${a.hoy && a.referencia ? `<span class="cuRef">Te avisamos si baja de ${fmt(a.referencia)}</span>` : ''}
          <button type="button" class="btnSec" data-dejar>Dejar de seguir</button></li>`).join('');
      app.innerHTML = `
        <div class="cuPerfil">${avatar(u.foto, u.nombre, 'cuAv')}<div><p class="cuNom">${esc(u.nombre)}</p><p class="cuCorreo">${esc(u.correo)}</p></div>
          <button type="button" class="btnSec" data-salir>Cerrar sesión</button></div>
        <section class="cuSec" aria-labelledby="cuT1"><h2 id="cuT1">Equipos que sigues</h2>
          ${filas ? `<ul class="cuLista">${filas}</ul>` : `<p class="cuVacio">Aún no sigues ningún equipo. En la ficha de cualquier equipo toca <b>«Avísame si baja de precio»</b> y te escribimos cuando baje.</p>
            <p><a class="btnPri" href="/notebooks">Ver notebooks</a> <a class="btnSec" href="/celulares">Ver celulares</a></p>`}
          <p class="cuMsg" aria-live="polite"></p></section>
        <section class="cuSec" aria-labelledby="cuT2"><h2 id="cuT2">Correos</h2>
          <label class="chk"><input type="checkbox" name="resumen"${u.resumen ? ' checked' : ''}><span><b>Resumen diario</b> con las mayores bajadas de precio de todo el sitio. Solo llega los días que hay bajadas.</span></label>
          <p class="cuMsg2" aria-live="polite"></p>
          <p class="nota">Los avisos de los equipos que sigues llegan solos cuando bajan. Cada correo trae un enlace para darte de baja.</p></section>
        <section class="cuSec" aria-labelledby="cuT3"><h2 id="cuT3">Borrar mi cuenta</h2>
          <p class="nota">Se borran tu nombre, tu correo, los equipos que sigues${d.comentarios === 1 ? ' y tu comentario' : d.comentarios ? ` y tus ${d.comentarios} comentarios` : ''}. No se puede deshacer.</p>
          <div class="cuBorrar"><button type="button" class="btnPeligro" data-borrar>Borrar mi cuenta</button></div></section>`;
      sinFotoRota(app);
    }
    app.addEventListener('click', async e => {
      const b = e.target.closest('button');
      if (!b) return;
      if (b.hasAttribute('data-salir')) return salir();
      if (b.hasAttribute('data-dejar')) {
        const li = b.closest('li');
        b.disabled = true;
        try {
          await api('/api/avisos?p=' + encodeURIComponent(li.dataset.p), { method: 'DELETE' });
          li.remove();
          $('.cuMsg', app).textContent = 'Listo, ya no sigues ese equipo.';
        } catch (er) { b.disabled = false; $('.cuMsg', app).textContent = er.message; }
        return;
      }
      if (b.hasAttribute('data-borrar')) {
        const box = b.parentElement;
        box.innerHTML = '<p><b>¿Seguro que quieres borrar tu cuenta?</b></p><button type="button" class="btnPeligro" data-borrar-si>Sí, borrar mi cuenta y mis comentarios</button> <button type="button" class="btnSec" data-cancelar>Cancelar</button>';
        $('[data-borrar-si]', box).focus();
        return;
      }
      if (b.hasAttribute('data-cancelar')) { b.parentElement.innerHTML = '<button type="button" class="btnPeligro" data-borrar>Borrar mi cuenta</button>'; return; }
      if (b.hasAttribute('data-borrar-si')) {
        b.disabled = true; b.textContent = 'Borrando…';
        try {
          await api('/api/cuenta', { method: 'DELETE' });
          try { if (window.google) google.accounts.id.disableAutoSelect(); } catch (_) {}
          S.usuario = null; S.aviso = null;
          app.innerHTML = '<div class="comLogin"><div><p class="comLoginT">Tu cuenta fue borrada</p><p class="comLoginS">Borramos tus datos, tus avisos y tus comentarios. Gracias por haber participado.</p></div><a class="btnPri" href="/">Volver al inicio</a></div>';
        } catch (er) { b.disabled = false; b.textContent = 'Sí, borrar mi cuenta y mis comentarios'; alert(er.message); }
      }
    });
    app.addEventListener('change', async e => {
      if (e.target.name !== 'resumen') return;
      const m = $('.cuMsg2', app);
      e.target.disabled = true;
      try {
        await guardarResumen(e.target.checked);
        m.textContent = e.target.checked ? 'Listo: te enviaremos el resumen los días que haya bajadas.' : 'Listo: no te enviaremos el resumen diario.';
      } catch (er) { e.target.checked = !e.target.checked; m.textContent = er.message; }
      e.target.disabled = false;
    });
    oyentes.add(pintarCuenta);
  }

  /* ---------- Arranque ---------- */
  window.cmcCuenta = {
    api, esc, fmt, botonGoogle, salir, alCambiar: f => { oyentes.add(f); if (S.listo) f(S); }, get estado() { return S; },
    // Solo funciona en el computador de pruebas (el servidor lo rechaza en el sitio publicado)
    probar: datos => api('/api/sesion', { method: 'POST', body: JSON.stringify({ prueba: datos, p: CLAVE }) }).then(ingresado)
  };
  api('/api/sesion' + (CLAVE ? '?p=' + encodeURIComponent(CLAVE) : ''))
    .then(d => { S = { ...S, ...d, listo: true }; })
    .catch(() => { S = { ...S, activo: false, listo: true }; })
    .finally(avisar);
})();
