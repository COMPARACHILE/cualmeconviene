// Guarda las opiniones del botón "¿Qué te parece?": voto (me gustó / no), texto y página.
// No guarda IP, cookies ni nada que identifique a la persona.
// Usa la misma base D1 del contador de clics (variable DB). Tabla: ver schema.sql.

const PAGINAS = new Set(['/', '/index', '/notebooks', '/celulares']);

function hoyChile() {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Santiago' }).format(new Date());
}

export async function onRequestPost({ request, env }) {
  if (!env.DB) return new Response(null, { status: 204 });

  const texto = await request.text();
  if (texto.length > 2000) return new Response(null, { status: 413 });

  let d;
  try { d = JSON.parse(texto); } catch { return new Response(null, { status: 400 }); }

  // Campo trampa: los bots lo llenan, las personas no lo ven
  if (d.w) return new Response(null, { status: 204 });

  const voto = d.v === 1 ? 1 : d.v === -1 ? -1 : 0;
  const msg = String(d.t || '').replace(/[\u0000-\u0008\u000b-\u001f<>]/g, '').trim().slice(0, 600);
  const pagina = PAGINAS.has(String(d.p)) ? String(d.p) : 'otra';
  if (!voto && msg.length < 3) return new Response(null, { status: 400 });

  // La tabla se crea sola la primera vez (no hace falta abrir la consola de D1)
  await env.DB.prepare(
    `CREATE TABLE IF NOT EXISTS opiniones (id INTEGER PRIMARY KEY AUTOINCREMENT, dia TEXT NOT NULL,
      pagina TEXT NOT NULL, voto INTEGER NOT NULL DEFAULT 0, texto TEXT NOT NULL DEFAULT '')`
  ).run();

  await env.DB.prepare(
    'INSERT INTO opiniones (dia, pagina, voto, texto) VALUES (?1, ?2, ?3, ?4)'
  ).bind(hoyChile(), pagina, voto, msg).run();

  return new Response(null, { status: 204, headers: { 'Cache-Control': 'no-store' } });
}
