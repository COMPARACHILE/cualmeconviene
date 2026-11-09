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

const miles = n => Math.round(n).toLocaleString('es-CL');

// Por qué se sugiere una alternativa, en una línea (lo calcula sugeridos() en herramientas/fichas.py)
function porQue(a) {
  if (a.tipo === 'min') {
    const [habitual, desde] = a.dato || [];
    const pct = habitual > a.ahora ? Math.round((habitual - a.ahora) / habitual * 100) : 0;
    return {
      etiqueta: 'Mínimo histórico',
      detalle: `Es lo más barato que ha costado desde el ${fechaLarga(desde)}${habitual ? `: suele costar ${plata(habitual)} (hoy −${pct}%)` : ''}.`,
    };
  }
  const [suyo, delQueSigues, nombre] = a.dato || [];
  const dif = (a.paraPrecio || a.ahora) - a.ahora;
  const plataTxt = dif > 0 ? ` y cuesta ${plata(dif)} menos` : dif < 0 ? `, por ${plata(-dif)} más` : '';
  const comp = suyo > delQueSigues * 1.02 ? 'rinde más' : suyo >= delQueSigues * 0.98 ? 'rinde lo mismo' : 'rinde casi lo mismo';
  return {
    etiqueta: 'Rinde más por tu plata',
    detalle: `${nombre === 'AnTuTu' ? 'Potencia (AnTuTu)' : 'Puntaje del puma'} ${miles(suyo)} contra ${miles(delQueSigues)} del que sigues: ${comp}${plataTxt}.`,
  };
}

function filaAlt(sitio, a) {
  const url = `${sitio}/${a.clave}`;
  const foto = a.id ? `${sitio}/assets/p/${encodeURIComponent(a.id)}.webp` : `${sitio}/assets/puma-icono-192.png`;
  const r = porQue(a);
  const color = a.tipo === 'min' ? 'background:#FFF4CC;color:#7A5A00' : 'background:#E2E8FF;color:#2E57FF';
  return `<tr><td style="padding:12px 0;border-top:1px solid #DCE1EE">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
<td width="60" valign="top" style="padding-right:12px"><a href="${esc(url)}"><img src="${esc(foto)}" width="56" height="56" alt="" style="display:block;width:56px;height:56px;object-fit:contain;border:1px solid #DCE1EE;border-radius:10px;background:#fff"></a></td>
<td valign="top" style="font-family:Arial,Helvetica,sans-serif;color:#10152B">
<span style="display:inline-block;${color};font-weight:700;font-size:12px;padding:2px 8px;border-radius:8px">${r.etiqueta}</span><br>
<a href="${esc(url)}" style="color:#10152B;font-weight:700;font-size:15px;line-height:1.3;text-decoration:none">${esc(a.nombre)}</a><br>
<span style="color:#10152B;font-weight:800;font-size:17px">${plata(a.ahora)}</span>${a.tienda ? `<span style="color:#566082;font-size:13px"> en ${esc(a.tienda)}</span>` : ''}<br>
<span style="color:#566082;font-size:13px;line-height:1.45">${esc(r.detalle)} En vez de: ${esc(corto(a.para, 50))}.</span>
</td></tr></table></td></tr>`;
}

function marco({ sitio, titulo, intro, filas, extra = '', correo, motivo, baja }) {
  return `<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${esc(titulo)}</title></head>
<body style="margin:0;padding:0;background:#F3F5FA">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F3F5FA"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#FFFFFF;border:1px solid #DCE1EE;border-radius:18px;overflow:hidden">
<tr><td style="background:#0E1533;padding:16px 22px"><a href="${esc(sitio)}" style="text-decoration:none;font-family:Arial,Helvetica,sans-serif;font-weight:800;font-size:19px;color:#FFD84D"><img src="${esc(sitio)}/assets/puma-icono-96.png" width="32" height="32" alt="" style="vertical-align:middle;border-radius:50%;margin-right:8px">¿Cuál me conviene?</a></td></tr>
<tr><td style="padding:22px 22px 6px;font-family:Arial,Helvetica,sans-serif;color:#10152B">
<h1 style="margin:0;font-size:22px;line-height:1.25">${esc(titulo)}</h1>
<p style="margin:8px 0 6px;font-size:15px;line-height:1.5;color:#566082">${intro}</p>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">${filas}</table>${extra}
<p style="margin:14px 0 18px;font-size:13px;line-height:1.5;color:#566082">Los precios son referenciales y salen de la revisión diaria de las tiendas. Confirma el precio final en la tienda antes de pagar.</p>
</td></tr>
<tr><td style="padding:16px 22px;background:#ECEFF7;font-family:Arial,Helvetica,sans-serif;font-size:12px;line-height:1.6;color:#566082">
Te escribimos a ${esc(correo)} porque ${motivo} en cualmeconviene.cl.<br>
<a href="${esc(sitio)}/mi-cuenta" style="color:#2E57FF">Elegir qué avisos recibo</a> · <a href="${esc(baja)}" style="color:#2E57FF">No quiero recibir más correos</a><br>
Adictos Digitales · Chile · Si respondes este correo, nos llega a ${esc('adictosdigitalesla@gmail.com')}.
</td></tr></table></td></tr></table></body></html>`;
}

