#!/usr/bin/env python3
"""Fichas de equipos de ¿Cuál me conviene?: una página por notebook, celular, tablet y televisor.

  python3 herramientas/fichas.py
      Crea o actualiza notebook/<nombre>.html y celular/<nombre>.html con los precios de
      notebooks.html y celulares.html, el historial de precios (sale del historial de git),
      equipos parecidos y datos para Google. También rehace sitemap.xml y assets/fichas.js.

No hace falta correrlo a mano: el flujo .github/workflows/fichas.yml lo corre cada vez que
cambian los precios. Las direcciones de cada ficha quedan fijas en herramientas/fichas.json
para que los enlaces compartidos no se rompan si el nombre del equipo cambia.
"""
import datetime, html, json, os, re, subprocess, sys, unicodedata

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import precios  # noqa: E402

SITIO = 'https://cualmeconviene.cl'
SLUGS = os.path.join(RAIZ, 'herramientas', 'fichas.json')
FOTOS = os.path.join(RAIZ, 'herramientas', 'fotos.json')
TIENDAS = {
    'falabella': ('Falabella', '#5FA21A', 'tienda'), 'paris': ('Paris', '#1B8FD6', 'tienda'),
    'ripley': ('Ripley', '#7A3FA0', 'tienda'), 'pcfactory': ('PCFactory', '#E8590C', 'tienda'),
    'entel': ('Entel', '#0047BB', 'operadora'), 'movistar': ('Movistar', '#00A9E0', 'operadora'),
    'claro': ('Claro', '#DA291C', 'operadora'), 'wom': ('WOM', '#8E24AA', 'operadora'),
}
CATN = {'Entrada': 'Gamer de entrada', 'Media': 'Gamer gama media', 'Alta': 'Gamer gama alta', 'Muy alta': 'Gamer gama muy alta'}
MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
e = lambda t: html.escape(str(t), quote=True)


def plata(n):
    return '$' + f'{int(round(n)):,}'.replace(',', '.')


def fecha_larga(d):
    return f'{d.day} de {MESES[d.month - 1]}'


def slugify(t):
    t = unicodedata.normalize('NFKD', t).encode('ascii', 'ignore').decode().lower()
    t = re.sub(r'[^a-z0-9]+', '-', t).strip('-')
    return re.sub(r'-+', '-', t)[:80].strip('-')


def pulg(v):
    if not v: return None
    return (f'{v:g}'.replace('.', ',')) + '"'


def gb(n):
    return f'{n // 1024} TB' if n and n >= 1024 else f'{n} GB'


def marca_nb(n):
    b = n['name'].split(' ')[0]
    return 'Apple' if b == 'MacBook' else b


# ---------------- Datos ----------------
def visibles(eq):
    return sorted([o for o in eq['offers'] if not o.get('x') and o.get('p')], key=lambda o: o['p'])


def equipos():
    _, _, nbs, _, _, phs = precios.cargar()
    out = []
    for n in nbs:
        out.append(dict(k='nb', eq=n, id=n['id'], marca=marca_nb(n), nombre=n['name']))
    for p in phs:
        nom = f"{p['name']} {gb(p['gb'])}"
        out.append(dict(k='ph', eq=p, id=p['id'], marca=p['brand'], nombre=nom))
    extra = precios.cargar_extra()
    for p in extra.get('tb', (None, None, []))[2]:
        out.append(dict(k='tb', eq=p, id=p['id'], marca=p['brand'], nombre=f"{p['name']} {gb(p['gb'])}"))
    for p in extra.get('tv', (None, None, []))[2]:
        out.append(dict(k='tv', eq=p, id=p['id'], marca=p['brand'], nombre=p['name']))
    for x in out:
        x['os'] = visibles(x['eq'])
    return out


