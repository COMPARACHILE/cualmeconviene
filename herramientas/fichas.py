#!/usr/bin/env python3
"""Fichas de equipos de ¿Cuál me conviene?: una página por notebook, celular, tablet, televisor y consola.

  python3 herramientas/fichas.py
      Crea o actualiza notebook/<nombre>.html y celular/<nombre>.html con los precios de
      notebooks.html y celulares.html, el historial de precios (sale del historial de git),
      equipos parecidos y datos para Google. También rehace sitemap.xml y assets/fichas.js.

No hace falta correrlo a mano: el flujo .github/workflows/fichas.yml lo corre cada vez que
cambian los precios. Las direcciones de cada ficha quedan fijas en herramientas/fichas.json
para que los enlaces compartidos no se rompan si el nombre del equipo cambia.
"""
import datetime, hashlib, html, json, os, re, subprocess, sys, unicodedata

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


def imagen_tv(q):
    """Puntaje de imagen de un televisor, igual que en /televisores: tecnología, gama de la serie, Hz y resolución."""
    base = {'LED': 35, 'QLED': 50, 'NanoCell': 50, 'QNED': 58, 'Mini LED': 70, 'OLED': 85, 'Micro RGB': 90, 'Micro LED': 95}.get(q.get('panel'), 35)
    base += {'e': -5, 'a': 4, 't': 8}.get(q.get('gama'), 0)
    hz = q.get('hz') or 0
    base += 7 if hz >= 144 else 5 if hz >= 120 else 0
    base += {'8K': 3, '4K': 0, 'Full HD': -12}.get(q.get('res'), -20)
    return max(5, min(100, base))


def tflops(v):
    return f"{v:g}".replace('.', ',') + ' TFLOPS' if v else None


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
    for p in extra.get('cs', (None, None, []))[2]:
        out.append(dict(k='cs', eq=p, id=p['id'], marca=p['plat'], nombre=p['name']))
    for x in out:
        x['os'] = visibles(x['eq'])
    return out


def historial():
    """Precio más bajo de cada equipo por día, leído de las versiones guardadas en git."""
    h = {}
    try:
        log = subprocess.run(['git', '-C', RAIZ, 'log', '--format=%H %cI', '--', 'notebooks.html', 'celulares.html', 'tablets.html', 'televisores.html', 'consolas.html'],
                             capture_output=True, text=True, check=True).stdout.split('\n')
    except Exception:
        return h
    for linea in reversed([l for l in log if l.strip()]):
        sha, cuando = linea.split(' ', 1)
        dia = datetime.datetime.fromisoformat(cuando).astimezone(datetime.timezone(datetime.timedelta(hours=-3))).date()
        for archivo, ini, fin in (('notebooks.html', 'const NOTEBOOKS = ', '\n];'), ('celulares.html', 'const PHONES = ', ';\n'),
                                  ('tablets.html', 'const EQUIPOS = ', ';\n'), ('televisores.html', 'const EQUIPOS = ', ';\n'),
                                  ('consolas.html', 'const EQUIPOS = ', ';\n')):
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
    if x['k'] == 'cs':
        return {'tv': 'Consola para el TV', 'hibrida': 'Consola para el TV y portátil', 'portatil': 'Consola portátil'}.get(q.get('tipo'), 'Consola')
    if q.get('refurb'): return 'Reacondicionado'
    p = x['os'][0]['p'] if x['os'] else 0
    return 'Gama de entrada' if p <= 250000 else 'Gama media' if p <= 600000 else 'Gama alta'


def specs_cortas(x):
    q = x['eq']
    if x['k'] == 'nb':
        return ', '.join(t for t in [q.get('cpu'), q.get('gpu') if q.get('gpuTier') else 'gráficos integrados', f"{q.get('ram')} GB RAM", gb(q.get('ssd', 0)) + ' SSD', f"{q.get('size')}\""] if t)
    if x['k'] == 'tv':
        return ', '.join(t for t in [pulg(q.get('size')), q.get('res'), q.get('panel'), f"{q['hz']} Hz" if q.get('hz') else None, q.get('os')] if t)
    if x['k'] == 'cs':
        return ', '.join(t for t in [gb(q.get('gb')), tflops(q.get('tf')), f"incluye {q['juego']}" if q.get('juego') else None] if t)
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
                  ('Gama de la serie', {'e': 'Gama de entrada', 'm': 'Gama media', 'a': 'Gama alta', 't': 'Tope de línea'}.get(q.get('gama'))),
                  ('Puntaje de imagen', f"{imagen_tv(q)} de 100"),
                  ('Tasa de refresco', f"{q['hz']} Hz" if q.get('hz') else None), ('Sistema', q.get('os')), ('Modelo', q.get('model')),
                  ('Precio por pulgada', plata(x['os'][0]['p'] / q['size']) if x['os'] and q.get('size') else None)]
    elif x['k'] == 'cs':
        filas += [('Marca', q.get('plat')), ('Modelo', q.get('fam')), ('Cómo se juega', {'tv': 'Se conecta al TV', 'hibrida': 'En el TV y portátil', 'portatil': 'Solo portátil'}.get(q.get('tipo'))),
                  ('Potencia gráfica', (tflops(q.get('tf')) + (' en el TV' if q.get('tfp') else '') + (f" · {tflops(q['tfp'])} en modo portátil" if q.get('tfp') else '') + (' (estimada)' if q.get('fam') == 'Nintendo Switch 2' else '')) if q.get('tf') else None),
                  ('Almacenamiento', gb(q.get('gb'))), ('Juegos físicos', 'Lector de discos' if q.get('disco') else 'Cartuchos o digitales' if q.get('plat') == 'Nintendo' else 'Solo digitales'),
                  ('Resolución máxima', q.get('res')), ('Cuadros por segundo', f"hasta {q['fps']}" if q.get('fps') else None), ('Pantalla propia', q.get('pant')),
                  ('Juego incluido', q.get('juego')), ('Salió al mercado', q.get('year'))]
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