function texto(titulo, items, sitio, baja, extras = []) {
  const l = items.map(it => `- ${it.nombre}: ${it.motivo === 'volvio' ? 'volvió a tener stock, ' : `antes ${plata(it.antes)}, `}ahora ${plata(it.ahora)}${it.tienda ? ' en ' + it.tienda : ''}\n  ${sitio}/${it.clave}`);
  const x = extras.map(a => { const r = porQue(a); return `- ${r.etiqueta}: ${a.nombre}, ${plata(a.ahora)}${a.tienda ? ' en ' + a.tienda : ''}. ${r.detalle}\n  ${sitio}/${a.clave}`; });
  return `${titulo}\n\n${l.join('\n\n')}\n\n${x.length ? `También te pueden convenir\n\n${x.join('\n\n')}\n\n` : ''}Los precios son referenciales. Confirma el precio final en la tienda.\n\nElegir qué avisos recibo: ${sitio}/mi-cuenta\nNo quiero recibir más correos: ${baja}\n`;
}

// Hasta 3 alternativas para el correo, sacadas de los equipos que trae el aviso (quinto dato de cada equipo en
// assets/avisos.json, lo calcula sugeridos() en herramientas/fichas.py): un equipo parecido en su mínimo histórico
// o uno que rinde más por su precio. Se salta lo que la persona ya sigue y lo que hoy no tiene precio.
export function alternativas(eqs, items, yaSigue = new Set(), max = 3) {
  const listas = items.map(it => (eqs[it.clave] && eqs[it.clave][4]) || []);
  const out = [], vistos = new Set(yaSigue);
  for (let r = 0; out.length < max && listas.some(l => l.length > r); r++) {
    for (let i = 0; i < listas.length && out.length < max; i++) {
      const s = listas[i][r];
      if (!s || vistos.has(s[0])) continue;
      const e = eqs[s[0]];
      if (!e || e[0] == null) continue;
      vistos.add(s[0]);
      out.push({ clave: s[0], nombre: e[1], id: e[2], tienda: e[3], ahora: e[0], tipo: s[1], dato: s[2], para: items[i].nombre, paraPrecio: items[i].ahora });
    }
  }
  return out;
}

// Aviso de los equipos que la persona sigue
export function correoAviso({ sitio, persona, correo, items, extras = [], baja }) {
  const n = items.length, it = items[0];
  const titulo = n > 1 ? `${n} equipos que sigues tienen novedades`
    : it.motivo === 'volvio' ? `Volvió a tener stock: ${corto(it.nombre, 60)}` : `Bajó de precio: ${corto(it.nombre, 60)}`;
  const asunto = n > 1 ? `${n} equipos que sigues bajaron de precio o volvieron`
    : it.motivo === 'volvio' ? `Volvió: ${corto(it.nombre, 50)} a ${plata(it.ahora)}` : `Bajó: ${corto(it.nombre, 50)} a ${plata(it.ahora)}`;
  const intro = `Hola${persona ? ' ' + esc(String(persona).split(' ')[0]) : ''}, ${n > 1 ? 'estos equipos que sigues cambiaron' : 'el equipo que sigues cambió'} en la revisión de hoy.`;
  return {
    asunto,
    html: marco({
      sitio, titulo, intro, filas: items.map(i => fila(sitio, i)).join(''), correo, motivo: 'pediste que te avisáramos del precio de estos equipos', baja,
      extra: extras.length ? `<h2 style="margin:22px 0 2px;font-size:17px">También te pueden convenir</h2>
<p style="margin:0 0 4px;font-size:13px;line-height:1.5;color:#566082">Parecidos al que sigues y en tu mismo presupuesto: uno en su precio más bajo o uno que rinde más por lo que cuesta.</p>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">${extras.map(a => filaAlt(sitio, a)).join('')}</table>` : '',
    }),
    texto: texto(titulo, items, sitio, baja, extras),
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
