// Piezas compartidas de cuentas, comentarios y avisos de precio de ¿Cuál me conviene?
// No es una ruta de la página (no exporta onRequest): las funciones de /functions/api la importan.
// Todo se guarda en la misma base D1 del contador de clics (variable DB). Las tablas se crean solas.

// ID de cliente de Google para "Continuar con Google". Es público (va en la página), no es una clave secreta.
// También se puede poner en Cloudflare como variable GOOGLE_CLIENT_ID (tiene prioridad sobre este valor).
export const GOOGLE_CLIENT_ID = '459759295645-cvcuqh31lo7bd05svkje37uk6bdm4sjd.apps.googleusercontent.com';

// Cuentas que pueden moderar comentarios y abrir /panel. Se suman otras con la variable ADMIN_CORREOS (separadas por coma).
const ADMINS = ['adictosdigitalesla@gmail.com'];

export const SITIO = 'https://cualmeconviene.cl';
export const CONTACTO = 'adictosdigitalesla@gmail.com';

// Dirección fija de la ficha de cada equipo (ej. notebook/acer-aspire-14). Comentarios y avisos se atan a ella,
// así que siguen ahí aunque el equipo se agote y vuelva.
export const CLAVE_OK = /^(notebook|celular|tablet|televisor|consola|lavadora|aspiradora|batidora|cafetera|aire-acondicionado)\/[a-z0-9-]{2,100}$/;

export const hoyChile = (d = new Date()) => new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Santiago' }).format(d);
export const ahora = () => new Date().toISOString();
export const plata = n => '$' + Math.round(n).toLocaleString('es-CL').replace(/,/g, '.');

export function json(data, status = 200, headers = {}) {
  return new Response(JSON.stringify(data), {
    status, headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store', ...headers }
  });
}
export const error = (status, mensaje, extra = {}) => json({ error: mensaje, ...extra }, status);

export const clientId = env => String(env.GOOGLE_CLIENT_ID || GOOGLE_CLIENT_ID || '').trim();

export function esAdmin(env, u) {
  if (!u) return false;
  const extra = String(env.ADMIN_CORREOS || '').split(',').map(s => s.trim().toLowerCase()).filter(Boolean);
  return [...ADMINS, ...extra].includes(String(u.correo || '').toLowerCase());
}

// Solo aceptamos cambios que vienen desde la misma página (protege contra formularios de otros sitios)
export function mismoOrigen(request) {
  const o = request.headers.get('Origin');
  if (!o) return true;
  try { return new URL(o).host === new URL(request.url).host; } catch { return false; }
}

// Texto que escribe la persona: sin caracteres de control ni saltos de línea de más
export function limpiar(t, max) {
  return String(t ?? '')
    .replace(/\r\n?/g, '\n')
    .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f‪-‮⁦-⁩]/g, '')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
    .slice(0, max);
}

// ---------------- Base de datos ----------------
const TABLAS = [
  // Personas que iniciaron sesión con Google
  `CREATE TABLE IF NOT EXISTS usuarios (
    id TEXT PRIMARY KEY, google TEXT NOT NULL UNIQUE, correo TEXT NOT NULL, nombre TEXT NOT NULL DEFAULT '',
    foto TEXT NOT NULL DEFAULT '', creado TEXT NOT NULL, ultimo TEXT NOT NULL,
    resumen INTEGER NOT NULL DEFAULT 0, consentimiento TEXT NOT NULL DEFAULT '', bloqueado INTEGER NOT NULL DEFAULT 0)`,
  // Comentarios de cada equipo (producto = dirección fija de la ficha)
  `CREATE TABLE IF NOT EXISTS comentarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT, producto TEXT NOT NULL, usuario TEXT NOT NULL, texto TEXT NOT NULL,
    creado TEXT NOT NULL, oculto INTEGER NOT NULL DEFAULT 0)`,
  'CREATE INDEX IF NOT EXISTS comentarios_producto ON comentarios (producto, id)',
  'CREATE INDEX IF NOT EXISTS comentarios_usuario ON comentarios (usuario, creado)',
  // Equipos que cada persona sigue: precio = el que vio al pedir el aviso (o el del último aviso)
  `CREATE TABLE IF NOT EXISTS avisos (
    usuario TEXT NOT NULL, producto TEXT NOT NULL, nombre TEXT NOT NULL DEFAULT '', precio INTEGER,
    stock INTEGER NOT NULL DEFAULT 1, creado TEXT NOT NULL, avisado TEXT NOT NULL DEFAULT '', PRIMARY KEY (usuario, producto))`,
  'CREATE INDEX IF NOT EXISTS avisos_producto ON avisos (producto)',
  // Cola de correos por enviar
  `CREATE TABLE IF NOT EXISTS correos (
    id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT NOT NULL, para TEXT NOT NULL, tipo TEXT NOT NULL,
    asunto TEXT NOT NULL, html TEXT NOT NULL, texto TEXT NOT NULL, baja TEXT NOT NULL DEFAULT '',
    creado TEXT NOT NULL, enviado TEXT NOT NULL DEFAULT '', intentos INTEGER NOT NULL DEFAULT 0, error TEXT NOT NULL DEFAULT '')`,
  'CREATE INDEX IF NOT EXISTS correos_pendientes ON correos (enviado, id)',
  'CREATE TABLE IF NOT EXISTS ajustes (clave TEXT PRIMARY KEY, valor TEXT NOT NULL)',
];
let preparada = false;
export async function preparar(env) {
  if (preparada) return;
  await env.DB.batch(TABLAS.map(s => env.DB.prepare(s)));
  preparada = true;
}
export async function leerAjuste(env, clave) {
  const r = await env.DB.prepare('SELECT valor FROM ajustes WHERE clave = ?1').bind(clave).first();
  return r ? r.valor : null;
}
export const guardarAjuste = (env, clave, valor) =>
  env.DB.prepare('INSERT INTO ajustes (clave, valor) VALUES (?1, ?2) ON CONFLICT (clave) DO UPDATE SET valor = excluded.valor').bind(clave, String(valor)).run();

