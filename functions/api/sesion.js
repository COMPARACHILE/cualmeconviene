// Inicio de sesión con Google, solo para comentar y pedir avisos de precio.
// GET    /api/sesion[?p=notebook/xxx]  -> quién está conectado (y si sigue el precio de ese equipo)
// POST   /api/sesion {credential}      -> verifica el token de Google y abre la sesión (cookie propia)
// DELETE /api/sesion                   -> cierra la sesión
import {
  json, error, clientId, preparar, usuarioActual, publico, cookieSesion, cookieBorrar, verificarGoogle,
  nombreVisible, fotoSegura, idNuevo, ahora, mismoOrigen, CLAVE_OK, limpiar
} from '../_comun.js';

async function avisoDe(env, u, p) {
  if (!u || !CLAVE_OK.test(p || '')) return null;
  const a = await env.DB.prepare('SELECT precio, stock FROM avisos WHERE usuario = ?1 AND producto = ?2').bind(u.id, p).first();
  return a ? { precio: a.precio, stock: !!a.stock } : null;
}

export async function onRequestGet({ request, env }) {
  const cid = clientId(env);
  if (!env.DB) return json({ activo: false, clientId: cid, usuario: null });
  const u = await usuarioActual(request, env);
  const p = new URL(request.url).searchParams.get('p');
  const datos = { activo: !!cid, clientId: cid, usuario: publico(env, u), aviso: await avisoDe(env, u, p) };
  // Cada visita renueva la sesión por 180 días más
  return json(datos, 200, u ? { 'Set-Cookie': await cookieSesion(env, u.id) } : {});
}

export async function onRequestPost({ request, env }) {
  if (!env.DB) return error(503, 'Los comentarios aún no están activos.');
  if (!mismoOrigen(request)) return error(403, 'Origen no permitido.');
  const cid = clientId(env);
  const texto = await request.text();
  if (texto.length > 6000) return error(413, 'Demasiado largo.');
  let d;
  try { d = JSON.parse(texto); } catch { return error(400, 'Formato inválido.'); }

  let g;
  const host = new URL(request.url).hostname;
  if (env.PRUEBA_LOGIN === '1' && (host === 'localhost' || host === '127.0.0.1') && d.prueba) {
    // Solo en el computador, para probar sin Google
    g = { sub: 'prueba-' + limpiar(d.prueba.sub, 20), email: limpiar(d.prueba.email, 120), given_name: limpiar(d.prueba.nombre, 30), family_name: limpiar(d.prueba.apellido, 30) };
  } else {
    if (!cid) return error(503, 'El inicio de sesión aún no está configurado.');
    try { g = await verificarGoogle(d.credential, cid); } catch (e) { return error(401, 'No pudimos confirmar tu cuenta de Google. Inténtalo de nuevo.'); }
  }

  await preparar(env);
  const correo = String(g.email).toLowerCase().slice(0, 254);
  const nombre = nombreVisible(g), foto = fotoSegura(g.picture);
  let u = await env.DB.prepare('SELECT * FROM usuarios WHERE google = ?1').bind(String(g.sub)).first();
  let nuevo = false;
  if (u) {
    await env.DB.prepare('UPDATE usuarios SET correo = ?2, nombre = ?3, foto = ?4, ultimo = ?5 WHERE id = ?1')
      .bind(u.id, correo, nombre, foto, ahora()).run();
    u = { ...u, correo, nombre, foto };
  } else {
    nuevo = true;
    const id = idNuevo(), t = ahora();
    await env.DB.prepare('INSERT INTO usuarios (id, google, correo, nombre, foto, creado, ultimo) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?6)')
      .bind(id, String(g.sub), correo, nombre, foto, t).run();
    u = { id, correo, nombre, foto, resumen: 0, consentimiento: '', bloqueado: 0 };
  }
  const p = typeof d.p === 'string' ? d.p : '';
  return json({ usuario: publico(env, u), nuevo, aviso: await avisoDe(env, u, p) }, 200, { 'Set-Cookie': await cookieSesion(env, u.id) });
}

export async function onRequestDelete({ request }) {
  if (!mismoOrigen(request)) return error(403, 'Origen no permitido.');
  return json({ ok: true }, 200, { 'Set-Cookie': cookieBorrar() });
}
