// Revisa los precios nuevos, arma los avisos y el resumen diario, y envía la cola de correos de a poco.
// POST /api/revisar-avisos  (lo llama el flujo .github/workflows/avisos.yml después de cada actualización de precios)
//
// Es seguro llamarlo varias veces: solo revisa cuando cambia assets/avisos.json (los precios) y cada aviso
// sale una sola vez por equipo y por día. Cada llamada envía como máximo 25 correos; el flujo repite
// mientras queden pendientes ("seguir": true).
import {
  json, preparar, usuarioActual, esAdmin, catalogo, leerAjuste, proveedor, limiteDiario, enviarCorreo, enlaceBaja,
  hoyChile, ahora, SITIO
} from '../_comun.js';
import { correoAviso, correoResumen, alternativas } from '../_correos.js';

const LOTE = 25;
const ajuste = (env, clave, valor) =>
  env.DB.prepare('INSERT INTO ajustes (clave, valor) VALUES (?1, ?2) ON CONFLICT (clave) DO UPDATE SET valor = excluded.valor').bind(clave, String(valor));

async function enLotes(env, sentencias) {
  for (let i = 0; i < sentencias.length; i += 50) await env.DB.batch(sentencias.slice(i, i + 50));
}

// Resumen diario a los suscritos: una vez al día, apenas se publica la revisión de precios que hace Claude
// (pedido del dueño, 19-11-2026; antes salía desde las 10:00). Solo con los precios de hoy y si hubo bajadas.
// Precio de cada ficha en el momento del resumen (los equipos sin stock no se guardan)
const fotoPrecios = (env, eqs) => ajuste(env, 'resumen_precios',
  JSON.stringify(Object.fromEntries(Object.entries(eqs).filter(([, e]) => e && e[0]).map(([clave, e]) => [clave, e[0]]))));
// Desde el 17-11-2026 (precios cada 2 horas) compara con los precios del último resumen enviado, no con los de ayer:
// así entra todo lo que bajó en las 24 horas entre un resumen y el siguiente, también lo que bajó en la tarde.
// La primera vez (sin foto guardada) usa las bajadas del día de assets/avisos.json.
async function resumenDiario(env, cat, eqs, sitio, t, cola) {
  const fotoTxt = await leerAjuste(env, 'resumen_precios');
  let foto = null;
  try { foto = fotoTxt ? JSON.parse(fotoTxt) : null; } catch (_) { foto = null; }
  const pares = foto
    ? Object.entries(foto).map(([clave, antes]) => [clave, antes, eqs[clave] && eqs[clave][0]])
      .filter(([, antes, ahoraP]) => antes && ahoraP && ahoraP <= antes * 0.97 && antes - ahoraP >= 3000 && ahoraP >= antes * 0.4)
      .sort((a, b) => (b[1] - b[2]) / b[1] - (a[1] - a[2]) / a[1])
    : (cat.bajadas || []);
  const bajadas = pares.map(([clave, antes]) => {
    const e = eqs[clave];
    return e && e[0] && { clave, nombre: e[1], id: e[2], tienda: e[3], antes, ahora: e[0], motivo: 'bajo' };
  }).filter(x => x && x.ahora < x.antes).slice(0, 10);
  const yaSalio = (await leerAjuste(env, 'resumen_dia')) === cat.dia;
  // Sin foto y con el resumen de hoy ya enviado (el primer día con este cambio): se guarda la foto ahora
  if (yaSalio && !foto && cat.dia === hoyChile()) return { resumenes: 0, bajadas, foto: fotoPrecios(env, eqs) };
  if (!bajadas.length || cat.dia !== hoyChile() || yaSalio)
    return { resumenes: 0, bajadas };
  const subs = (await env.DB.prepare('SELECT id, correo, nombre FROM usuarios WHERE resumen = 1 AND bloqueado = 0').all()).results;
  for (const s of subs) {
    const baja = await enlaceBaja(env, s.id);
    const c = correoResumen({ sitio, persona: s.nombre, correo: s.correo, items: bajadas, baja, dia: cat.dia });
    cola.push(env.DB.prepare('INSERT INTO correos (usuario, para, tipo, asunto, html, texto, baja, creado) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)')
      .bind(s.id, s.correo, 'resumen', c.asunto, c.html, c.texto, baja, t));
  }
  return { resumenes: subs.length, bajadas, marca: ajuste(env, 'resumen_dia', cat.dia), foto: fotoPrecios(env, eqs) };
}

