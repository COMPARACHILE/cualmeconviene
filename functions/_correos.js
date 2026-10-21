// Plantillas de los correos de avisos de precio y del resumen diario. Sin imágenes de seguimiento ni rastreo de clics.
import { plata } from './_comun.js';

const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
export const fechaLarga = dia => { const [, m, d] = String(dia).split('-').map(Number); return d ? `${d} de ${MESES[m - 1]}` : ''; };
const corto = (t, n) => (t.length > n ? t.slice(0, n - 1).trimEnd() + '…' : t);

function fila(sitio, it) {
  const url = `${sitio}/${it.clave}`;
  const foto = it.id ? `${sitio}/assets/p/${encodeURIComponent(it.id)}.webp` : `${sitio}/assets/puma-icono-192.png`;
  const baja = it.antes && it.ahora && it.antes > it.ahora;
  const pct = baja ? Math.round((it.antes - it.ahora) / it.antes * 100) : 0;
  const etiqueta = it.motivo === 'volvio'
    ? '<span style="display:inline-block;background:#E2E8FF;color:#2E57FF;font-weight:700;font-size:13px;padding:3px 9px;border-radius:8px">Volvió a tener stock</span>'
    : `<span style="display:inline-block;background:#DDF5EA;color:#0B7F57;font-weight:700;font-size:13px;padding:3px 9px;border-radius:8px">Bajó ${plata(it.antes - it.ahora)} (−${pct}%)</span>`;
  return `<tr><td style="padding:14px 0;border-top:1px solid #DCE1EE">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
<td width="76" valign="top" style="padding-right:14px"><a href="${esc(url)}"><img src="${esc(foto)}" width="72" height="72" alt="" style="display:block;width:72px;height:72px;object-fit:contain;border:1px solid #DCE1EE;border-radius:12px;background:#fff"></a></td>
<td valign="top" style="font-family:Arial,Helvetica,sans-serif;color:#10152B">
<a href="${esc(url)}" style="color:#10152B;font-weight:700;font-size:16px;line-height:1.3;text-decoration:none">${esc(it.nombre)}</a><br>
<div style="margin:6px 0">${etiqueta}</div>
${baja ? `<span style="color:#566082;font-size:14px;text-decoration:line-through">${plata(it.antes)}</span>&nbsp; ` : ''}<span style="color:#0B7F57;font-weight:800;font-size:20px">${plata(it.ahora)}</span>${it.tienda ? `<span style="color:#566082;font-size:14px"> en ${esc(it.tienda)}</span>` : ''}<br>
<a href="${esc(url)}" style="display:inline-block;margin-top:10px;background:#FFD84D;color:#2A2100;font-weight:700;font-size:14px;text-decoration:none;padding:9px 16px;border-radius:10px">Ver precios en cada tienda</a>
</td></tr></table></td></tr>`;
}

function marco({ sitio, titulo, intro, filas, correo, motivo, baja }) {
  return `<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${esc(titulo)}</title></head>
<body style="margin:0;padding:0;background:#F3F5FA">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F3F5FA"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#FFFFFF;border:1px solid #DCE1EE;border-radius:18px;overflow:hidden">
<tr><td style="background:#0E1533;padding:16px 22px"><a href="${esc(sitio)}" style="text-decoration:none;font-family:Arial,Helvetica,sans-serif;font-weight:800;font-size:19px;color:#FFD84D"><img src="${esc(sitio)}/assets/puma-icono-96.png" width="32" height="32" alt="" style="vertical-align:middle;border-radius:50%;margin-right:8px">¿Cuál me conviene?</a></td></tr>
<tr><td style="padding:22px 22px 6px;font-family:Arial,Helvetica,sans-serif;color:#10152B">
<h1 style="margin:0;font-size:22px;line-height:1.25">${esc(titulo)}</h1>
<p style="margin:8px 0 6px;font-size:15px;line-height:1.5;color:#566082">${intro}</p>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">${filas}</table>
<p style="margin:14px 0 18px;font-size:13px;line-height:1.5;color:#566082">Los precios son referenciales y salen de la revisión diaria de las tiendas. Confirma el precio final en la tienda antes de pagar.</p>
</td></tr>
<tr><td style="padding:16px 22px;background:#ECEFF7;font-family:Arial,Helvetica,sans-serif;font-size:12px;line-height:1.6;color:#566082">
Te escribimos a ${esc(correo)} porque ${motivo} en cualmeconviene.cl.<br>
<a href="${esc(sitio)}/mi-cuenta" style="color:#2E57FF">Elegir qué avisos recibo</a> · <a href="${esc(baja)}" style="color:#2E57FF">No quiero recibir más correos</a><br>
Adictos Digitales · Chile · Si respondes este correo, nos llega a ${esc('adictosdigitalesla@gmail.com')}.
</td></tr></table></td></tr></table></body></html>`;
}

function texto(titulo, items, sitio, baja) {
  const l = items.map(it => `- ${it.nombre}: ${it.motivo === 'volvio' ? 'volvió a tener stock, ' : `antes ${plata(it.antes)}, `}ahora ${plata(it.ahora)}${it.tienda ? ' en ' + it.tienda : ''}\n  ${sitio}/${it.clave}`);
  return `${titulo}\n\n${l.join('\n\n')}\n\nLos precios son referenciales. Confirma el precio final en la tienda.\n\nElegir qué avisos recibo: ${sitio}/mi-cuenta\nNo quiero recibir más correos: ${baja}\n`;
}

// Aviso de los equipos que la persona sigue
export function correoAviso({ sitio, persona, correo, items, baja }) {
  const n = items.length, it = items[0];
  const titulo = n > 1 ? `${n} equipos que sigues tienen novedades`
    : it.motivo === 'volvio' ? `Volvió a tener stock: ${corto(it.nombre, 60)}` : `Bajó de precio: ${corto(it.nombre, 60)}`;
  const asunto = n > 1 ? `${n} equipos que sigues bajaron de precio o volvieron`
    : it.motivo === 'volvio' ? `Volvió: ${corto(it.nombre, 50)} a ${plata(it.ahora)}` : `Bajó: ${corto(it.nombre, 50)} a ${plata(it.ahora)}`;
  const intro = `Hola${persona ? ' ' + esc(String(persona).split(' ')[0]) : ''}, ${n > 1 ? 'estos equipos que sigues cambiaron' : 'el equipo que sigues cambió'} en la revisión de hoy.`;
  return {
    asunto,
    html: marco({ sitio, titulo, intro, filas: items.map(i => fila(sitio, i)).join(''), correo, motivo: 'pediste que te avisáramos del precio de estos equipos', baja }),
    texto: texto(titulo, items, sitio, baja),
  };
}

// Resumen diario con las mayores bajadas del día (solo se envía los días que hay bajadas)
export function correoResumen({ sitio, persona, correo, items, baja, dia }) {
  const titulo = `Las mayores bajadas de precio del ${fechaLarga(dia)}`;
  const asunto = `Bajó de precio: ${corto(items[0].nombre, 45)}${items.length > 1 ? ` y ${items.length - 1} más` : ''}`;
  const intro = `Hola${persona ? ' ' + esc(String(persona).split(' ')[0]) : ''}, estos son los equipos que más bajaron desde la revisión anterior.`;
  return {
    asunto,
    html: marco({ sitio, titulo, intro, filas: items.map(i => fila(sitio, i)).join(''), correo, motivo: 'activaste el resumen diario de bajadas', baja }),
    texto: texto(titulo, items, sitio, baja),
  };
}