// ---------------- Firmas (sesión y enlaces para darse de baja) ----------------
const enc = new TextEncoder();
export function b64url(bytes) {
  let s = '';
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
export function desdeB64url(t) {
  t = String(t).replace(/-/g, '+').replace(/_/g, '/');
  while (t.length % 4) t += '=';
  return Uint8Array.from(atob(t), c => c.charCodeAt(0));
}
export const idNuevo = () => b64url(crypto.getRandomValues(new Uint8Array(12)));

// La clave secreta se crea sola la primera vez y queda en la base (o se fija con la variable SESION_SECRETO)
let claveMem = null;
async function claveHmac(env) {
  if (claveMem) return claveMem;
  let s = env.SESION_SECRETO;
  if (!s) {
    await preparar(env);
    s = await leerAjuste(env, 'secreto');
    if (!s) {
      await env.DB.prepare("INSERT OR IGNORE INTO ajustes (clave, valor) VALUES ('secreto', ?1)").bind(b64url(crypto.getRandomValues(new Uint8Array(32)))).run();
      s = await leerAjuste(env, 'secreto');
    }
  }
  claveMem = await crypto.subtle.importKey('raw', enc.encode(s), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign', 'verify']);
  return claveMem;
}
export async function firmar(env, texto) {
  return b64url(new Uint8Array(await crypto.subtle.sign('HMAC', await claveHmac(env), enc.encode(texto))));
}
export async function firmaValida(env, texto, firma) {
  try { return await crypto.subtle.verify('HMAC', await claveHmac(env), desdeB64url(firma), enc.encode(texto)); } catch { return false; }
}

// ---------------- Sesión ----------------
const COOKIE = 'cmc_s';
const DURACION = 180 * 86400; // 180 días
export async function cookieSesion(env, uid) {
  const exp = Math.floor(Date.now() / 1000) + DURACION;
  const v = `${uid}.${exp}`;
  return `${COOKIE}=${v}.${await firmar(env, 's:' + v)}; Path=/; Max-Age=${DURACION}; HttpOnly; Secure; SameSite=Lax`;
}
export const cookieBorrar = () => `${COOKIE}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax`;

export async function usuarioActual(request, env) {
  if (!env.DB) return null;
  const m = (request.headers.get('Cookie') || '').match(/(?:^|;\s*)cmc_s=([A-Za-z0-9_-]{8,40})\.(\d{9,11})\.([A-Za-z0-9_-]{20,})/);
  if (!m) return null;
  const [, uid, exp, firma] = m;
  if (+exp < Date.now() / 1000) return null;
  if (!(await firmaValida(env, `s:${uid}.${exp}`, firma))) return null;
  await preparar(env);
  return (await env.DB.prepare('SELECT * FROM usuarios WHERE id = ?1').bind(uid).first()) || null;
}

// Lo que la página puede saber de la persona conectada (solo ella ve su propio correo)
export const publico = (env, u) => u && ({
  nombre: u.nombre, foto: u.foto, correo: u.correo, resumen: !!u.resumen,
  decidio: !!u.consentimiento, bloqueado: !!u.bloqueado, admin: esAdmin(env, u)
});

// ---------------- Inicio de sesión con Google ----------------
// Se verifica la firma del token con las claves públicas de Google: no se confía en lo que diga el navegador.
let jwks = null, jwksHasta = 0;
async function clavesGoogle(forzar) {
  if (!forzar && jwks && Date.now() < jwksHasta) return jwks;
  const r = await fetch('https://www.googleapis.com/oauth2/v3/certs');
  if (!r.ok) throw new Error('No se pudieron leer las claves de Google');
  const edad = /max-age=(\d+)/.exec(r.headers.get('cache-control') || '');
  jwks = (await r.json()).keys || [];
  jwksHasta = Date.now() + (edad ? Math.min(+edad[1], 86400) * 1000 : 3600e3);
  return jwks;
}
const parte = t => JSON.parse(new TextDecoder().decode(desdeB64url(t)));

export async function verificarGoogle(credential, aud) {
  const partes = String(credential || '').split('.');
  if (partes.length !== 3) throw new Error('token');
  const [h, p, s] = partes;
  const cab = parte(h), datos = parte(p);
  if (cab.alg !== 'RS256') throw new Error('alg');
  let jwk = (await clavesGoogle()).find(k => k.kid === cab.kid);
  if (!jwk) jwk = (await clavesGoogle(true)).find(k => k.kid === cab.kid);
  if (!jwk) throw new Error('kid');
  const clave = await crypto.subtle.importKey('jwk', { kty: jwk.kty, n: jwk.n, e: jwk.e, alg: 'RS256', ext: true },
    { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' }, false, ['verify']);
  const ok = await crypto.subtle.verify('RSASSA-PKCS1-v1_5', clave, desdeB64url(s), enc.encode(h + '.' + p));
  if (!ok) throw new Error('firma');
  const t = Date.now() / 1000;
  if (!['accounts.google.com', 'https://accounts.google.com'].includes(datos.iss)) throw new Error('iss');
  if (datos.aud !== aud) throw new Error('aud');
  if (!(datos.exp > t - 30) || (datos.iat && datos.iat > t + 300)) throw new Error('exp');
  if (!datos.sub || !datos.email || datos.email_verified === false || datos.email_verified === 'false') throw new Error('correo');
  return datos;
}

// "Javiera Pérez" -> "Javiera P." (nombre e inicial del apellido)
export function nombreVisible(d) {
  const nom = limpiar(d.given_name || '', 30), ape = limpiar(d.family_name || '', 30);
  const t = nom ? (ape ? `${nom} ${ape[0].toUpperCase()}.` : nom) : limpiar(d.name || String(d.email).split('@')[0], 40);
  return t.replace(/[<>]/g, '').slice(0, 40) || 'Usuario';
}
export const fotoSegura = u => (/^https:\/\/lh\d\.googleusercontent\.com\/[\w\-./=?&%]+$/.test(u || '') ? u : '');

// ---------------- Catálogo: precio de hoy de cada equipo ----------------
// assets/avisos.json lo genera herramientas/fichas.py: {v, dia, equipos: {clave: [precio|null, nombre, id, tienda]}, bajadas}
let catMem = null, catHasta = 0;
export async function catalogo(env, request, fresco = false) {
  if (!fresco && catMem && Date.now() < catHasta) return catMem;
  try {
    const r = await env.ASSETS.fetch(new URL('/assets/avisos.json', request.url).toString());
    if (r.ok) { catMem = await r.json(); catHasta = Date.now() + 120e3; }
  } catch (_) { /* sin catálogo: los avisos esperan a la próxima revisión */ }
  return catMem || { v: '', dia: '', equipos: {}, bajadas: [] };
}

// ---------------- Correo ----------------
// Brevo (300 correos diarios gratis) o Resend (100 diarios gratis). Basta con poner la clave en Cloudflare.
export function proveedor(env) {
  if (env.BREVO_API_KEY) return 'brevo';
  if (env.RESEND_API_KEY) return 'resend';
  if (env.CORREO_CONSOLA === '1') return 'consola'; // solo para pruebas en el computador
  return '';
}
export const limiteDiario = env => +env.CORREOS_POR_DIA || (env.BREVO_API_KEY ? 290 : env.RESEND_API_KEY ? 95 : 1000);

export async function enviarCorreo(env, c) {
  const desde = env.CORREO_REMITENTE || 'avisos@cualmeconviene.cl';
  const nombre = '¿Cuál me conviene?';
  const headers = c.baja ? { 'List-Unsubscribe': `<${c.baja}>`, 'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click' } : {};
  const p = proveedor(env);
  if (p === 'brevo') {
    const r = await fetch('https://api.brevo.com/v3/smtp/email', {
      method: 'POST',
      headers: { 'api-key': env.BREVO_API_KEY, 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ sender: { name: nombre, email: desde }, to: [{ email: c.para }], replyTo: { email: CONTACTO },
        subject: c.asunto, htmlContent: c.html, textContent: c.texto, headers })
    });
    if (!r.ok) throw new Error(`Brevo ${r.status}: ${(await r.text()).slice(0, 180)}`);
  } else if (p === 'resend') {
    const r = await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: { Authorization: 'Bearer ' + env.RESEND_API_KEY, 'Content-Type': 'application/json' },
      body: JSON.stringify({ from: `${nombre} <${desde}>`, to: [c.para], reply_to: CONTACTO, subject: c.asunto, html: c.html, text: c.texto, headers })
    });
    if (!r.ok) throw new Error(`Resend ${r.status}: ${(await r.text()).slice(0, 180)}`);
  } else if (p === 'consola') {
    console.log('CORREO', JSON.stringify({ para: c.para, asunto: c.asunto, texto: c.texto }));
  } else {
    throw new Error('Falta configurar el envío de correos');
  }
}

export async function enlaceBaja(env, uid) {
  return `${env.SITIO || SITIO}/api/baja?u=${encodeURIComponent(uid)}&t=${await firmar(env, 'b:' + uid)}`;
}