async function revisar(env, request, forzar) {
  const cat = await catalogo(env, request, true);
  if (!cat.v) return { motivo: 'sin catálogo de precios' };
  // Se "toma" la versión de precios de una sola vez, para que dos llamadas seguidas no dupliquen los correos
  const toma = await env.DB.prepare(`INSERT INTO ajustes (clave, valor) VALUES ('revision_v', ?1)
    ON CONFLICT (clave) DO UPDATE SET valor = excluded.valor WHERE ajustes.valor != excluded.valor`).bind(cat.v).run();
  if (!toma.meta.changes && !forzar) {
    // Aunque los precios no hayan cambiado, el resumen diario puede tocar ahora (sale desde las 10:00 de Chile)
    const cola = [], r = await resumenDiario(env, cat, cat.equipos || {}, env.SITIO || SITIO, ahora(), cola);
    const extra = [r.marca, r.foto].filter(Boolean);
    if (extra.length) await enLotes(env, [...extra, ...cola]);
    return { motivo: 'los precios no han cambiado desde la última revisión', resumenes: r.resumenes, bajadas_del_dia: r.bajadas.length };
  }
  const sitio = env.SITIO || SITIO, dia = hoyChile(), t = ahora();
  const eqs = cat.equipos || {};
  const cambios = [], cola = [];

  // 1) Equipos que cada persona sigue: bajó desde el precio que vio, o volvió a tener stock
  const filas = (await env.DB.prepare(`SELECT a.usuario, a.producto, a.nombre, a.precio, a.stock, a.avisado, u.correo, u.nombre AS persona
    FROM avisos a JOIN usuarios u ON u.id = a.usuario WHERE u.bloqueado = 0`).all()).results;
  const porPersona = new Map();
  for (const a of filas) {
    const e = eqs[a.producto];
    const hoy = e ? e[0] : null;
    if (hoy == null) {
      if (a.stock) cambios.push(env.DB.prepare('UPDATE avisos SET stock = 0 WHERE usuario = ?1 AND producto = ?2').bind(a.usuario, a.producto));
      continue;
    }
    if (a.stock && a.precio == null) {
      cambios.push(env.DB.prepare('UPDATE avisos SET precio = ?3 WHERE usuario = ?1 AND producto = ?2').bind(a.usuario, a.producto, hoy));
      continue;
    }
    // Baja que vale la pena avisar: al menos 2% y $2.000 bajo el precio de referencia
    const motivo = !a.stock ? 'volvio' : hoy <= a.precio - Math.max(2000, a.precio * 0.02) ? 'bajo' : null;
    if (!motivo || a.avisado === dia) continue;
    if (!porPersona.has(a.usuario)) porPersona.set(a.usuario, { correo: a.correo, persona: a.persona, items: [] });
    porPersona.get(a.usuario).items.push({ clave: a.producto, nombre: e[1] || a.nombre, id: e[2], tienda: e[3], antes: a.precio, ahora: hoy, motivo });
    cambios.push(env.DB.prepare('UPDATE avisos SET precio = ?3, stock = 1, avisado = ?4 WHERE usuario = ?1 AND producto = ?2').bind(a.usuario, a.producto, hoy, dia));
  }
  const sigue = new Map();
  for (const a of filas) (sigue.get(a.usuario) || sigue.set(a.usuario, new Set()).get(a.usuario)).add(a.producto);
  for (const [uid, x] of porPersona) {
    const baja = await enlaceBaja(env, uid);
    const items = x.items.slice(0, 12);
    const extras = alternativas(eqs, items, sigue.get(uid));
    const c = correoAviso({ sitio, persona: x.persona, correo: x.correo, items, extras, baja });
    cola.push(env.DB.prepare('INSERT INTO correos (usuario, para, tipo, asunto, html, texto, baja, creado) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)')
      .bind(uid, x.correo, 'aviso', c.asunto, c.html, c.texto, baja, t));
  }

  // 2) Resumen diario (ver resumenDiario)
  const r = await resumenDiario(env, cat, eqs, sitio, t, cola);
  if (r.marca) cambios.push(r.marca);
  if (r.foto) cambios.push(r.foto);
  const resumenes = r.resumenes, bajadas = r.bajadas;

  // 3) Limpieza: correos enviados hace más de 30 días y contadores viejos
  cambios.push(env.DB.prepare("DELETE FROM correos WHERE enviado != '' AND creado < ?1").bind(new Date(Date.now() - 30 * 864e5).toISOString()));
  cambios.push(env.DB.prepare("DELETE FROM ajustes WHERE clave LIKE 'enviados:%' AND clave < ?1").bind('enviados:' + hoyChile(new Date(Date.now() - 14 * 864e5))));
  cambios.push(ajuste(env, 'revision_hora', t));
  await enLotes(env, [...cambios, ...cola]);
  return { avisos: porPersona.size, resumenes, bajadas_del_dia: bajadas.length };
}

