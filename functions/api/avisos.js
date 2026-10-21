// "Avísame si baja de precio" (o cuando vuelva a tener stock) para un equipo.
// POST   /api/avisos {p}   -> empieza a seguir el precio. Se guarda el precio de hoy: avisamos si baja de ahí.
// DELETE /api/avisos?p=..  -> deja de seguirlo
import { json, error, preparar, usuarioActual, mismoOrigen, catalogo, ahora, limpiar, CLAVE_OK } from '../_comun.js';

const MAX_AVISOS = 60;

export async function onRequestPost({ request, env }) {
  if (!env.DB) return error(503, 'Los avisos aún no están activos.');
  if (!mismoOrigen(request)) return error(403, 'Origen no permitido.');
  const u = await usuarioActual(request, env);
  if (!u) return error(401, 'Inicia sesión con Google para recibir avisos.');
  let d;
  try { d = JSON.parse(await request.text()); } catch { return error(400, 'Formato inválido.'); }
  const p = String(d.p || '');
  if (!CLAVE_OK.test(p)) return error(400, 'Equipo inválido.');
  await preparar(env);

  const ya = await env.DB.prepare('SELECT precio, stock FROM avisos WHERE usuario = ?1 AND producto = ?2').bind(u.id, p).first();
  if (ya) return json({ aviso: { precio: ya.precio, stock: !!ya.stock } });
  const n = await env.DB.prepare('SELECT COUNT(*) AS n FROM avisos WHERE usuario = ?1').bind(u.id).first();
  if (n.n >= MAX_AVISOS) return error(429, `Puedes seguir hasta ${MAX_AVISOS} equipos. Deja de seguir alguno desde "Mi cuenta".`);

  // El precio de referencia sale del catálogo del sitio, no de lo que envía el navegador
  const eq = (await catalogo(env, request)).equipos[p];
  const precio = eq && eq[0] ? eq[0] : null;
  const nombre = limpiar(eq ? eq[1] : d.nombre, 140);
  await env.DB.prepare('INSERT INTO avisos (usuario, producto, nombre, precio, stock, creado) VALUES (?1, ?2, ?3, ?4, ?5, ?6) ON CONFLICT DO NOTHING')
    .bind(u.id, p, nombre, precio, precio ? 1 : 0, ahora()).run();
  return json({ aviso: { precio, stock: !!precio } }, 201);
}

export async function onRequestDelete({ request, env }) {
  if (!env.DB) return error(503, 'Los avisos aún no están activos.');
  if (!mismoOrigen(request)) return error(403, 'Origen no permitido.');
  const u = await usuarioActual(request, env);
  if (!u) return error(401, 'Inicia sesión para cambiar tus avisos.');
  const p = new URL(request.url).searchParams.get('p') || '';
  if (!CLAVE_OK.test(p)) return error(400, 'Equipo inválido.');
  await env.DB.prepare('DELETE FROM avisos WHERE usuario = ?1 AND producto = ?2').bind(u.id, p).run();
  return json({ ok: true });
}
