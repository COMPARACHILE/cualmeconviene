// Comentarios de cada equipo. Se guardan con la dirección fija de la ficha (ej. notebook/acer-aspire-14),
// así que no se pierden si el equipo se agota y vuelve a publicarse.
// GET    /api/comentarios?p=<ficha>[&antes=<id>]  -> los últimos 30 (más nuevos primero)
// POST   /api/comentarios {p, t}                  -> publica (hay que iniciar sesión con Google)
// DELETE /api/comentarios?id=<id>                 -> borra un comentario propio (o cualquiera, si administras)
import { json, error, preparar, usuarioActual, esAdmin, mismoOrigen, limpiar, ahora, CLAVE_OK } from '../_comun.js';

const POR_PAGINA = 30;
const MAX_TEXTO = 1000;

export async function onRequestGet({ request, env }) {
  const q = new URL(request.url).searchParams;
  const p = q.get('p') || '';
  if (!CLAVE_OK.test(p)) return error(400, 'Equipo inválido.');
  if (!env.DB) return json({ total: 0, comentarios: [], mas: false });
  await preparar(env);
  const u = await usuarioActual(request, env);
  const admin = esAdmin(env, u);
  const antes = Math.max(0, parseInt(q.get('antes') || '0', 10)) || 9e15;
  const [filas, cuenta] = await env.DB.batch([
    env.DB.prepare(`SELECT c.id, c.texto, c.creado, c.oculto, c.usuario, u.nombre, u.foto
      FROM comentarios c JOIN usuarios u ON u.id = c.usuario
      WHERE c.producto = ?1 AND c.id < ?2 AND (c.oculto = 0 OR ?3 = 1 OR c.usuario = ?4)
      ORDER BY c.id DESC LIMIT ?5`).bind(p, antes, admin ? 1 : 0, u ? u.id : '', POR_PAGINA + 1),
    env.DB.prepare('SELECT COUNT(*) AS n FROM comentarios WHERE producto = ?1 AND oculto = 0').bind(p),
  ]);
  const lista = filas.results.slice(0, POR_PAGINA).map(c => ({
    id: c.id, nombre: c.nombre, foto: c.foto, texto: c.texto, fecha: c.creado,
    mio: !!u && c.usuario === u.id, oculto: !!c.oculto
  }));
  return json({ total: cuenta.results[0].n, comentarios: lista, mas: filas.results.length > POR_PAGINA });
}

export async function onRequestPost({ request, env }) {
  if (!env.DB) return error(503, 'Los comentarios aún no están activos.');
  if (!mismoOrigen(request)) return error(403, 'Origen no permitido.');
  const u = await usuarioActual(request, env);
  if (!u) return error(401, 'Inicia sesión con Google para comentar.');
  if (u.bloqueado) return error(403, 'Tu cuenta no puede publicar comentarios. Si crees que es un error, escríbenos.');
  const cuerpo = await request.text();
  if (cuerpo.length > 8000) return error(413, 'El comentario es demasiado largo.');
  let d;
  try { d = JSON.parse(cuerpo); } catch { return error(400, 'Formato inválido.'); }
  const p = String(d.p || '');
  if (!CLAVE_OK.test(p)) return error(400, 'Equipo inválido.');
  const texto = limpiar(d.t, MAX_TEXTO);
  if (texto.length < 3) return error(400, 'Escribe al menos unas palabras.');

  // Freno contra spam: un comentario cada 20 segundos, 20 al día y sin repetir el mismo texto
  const hace20s = new Date(Date.now() - 20e3).toISOString(), hace1d = new Date(Date.now() - 864e5).toISOString();
  const [reciente, delDia, repetido] = await env.DB.batch([
    env.DB.prepare('SELECT COUNT(*) AS n FROM comentarios WHERE usuario = ?1 AND creado > ?2').bind(u.id, hace20s),
    env.DB.prepare('SELECT COUNT(*) AS n FROM comentarios WHERE usuario = ?1 AND creado > ?2').bind(u.id, hace1d),
    env.DB.prepare('SELECT COUNT(*) AS n FROM comentarios WHERE usuario = ?1 AND producto = ?2 AND texto = ?3').bind(u.id, p, texto),
  ]);
  if (reciente.results[0].n) return error(429, 'Espera unos segundos antes de publicar otro comentario.');
  if (delDia.results[0].n >= 20) return error(429, 'Llegaste al máximo de comentarios por hoy. Vuelve mañana.');
  if (repetido.results[0].n) return error(409, 'Ya publicaste ese mismo comentario.');

  const creado = ahora();
  const r = await env.DB.prepare('INSERT INTO comentarios (producto, usuario, texto, creado) VALUES (?1, ?2, ?3, ?4)')
    .bind(p, u.id, texto, creado).run();
  return json({ comentario: { id: r.meta.last_row_id, nombre: u.nombre, foto: u.foto, texto, fecha: creado, mio: true, oculto: false } }, 201);
}

export async function onRequestDelete({ request, env }) {
  if (!env.DB) return error(503, 'Los comentarios aún no están activos.');
  if (!mismoOrigen(request)) return error(403, 'Origen no permitido.');
  const u = await usuarioActual(request, env);
  if (!u) return error(401, 'Inicia sesión para borrar tu comentario.');
  const id = parseInt(new URL(request.url).searchParams.get('id') || '', 10);
  if (!id) return error(400, 'Comentario inválido.');
  const r = esAdmin(env, u)
    ? await env.DB.prepare('DELETE FROM comentarios WHERE id = ?1').bind(id).run()
    : await env.DB.prepare('DELETE FROM comentarios WHERE id = ?1 AND usuario = ?2').bind(id, u.id).run();
  if (!r.meta.changes) return error(404, 'Ese comentario ya no existe o no es tuyo.');
  return json({ ok: true });
}