def pago(o):
    """Etiqueta corta del medio de pago ("con tarjeta" o "transferencia") en vez de un asterisco."""
    if not o.get('c'):
        return ''
    t = 'transferencia' if 'transfer' in (o.get('note') or '').lower() else 'con tarjeta'
    return f' <span class="pago" title="{e(o.get("note") or "")}">{t}</span>'


def tarjeta(x, fotos, url_ficha):
    f, _ = foto_de(x['id'], fotos)
    img = f'<img src="{e(f)}" alt="" width="480" height="480" loading="lazy" decoding="async" referrerpolicy="no-referrer">' if f else ''
    o = x['os'][0]
    return (f'<a class="par" href="{url_ficha}"><span class="parF">{img}</span><span class="parT">{e(x["nombre"])}</span>'
            f'<span class="parP">{plata(o["p"])}{pago(o)}</span><span class="parE">en {TIENDAS[o["s"]][0]}</span></a>')


CAMPANA = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg>'


def avisame(sin_stock):
    """Botón para pedir aviso por correo. Queda oculto hasta que assets/comentarios.js confirma que el inicio de sesión está activo."""
    txt = 'Avísame cuando vuelva a tener stock' if sin_stock else 'Avísame si baja de precio'
    return f'<button type="button" class="avisa" data-avisame{" data-sin" if sin_stock else ""} hidden>{CAMPANA}<span>{txt}</span></button><p class="avisaMsg" aria-live="polite" hidden></p>'


def comentarios(clave, nombre):
    """Sección de comentarios: se llena desde /api/comentarios con la dirección fija de la ficha."""
    return (f'<section class="bloque com" id="comentarios" aria-labelledby="t5" data-producto="{e(clave)}" data-nombre="{e(nombre)}">'
            f'<h2 id="t5">Comentarios <span class="comN"></span></h2>'
            f'<div class="comApp"><p class="comCarga">Cargando comentarios…</p></div>'
            f'<noscript><p class="nota">Activa JavaScript para leer y escribir comentarios.</p></noscript></section>')


def pagina(x, url, fotos, hist, todos, urls, hoy_txt, hoy):
    q, os_ = x['eq'], x['os']
    tipo = {'nb': 'Notebooks', 'ph': 'Celulares', 'tb': 'Tablets', 'tv': 'Televisores', 'cs': 'Consolas'}[x['k']]
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
        {'@type': 'Product', 'name': nombre, 'brand': {'@type': 'Brand', 'name': x['marca']}, 'category': {'nb': 'Notebook', 'ph': 'Celular', 'tb': 'Tablet', 'tv': 'Televisor', 'cs': 'Consola de videojuegos'}[x['k']],
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
                  f'<span class="tp">{plata(o["p"])}{pago(o)}{etiqueta}</span>'
                  f'<a class="tb" href="{e(o["url"])}" target="_blank" rel="nofollow sponsored noopener" data-id="{("" if x["k"] == "nb" else "c-") + x["id"]}" data-store="{o["s"]}">Ver en {nom}</a></li>')
    svg, frase = grafico(hist.get(x['id'], {}), os_[0]['p'] if os_ else None, hoy)
    # Parecidos: misma familia y precio cercano
    ref = os_[0]['p'] if os_ else (list(hist.get(x['id'], {}).values()) or [0])[-1]
    cands = [y for y in todos if y['id'] != x['id'] and y['k'] == x['k'] and y['os']]
    if x['k'] == 'nb':
        cands = [y for y in cands if (y['eq'].get('gpuTier', 0) >= 2) == (q.get('gpuTier', 0) >= 2)]
    elif x['k'] == 'ph':
        cands = [y for y in cands if bool(y['eq'].get('refurb')) == bool(q.get('refurb'))]
    elif x['k'] == 'cs':
        cands = [y for y in cands if (y['eq'].get('tipo') == 'tv') == (q.get('tipo') == 'tv')] or cands
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
        mejor = (f'<div class="mejor"><p class="et">Precio más bajo hoy</p><p class="precio">{plata(b["p"])}{pago(b)}</p>'
                 f'<p class="donde"><i style="background:{TIENDAS[b["s"]][1]}"></i>en {e(donde)}{(" · " + e(b["note"])) if b.get("note") else ""}</p>{ahorro}'
                 f'<a class="ir" href="{e(b["url"])}" target="_blank" rel="nofollow sponsored noopener" data-id="{("" if x["k"] == "nb" else "c-") + x["id"]}" data-store="{b["s"]}">Ir a {TIENDAS[b["s"]][0]}</a>{avisame(False)}</div>')
    else:
        mejor = f'<div class="mejor sin"><p class="et">Sin stock hoy</p><p>No lo encontramos disponible en las tiendas que revisamos. Abajo tienes equipos parecidos.</p>{avisame(True)}</div>'
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
<script defer src="/assets/comentarios.js"></script>
</head>
<body>
<header class="hd"><div class="hd-in wrap">
  <a class="hd-logo" href="/" aria-label="¿Cuál me conviene? Inicio"><img src="/assets/puma-icono-96.png" alt="" width="36" height="36" decoding="async"><span>¿Cuál me <em>conviene?</em></span></a>
  <form class="search" action="{lista}" role="search"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/></svg><input name="q" type="search" placeholder="Buscar {tipo.lower()}" aria-label="Buscar {tipo.lower()}" autocomplete="off"></form>
  <nav class="hd-cats" aria-label="Categorías">{''.join(f'<a href="/{c.lower()}"' + (' aria-current="page"' if c == tipo else '') + '>' + (f'<span class="lg">{c}</span><span class="sm">TV</span>' if c == 'Televisores' else c) + '</a>' for c in ('Notebooks', 'Celulares', 'Tablets', 'Televisores', 'Consolas'))}</nav>
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
    <p class="nota">Precios revisados el {hoy_txt}. Confirma el precio final en la tienda antes de pagar.</p>
  </section>
  <section class="bloque" aria-labelledby="t2">
    <h2 id="t2">Historial del precio más bajo</h2>
    {svg}
    <p class="frase">{e(frase)}</p>
  </section>
  <section class="bloque" aria-labelledby="t3">
    <h2 id="t3">Características</h2>
    <dl class="tec">{tabla_tecnica(x)}</dl>
    <p class="nota"><a href="{lista}?ver={e(x['id'])}">{'Compararla con otras' if x['k'] in ('cs', 'tb') else 'Compararlo con otros'} {tipo.lower()} en el comparador</a></p>
  </section>
  {comentarios(url.lstrip('/'), nombre)}
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