def historial():
    """Precio más bajo de cada equipo por día, leído de las versiones guardadas en git."""
    h = {}
    try:
        log = subprocess.run(['git', '-C', RAIZ, 'log', '--format=%H %cI', '--', 'notebooks.html', 'celulares.html', 'tablets.html', 'televisores.html'],
                             capture_output=True, text=True, check=True).stdout.split('\n')
    except Exception:
        return h
    for linea in reversed([l for l in log if l.strip()]):
        sha, cuando = linea.split(' ', 1)
        dia = datetime.datetime.fromisoformat(cuando).astimezone(datetime.timezone(datetime.timedelta(hours=-3))).date()
        for archivo, ini, fin in (('notebooks.html', 'const NOTEBOOKS = ', '\n];'), ('celulares.html', 'const PHONES = ', ';\n'),
                                  ('tablets.html', 'const EQUIPOS = ', ';\n'), ('televisores.html', 'const EQUIPOS = ', ';\n')):
            try:
                t = subprocess.run(['git', '-C', RAIZ, 'show', f'{sha}:{archivo}'], capture_output=True, text=True, check=True).stdout
                i = t.index(ini) + len(ini); j = t.index(fin, i) + (2 if fin.startswith('\n]') else 0)
                # La fecha es la de la revisión de precios que dice el archivo, no la del cambio en git
                m = re.search(r"const SEEN(?:_GAMER)? = '(\d\d)-(\d\d)-(\d{4})'", t)
                d_rev = datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1))) if m else dia
                for x in json.loads(t[i:j]):
                    os_ = [o['p'] for o in x.get('offers', []) if not o.get('x') and o.get('p')]
                    if os_:
                        h.setdefault(x['id'], {})[d_rev] = min(os_)
            except Exception:
                continue
    return h


# ---------------- Piezas de la página ----------------
def foto_de(i, fotos):
    if os.path.exists(os.path.join(RAIZ, 'assets', 'p', i + '.webp')):
        return f'/assets/p/{i}.webp', f'{SITIO}/assets/p/{i}.webp'
    u = fotos.get(i)
    if isinstance(u, list):
        u = u[0] if u else None
    return u, u


def categoria(x):
    q = x['eq']
    if x['k'] == 'nb':
        if q.get('cat'): return CATN.get(q['cat'], 'Gamer')
        if q.get('gpuTier', 0) >= 2: return 'Gamer'
        return 'Portátil hasta 14"' if q.get('size', 15) <= 14.5 else 'Uso general'
    if x['k'] == 'tv':
        return ' '.join(t for t in ['Televisor', q.get('panel'), q.get('res')] if t)
    if q.get('refurb'): return 'Reacondicionado'
    p = x['os'][0]['p'] if x['os'] else 0
    return 'Gama de entrada' if p <= 250000 else 'Gama media' if p <= 600000 else 'Gama alta'


def specs_cortas(x):
    q = x['eq']
    if x['k'] == 'nb':
        return ', '.join(t for t in [q.get('cpu'), q.get('gpu') if q.get('gpuTier') else 'gráficos integrados', f"{q.get('ram')} GB RAM", gb(q.get('ssd', 0)) + ' SSD', f"{q.get('size')}\""] if t)
    if x['k'] == 'tv':
        return ', '.join(t for t in [pulg(q.get('size')), q.get('res'), q.get('panel'), f"{q['hz']} Hz" if q.get('hz') else None, q.get('os')] if t)
    return ', '.join(t for t in [q.get('chip'), f"{q['ram']} GB RAM" if q.get('ram') else None, gb(q['gb']), f"{q['size']}\"" if q.get('size') else None,
                                 f"{q['bat']:,} mAh".replace(',', '.') if q.get('bat') else None, q.get('net') if x['k'] == 'tb' else None] if t)


