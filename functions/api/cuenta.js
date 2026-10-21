// "Mi cuenta": equipos que sigues, resumen diario por correo y borrar la cuenta.
// GET    /api/cuenta                 -> datos de la persona y sus avisos con el precio de hoy
// POST   /api/cuenta {resumen: bool} -> acepta o deja de recibir el resumen diario de bajadas
// DELETE /api/cuenta                 -> borra la cuenta, sus avisos y sus comentarios
import { json, error, preparar, usuarioActual, publico, mismoOrigen, catalogo, ahora, cookieBorrar } from '../_comun.js';

export async function onRequestGet({ request, env }) {
  if (!env.DB) return error(503, 'Las cuentas aún no están activas.');
  const u = await usuarioActual(request, env);
  if (!u) return error(401, 'Inicia sesión para ver tu cuenta.');
  const [av, com] = await env.DB.batch([
    env.DB.prepare('SELECT producto, nombre, precio, stock, creado FROM avisos WHERE usuario = ?1 ORDER BY creado DESC').bind(u.id),
    env.DB.prepare('SELECT COUNT(*) AS n FROM comentarios WHERE usuario = ?1').bind(u.id),
  ]);
  const eqs = (await catalogo(env, request)).equipos;
  const avisos = av.results.map(a => {
    const e = eqs[a.producto];
    return { producto: a.producto, nombre: (e && e[1]) || a.nombre, referencia: a.precio, hoy: e ? e[0] : null, tienda: e ? e[3] : '', id: e ? e[2] : '' };
  });
  return json({ usuario: publico(env, u), avisos, comentarios: com.results[0].n });
}

export async function onRequestPost({ request, env }) {
  if (!env.DB) return error(503, 'Las cuentas aún no están activas.');
  if (!mismoOrigen(request)) return error(403, 'Origen no permitido.');
  const u = await usuarioActual(request, env);
  if (!u) return error(401, 'Inicia sesión para cambiar tus correos.');
  let d;
  try { d = JSON.parse(await request.text()); } catch { return error(400, 'Formato inválido.'); }
  const resumen = d.resumen === true ? 1 : 0;
  // Queda registro de qué eligió y cuándo (prueba del consentimiento)
  const registro = `${resumen ? 'acepta' : 'no acepta'} resumen diario · ${ahora()}`;
  await env.DB.prepare('UPDATE usuarios SET resumen = ?2, consentimiento = ?3 WHERE id = ?1').bind(u.id, resumen, registro).run();
  return json({ usuario: publico(env, { ...u, resumen, consentimiento: registro }) });
}

export async function onRequestDelete({ request, env }) {
  if (!env.DB) return error(503, 'Las cuentas aún no están activas.');
  if (!mismoOrigen(request)) return error(403, 'Origen no permitido.');
  const u = await usuarioActual(request, env);
  if (!u) return error(401, 'Inicia sesión para borrar tu cuenta.');
  await preparar(env);
  await env.DB.batch([
    env.DB.prepare('DELETE FROM comentarios WHERE usuario = ?1').bind(u.id),
    env.DB.prepare('DELETE FROM avisos WHERE usuario = ?1').bind(u.id),
    env.DB.prepare("DELETE FROM correos WHERE usuario = ?1 AND enviado = ''").bind(u.id),
    env.DB.prepare('DELETE FROM usuarios WHERE id = ?1').bind(u.id),
  ]);
  return json({ ok: true }, 200, { 'Set-Cookie': cookieBorrar() });
}