# ---------------- Guías: listas que se arman solas con los precios del día ----------------
# Cada guía responde algo que la gente busca en Google ("mejor notebook para estudiar hasta 500 mil")
# con los equipos y precios de hoy, y queda en /guia/<slug>. Para sumar otra, agrega una entrada aquí
# (por ahora solo notebooks: usan la misma fórmula de "Recomendados" del comparador).
GUIAS = [
    {
        'slug': 'mejor-notebook-para-estudiar-hasta-500-mil', 'k': 'nb', 'uso': 'estudio', 'hasta': 500000, 'n': 10,
        'titulo': 'Mejor notebook para estudiar hasta $500.000',
        'que': 'para estudiar', 'uso_txt': 'Estudio y oficina',
        'criterio': 'lo que más importa para estudiar: procesador, memoria RAM, almacenamiento y lo fácil que es llevarlo',
        'consejos': [
            ('Memoria RAM: 8 GB es el mínimo, 16 GB es lo cómodo',
             'Con 8 GB funcionan bien Word, Canva, las clases por Zoom o Meet y el navegador con varias pestañas. '
             'Si vas a usar programas más pesados o quieres que te dure varios años, apunta a 16 GB.'),
            ('Almacenamiento: siempre SSD',
             'Con un SSD el notebook enciende y abre los programas en segundos. 256 GB alcanzan si guardas tus archivos '
             'en Google Drive u OneDrive; 512 GB te dan más tranquilidad.'),
            ('Procesador: no necesitas el más potente',
             'Un Ryzen 3 o Core i3 sirve para lo básico. Un Ryzen 5, Core 5 o Core i5 se nota más rápido y aguanta más años. '
             'En cada equipo te mostramos su puntaje PassMark: mientras más alto, más rápido.'),
            ('Tamaño: 14" para llevar, 15,6" para la casa',
             'Si lo vas a llevar todos los días a clases, uno de 14" pesa menos. Si se queda en la casa, la pantalla de 15,6" '
             'es más cómoda para leer y escribir.'),
            ('Fíjate en el medio de pago',
             'Algunos precios son pagando con la tarjeta de la tienda o con transferencia. Lo marcamos en cada equipo para que '
             'compares lo mismo.'),
        ],
    },
]
TIPOS = {'nb': ('Notebooks', 'notebook', 'notebooks'), 'ph': ('Celulares', 'celular', 'celulares'), 'tb': ('Tablets', 'tablet', 'tablets'),
         'tv': ('Televisores', 'televisor', 'televisores'), 'cs': ('Consolas', 'consola', 'consolas')}


def miles(n):
    return f'{int(n):,}'.replace(',', '.')


def _js_obj(h, nombre):
    i = h.index(f'const {nombre} = ')
    return h[i:h.index('};', i)]