def tabla_tecnica(x):
    q = x['eq']
    filas = []
    if x['k'] == 'nb':
        filas += [('Procesador', q.get('cpu')), ('Gráficos', q.get('gpu') if q.get('gpuTier') else 'Integrados en el procesador'),
                  ('Memoria RAM', f"{q.get('ram')} GB"), ('Almacenamiento', gb(q.get('ssd', 0)) + ' SSD'),
                  ('Pantalla', f"{q.get('size')}\"" + (f", {q['hz']} Hz" if q.get('hz') else '')), ('Tipo', categoria(x))]
    elif x['k'] == 'tv':
        filas += [('Tamaño', pulg(q.get('size'))), ('Resolución', q.get('res')), ('Tipo de panel', q.get('panel')),
                  ('Tasa de refresco', f"{q['hz']} Hz" if q.get('hz') else None), ('Sistema', q.get('os')), ('Modelo', q.get('model')),
                  ('Precio por pulgada', plata(x['os'][0]['p'] / q['size']) if x['os'] and q.get('size') else None)]
    elif x['k'] == 'tb':
        filas += [('Procesador', q.get('chip')), ('Almacenamiento', gb(q['gb'])), ('Memoria RAM', f"{q['ram']} GB" if q.get('ram') else None),
                  ('Pantalla', ' '.join(t for t in [f"{q['size']}\"" if q.get('size') else '', f"({q['res']})" if q.get('res') else ''] if t) or None),
                  ('Batería', f"{q['bat']:,} mAh".replace(',', '.') if q.get('bat') else None), ('Cámara trasera', f"{q['cam']} MP" if q.get('cam') else None),
                  ('Conectividad', q.get('net')), ('Incluye', q.get('extra')),
                  ('Geekbench 6', f"{q['gb6'][0]:,} un núcleo · {q['gb6'][1]:,} multinúcleo".replace(',', '.') if q.get('gb6') else None),
                  ('AnTuTu', f"{q['antutu']:,}".replace(',', '.') if q.get('antutu') else None)]
    else:
        filas += [('Procesador', q.get('chip')), ('Almacenamiento', gb(q['gb'])), ('Memoria RAM', f"{q['ram']} GB" if q.get('ram') else None),
                  ('Pantalla', ' '.join(t for t in [f"{q['size']}\"" if q.get('size') else '', q.get('panel') or '', f"{q['hz']} Hz" if q.get('hz') else ''] if t) or None),
                  ('Batería', (f"{q['bat']:,} mAh".replace(',', '.') + (f", carga {q['chg']} W" if q.get('chg') else '')) if q.get('bat') else None),
                  ('Cámara principal', f"{q['cam']} MP" if q.get('cam') else None), ('Lanzamiento', q.get('year')),
                  ('Geekbench 6', f"{q['gb6'][0]:,} un núcleo · {q['gb6'][1]:,} multinúcleo".replace(',', '.') if q.get('gb6') else None),
                  ('AnTuTu', f"{q['antutu']:,}".replace(',', '.') if q.get('antutu') else None),
                  ('Red', '4G' if '(4G)' in q['name'] else '5G'), ('Estado', q.get('cond') or ('Reacondicionado' if q.get('refurb') else 'Nuevo'))]
    return ''.join(f'<div><dt>{e(a)}</dt><dd>{e(b)}</dd></div>' for a, b in filas if b)


def grafico(hist, hoy_precio, hoy):
    """Línea simple del precio más bajo por día. Devuelve (svg, frase)."""
    pts = sorted(hist.items())
    if hoy_precio and (not pts or pts[-1][0] != hoy):
        pts.append((hoy, hoy_precio))
    pts = pts[-60:]
    if len(pts) < 2:
        d = pts[0][0] if pts else hoy
        return '', f'Empezamos a seguir este precio el {fecha_larga(d)}. En unos días verás aquí cómo cambia.'
    W, H, PY = 1000, 200, 14
    vals = [v for _, v in pts]
    lo, hi = min(vals), max(vals)
    # Escala mínima de 12% del precio para no exagerar cambios chicos
    rng = max(hi - lo, hi * 0.12, 1)
    tope = hi + (rng - (hi - lo)) / 2
    xs = lambda k: k * W / (len(pts) - 1)
    ys = lambda v: PY + (tope - v) / rng * (H - 2 * PY)
    linea = ' '.join(f'{xs(k):.1f},{ys(v):.1f}' for k, (_, v) in enumerate(pts))
    area = f'0,{H} ' + linea + f' {W},{H}'
    ultimo, primero = vals[-1], vals[0]
    if ultimo <= lo and hi > lo:
        frase = f'Hoy está en su precio más bajo desde el {fecha_larga(pts[0][0])}.'
    elif ultimo < primero:
        frase = f'Bajó {plata(primero - ultimo)} desde el {fecha_larga(pts[0][0])}.'
    elif ultimo > primero:
        frase = f'Subió {plata(ultimo - primero)} desde el {fecha_larga(pts[0][0])}. El más bajo que vimos fue {plata(lo)}.'
    else:
        frase = f'Se mantiene igual desde el {fecha_larga(pts[0][0])}.'
    pct = lambda v: (ys(v) / H * 100)
    svg = (f'<figure class="graf"><div class="grafZona">'
           f'<svg viewBox="0 0 {W} {H}" preserveAspectRatio="none" role="img" aria-label="Precio más bajo por día. {e(frase)}">'
           f'<polygon class="area" points="{area}"/><polyline class="lin" points="{linea}"/></svg>'
           f'<span class="ult" style="top:{pct(ultimo):.1f}%"></span></div>'
           f'<figcaption><span>{fecha_larga(pts[0][0])}</span><span class="rango">entre {plata(lo)} y {plata(hi)}</span><span>{fecha_larga(pts[-1][0])}: <b>{plata(ultimo)}</b></span></figcaption></figure>')
    return svg, frase


