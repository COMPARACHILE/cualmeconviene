// Cuenta clics hacia las tiendas: suma 1 por día, equipo y tienda.
// No guarda IP, cookies ni nada que identifique a la persona.
// Necesita una base D1 enlazada al proyecto de Pages con el nombre de variable DB (ver CONTADOR.md).

const TIENDAS = new Set(['falabella', 'paris', 'ripley', 'pcfactory']);
const ID_OK = /^[a-z]{1,4}\d{1,5}$/;

function hoyChile() {
  // Fecha local de Chile en formato AAAA-MM-DD
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Santiago' }).format(new Date());
}

export async function onRequestPost({ request, env }) {
  if (!env.DB) return new Response(null, { status: 204 });

  const texto = await request.text();
  if (texto.length > 600) return new Response(null, { status: 413 });

  let datos;
  try { datos = JSON.parse(texto); } catch { return new Response(null, { status: 400 }); }

  const equipo = String(datos.id || '');
  const tienda = String(datos.s || '');
  const nombre = String(datos.n || '').replace(/[\u0000-\u001f<>]/g, '').slice(0, 120);
  if (!ID_OK.test(equipo) || !TIENDAS.has(tienda)) return new Response(null, { status: 400 });

  await env.DB.prepare(
    `INSERT INTO clics (dia, equipo, tienda, nombre, n) VALUES (?1, ?2, ?3, ?4, 1)
     ON CONFLICT (dia, equipo, tienda) DO UPDATE SET n = n + 1, nombre = excluded.nombre`
  ).bind(hoyChile(), equipo, tienda, nombre).run();

  return new Response(null, { status: 204, headers: { 'Cache-Control': 'no-store' } });
}