def datos_nb():
    """Potencia de cada procesador (PassMark) y pesos por uso, leídos de notebooks.html: la guía usa la misma fórmula que el comparador."""
    h = open(os.path.join(RAIZ, 'notebooks.html'), encoding='utf-8').read()
    db = {m.group(1): int(m.group(2)) for m in re.finditer(r"'([^']+)':\s*\{[^}]*?\bm:\s*(\d+)", _js_obj(h, 'CPUDB'))}
    of = dict(re.findall(r"\b(\w+):\s*'([^']+)'", _js_obj(h, 'CPU_OF')))
    tier = [int(v) for v in re.search(r'const TIER_POW = \[([^\]]*)\]', h).group(1).split(',')]
    pmax = int(re.search(r'const POW_MAX = (\d+)', h).group(1))
    pesos = {u: {k: float(v) for k, v in re.findall(r'(\w+):\s*([\d.]+)', w)}
             for u, w in re.findall(r'(\w+):\s*\{([^}]*)\}', _js_obj(h, 'USE_W'))}
    return dict(db=db, of=of, tier=tier, pmax=pmax, pesos=pesos)


def potencia(q, nb):
    """(puntaje PassMark, nombre del procesador, ¿es el modelo exacto?) igual que powOf() en notebooks.html."""
    modelo = nb['of'].get(q['id'])
    if modelo and modelo in nb['db']:
        return nb['db'][modelo], modelo, True
    t = nb['tier']
    return t[min(q.get('cpuTier', 0), len(t) - 1)], q.get('cpu'), False


def puntaje_nb(q, pot, nb, uso):
    """Igual que score() en notebooks.html con prioridad "equilibrado": 0 a 100 según el uso."""
    cl = lambda v: max(0.0, min(1.0, v))
    hz = q.get('hz')
    f = {'cpu': cl(pot / nb['pmax']), 'ram': 1 if q['ram'] >= 32 else .9 if q['ram'] >= 24 else .75 if q['ram'] >= 16 else .4,
         'ssd': 1 if q['ssd'] >= 1024 else .7 if q['ssd'] >= 512 else .35, 'gpu': q.get('gpuTier', 0) / 5,
         'size': cl((q['size'] - 13.5) / 3), 'hz': .5 if hz is None else 1 if hz >= 120 else .2, 'port': cl((16.5 - q['size']) / 3)}
    return int(cl(sum(w * f[k] for k, w in nb['pesos'][uso].items())) * 100 + .5)


def ranking_guia(g, todos, nb):
    """Equipos de la guía ordenados como "Recomendados" del comparador (puntaje² / precio). Sin repetir el mismo modelo."""
    cands, nombres = [], set()
    for x in todos:
        if x['k'] != g['k'] or not x['os'] or x['os'][0]['p'] > g['hasta']:
            continue
        pot, cpu, exacta = potencia(x['eq'], nb)
        sc = puntaje_nb(x['eq'], pot, nb, g['uso'])
        cands.append(dict(x=x, pot=pot, cpu=cpu, exacta=exacta, sc=sc, p=x['os'][0]['p']))
    cands.sort(key=lambda c: (-(c['sc'] ** 2 / c['p']), c['p']))
    out = []
    for c in cands:
        clave = slugify(c['x']['nombre'])
        if clave in nombres:
            continue
        nombres.add(clave); out.append(c)
    return out


def razones_nb(c, completo=False):
    """Por qué conviene. En la lista (completo=False) solo lo que distingue al equipo: la RAM y el SSD comunes ya salen en la ficha corta."""
    q, os_ = c['x']['eq'], c['x']['os']
    r = [f"Procesador {c['cpu']}: {miles(c['pot'])} puntos en PassMark" + ('' if c['exacta'] else ' (estimado por su gama)')]
    if len(os_) > 1 and os_[-1]['p'] > os_[0]['p']:
        r.append(f"{plata(os_[-1]['p'] - os_[0]['p'])} más barato en {TIENDAS[os_[0]['s']][0]} que en {TIENDAS[os_[-1]['s']][0]}")
    if q['ram'] >= 16:
        r.append(f"{q['ram']} GB de RAM: varias pestañas y programas abiertos sin trabarse")
    elif completo:
        r.append(f"{q['ram']} GB de RAM: alcanza para clases en línea, documentos y navegar")
    if q['ssd'] < 512:
        r.append(f"{gb(q['ssd'])} SSD: rápido, pero conviene guardar fotos y videos en la nube")
    elif q['ssd'] >= 1024 or completo:
        r.append(f"{gb(q['ssd'])} SSD: espacio de sobra para trabajos, fotos y programas")
    if q['size'] <= 14.5:
        r.append(f"Pantalla de {pulg(q['size'])}: más liviano para llevar a clases")
    elif q['size'] >= 15.5:
        r.append(f"Pantalla de {pulg(q['size'])}: más cómoda para leer y escribir")
    return r


def _ir_tienda(x, o, clase, texto):
    return (f'<a class="{clase}" href="{e(o["url"])}" target="_blank" rel="nofollow sponsored noopener" '
            f'data-id="{("" if x["k"] == "nb" else "c-") + x["id"]}" data-store="{o["s"]}" data-n="{e(x["nombre"])}">{texto}</a>')


