// Darse de baja de todos los correos con un clic (enlace al pie de cada correo).
// GET  /api/baja?u=..&t=..  -> página para confirmar (así los antivirus que abren enlaces no dan de baja a nadie)
// POST /api/baja?u=..&t=..  -> da de baja: sin resumen diario y sin avisos de equipos. La cuenta y los comentarios siguen.
import { preparar, firmaValida } from '../_comun.js';

const pagina = (titulo, cuerpo, estado = 200) => new Response(`<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex"><title>${titulo} | ¿Cuál me conviene?</title>
<link rel="icon" href="/assets/puma-icono-48.png" type="image/png">
<style>
:root{color-scheme:light dark}
body{margin:0;min-height:100vh;display:grid;place-items:center;background:#F3F5FA;color:#10152B;font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif;padding:16px}
main{max-width:440px;width:100%;background:#fff;border:1px solid #DCE1EE;border-radius:18px;padding:28px 24px;text-align:center}
img{width:72px;height:72px;border-radius:50%}
h1{font-size:1.4rem;line-height:1.2;margin:14px 0 8px}
p{margin:0 0 12px;color:#566082}
button,a.b{display:inline-flex;align-items:center;justify-content:center;min-height:48px;padding:0 20px;border:0;border-radius:12px;background:#10152B;color:#fff;font:700 16px system-ui,sans-serif;cursor:pointer;text-decoration:none;margin-top:6px}
a{color:#2E57FF;font-weight:600}
@media (prefers-color-scheme:dark){body{background:#0A0F24;color:#EAEEFF}main{background:#131A36;border-color:#283160}p{color:#9DA6CC}button,a.b{background:#FFD84D;color:#2A2100}a{color:#7F99FF}}
</style></head><body><main><img src="/assets/puma-icono-192.png" alt=""><h1>${titulo}</h1>${cuerpo}</main></body></html>`,
  { status: estado, headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store', 'X-Robots-Tag': 'noindex' } });

async function valido(request, env) {
  const q = new URL(request.url).searchParams;
  const u = q.get('u') || '', t = q.get('t') || '';
  if (!env.DB || !/^[A-Za-z0-9_-]{8,40}$/.test(u) || !(await firmaValida(env, 'b:' + u, t))) return null;
  return u;
}

export async function onRequestGet({ request, env }) {
  if (!(await valido(request, env))) return pagina('Enlace no válido', '<p>Este enlace no funciona o está incompleto. Puedes elegir tus correos desde <a href="/mi-cuenta">Mi cuenta</a>.</p>', 400);
  return pagina('¿Dejar de recibir correos?', `<p>Ya no te enviaremos el resumen diario ni avisos de precio. Tu cuenta y tus comentarios siguen igual.</p>
<form method="post"><button type="submit">Sí, no quiero más correos</button></form>
<p style="margin-top:14px"><a href="/mi-cuenta">Prefiero elegir qué correos recibir</a></p>`);
}

export async function onRequestPost({ request, env }) {
  const u = await valido(request, env);
  if (!u) return pagina('Enlace no válido', '<p>Este enlace no funciona o está incompleto. Puedes elegir tus correos desde <a href="/mi-cuenta">Mi cuenta</a>.</p>', 400);
  await preparar(env);
  await env.DB.batch([
    env.DB.prepare("UPDATE usuarios SET resumen = 0, consentimiento = ?2 WHERE id = ?1").bind(u, 'se dio de baja desde el correo · ' + new Date().toISOString()),
    env.DB.prepare('DELETE FROM avisos WHERE usuario = ?1').bind(u),
    env.DB.prepare("DELETE FROM correos WHERE usuario = ?1 AND enviado = ''").bind(u),
  ]);
  return pagina('Listo, no te escribiremos más', '<p>Te diste de baja de todos los correos. Si cambias de opinión, puedes volver a pedir avisos en la ficha de cualquier equipo.</p><a class="b" href="/">Volver a ¿Cuál me conviene?</a>');
}