def tarjeta(x, fotos, url_ficha):
    f, _ = foto_de(x['id'], fotos)
    img = f'<img src="{e(f)}" alt="" width="480" height="480" loading="lazy" decoding="async" referrerpolicy="no-referrer">' if f else ''
    o = x['os'][0]
    return (f'<a class="par" href="{url_ficha}"><span class="parF">{img}</span><span class="parT">{e(x["nombre"])}</span>'
            f'<span class="parP">{plata(o["p"])}{"*" if o.get("c") else ""}</span><span class="parE">en {TIENDAS[o["s"]][0]}</span></a>')


def pagina(x, url, fotos, hist, todos, urls, hoy_txt, hoy):
    q, os_ = x['eq'], x['os']
    tipo = {'nb': 'Notebooks', 'ph': 'Celulares', 'tb': 'Tablets', 'tv': 'Televisores'}[x['k']]
    lista = '/' + tipo.lower()
    f_rel, f_abs = foto_de(x['id'], fotos)
    nombre = x['nombre']
    cat = categoria(x)
    specs = specs_cortas(x)
    if os_:
        b, w = os_[0], os_[-1]
        tit = f'{nombre}: precio en Chile desde {plata(b["p"])} | ¿Cuál me conviene?'
        desc = (f'Compara el precio del {nombre} en ' + ', '.join(dict.fromkeys(TIENDAS[o["s"]][0] for o in os_)) +
                f'. Hoy desde {plata(b["p"])} en {TIENDAS[b["s"]][0]}. Precios revisados el {hoy_txt}.')
    else:
        tit = f'{nombre}: precio en Chile | ¿Cuál me conviene?'
        desc = f'{nombre}: hoy no lo encontramos con stock en las tiendas que revisamos. Mira equipos parecidos y sus precios.'
    # Datos para Google
    ld = {'@context': 'https://schema.org', '@graph': [
        {'@type': 'Product', 'name': nombre, 'brand': {'@type': 'Brand', 'name': x['marca']}, 'category': {'nb': 'Notebook', 'ph': 'Celular', 'tb': 'Tablet', 'tv': 'Televisor'}[x['k']],
         'description': f'{nombre}: {specs}.', 'url': SITIO + url, **({'image': f_abs} if f_abs else {}),
         **({'offers': {'@type': 'AggregateOffer', 'priceCurrency': 'CLP', 'lowPrice': os_[0]['p'], 'highPrice': os_[-1]['p'], 'offerCount': len(os_),
                        'availability': 'https://schema.org/InStock', **({'itemCondition': 'https://schema.org/RefurbishedCondition'} if q.get('refurb') else {'itemCondition': 'https://schema.org/NewCondition'})}} if os_ else {})},
        {'@type': 'BreadcrumbList', 'itemListElement': [
            {'@type': 'ListItem', 'position': 1, 'name': 'Inicio', 'item': SITIO + '/'},
            {'@type': 'ListItem', 'position': 2, 'name': tipo, 'item': SITIO + lista},
            {'@type': 'ListItem', 'position': 3, 'name': nombre, 'item': SITIO + url}]}]}
    # Precio en cada tienda
    filas = ''
    for k, o in enumerate(os_):
        nom, color, canal = TIENDAS[o['s']]
        dif = o['p'] - os_[0]['p']
        extra = ' · '.join(t for t in [o.get('note'), ('Vende: ' + o['seller']) if o.get('seller') else None] if t)
        etiqueta = '<b class="gana">Más barato</b>' if k == 0 or dif == 0 else f'<b class="mas">+{plata(dif)}</b>'
        filas += (f'<li class="{"g" if dif == 0 else ""}"><span class="tn"><i style="background:{color}"></i><span><strong>{nom}</strong>'
                  f'{" <small>operadora</small>" if canal == "operadora" else ""}{f"<em>{e(extra)}</em>" if extra else ""}</span></span>'
                  f'<span class="tp">{plata(o["p"])}{"<abbr title=\"Pide tarjeta de la tienda o transferencia\">*</abbr>" if o.get("c") else ""}{etiqueta}</span>'
                  f'<a class="tb" href="{e(o["url"])}" target="_blank" rel="nofollow sponsored noopener" data-id="{("" if x["k"] == "nb" else "c-") + x["id"]}" data-store="{o["s"]}">Ver en {nom}</a></li>')
    svg, frase = grafico(hist.get(x['id'], {}), os_[0]['p'] if os_ else None, hoy)
    # Parecidos: misma familia y precio cercano
    ref = os_[0]['p'] if os_ else (list(hist.get(x['id'], {}).values()) or [0])[-1]
    cands = [y for y in todos if y['id'] != x['id'] and y['k'] == x['k'] and y['os']]
    if x['k'] == 'nb':
        cands = [y for y in cands if (y['eq'].get('gpuTier', 0) >= 2) == (q.get('gpuTier', 0) >= 2)]
    elif x['k'] == 'ph':
        cands = [y for y in cands if bool(y['eq'].get('refurb')) == bool(q.get('refurb'))]
    if x['k'] == 'tv':
        cands.sort(key=lambda y: (abs((y['eq'].get('size') or 0) - (q.get('size') or 0)) > 5, abs(y['os'][0]['p'] - ref)))
    else:
        cands.sort(key=lambda y: abs(y['os'][0]['p'] - ref))
    parecidos = ''.join(tarjeta(y, fotos, urls[y['id']]) for y in cands[:4])
    # Bloque principal
    if os_:
        b, w = os_[0], os_[-1]
        empatan = [TIENDAS[o['s']][0] for o in os_ if o['p'] == b['p']]
        donde = ' o '.join([', '.join(empatan[:-1]), empatan[-1]]) if len(empatan) > 1 else empatan[0]
        ahorro = (f'<p class="ah">Ahorras <b>{plata(w["p"] - b["p"])}</b> frente a {TIENDAS[w["s"]][0]}</p>' if w['p'] > b['p'] else
                  (f'<p class="ah neutro">Mismo precio en {len(os_)} tiendas</p>' if len(os_) > 1 else '<p class="ah neutro">Lo encontramos en una tienda</p>'))
        mejor = (f'<div class="mejor"><p class="et">Precio más bajo hoy</p><p class="precio">{plata(b["p"])}{"<abbr title=\"Pide tarjeta de la tienda o transferencia\">*</abbr>" if b.get("c") else ""}</p>'
                 f'<p class="donde"><i style="background:{TIENDAS[b["s"]][1]}"></i>en {e(donde)}{(" · " + e(b["note"])) if b.get("note") else ""}</p>{ahorro}'
                 f'<a class="ir" href="{e(b["url"])}" target="_blank" rel="nofollow sponsored noopener" data-id="{("" if x["k"] == "nb" else "c-") + x["id"]}" data-store="{b["s"]}">Ir a {TIENDAS[b["s"]][0]}</a></div>')
    else:
        mejor = '<div class="mejor sin"><p class="et">Sin stock hoy</p><p>No lo encontramos disponible en las tiendas que revisamos. Abajo tienes equipos parecidos.</p></div>'
    ref_txt = ('<p class="aviso">Equipo reacondicionado: usado y revisado. Confirma garantía, estado y batería en la ficha de la tienda.</p>' if q.get('refurb') else '')
    img = (f'<img src="{e(f_rel)}" alt="{e(nombre)}" width="480" height="480" fetchpriority="high" decoding="async" referrerpolicy="no-referrer">' if f_rel else '')
    og = (f'{SITIO}/assets/og/{x["id"]}.jpg' if os.path.exists(os.path.join(OG_DIR, x['id'] + '.jpg')) else (f_abs or f'{SITIO}/assets/og.png'))
    return f'''<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(tit)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{SITIO}{url}">
<meta name="theme-color" content="#0E1533">
<meta property="og:type" content="product">
<meta property="og:locale" content="es_CL">
<meta property="og:site_name" content="¿Cuál me conviene?">
<meta property="og:title" content="{e(tit.split(' | ')[0])}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{SITIO}{url}">
<meta property="og:image" content="{e(og)}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="/assets/puma-icono-48.png" type="image/png" sizes="48x48">
<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
<link rel="preload" href="/assets/fonts/bricolage.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="/assets/fonts/dmsans.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/assets/cmc.css">
<link rel="stylesheet" href="/assets/ficha.css">
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False).replace('</', '<\\/')}</script>
<script defer src="/assets/cmc.js"></script>
</head>
<body>
<header class="cab"><div class="wrap cabIn">
  <a class="marca" href="/" aria-label="¿Cuál me conviene? Inicio"><img src="/assets/puma-icono-96.png" alt="" width="40" height="40" decoding="async"><span>¿Cuál me conviene?</span></a>
  <nav class="cats" aria-label="Categorías">{''.join(f'<a href="/{c.lower()}"' + (' aria-current="true"' if c == tipo else '') + f'>{c}</a>' for c in ('Notebooks', 'Celulares', 'Tablets', 'Televisores'))}</nav>
</div></header>
<main class="wrap">
  <nav class="migas" aria-label="Ruta"><a href="/">Inicio</a><span aria-hidden="true">›</span><a href="{lista}">{tipo}</a><span aria-hidden="true">›</span><span aria-current="page">{e(nombre)}</span></nav>
  <div class="top">
    <figure class="fg">{img}</figure>
    <div class="res">
      <p class="mc">{e(x['marca'])} · {e(cat)}</p>
      <h1>{e(nombre)}</h1>
      <p class="sp">{e(specs)}</p>
      {ref_txt}
      {mejor}
    </div>
  </div>
  <section class="bloque" aria-labelledby="t1">
    <h2 id="t1">Precio en cada tienda</h2>
    {f'<ol class="tiendas">{filas}</ol>' if filas else '<p>Hoy no hay tiendas con stock.</p>'}
    <p class="nota">Precios revisados el {hoy_txt}. El asterisco (*) indica que el precio pide la tarjeta de la tienda o transferencia. Confirma siempre el precio final en la tienda antes de pagar.</p>
  </section>
  <section class="bloque" aria-labelledby="t2">
    <h2 id="t2">Historial del precio más bajo</h2>
    {svg}
    <p class="frase">{e(frase)}</p>
  </section>
  <section class="bloque" aria-labelledby="t3">
    <h2 id="t3">Características</h2>
    <dl class="tec">{tabla_tecnica(x)}</dl>
    <p class="nota"><a href="{lista}?ver={e(x['id'])}">Compararlo con otros {tipo.lower()} en el comparador</a></p>
  </section>
  {f'<section class="bloque" aria-labelledby="t4"><h2 id="t4">Otros que te pueden convenir</h2><div class="pars">{parecidos}</div></section>' if parecidos else ''}
</main>
<footer class="pie"><div class="wrap">
  <a class="marca" href="/"><img src="/assets/puma-icono-96.png" alt="" width="40" height="40" loading="lazy"><span>¿Cuál me conviene?</span></a>
  <p>Comparamos el precio del mismo equipo en las tiendas y operadoras de Chile. No vendemos equipos: te llevamos a la tienda. Los precios son referenciales. <a href="/#privacidad">Privacidad y términos</a></p>
</div></footer>
<script>
/* Contador de clics a tiendas: solo equipo, tienda y nombre. Sin cookies ni datos personales. */
document.addEventListener('click', ev => {{
  const a = ev.target.closest('a[data-store]');
  if (!a || location.protocol === 'file:') return;
  const body = JSON.stringify({{ id: a.dataset.id, s: a.dataset.store, n: {json.dumps(nombre, ensure_ascii=False)} }});
  try {{ navigator.sendBeacon ? navigator.sendBeacon('/api/clic', new Blob([body], {{ type: 'application/json' }})) : fetch('/api/clic', {{ method: 'POST', body, keepalive: true }}); }} catch (_) {{}}
}});
</script>
<script defer src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon='{{"token": "839f9ada4cc443eaa027f591d0400c85"}}'></script>
</body>
</html>
'''