def pagina_guia(g, cands, fotos, urls, hoy_txt, hoy):
    tipo, _, lista_slug = TIPOS[g['k']]
    lista = '/' + lista_slug
    url = f'/guia/{g["slug"]}'
    top = cands[:g['n']]
    tiendas = ', '.join(dict.fromkeys(TIENDAS[o['s']][0] for c in cands for o in c['x']['os'] if TIENDAS[o['s']][2] == 'tienda'))
    mes = f'{MESES[hoy.month - 1]} {hoy.year}'
    tit = f'{g["titulo"]} en Chile ({mes}) | ¿Cuál me conviene?'
    if top:
        u = top[0]
        desc = (f'Los {len(top)} notebooks {g["que"]} que más rinden por su precio hasta {plata(g["hasta"])}. Hoy el N°1 es el '
                f'{u["x"]["nombre"]} a {plata(u["p"])} en {TIENDAS[u["x"]["os"][0]["s"]][0]}. Precios revisados el {hoy_txt}.')
    else:
        desc = f'Los notebooks {g["que"]} que más rinden por su precio hasta {plata(g["hasta"])}, con los precios de hoy.'
    comp = f'{lista}?uso={g["uso"]}&amp;hasta={g["hasta"]}'
    ld = {'@context': 'https://schema.org', '@graph': [
        {'@type': 'ItemList', 'name': g['titulo'], 'url': SITIO + url, 'numberOfItems': len(top),
         'itemListElement': [{'@type': 'ListItem', 'position': k, 'url': SITIO + urls[c['x']['id']], 'name': c['x']['nombre']}
                             for k, c in enumerate(top, 1)]},
        {'@type': 'BreadcrumbList', 'itemListElement': [
            {'@type': 'ListItem', 'position': 1, 'name': 'Inicio', 'item': SITIO + '/'},
            {'@type': 'ListItem', 'position': 2, 'name': tipo, 'item': SITIO + lista},
            {'@type': 'ListItem', 'position': 3, 'name': g['titulo'], 'item': SITIO + url}]}]}

    def foto(c, cls='', alt=''):
        f, _ = foto_de(c['x']['id'], fotos)
        return f'<img src="{e(f)}" alt="{e(alt)}" width="480" height="480" {cls}decoding="async" referrerpolicy="no-referrer">' if f else ''

    def precio(c):
        o = c['x']['os']
        n = len(dict.fromkeys(z['s'] for z in o))
        return (f'<p class="precio">{plata(o[0]["p"])}{pago(o[0])}</p>'
                f'<p class="donde"><i style="background:{TIENDAS[o[0]["s"]][1]}"></i>en {TIENDAS[o[0]["s"]][0]}'
                f'{f" · {n} tiendas" if n > 1 else ""}</p>')

    foto_lazy = lambda c: foto(c, 'loading="lazy" ')
    raz = lambda c, k: ''.join(f'<li>{e(t)}</li>' for t in razones_nb(c, k > 3)[:k])
    if top:
        u = top[0]
        fu = urls[u['x']['id']]
        img_uno = foto(u, 'fetchpriority="high" ')
        uno = (f'<section class="gUno" aria-labelledby="g1T">'
               f'<a class="gUnoF" href="{fu}" tabindex="-1" aria-hidden="true">{img_uno}</a>'
               f'<div class="gUnoT"><p class="gEt"><img src="/assets/puma-sello.webp" alt="" width="28" height="28" decoding="async">La elección del puma</p>'
               f'<h2 id="g1T"><a href="{fu}">{e(u["x"]["nombre"])}</a></h2><p class="sp">{e(specs_cortas(u["x"]))}</p>'
               f'<ul class="gRaz">{raz(u, 5)}</ul><div class="gUnoP">{precio(u)}</div>'
               f'<div class="gBtns">{_ir_tienda(u["x"], u["x"]["os"][0], "ir", "Ir a " + TIENDAS[u["x"]["os"][0]["s"]][0])}'
               f'<a class="tb" href="{fu}">Ver el precio en cada tienda</a></div></div></section>')
        resto = ''.join(
            f'<li class="rkI"><a class="rkF" href="{urls[c["x"]["id"]]}" tabindex="-1" aria-hidden="true">{foto_lazy(c)}</a>'
            f'<div class="rkT"><p class="rkN">N° {k}</p><h3><a href="{urls[c["x"]["id"]]}">{e(c["x"]["nombre"])}</a></h3>'
            f'<p class="sp">{e(specs_cortas(c["x"]))}</p><ul class="gRaz">{raz(c, 3)}</ul></div>'
            f'<div class="rkP">{precio(c)}<a class="tb" href="{urls[c["x"]["id"]]}">Ver precios</a></div></li>'
            for k, c in enumerate(top[1:], 2))
        cuerpo = uno + (f'<section class="bloque" aria-labelledby="g2T"><h2 id="g2T">Del N° 2 al {len(top)}</h2><ol class="rk">{resto}</ol></section>' if resto else '')
    else:
        cuerpo = f'<p class="nota">Hoy no encontramos notebooks con stock bajo {plata(g["hasta"])}. Mira el <a href="{comp}">comparador</a>.</p>'
    tips = ''.join(f'<div><h3>{e(a)}</h3><p>{e(b)}</p></div>' for a, b in g['consejos'])
    otras = ''.join(f'<li><a href="/guia/{o["slug"]}">{e(o["titulo"])}</a></li>' for o in GUIAS if o['slug'] != g['slug'])
    return f'''<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(tit)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{SITIO}{url}">
<meta name="theme-color" content="#0E1533">
<meta property="og:type" content="article">
<meta property="og:locale" content="es_CL">
<meta property="og:site_name" content="¿Cuál me conviene?">
<meta property="og:title" content="{e(g['titulo'])}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{SITIO}{url}">
<meta property="og:image" content="{SITIO}/assets/og.png">
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
<header class="hd"><div class="hd-in wrap">
  <a class="hd-logo" href="/" aria-label="¿Cuál me conviene? Inicio"><img src="/assets/puma-icono-96.png" alt="" width="36" height="36" decoding="async"><span>¿Cuál me <em>conviene?</em></span></a>
  <form class="search" action="{lista}" role="search"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/></svg><input name="q" type="search" placeholder="Buscar {tipo.lower()}" aria-label="Buscar {tipo.lower()}" autocomplete="off"></form>
  <nav class="hd-cats" aria-label="Categorías">{''.join(f'<a href="/{c.lower()}"' + (' aria-current="page"' if c == tipo else '') + '>' + (f'<span class="lg">{c}</span><span class="sm">TV</span>' if c == 'Televisores' else c) + '</a>' for c in ('Notebooks', 'Celulares', 'Tablets', 'Televisores', 'Consolas'))}</nav>
</div></header>
<main class="wrap gPag">
  <nav class="migas" aria-label="Ruta"><a href="/">Inicio</a><span aria-hidden="true">›</span><a href="{lista}">{tipo}</a><span aria-hidden="true">›</span><span aria-current="page">Guía</span></nav>
  <div class="gCab">
    <p class="mc">Guía del puma · Actualizada el {fecha_larga(hoy)} de {hoy.year}</p>
    <h1>{e(g['titulo'])}</h1>
    <p class="sp">Revisamos los {len(cands)} notebooks que hoy cuestan {plata(g['hasta'])} o menos en {e(tiendas)}, y los ordenamos según {e(g['criterio'])}, frente a lo que cuestan. La lista se actualiza sola cada día con los precios nuevos.</p>
  </div>
  {cuerpo}
  <section class="bloque" aria-labelledby="g3T">
    <h2 id="g3T">Qué mirar en un notebook {e(g['que'])}</h2>
    <div class="gTips">{tips}</div>
  </section>
  <section class="bloque" aria-labelledby="g4T">
    <h2 id="g4T">Cómo armamos esta lista</h2>
    <p class="nota">Usamos la misma fórmula del comparador cuando eliges «{e(g['uso_txt'])}» y ordenas por «Recomendados»: combina la potencia del procesador (puntaje CPU Mark de PassMark), la memoria RAM, el almacenamiento y el tamaño de la pantalla, y la compara con el precio. No es una prueba de laboratorio ni asesoría profesional. Si un modelo aparece en varias versiones, mostramos la que más conviene.</p>
    <p class="nota">Precios revisados el {hoy_txt}: es el precio más bajo publicado en cada tienda, y algunos exigen la tarjeta de la tienda o transferencia. Confirma siempre en la tienda antes de pagar.</p>
    <p class="nota"><a href="{comp}">Ver todos los notebooks {e(g['que'])} hasta {plata(g['hasta'])} en el comparador</a></p>
  </section>
  {f'<section class="bloque" aria-labelledby="g5T"><h2 id="g5T">Otras guías</h2><ul class="gOtras">{otras}</ul></section>' if otras else ''}
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
  const body = JSON.stringify({{ id: a.dataset.id, s: a.dataset.store, n: a.dataset.n || '' }});
  try {{ navigator.sendBeacon ? navigator.sendBeacon('/api/clic', new Blob([body], {{ type: 'application/json' }})) : fetch('/api/clic', {{ method: 'POST', body, keepalive: true }}); }} catch (_) {{}}
}});
</script>
<script defer src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon='{{"token": "839f9ada4cc443eaa027f591d0400c85"}}'></script>
</body>
</html>
'''