async function enviarCola(env) {
  const prov = proveedor(env);
  const pendientes = async () => (await env.DB.prepare("SELECT COUNT(*) AS n FROM correos WHERE enviado = ''").first()).n;
  const dia = hoyChile();
  const ya = +((await leerAjuste(env, 'enviados:' + dia)) || 0);
  const cupo = Math.min(LOTE, limiteDiario(env) - ya);
  if (cupo <= 0) return { enviados: 0, pendientes: await pendientes(), seguir: false, nota: 'Se llegó al límite diario de correos: el resto sale mañana.' };
  const lote = (await env.DB.prepare("SELECT id, para, asunto, html, texto, baja FROM correos WHERE enviado = '' ORDER BY (tipo = 'resumen'), id LIMIT ?1")
    .bind(cupo).all()).results;
  let enviados = 0, fallos = 0, ultimoError = '';
  const marcas = [];
  for (const c of lote) {
    try {
      await enviarCorreo(env, c);
      enviados++;
      marcas.push(env.DB.prepare('UPDATE correos SET enviado = ?2 WHERE id = ?1').bind(c.id, ahora()));
    } catch (e) {
      fallos++; ultimoError = String(e.message || e).slice(0, 300);
      // Tres intentos fallidos y el correo se descarta (queda marcado como "fallido")
      marcas.push(env.DB.prepare("UPDATE correos SET intentos = intentos + 1, error = ?2, enviado = CASE WHEN intentos + 1 >= 3 THEN 'fallido' ELSE '' END WHERE id = ?1")
        .bind(c.id, ultimoError));
      if (fallos >= 3) break;
    }
  }
  if (enviados) marcas.push(ajuste(env, 'enviados:' + dia, ya + enviados));
  if (marcas.length) await env.DB.batch(marcas);
  const quedan = await pendientes();
  return { enviados, fallos, error: ultimoError || undefined, pendientes: quedan, seguir: quedan > 0 && fallos < 3 && enviados > 0 };
}

export async function onRequestPost({ request, env }) {
  if (!env.DB) return json({ ok: false, motivo: 'la base de datos no está enlazada' }, 503);
  await preparar(env);
  if (!proveedor(env)) return json({ ok: false, motivo: 'falta configurar el envío de correos (BREVO_API_KEY o RESEND_API_KEY)', seguir: false });
  const forzar = new URL(request.url).searchParams.has('forzar') && esAdmin(env, await usuarioActual(request, env));
  const revision = await revisar(env, request, forzar);
  const envio = await enviarCola(env);
  return json({ ok: true, proveedor: proveedor(env), revision, ...envio });
}
