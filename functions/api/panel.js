// Panel de administración (/panel): moderar comentarios, ver la base de correos y descargarla.
// Solo entra quien inicia sesión con una cuenta administradora (ver ADMINS en functions/_comun.js).
// GET  /api/panel          -> números, últimos comentarios y personas registradas
// GET  /api/panel?csv=1    -> descarga la base de personas (para Excel)
// POST /api/panel {accion, id}  -> ocultar / mostrar / borrar comentario, bloquear / desbloquear persona
import { json, error, preparar, usuarioActual, esAdmin, mismoOrigen, proveedor, limiteDiario, leerAjuste, hoyChile } from '../_comun.js';

async function admin(request, env) {
  if (!env.DB) return [null, error(503, 'La base de datos no está enlazada al sitio.')];
  const u = await usuarioActual(request, env);
  if (!u) return [null, error(401, 'Inicia sesión con la cuenta administradora.')];
  if (!esAdmin(env, u)) return [null, error(403, 'Esta cuenta no administra el sitio.')];
  await preparar(env);
  return [u, null];
}

const csvCampo = v => {
  let s = String(v ?? '');
  if (/^[=+\-@]/.test(s)) s = "'" + s; // evita fórmulas al abrirlo en Excel
  return /[";\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
};

export async function onRequestGet({ request, env }) {
  const [, falla] = await admin(request, env);
  if (falla) return falla;
  const q = new URL(request.url).searchParams;

  if (q.get('csv')) {
    const filas = (await env.DB.prepare(`SELECT u.correo, u.nombre, u.creado, u.ultimo, u.resumen, u.consentimiento, u.bloqueado,
      (SELECT COUNT(*) FROM avisos a WHERE a.usuario = u.id) AS avisos,
      (SELECT COUNT(*) FROM comentarios c WHERE c.usuario = u.id) AS comentarios
      FROM usuarios u ORDER BY u.creado`).all()).results;
    const cab = ['Correo', 'Nombre', 'Registro', 'Último ingreso', 'Acepta resumen diario', 'Registro del consentimiento', 'Equipos que sigue', 'Comentarios', 'Bloqueado'];
    const lineas = [cab.join(';'), ...filas.map(f => [f.correo, f.nombre, f.creado.slice(0, 10), f.ultimo.slice(0, 10), f.resumen ? 'Sí' : 'No',
      f.consentimiento, f.avisos, f.comentarios, f.bloqueado ? 'Sí' : 'No'].map(csvCampo).join(';'))];
    return new Response('﻿' + lineas.join('\r\n'), {
      headers: { 'Content-Type': 'text/csv; charset=utf-8', 'Content-Disposition': `attachment; filename="cualmeconviene-personas-${hoyChile()}.csv"`, 'Cache-Control': 'no-store' }
    });
  }

  const dia = hoyChile();
  const [nums, coms, pers, pop] = await env.DB.batch([
    env.DB.prepare(`SELECT (SELECT COUNT(*) FROM usuarios) AS personas, (SELECT COUNT(*) FROM usuarios WHERE resumen = 1) AS resumen,
      (SELECT COUNT(*) FROM avisos) AS avisos, (SELECT COUNT(DISTINCT usuario) FROM avisos) AS siguen,
      (SELECT COUNT(*) FROM comentarios WHERE oculto = 0) AS comentarios, (SELECT COUNT(*) FROM comentarios WHERE oculto = 1) AS ocultos,
      (SELECT COUNT(*) FROM correos WHERE enviado = '') AS pendientes, (SELECT COUNT(*) FROM correos WHERE enviado = 'fallido') AS fallidos`),
    env.DB.prepare(`SELECT c.id, c.producto, c.texto, c.creado, c.oculto, u.id AS uid, u.nombre, u.correo, u.bloqueado
      FROM comentarios c JOIN usuarios u ON u.id = c.usuario ORDER BY c.id DESC LIMIT 150`),
    env.DB.prepare(`SELECT u.id, u.nombre, u.correo, u.creado, u.ultimo, u.resumen, u.bloqueado,
      (SELECT COUNT(*) FROM avisos a WHERE a.usuario = u.id) AS avisos,
      (SELECT COUNT(*) FROM comentarios c WHERE c.usuario = u.id) AS comentarios
      FROM usuarios u ORDER BY u.creado DESC LIMIT 300`),
    env.DB.prepare('SELECT producto, MAX(nombre) AS nombre, COUNT(*) AS n FROM avisos GROUP BY producto ORDER BY n DESC LIMIT 15'),
  ]);
  return json({
    numeros: nums.results[0],
    correo: {
      proveedor: proveedor(env), limite: limiteDiario(env), enviadosHoy: +((await leerAjuste(env, 'enviados:' + dia)) || 0),
      ultimaRevision: await leerAjuste(env, 'revision_hora'), ultimoResumen: await leerAjuste(env, 'resumen_dia'),
      ultimoError: (await env.DB.prepare("SELECT error FROM correos WHERE error != '' ORDER BY id DESC LIMIT 1").first())?.error || ''
    },
    comentarios: coms.results, personas: pers.results, masSeguidos: pop.results
  });
}

export async function onRequestPost({ request, env }) {
  const [, falla] = await admin(request, env);
  if (falla) return falla;
  if (!mismoOrigen(request)) return error(403, 'Origen no permitido.');
  let d;
  try { d = JSON.parse(await request.text()); } catch { return error(400, 'Formato inválido.'); }
  const id = d.id;
  const sql = {
    ocultar: ['UPDATE comentarios SET oculto = 1 WHERE id = ?1', +id],
    mostrar: ['UPDATE comentarios SET oculto = 0 WHERE id = ?1', +id],
    borrar: ['DELETE FROM comentarios WHERE id = ?1', +id],
    bloquear: ['UPDATE usuarios SET bloqueado = 1 WHERE id = ?1', String(id)],
    desbloquear: ['UPDATE usuarios SET bloqueado = 0 WHERE id = ?1', String(id)],
  }[d.accion];
  if (!sql || !id) return error(400, 'Acción inválida.');
  const r = await env.DB.prepare(sql[0]).bind(sql[1]).run();
  if (d.accion === 'bloquear') await env.DB.prepare('UPDATE comentarios SET oculto = 1 WHERE usuario = ?1').bind(String(id)).run();
  return json({ ok: !!r.meta.changes });
}