# ---------------- Bloques escritos en las páginas que se arman en el navegador ----------------
# La portada y las categorías muestran los equipos con JavaScript. Estos bloques dejan escritos en el HTML
# los enlaces a cada ficha y a las guías, para que Google los encuentre sin esperar a que corra el código.
def _poner_bloque(archivo, nombre, contenido, antes_de):
    ruta = os.path.join(RAIZ, archivo)
    if not os.path.exists(ruta):
        return False
    h = open(ruta, encoding='utf-8').read()
    ini, fin = f'<!-- fichas:{nombre} -->', f'<!-- /fichas:{nombre} -->'
    bloque = ini + contenido + fin
    if ini in h and fin in h:
        i, j = h.index(ini), h.index(fin) + len(fin)
        nuevo = h[:i] + bloque + h[j:]
    elif antes_de in h:
        i = h.index(antes_de)
        nuevo = h[:i] + bloque + '\n\n' + h[i:]
    else:
        print(f'Aviso: no encontré dónde poner el bloque {nombre} en {archivo}')
        return False
    if nuevo != h:
        open(ruta, 'w', encoding='utf-8').write(nuevo)
        return True
    return False


def bloque_categoria(k, todos, urls, rankings):
    tipo, _, _ = TIPOS[k]
    eqs = sorted([x for x in todos if x['k'] == k and x['os']], key=lambda x: (x['os'][0]['p'], x['nombre']))
    guias = ''.join(f'<li><a href="/guia/{g["slug"]}"><img src="/assets/puma-sello.webp" alt="" width="32" height="32" loading="lazy" decoding="async">'
                    f'<span><strong>{e(g["titulo"])}</strong>'
                    + (f'<small>Hoy gana el {e(rankings[g["slug"]][0]["x"]["nombre"])}</small>' if rankings.get(g['slug']) else '')
                    + '</span></a></li>' for g in GUIAS if g['k'] == k)
    items = ''.join(f'<li><a href="{urls[x["id"]]}">{e(x["nombre"])}</a> <span>{plata(x["os"][0]["p"])}</span></li>' for x in eqs)
    return (f'<section class="indice" aria-label="Guías y lista completa de {tipo.lower()}">'
            + (f'<h2 class="idxT">Guías del puma</h2><ul class="idxGuias">{guias}</ul>' if guias else '')
            + f'<details class="idxTodos"><summary>Lista completa: {len(eqs)} {tipo.lower()} con su precio más bajo de hoy</summary>'
            f'<ul class="idxLista">{items}</ul></details></section>')


