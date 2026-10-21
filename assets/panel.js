/* ¿Cuál me conviene? — Panel de administración (/panel). Usa la sesión de assets/comentarios.js.
   Moderar comentarios, ver quiénes aceptaron correos, descargar la base y revisar el envío de avisos. */
(() => {
  const app = document.querySelector('.panelApp');
  if (!app || !window.cmcCuenta) return;
  const { api, esc, botonGoogle, salir } = window.cmcCuenta;
  const fecha = iso => iso ? new Date(iso).toLocaleString('es-CL', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—';
  const dia = iso => iso ? new Date(iso).toLocaleDateString('es-CL', { day: 'numeric', month: 'short', year: 'numeric' }) : '—';
  const PROV = { brevo: 'Brevo', resend: 'Resend', consola: 'Prueba (consola)', '': 'Sin configurar' };

  async function pintar(S) {
    if (!S.listo) return;
    if (!S.usuario) {
      app.innerHTML = `<div class="comLogin"><div><p class="comLoginT">Entra con la cuenta administradora</p>
        <p class="comLoginS">Solo las cuentas autorizadas ven este panel.</p></div><div class="gBtn"></div><p class="loginErr" aria-live="polite"></p></div>`;
      if (S.activo) botonGoogle(app.querySelector('.gBtn'));
      else app.querySelector('.gBtn').innerHTML = '<p class="loginErr">Falta configurar el inicio de sesión con Google (GOOGLE_CLIENT_ID).</p>';
      return;
    }
    if (!S.usuario.admin) {
      app.innerHTML = `<p class="comPronto">La cuenta ${esc(S.usuario.correo)} no administra el sitio. <button type="button" class="lnk" data-salir>Cerrar sesión</button></p>`;
      return;
    }
    app.innerHTML = '<p class="comCarga">Cargando datos…</p>';
    let d;
    try { d = await api('/api/panel'); } catch (e) { app.innerHTML = `<p class="comPronto">${esc(e.message)}</p>`; return; }
    const n = d.numeros, c = d.correo;
    app.innerHTML = `
      <div class="pnNums">
        <div><b>${n.personas}</b><span>personas con cuenta</span></div>
        <div><b>${n.resumen}</b><span>aceptan el resumen diario</span></div>
        <div><b>${n.siguen}</b><span>siguen equipos (${n.avisos} avisos)</span></div>
        <div><b>${n.comentarios}</b><span>comentarios visibles${n.ocultos ? ` · ${n.ocultos} ocultos` : ''}</span></div>
      </div>
      <p class="pnAcc"><a class="btnPri" href="/api/panel?csv=1">Descargar la base de correos (Excel)</a>
        <button type="button" class="btnSec" data-revisar>Revisar avisos ahora</button>
        <button type="button" class="lnk" data-salir>Cerrar sesión (${esc(S.usuario.correo)})</button></p>
      <p class="pnMsg" aria-live="polite"></p>
      <section class="cuSec"><h2>Envío de correos</h2>
        <dl class="tec pnDl">
          <div><dt>Servicio</dt><dd>${esc(PROV[c.proveedor] || c.proveedor)}</dd></div>
          <div><dt>Enviados hoy</dt><dd>${c.enviadosHoy} de ${c.limite}</dd></div>
          <div><dt>Pendientes</dt><dd>${n.pendientes}${n.fallidos ? ` · ${n.fallidos} fallidos` : ''}</dd></div>
          <div><dt>Última revisión</dt><dd>${fecha(c.ultimaRevision)}</dd></div>
          <div><dt>Último resumen</dt><dd>${esc(c.ultimoResumen || '—')}</dd></div>
          ${c.ultimoError ? `<div><dt>Último error</dt><dd>${esc(c.ultimoError)}</dd></div>` : ''}
        </dl></section>
      ${d.masSeguidos.length ? `<section class="cuSec"><h2>Equipos más seguidos</h2><ol class="cuLista pnSimple">${d.masSeguidos.map(m => `<li><a class="cuEq" href="/${esc(m.producto)}">${esc(m.nombre || m.producto)}</a><span class="cuHoy">${m.n} ${m.n === 1 ? 'persona' : 'personas'}</span></li>`).join('')}</ol></section>` : ''}
      <section class="cuSec"><h2>Últimos comentarios</h2>
        ${d.comentarios.length ? `<ol class="comLista pnComs">${d.comentarios.map(k => `<li class="comI${k.oculto ? ' oculto' : ''}" data-id="${k.id}" data-u="${esc(k.uid)}">
          <span class="comAv" aria-hidden="true"><span>${esc((k.nombre || '?')[0])}</span></span>
          <div class="comC"><p class="comH"><b>${esc(k.nombre)}</b><span class="pnCorreo">${esc(k.correo)}</span><time>${fecha(k.creado)}</time>${k.oculto ? '<span class="comTag">Oculto</span>' : ''}${k.bloqueado ? '<span class="comTag">Cuenta bloqueada</span>' : ''}</p>
          <p class="pnProd"><a href="/${esc(k.producto)}#comentarios">${esc(k.producto.split('/')[1])}</a></p>
          <p class="comT">${esc(k.texto)}</p>
          <p class="comAcc"><button type="button" class="lnk" data-acc="${k.oculto ? 'mostrar' : 'ocultar'}">${k.oculto ? 'Mostrar' : 'Ocultar'}</button>
          <button type="button" class="lnk peligro" data-acc="borrar">Borrar</button>
          <button type="button" class="lnk peligro" data-acc="${k.bloqueado ? 'desbloquear' : 'bloquear'}">${k.bloqueado ? 'Desbloquear persona' : 'Bloquear persona'}</button></p></div></li>`).join('')}</ol>` : '<p class="cuVacio">Todavía no hay comentarios.</p>'}
      </section>
      <section class="cuSec"><h2>Personas registradas</h2>
        ${d.personas.length ? `<div class="pnTablaW"><table class="pnTabla"><thead><tr><th>Nombre</th><th>Correo</th><th>Registro</th><th>Resumen</th><th>Sigue</th><th>Coment.</th><th></th></tr></thead><tbody>
          ${d.personas.map(p => `<tr data-u="${esc(p.id)}"><td>${esc(p.nombre)}</td><td>${esc(p.correo)}</td><td>${dia(p.creado)}</td><td>${p.resumen ? 'Sí' : 'No'}</td><td>${p.avisos}</td><td>${p.comentarios}</td>
          <td><button type="button" class="lnk peligro" data-acc="${p.bloqueado ? 'desbloquear' : 'bloquear'}">${p.bloqueado ? 'Desbloquear' : 'Bloquear'}</button></td></tr>`).join('')}
        </tbody></table></div>` : '<p class="cuVacio">Todavía nadie ha creado una cuenta.</p>'}
      </section>`;
  }

  app.addEventListener('click', async e => {
    const b = e.target.closest('button');
    if (!b) return;
    if (b.hasAttribute('data-salir')) return salir();
    const msg = app.querySelector('.pnMsg');
    if (b.hasAttribute('data-revisar')) {
      b.disabled = true; b.textContent = 'Revisando…';
      try {
        const r = await api('/api/revisar-avisos?forzar=1', { method: 'POST' });
        msg.textContent = r.ok ? `Listo: ${r.revision && r.revision.avisos != null ? `${r.revision.avisos} avisos y ${r.revision.resumenes} resúmenes en cola. ` : ''}Enviados ahora: ${r.enviados}. Pendientes: ${r.pendientes}.${r.error ? ' Error: ' + r.error : ''}` : r.motivo;
      } catch (er) { msg.textContent = er.message; }
      b.disabled = false; b.textContent = 'Revisar avisos ahora';
      return;
    }
    const acc = b.dataset.acc;
    if (!acc) return;
    const fila = b.closest('[data-u]');
    const id = ['bloquear', 'desbloquear'].includes(acc) ? fila.dataset.u : +b.closest('[data-id]').dataset.id;
    if ((acc === 'borrar' || acc === 'bloquear') && !b.dataset.seguro) {
      b.dataset.seguro = '1';
      b.textContent = acc === 'borrar' ? 'Toca otra vez para borrar el comentario' : 'Toca otra vez para bloquear y ocultar sus comentarios';
      return;
    }
    b.disabled = true;
    try {
      await api('/api/panel', { method: 'POST', body: JSON.stringify({ accion: acc, id }) });
      pintar(window.cmcCuenta.estado);
    } catch (er) { b.disabled = false; msg.textContent = er.message; }
  });

  window.cmcCuenta.alCambiar(pintar);
})();