# ---------------- Imagen para compartir (WhatsApp, Instagram, Facebook) ----------------
OG_DIR = os.path.join(RAIZ, 'assets', 'og')
FUENTES = os.path.join(RAIZ, 'herramientas', 'fuentes')


def _fuente(nombre, tam, peso=None, opsz=None):
    from PIL import ImageFont
    f = ImageFont.truetype(os.path.join(FUENTES, nombre), tam)
    try:
        ejes = f.get_variation_axes()
        vals = []
        for a in ejes:
            n = a['name'].decode() if isinstance(a['name'], bytes) else a['name']
            vals.append(opsz if 'Optical' in n and opsz else peso if 'Weight' in n and peso else a['default'])
        f.set_variation_by_axes(vals)
    except Exception:
        pass
    return f


def _envolver(draw, texto, fuente, ancho, max_lineas):
    palabras, lineas, actual = texto.split(), [], ''
    for p in palabras:
        prueba = (actual + ' ' + p).strip()
        if draw.textlength(prueba, font=fuente) <= ancho:
            actual = prueba
        else:
            if actual: lineas.append(actual)
            actual = p
    if actual: lineas.append(actual)
    if len(lineas) > max_lineas:
        lineas = lineas[:max_lineas]
        while draw.textlength(lineas[-1] + '…', font=fuente) > ancho and ' ' in lineas[-1]:
            lineas[-1] = lineas[-1].rsplit(' ', 1)[0]
        lineas[-1] += '…'
    return lineas


