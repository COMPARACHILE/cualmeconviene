// Envía al correo de la página el resumen de la actualización diaria de precios.
// POST /api/resumen-precios  (lo llama .github/workflows/precios-diarios.yml cuando Cloudflare ya publicó)
// Lee /assets/resumen-precios.json (lo arma herramientas/resumen.py) y lo envía una sola vez por versión,
// así que es seguro llamarlo de más. Solo envía a la cuenta de la página (CONTACTO o RESUMEN_PARA).
import { json, preparar, leerAjuste, guardarAjuste, enviarCorreo, proveedor, CONTACTO } from '../_comun.js';

export async function onRequestPost({ request, env }) {
  await preparar(env);
  const r = await env.ASSETS.fetch(new URL('/assets/resumen-precios.json', request.url).toString());
  if (!r.ok) return json({ enviado: false, motivo: 'no hay resumen' });
  const res = await r.json();
  if (!res.v) return json({ enviado: false, motivo: 'resumen sin versión' });
  if ((await leerAjuste(env, 'resumen_precios_v')) === res.v) return json({ enviado: false, motivo: 'ya enviado' });
  if (!proveedor(env)) return json({ enviado: false, motivo: 'falta configurar el envío de correos' });
  const para = String(env.RESUMEN_PARA || CONTACTO).split(',').map(s => s.trim()).filter(Boolean);
  try {
    for (const p of para) await enviarCorreo(env, { para: p, asunto: res.asunto, html: res.html, texto: res.texto });
  } catch (e) {
    return json({ enviado: false, motivo: String(e && e.message || e).slice(0, 300) });
  }
  await guardarAjuste(env, 'resumen_precios_v', res.v);  // solo después de enviar: si falla, se reintenta
  return json({ enviado: true, v: res.v });
}