def bloque_portada(rankings, fotos, urls):
    tarjetas = ''
    for g in GUIAS:
        r = rankings.get(g['slug'])
        if not r:
            continue
        u = r[0]
        f, _ = foto_de(u['x']['id'], fotos)
        img = f'<img src="{e(f)}" alt="" width="480" height="480" loading="lazy" decoding="async" referrerpolicy="no-referrer">' if f else ''
        tarjetas += (f'<a class="guiaC" href="/guia/{g["slug"]}"><span class="guiaF">{img}</span><span class="guiaT">'
                     f'<small>{TIPOS[g["k"]][0]} · Guía del puma</small><strong>{e(g["titulo"])}</strong>'
                     f'<span>Hoy gana el {e(u["x"]["nombre"])}, a {plata(u["p"])}{pago(u["x"]["os"][0])} en {TIENDAS[u["x"]["os"][0]["s"]][0]}.</span>'
                     f'<b>Ver los {min(len(r), g["n"])} que más convienen</b></span></a>')
    if not tarjetas:
        return ''
    return ('<section class="sec wrap" aria-labelledby="guiasT"><div class="secCab"><div><h2 id="guiasT">Guías del puma</h2>'
            '<p>Los que más convienen según lo que necesitas. Se actualizan solas con los precios de cada día.</p></div></div>'
            f'<div class="guiasH">{tarjetas}</div></section>')