def generar_og(todos):
    """Crea assets/og/<id>.jpg (1200x630) una sola vez por equipo, sin precio para que no quede viejo."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return 0
    os.makedirs(OG_DIR, exist_ok=True)
    sello_p = os.path.join(RAIZ, 'assets', 'puma-sello.png')
    hechas = 0
    for x in todos:
        dest = os.path.join(OG_DIR, x['id'] + '.jpg')
        foto = os.path.join(RAIZ, 'assets', 'p', x['id'] + '.webp')
        if os.path.exists(dest) or not os.path.exists(foto):
            continue
        W, H = 1200, 630
        im = Image.new('RGB', (W, H), (14, 21, 51))
        d = ImageDraw.Draw(im)
        # Foto del equipo sobre una placa blanca
        d.rounded_rectangle((640, 45, 1155, 585), radius=36, fill=(255, 255, 255))
        ph = Image.open(foto).convert('RGB')
        ph.thumbnail((470, 470))
        im.paste(ph, (640 + (515 - ph.width) // 2, 45 + (540 - ph.height) // 2))
        # Sello del puma y nombre del sitio
        if os.path.exists(sello_p):
            se = Image.open(sello_p).convert('RGBA'); se.thumbnail((92, 92))
            im.paste(se, (60, 52), se)
        d.text((168, 98), '¿Cuál me conviene?', font=_fuente('bricolage.ttf', 36, 800, 48), fill=(255, 216, 77), anchor='lm')
        # Nombre del equipo
        fn = _fuente('bricolage.ttf', 62, 800, 96)
        lineas = _envolver(d, x['nombre'], fn, 540, 3)
        y = 190
        for l in lineas:
            d.text((60, y), l, font=fn, fill=(255, 255, 255)); y += 70
        sub = 'Compara su precio en ' + ('las tiendas y operadoras de Chile' if x['k'] == 'ph' else 'las tiendas de Chile')
        fs = _fuente('dmsans.ttf', 30, 500)
        for l in _envolver(d, sub, fs, 540, 2):
            d.text((60, y + 18), l, font=fs, fill=(196, 203, 234)); y += 40
        d.text((60, 560), 'cualmeconviene.cl', font=_fuente('dmsans.ttf', 30, 700), fill=(255, 216, 77))
        im.save(dest, 'JPEG', quality=84, optimize=True, progressive=True)
        hechas += 1
    return hechas


def main():
    todos = equipos()
    slugs = json.load(open(SLUGS, encoding='utf-8')) if os.path.exists(SLUGS) else {}
    fotos = json.load(open(FOTOS, encoding='utf-8')) if os.path.exists(FOTOS) else {}
    usados = set(slugs.values())
    for x in todos:
        if x['id'] in slugs:
            continue
        base = slugify((x['marca'] + ' ' + x['nombre']) if not x['nombre'].lower().startswith(x['marca'].lower()) else x['nombre'])
        if x['k'] == 'tv' and x['eq'].get('model') and slugify(x['eq']['model']) not in base:
            base = slugify(base + ' ' + x['eq']['model'])
        if x['eq'].get('refurb') and 'reacond' not in base: base += '-reacondicionado'
        s, k = base, 2
        while s in usados: s, k = f'{base}-{k}', k + 1
        slugs[x['id']] = s; usados.add(s)
    json.dump(slugs, open(SLUGS, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    CARP = {'nb': '/notebook/', 'ph': '/celular/', 'tb': '/tablet/', 'tv': '/televisor/'}
    urls = {x['id']: CARP[x['k']] + slugs[x['id']] for x in todos}
    n_og = generar_og(todos)
    hist = historial()
    hoy = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-3))).date()
    vistos = [x['eq'].get('seen') for x in todos if x['eq'].get('seen')]
    hoy_txt = max(vistos, key=lambda d: d.split('-')[::-1]) if vistos else hoy.strftime('%d-%m-%Y')
    try:
        hoy = datetime.datetime.strptime(hoy_txt, '%d-%m-%Y').date()
    except ValueError:
        pass
    for carpeta in ('notebook', 'celular', 'tablet', 'televisor'):
        os.makedirs(os.path.join(RAIZ, carpeta), exist_ok=True)
    escritas = 0
    for x in todos:
        ruta = os.path.join(RAIZ, urls[x['id']].lstrip('/') + '.html')
        nuevo = pagina(x, urls[x['id']], fotos, hist, todos, urls, hoy_txt, hoy)
        viejo = open(ruta, encoding='utf-8').read() if os.path.exists(ruta) else ''
        if nuevo != viejo:
            open(ruta, 'w', encoding='utf-8').write(nuevo); escritas += 1
    # Enlaces para las páginas que se arman en el navegador
    open(os.path.join(RAIZ, 'assets', 'fichas.js'), 'w', encoding='utf-8').write(
        '/* Generado por herramientas/fichas.py: dirección de la ficha de cada equipo. */\n'
        'window.CMC_FICHAS = ' + json.dumps(urls, ensure_ascii=False, separators=(',', ':')) + ';\n')
    # Datos livianos para la portada: todas las categorías en un solo archivo (sin enlaces ni notas)
    port = []
    for x in todos:
        q = {k: v for k, v in x['eq'].items() if k != 'offers'}
        q['offers'] = [{k: o[k] for k in ('s', 'p', 'c', 'x') if k in o} for o in x['eq']['offers']]
        port.append({'k': x['k'], **q})
    open(os.path.join(RAIZ, 'assets', 'portada.json'), 'w', encoding='utf-8').write(json.dumps(port, ensure_ascii=False, separators=(',', ':')))
    # Mapa del sitio para Google
    lm = hoy.isoformat()
    filas = [f'  <url><loc>{SITIO}/</loc><lastmod>{lm}</lastmod><changefreq>daily</changefreq><priority>1.0</priority></url>',
             f'  <url><loc>{SITIO}/notebooks</loc><lastmod>{lm}</lastmod><changefreq>daily</changefreq><priority>0.9</priority></url>',
             f'  <url><loc>{SITIO}/celulares</loc><lastmod>{lm}</lastmod><changefreq>daily</changefreq><priority>0.9</priority></url>',
             f'  <url><loc>{SITIO}/tablets</loc><lastmod>{lm}</lastmod><changefreq>daily</changefreq><priority>0.9</priority></url>',
             f'  <url><loc>{SITIO}/televisores</loc><lastmod>{lm}</lastmod><changefreq>daily</changefreq><priority>0.9</priority></url>']
    filas += [f'  <url><loc>{SITIO}{urls[x["id"]]}</loc><lastmod>{lm}</lastmod><changefreq>daily</changefreq><priority>0.7</priority></url>' for x in todos if x['os']]
    open(os.path.join(RAIZ, 'sitemap.xml'), 'w', encoding='utf-8').write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + '\n'.join(filas) + '\n</urlset>\n')
    print(f'Fichas: {len(todos)} equipos, {escritas} páginas nuevas o cambiadas. Imágenes para compartir nuevas: {n_og}. Historial: {len(hist)} equipos con datos.')


if __name__ == '__main__':
    main()