def main():
    todos = equipos()
    # Cada equipo necesita un id único en todo el sitio (fotos, fichas e historial usan el id sin la categoría)
    vistos, repetidos = {}, []
    for x in todos:
        if x['id'] in vistos:
            repetidos.append(f"{x['id']}: {vistos[x['id']]} / {x['nombre']}")
        vistos[x['id']] = x['nombre']
    if repetidos:
        print('ERROR: ids repetidos entre categorías (cambia el id del equipo nuevo):\n  ' + '\n  '.join(repetidos))
        sys.exit(1)
    slugs = json.load(open(SLUGS, encoding='utf-8')) if os.path.exists(SLUGS) else {}
    fotos = json.load(open(FOTOS, encoding='utf-8')) if os.path.exists(FOTOS) else {}
    usados = set(slugs.values())
    CARP = {'nb': '/notebook/', 'ph': '/celular/', 'tb': '/tablet/', 'tv': '/televisor/', 'cs': '/consola/'}
    # Equipos que salieron de las listas: si el mismo equipo vuelve con otro id, recupera su dirección,
    # y con ella sus comentarios y los avisos de precio que la gente pidió (se guardan por dirección).
    actuales = {x['id'] for x in todos}
    retirados = {s: i for i, s in slugs.items() if i not in actuales}
    for x in todos:
        if x['id'] in slugs:
            continue
        base = slugify((x['marca'] + ' ' + x['nombre']) if not x['nombre'].lower().startswith(x['marca'].lower()) else x['nombre'])
        if x['k'] == 'tv' and x['eq'].get('model') and slugify(x['eq']['model']) not in base:
            base = slugify(base + ' ' + x['eq']['model'])
        if x['eq'].get('refurb') and 'reacond' not in base: base += '-reacondicionado'
        if base in retirados and os.path.exists(os.path.join(RAIZ, CARP[x['k']].strip('/'), base + '.html')):
            viejo = retirados.pop(base)
            del slugs[viejo]
            slugs[x['id']] = base
            print(f'Volvió {x["nombre"]}: usa la dirección de antes (/{base}, id anterior {viejo}) con sus comentarios.')
            continue
        s, k = base, 2
        while s in usados: s, k = f'{base}-{k}', k + 1
        slugs[x['id']] = s; usados.add(s)
    json.dump(slugs, open(SLUGS, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
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
    for carpeta in ('notebook', 'celular', 'tablet', 'televisor', 'consola'):
        os.makedirs(os.path.join(RAIZ, carpeta), exist_ok=True)
    escritas = 0
    for x in todos:
        ruta = os.path.join(RAIZ, urls[x['id']].lstrip('/') + '.html')
        nuevo = pagina(x, urls[x['id']], fotos, hist, todos, urls, hoy_txt, hoy)
        viejo = open(ruta, encoding='utf-8').read() if os.path.exists(ruta) else ''
        if nuevo != viejo:
            open(ruta, 'w', encoding='utf-8').write(nuevo); escritas += 1
    # Guías (/guia/<slug>) y bloques con enlaces escritos en la portada y en cada categoría
    nb = datos_nb()
    rankings = {g['slug']: ranking_guia(g, todos, nb) for g in GUIAS}
    os.makedirs(os.path.join(RAIZ, 'guia'), exist_ok=True)
    for g in GUIAS:
        ruta = os.path.join(RAIZ, 'guia', g['slug'] + '.html')
        nuevo = pagina_guia(g, rankings[g['slug']], fotos, urls, hoy_txt, hoy)
        viejo = open(ruta, encoding='utf-8').read() if os.path.exists(ruta) else ''
        if nuevo != viejo:
            open(ruta, 'w', encoding='utf-8').write(nuevo); escritas += 1
    for k, (_, _, archivo) in TIPOS.items():
        if _poner_bloque(archivo + '.html', 'lista', bloque_categoria(k, todos, urls, rankings), '  <footer class="note">'):
            escritas += 1
    if _poner_bloque('index.html', 'guias', bloque_portada(rankings, fotos, urls), '  <section class="sec wrap" id="como"'):
        escritas += 1
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
    # Precio de hoy de cada ficha y bajadas del día, para los avisos por correo (functions/api/revisar-avisos.js).
    # Se ordena por dirección de ficha: así los avisos y comentarios siguen al equipo aunque cambie su id.
    eqs = {urls[x['id']].lstrip('/'): [x['os'][0]['p'] if x['os'] else None, x['nombre'], x['id'], TIENDAS[x['os'][0]['s']][0] if x['os'] else '']
           for x in todos}
    baj = []
    for x in todos:
        h = hist.get(x['id'], {})
        previos = [d for d in h if d < hoy]
        if not x['os'] or not previos:
            continue
        antes, ahora = h[max(previos)], x['os'][0]['p']
        # Al menos 3% y $3.000 menos que en la revisión anterior; una caída de más de 60% suele ser un error de la tienda
        if antes and ahora <= antes * 0.97 and antes - ahora >= 3000 and ahora >= antes * 0.4:
            baj.append(((antes - ahora) / antes, urls[x['id']].lstrip('/'), antes, ahora))
    baj.sort(key=lambda b: -b[0])
    av = {'dia': hoy.isoformat(), 'equipos': eqs, 'bajadas': [[c, a, n] for _, c, a, n in baj[:12]]}
    av = {'v': hashlib.md5(json.dumps(av, sort_keys=True).encode()).hexdigest()[:12], **av}
    open(os.path.join(RAIZ, 'assets', 'avisos.json'), 'w', encoding='utf-8').write(json.dumps(av, ensure_ascii=False, separators=(',', ':')))
    # Mapa del sitio para Google
    lm = hoy.isoformat()
    filas = [f'  <url><loc>{SITIO}/</loc><lastmod>{lm}</lastmod><changefreq>daily</changefreq><priority>1.0</priority></url>',
             f'  <url><loc>{SITIO}/notebooks</loc><lastmod>{lm}</lastmod><changefreq>daily</changefreq><priority>0.9</priority></url>',
             f'  <url><loc>{SITIO}/celulares</loc><lastmod>{lm}</lastmod><changefreq>daily</changefreq><priority>0.9</priority></url>',
             f'  <url><loc>{SITIO}/tablets</loc><lastmod>{lm}</lastmod><changefreq>daily</changefreq><priority>0.9</priority></url>',
             f'  <url><loc>{SITIO}/televisores</loc><lastmod>{lm}</lastmod><changefreq>daily</changefreq><priority>0.9</priority></url>',
             f'  <url><loc>{SITIO}/consolas</loc><lastmod>{lm}</lastmod><changefreq>daily</changefreq><priority>0.9</priority></url>']
    filas += [f'  <url><loc>{SITIO}/guia/{g["slug"]}</loc><lastmod>{lm}</lastmod><changefreq>daily</changefreq><priority>0.8</priority></url>' for g in GUIAS]
    filas += [f'  <url><loc>{SITIO}{urls[x["id"]]}</loc><lastmod>{lm}</lastmod><changefreq>daily</changefreq><priority>0.7</priority></url>' for x in todos if x['os']]
    open(os.path.join(RAIZ, 'sitemap.xml'), 'w', encoding='utf-8').write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + '\n'.join(filas) + '\n</urlset>\n')
    print(f'Fichas: {len(todos)} equipos, {escritas} páginas nuevas o cambiadas. Imágenes para compartir nuevas: {n_og}. Historial: {len(hist)} equipos con datos. Bajadas del día: {len(baj)}.')


if __name__ == '__main__':
    main()
