#!/usr/bin/env python3
"""Fichas de equipos de ¿Cuál me conviene?: una página por notebook, celular, tablet, televisor, consola,
lavadora o secadora, aspiradora, batidora y cafetera.

  python3 herramientas/fichas.py
      Crea o actualiza notebook/<nombre>.html y celular/<nombre>.html con los precios de
      notebooks.html y celulares.html, el historial de precios (sale del historial de git),
      equipos parecidos y datos para Google. También rehace sitemap.xml y assets/fichas.js.

No hace falta correrlo a mano: el flujo .github/workflows/fichas.yml lo corre cada vez que
cambian los precios. Las direcciones de cada ficha quedan fijas en herramientas/fichas.json
para que los enlaces compartidos no se rompan si el nombre del equipo cambia.
"""
import datetime, hashlib, html, json, os, re, statistics, subprocess, sys, unicodedata, urllib.parse

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
# Tiendas oficiales de cada marca (Samsung, LG, Xiaomi, Apple, HP, Nespresso, Dolce Gusto): se definen en precios.OFICIALES
TIENDAS.update({k: (v['name'], v['color'], 'tienda') for k, v in precios.OFICIALES.items()})
# Categorías: k -> (título, página de la lista, carpeta de las fichas, nombre en el menú, femenino)
CATS = {
    'nb': ('Notebooks', 'notebooks', 'notebook', 'Notebooks', False), 'ph': ('Celulares', 'celulares', 'celular', 'Celulares', False),
    'tb': ('Tablets', 'tablets', 'tablet', 'Tablets', True), 'tv': ('Televisores', 'televisores', 'televisor', 'Televisores', False),
    'cs': ('Consolas', 'consolas', 'consola', 'Consolas', True), 'lv': ('Lavadoras y secadoras', 'lavadoras', 'lavadora', 'Lavado', True),
    'as': ('Aspiradoras', 'aspiradoras', 'aspiradora', 'Aspiradoras', True), 'bt': ('Batidoras', 'batidoras', 'batidora', 'Batidoras', True),
    'cf': ('Cafeteras', 'cafeteras', 'cafetera', 'Cafeteras', True),
    'ac': ('Aires acondicionados', 'aires-acondicionados', 'aire-acondicionado', 'Aires', False),
}


def menu(actual):
    """Menú de categorías de la cabecera (actual = página de la lista: 'notebooks', 'lavadoras'...)."""
    return ''.join(f'<a href="/{c[1]}"' + (' aria-current="page"' if c[1] == actual else '') + '>'
                   + ('<span class="lg">Televisores</span><span class="sm">TV</span>' if c[3] == 'Televisores' else c[3]) + '</a>' for c in CATS.values())


# Lavado, aspiradoras, batidoras y cafeteras
TIPO_LV = {'superior': 'Lavadora de carga superior', 'frontal': 'Lavadora de carga frontal', 'lavaseca': 'Lavadora-secadora',
           'torre': 'Lavadora-secadora en torre', 'secadora': 'Secadora'}
TIPO_AS = {'robot': 'Aspiradora robot', 'vertical': 'Aspiradora vertical', 'arrastre': 'Aspiradora de arrastre'}
TIPO_BT = {'pedestal': 'Batidora de pedestal', 'mano': 'Batidora de mano', 'inmersion': 'Batidora de inmersión'}
TIPO_AC = {'split': 'Aire acondicionado split muro', 'portatil': 'Aire acondicionado portátil'}
EF_AC = {'A+++': 15, 'A++': 15, 'A+': 15, 'A': 12, 'B': 8, 'C': 5, 'D': 2, 'E': 2, 'F': 2, 'G': 2}


def puntaje_ac(q):
    """Puntaje del puma de un aire acondicionado (0 a 100), igual que en /aires-acondicionados:
    inverter 35, split 25, frío y calor 15, etiqueta de eficiencia hasta 15 (sin dato 6) y Wi-Fi 10."""
    return ((35 if q.get('inv') else 0) + (25 if q.get('tipo') == 'split' else 0) + (15 if q.get('calor') else 0)
            + EF_AC.get(q.get('ef') or '', 6) + (10 if q.get('wifi') else 0))


def btu(v):
    return f'{int(v):,}'.replace(',', '.') + ' BTU'


def tipo_lv(q):
    return q.get('carga') if q.get('tipo') == 'lavadora' else q.get('tipo')


def num(v):
    return f'{v:g}'.replace('.', ',') if isinstance(v, (int, float)) else str(v)


def cap_lv(q):
    if q.get('tipo') == 'secadora': return f"seca {num(q['kgs'])} kg"
    if q.get('kgs'): return f"lava {num(q['kg'])} kg y seca {num(q['kgs'])} kg"
    return f"{num(q['kg'])} kg"


def ext_cf(q):
    return 'Centrifusión (la cápsula gira)' if q.get('ext') == 'centrifusion' else f"Presión de {q.get('bar')} bar"

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
def cupon_vigente(q):
    return bool(q and q.get('c')) and datetime.datetime.fromisoformat(q['v'].replace('Z', '+00:00')) > datetime.datetime.now(datetime.timezone.utc)


def con_cupon(o):
    """El precio con cupón es el precio principal (igual que CMC.usarCupones de assets/cmc-ui.js).
    p0 guarda el precio de la tienda: historial, mínimos y avisos siguen con ese."""
    q = o.get('cup')
    if not cupon_vigente(q) or not q.get('pc') or q['pc'] >= o['p']:
        return o
    n = {k: v for k, v in o.items() if k != 'c'}
    n.update(p=q['pc'], p0=o['p'], c0=o.get('c'), note=f"Con cupón {q['c']}")
    return n


def visibles(eq):
    return sorted([con_cupon(o) for o in eq['offers'] if not o.get('x') and o.get('p')], key=lambda o: o['p'])


def de_tienda(x):
    """La oferta más barata sin contar cupones (historial, mínimos históricos y avisos)."""
    return min(x['os'], key=lambda o: o.get('p0', o['p']))


def precio_tienda(x):
    o = de_tienda(x)
    return o.get('p0', o['p'])


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
    for k in ('lv', 'as', 'bt', 'cf', 'ac'):
        for p in extra.get(k, (None, None, []))[2]:
            out.append(dict(k=k, eq=p, id=p['id'], marca=p['brand'], nombre=p['name']))
    for x in out:
        x['os'] = visibles(x['eq'])
    return out


SERIE_TIENDA = {}  # (id del equipo, tienda) -> {día: precio sin cupón}; la llena historial()


def historial():
    """Precio más bajo de cada equipo por día, leído de las versiones guardadas en git."""
    h = {}
    try:
        log = subprocess.run(['git', '-C', RAIZ, 'log', '--format=%H %cI', '--', 'notebooks.html', 'celulares.html'] + [a for a, _ in precios.EXTRA.values()],
                             capture_output=True, text=True, check=True).stdout.split('\n')
    except Exception:
        return h
    for linea in reversed([l for l in log if l.strip()]):
        sha, cuando = linea.split(' ', 1)
        dia = datetime.datetime.fromisoformat(cuando).astimezone(datetime.timezone(datetime.timedelta(hours=-3))).date()
        for archivo, ini, fin in [('notebooks.html', 'const NOTEBOOKS = ', '\n];'), ('celulares.html', 'const PHONES = ', ';\n')] + \
                                 [(a, 'const EQUIPOS = ', ';\n') for a, _ in precios.EXTRA.values()]:
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
                    for o in x.get('offers', []):
                        if not o.get('x') and o.get('p'):
                            SERIE_TIENDA.setdefault((x['id'], o['s']), {})[d_rev] = o['p']
            except Exception:
                continue
    return h


def minimos_historicos(todos, hist, hoy):
    """Equipos que hoy están en su precio más bajo desde que los seguimos: {id: (precio, primer día con precio)}.
    Pide al menos 2 días anteriores con precio, que nunca haya estado más barato y que hoy esté al menos 3% y
    $3.000 bajo su precio habitual (la mediana de los días anteriores). Así no se marca un equipo cuyo precio
    nunca se movió, y el sello se va solo cuando el precio sube o cuando el precio bajo pasa a ser el de siempre."""
    out = {}
    for x in todos:
        if not x['os']:
            continue
        h = hist.get(x['id'], {})
        antes = [v for d, v in h.items() if d < hoy]
        if len(antes) < 2:
            continue
        p, med = precio_tienda(x), statistics.median(antes)
        if p <= min(antes) and med - p >= max(med * 0.03, 3000):
            out[x['id']] = (p, min(h))
    return out


def sello_minimo(desde):
    """Sello "Mínimo histórico": mismo formato que el del puma (assets/cmc.css, clase minimo)."""
    return (f'<span class="minimo" title="El precio más bajo que hemos visto para este equipo desde el {fecha_larga(desde)}">'
            f'<img src="/assets/puma-sello.webp" alt="" width="26" height="26" decoding="async">'
            f'<span>Mínimo histórico<small>El más bajo desde el {fecha_larga(desde)}</small></span></span>')


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
    if x['k'] == 'lv': return TIPO_LV.get(tipo_lv(q), 'Lavadora')
    if x['k'] == 'as': return TIPO_AS.get(q.get('tipo'), 'Aspiradora')
    if x['k'] == 'bt': return TIPO_BT.get(q.get('tipo'), 'Batidora')
    if x['k'] == 'cf': return 'Cafetera de cápsulas ' + q.get('sis', '')
    if x['k'] == 'ac': return TIPO_AC.get(q.get('tipo'), 'Aire acondicionado')
    if q.get('refurb'): return 'Reacondicionado'
    p = precio_tienda(x) if x['os'] else 0
    return 'Gama de entrada' if p <= 250000 else 'Gama media' if p <= 600000 else 'Gama alta'


def specs_cortas(x):
    q = x['eq']
    if x['k'] == 'nb':
        return ', '.join(t for t in [q.get('cpu'), q.get('gpu') if q.get('gpuTier') else 'gráficos integrados', f"{q.get('ram')} GB RAM", gb(q.get('ssd', 0)) + ' SSD', f"{q.get('size')}\""] if t)
    if x['k'] == 'tv':
        return ', '.join(t for t in [pulg(q.get('size')), q.get('res'), q.get('panel'), f"{q['hz']} Hz" if q.get('hz') else None, q.get('os')] if t)
    if x['k'] == 'cs':
        return ', '.join(t for t in [gb(q.get('gb')), tflops(q.get('tf')), f"incluye {q['juego']}" if q.get('juego') else None] if t)
    if x['k'] == 'lv':
        return ', '.join(t for t in [cap_lv(q), f"eficiencia {q['ef']}" if q.get('ef') else None, 'motor inverter' if q.get('inv') else None,
                                     f"{q['rpm']} rpm" if q.get('rpm') else None, 'vapor' if q.get('vapor') else None] if t)
    if x['k'] == 'as':
        return ', '.join(t for t in [q.get('sub'), f"succión {miles(q['pa'])} Pa" if q.get('pa') else None, f"succión {q['aw']} AW" if q.get('aw') else None,
                                     f"motor {miles(q['w'])} W" if q.get('w') else None, f"depósito {num(q['dep'])} L" if q.get('dep') else None,
                                     f"hasta {q['aut']} min" if q.get('aut') else None] if t)
    if x['k'] == 'bt':
        return ', '.join(t for t in [f"{miles(q['w'])} W" if q.get('w') else None, f"{q['vel']} velocidades" if q.get('vel') else None,
                                     (('vaso ' if q.get('tipo') == 'inmersion' else 'bol ') + num(q['bowl']) + ' L') if q.get('bowl') else None,
                                     'bol de acero' if q.get('metal') else None] if t)
    if x['k'] == 'ac':
        return ', '.join(t for t in [btu(q['btu']), 'inverter' if q.get('inv') else 'sin inverter', 'frío y calor' if q.get('calor') else 'solo frío',
                                     f"eficiencia {q['ef']}" if q.get('ef') else None, 'Wi-Fi' if q.get('wifi') else None] if t)
    if x['k'] == 'cf':
        return ', '.join(t for t in [ext_cf(q), f"tazas de hasta {q['ml']} ml" if q.get('ml') else 'tamaño según la cápsula',
                                     f"estanque {num(q['dep'])} L" if q.get('dep') else None, q.get('leche')] if t)
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
    elif x['k'] == 'lv':
        cap = q.get('kg') or q.get('kgs')
        filas += [('Tipo', TIPO_LV.get(tipo_lv(q))), ('Capacidad de lavado', f"{num(q['kg'])} kg" if q.get('kg') else None),
                  ('Capacidad de secado', f"{num(q['kgs'])} kg" if q.get('kgs') else None),
                  ('Precio por kilo', plata(x['os'][0]['p'] / cap) if x['os'] and cap else None),
                  ('Eficiencia energética', f"Clase {q['ef']}" if q.get('ef') else 'La tienda no la informa'),
                  ('Motor', 'Inverter' if q.get('inv') else 'Convencional' if q.get('inv') == 0 else None),
                  ('Centrifugado', f"{q['rpm']} rpm" if q.get('rpm') else None), ('Cómo seca', q.get('sec')),
                  ('Funcionamiento', 'Semiautomática' if q.get('auto') == 0 else None),
                  ('Vapor', 'Sí' if q.get('vapor') else None), ('Wi-Fi', 'Sí' if q.get('wifi') else None), ('Modelo', q.get('model'))]
    elif x['k'] == 'as':
        filas += [('Tipo', TIPO_AS.get(q.get('tipo'))), ('Formato', q.get('sub')),
                  ('Succión (pascales)', f"{miles(q['pa'])} Pa" if q.get('pa') else None), ('Succión (air watts)', f"{q['aw']} AW" if q.get('aw') else None),
                  ('Potencia del motor', f"{miles(q['w'])} W" if q.get('w') else None), ('Depósito', f"{num(q['dep'])} L" if q.get('dep') else None),
                  ('Autonomía', f"hasta {q['aut']} min" if q.get('aut') else None), ('Trapea', 'Sí' if q.get('mopa') else None),
                  ('Base', q.get('base')), ('Cómo se ubica', q.get('nav')), ('Modelo', q.get('model'))]
    elif x['k'] == 'bt':
        filas += [('Tipo', TIPO_BT.get(q.get('tipo'))), ('Potencia', f"{miles(q['w'])} W" if q.get('w') else None),
                  ('Velocidades', q.get('vel')), ('Bol o vaso', f"{num(q['bowl'])} L" if q.get('bowl') else None),
                  ('Bol de acero', 'Sí' if q.get('metal') else None), ('Turbo', 'Sí' if q.get('turbo') else None), ('Modelo', q.get('model'))]
    elif x['k'] == 'ac':
        filas += [('Tipo', TIPO_AC.get(q.get('tipo'))), ('Puntaje del puma', f"{puntaje_ac(q)} de 100"),
                  ('Capacidad', btu(q['btu'])), ('Para una pieza de', f"unos {round(q['btu'] / 480 / 5) * 5} m² (techo de 2,4 m)"),
                  ('Precio por 1.000 BTU', plata(x['os'][0]['p'] / q['btu'] * 1000) if x['os'] else None),
                  ('Compresor', 'Inverter' if q.get('inv') else 'Convencional (prende y apaga)'),
                  ('Frío y calor', 'Sí' if q.get('calor') else 'Solo frío'),
                  ('Eficiencia energética', f"Clase {q['ef']}" if q.get('ef') else 'La tienda no la informa'),
                  ('Wi-Fi', 'Sí' if q.get('wifi') else 'No'), ('Modelo', q.get('model'))]
    elif x['k'] == 'cf':
        filas += [('Sistema', q.get('sis')), ('Cómo extrae el café', ext_cf(q)),
                  ('Taza más grande', f"{q['ml']} ml" if q.get('ml') else 'Según la cápsula'), ('Tamaños de taza', q.get('tam')),
                  ('Estanque de agua', f"{num(q['dep'])} L" if q.get('dep') else None), ('Leche', q.get('leche') or 'No'),
                  ('Cápsulas', q.get('compat') or {'Nespresso Original': 'Nespresso Original y compatibles de otras marcas', 'Nespresso Vertuo': 'Solo Nespresso Vertuo',
                                                   'Dolce Gusto': 'Nescafé Dolce Gusto y compatibles'}.get(q.get('sis'))),
                  ('Modelo', q.get('model'))]
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


def cupon(o):
    """Línea del cupón de la oferta (mismo texto que CMC.cupon de assets/cmc-ui.js). cmc.js la quita al vencer."""
    q = o.get('cup')
    if not q or not q.get('c'):
        return ''
    lim = datetime.datetime.fromisoformat(q['v'].replace('Z', '+00:00'))
    if lim <= datetime.datetime.now(datetime.timezone.utc):
        return ''
    cl = lim.astimezone(datetime.timezone(datetime.timedelta(hours=-3)))
    meses = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sept', 'oct', 'nov', 'dic']
    if cl.hour == 0 and cl.minute == 0:
        d = cl - datetime.timedelta(minutes=1)
        fecha = f'hasta el {d.day} {meses[d.month - 1]}'
    else:
        fecha = f'vence el {cl.day} {meses[cl.month - 1]}, {cl.hour}:{cl.minute:02d}'
    if q.get('sf'):
        fecha = 'la tienda no informa hasta cuándo'
    tienda = TIENDAS[o['s']][0]
    que = f'Cupón de la app de {tienda}' if q.get('app') else f"{q.get('l') or 'Cupón'} en {tienda}"
    if o.get('p0'):
        que += ' · sin cupón ' + plata(o['p0'])
    base = 'Calculado sobre el precio sin tarjeta. ' if o.get('p0') and o.get('c0') else ('Calculado sobre el precio publicado. ' if o.get('p0') else '')
    return (f'<span class="c3-cupon" data-vence="{e(q["v"])}"><button type="button" class="cupon" data-cupon="{e(q["c"])}" aria-label="Copiar cupón {e(q["c"])}" title="Copiar">{e(q["c"])}</button>'
            f'<span title="{e(base + "El descuento se aplica al pagar y se confirma en la tienda.")}">{e(que)} · {fecha}</span></span>')


def pago(o):
    """Etiqueta corta del medio de pago ("con tarjeta" o "transferencia") en vez de un asterisco."""
    if o.get('p0'):
        q = o['cup']
        return f' <span class="pago cup" data-vence="{e(q["v"])}" title="{e("Precio con el cupón " + q["c"] + ". Sin cupón " + plata(o["p0"]))}">con cupón</span>'
    if not o.get('c'):
        return ''
    t = 'transferencia' if 'transfer' in (o.get('note') or '').lower() else 'con tarjeta'
    return f' <span class="pago" title="{e(o.get("note") or "")}">{t}</span>'


def precio_html(o):
    """Precio de la oferta. Si es con cupón, cmc.js vuelve al precio de la tienda cuando el cupón vence."""
    if o.get('p0'):
        return f'<span data-hasta="{e(o["cup"]["v"])}" data-sin="{plata(o["p0"])}">{plata(o["p"])}</span>'
    return plata(o['p'])


def tarjeta(x, fotos, url_ficha):
    f, _ = foto_de(x['id'], fotos)
    img = f'<img src="{e(f)}" alt="" width="480" height="480" loading="lazy" decoding="async" referrerpolicy="no-referrer">' if f else ''
    o = x['os'][0]
    return (f'<a class="par" href="{url_ficha}"><span class="parF">{img}</span><span class="parT">{e(x["nombre"])}</span>'
            f'<span class="parP">{precio_html(o)}{pago(o)}</span><span class="parE">en {TIENDAS[o["s"]][0]}</span></a>')


CAMPANA = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg>'


def avisame(sin_stock):
    """Botón para pedir aviso por correo. Queda oculto hasta que assets/comentarios.js confirma que el inicio de sesión está activo."""
    txt = 'Avísame cuando vuelva a tener stock' if sin_stock else 'Avísame si baja de precio'
    return f'<button type="button" class="avisa" data-avisame{" data-sin" if sin_stock else ""} hidden>{CAMPANA}<span>{txt}</span></button><p class="avisaMsg" aria-live="polite" hidden></p>'


WSP = ('<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" fill="currentColor"><path d="M12.04 2a9.9 9.9 0 0 0-8.43 15.1L2 22l5.03-1.58A9.9 9.9 0 1 0 12.04 2Zm0 1.8a8.1 8.1 0 1 1-4.3 14.96l-.3-.19-2.98.94.97-2.9-.2-.31A8.1 8.1 0 0 1 12.04 3.8Zm-3.2 3.9c-.17 0-.45.06-.69.32-.24.26-.9.88-.9 2.15 0 1.26.92 2.49 1.05 2.66.13.17 1.8 2.86 4.45 3.9 2.2.87 2.65.7 3.13.65.48-.04 1.54-.63 1.76-1.24.22-.6.22-1.13.15-1.24-.06-.1-.24-.17-.5-.3-.27-.13-1.54-.76-1.78-.85-.24-.09-.41-.13-.59.13-.17.26-.68.85-.83 1.02-.15.18-.3.2-.57.07-.26-.13-1.1-.4-2.1-1.3-.78-.69-1.3-1.55-1.45-1.8-.15-.27-.02-.4.11-.53.12-.12.26-.3.4-.46.13-.15.17-.26.26-.44.09-.17.04-.33-.02-.46-.07-.13-.59-1.4-.8-1.92-.2-.5-.42-.43-.59-.44h-.5Z"/></svg>')


def compartir(texto, ruta, titulo):
    """Botón "Compartir por WhatsApp": enlace de wa.me (sirve sin JavaScript y sin número de la página).
    En el celular assets/cmc.js abre el menú de compartir del teléfono si existe (WhatsApp, Instagram, etc.)."""
    enlace = f'{SITIO}{ruta}?u=wsp'
    href = 'https://wa.me/?text=' + urllib.parse.quote(f'{texto} {enlace}')
    return (f'<a class="comp" href="{e(href)}" target="_blank" rel="noopener" data-compartir data-titulo="{e(titulo)}" data-texto="{e(texto)}" '
            f'data-url="{e(enlace)}">{WSP}<span>Compartir por WhatsApp</span></a>')


def comentarios(clave, nombre):
    """Sección de comentarios: se llena desde /api/comentarios con la dirección fija de la ficha."""
    return (f'<section class="bloque com" id="comentarios" aria-labelledby="t5" data-producto="{e(clave)}" data-nombre="{e(nombre)}">'
            f'<h2 id="t5">Comentarios <span class="comN"></span></h2>'
            f'<div class="comApp"><p class="comCarga">Cargando comentarios…</p></div>'
            f'<noscript><p class="nota">Activa JavaScript para leer y escribir comentarios.</p></noscript></section>')


def pagina(x, url, fotos, hist, todos, urls, hoy_txt, hoy, mins=None):
    q, os_ = x['eq'], x['os']
    tipo, lista = CATS[x['k']][0], '/' + CATS[x['k']][1]
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
        {'@type': 'Product', 'name': nombre, 'brand': {'@type': 'Brand', 'name': x['marca']}, 'category': {'nb': 'Notebook', 'ph': 'Celular', 'tb': 'Tablet', 'tv': 'Televisor', 'cs': 'Consola de videojuegos'}.get(x['k']) or categoria(x),
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
                  f'{" <small>operadora</small>" if canal == "operadora" else ""}{f"<em>{e(extra)}</em>" if extra else ""}{cupon(o)}</span></span>'
                  f'<span class="tp">{precio_html(o)}{pago(o)}{etiqueta}</span>'
                  f'<a class="tb" href="{e(o["url"])}" target="_blank" rel="nofollow sponsored noopener" data-id="{("" if x["k"] == "nb" else "c-") + x["id"]}" data-store="{o["s"]}">Ver en {nom}</a></li>')
    svg, frase = grafico(hist.get(x['id'], {}), precio_tienda(x) if os_ else None, hoy)
    if os_ and os_[0].get('p0'):
        frase += ' El gráfico no incluye cupones.'
    # Parecidos: misma familia y precio cercano
    ref = os_[0]['p'] if os_ else (list(hist.get(x['id'], {}).values()) or [0])[-1]
    cands = [y for y in todos if y['id'] != x['id'] and y['k'] == x['k'] and y['os']]
    if x['k'] == 'nb':
        cands = [y for y in cands if (y['eq'].get('gpuTier', 0) >= 2) == (q.get('gpuTier', 0) >= 2)]
    elif x['k'] == 'ph':
        cands = [y for y in cands if bool(y['eq'].get('refurb')) == bool(q.get('refurb'))]
    elif x['k'] == 'cs':
        cands = [y for y in cands if (y['eq'].get('tipo') == 'tv') == (q.get('tipo') == 'tv')] or cands
    elif x['k'] in ('lv', 'as', 'bt', 'cf'):
        cands = [y for y in cands if categoria(y) == categoria(x)] or cands
    elif x['k'] == 'ac':
        cands = [y for y in cands if categoria(y) == categoria(x) and abs(y['eq']['btu'] - q['btu']) <= 3000] or [y for y in cands if categoria(y) == categoria(x)] or cands
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
        mh = (mins or {}).get(x['id'])
        txt_comp = f'Mira este {nombre}: desde {plata(precio_tienda(x))} en {TIENDAS[de_tienda(x)["s"]][0]}. Compara las tiendas aquí:'
        mejor = (f'<div class="mejor">{sello_minimo(mh[1]) if mh and mh[0] >= b["p"] else ""}<p class="et">Precio más bajo hoy</p><p class="precio">{precio_html(b)}{pago(b)}</p>'
                 f'<p class="donde"><i style="background:{TIENDAS[b["s"]][1]}"></i>en {e(donde)}{(" · " + e(b["note"])) if b.get("note") else ""}</p>{next((c for c in map(cupon, os_) if c), "")}{ahorro}'
                 f'<a class="ir" href="{e(b["url"])}" target="_blank" rel="nofollow sponsored noopener" data-id="{("" if x["k"] == "nb" else "c-") + x["id"]}" data-store="{b["s"]}">Ir a {TIENDAS[b["s"]][0]}</a>{avisame(False)}'
                 f'{compartir(txt_comp, url, nombre)}</div>')
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
  <nav class="hd-cats" aria-label="Categorías">{menu(lista.strip('/'))}</nav>
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
    <p class="nota"><a href="{lista}?ver={e(x['id'])}">{'Compararla con otras' if CATS[x['k']][4] else 'Compararlo con otros'} {tipo.lower()} en el comparador</a></p>
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
TIPOS = {k: (c[0], c[2], c[1]) for k, c in CATS.items()}


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
        return (f'<p class="precio">{precio_html(o[0])}{pago(o[0])}</p>'
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
  <nav class="hd-cats" aria-label="Categorías">{menu(lista.strip('/'))}</nav>
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
def bajadas(todos, hist, hoy, urls):
    """Equipos que hoy cuestan menos que en la revisión anterior (sin contar cupones), de mayor a menor porcentaje.
    Al menos 3% y $3.000 menos; una caída de más de 60% suele ser un error de la tienda y no se publica."""
    baj = []
    for x in todos:
        h = hist.get(x['id'], {})
        previos = [d for d in h if d < hoy]
        if not x['os'] or not previos:
            continue
        antes, ahora = h[max(previos)], precio_tienda(x)
        if antes and ahora <= antes * 0.97 and antes - ahora >= 3000 and ahora >= antes * 0.4:
            baj.append({'pct': (antes - ahora) / antes, 'ficha': urls[x['id']].lstrip('/'), 'antes': antes, 'ahora': ahora, 'x': x, 'desde': max(previos)})
    baj.sort(key=lambda b: -b['pct'])
    return baj


def ofertas_reales(todos, hist, hoy, urls, min_dias=6):
    """Compara el precio de hoy (sin cupones) con el historial de cada equipo nuevo.
    reales: hoy está en el precio más bajo que hemos visto y al menos 5% bajo su precio habitual (la mediana).
    caros: solo para análisis interno; no se publica (suele ser stock agotado en la tienda más barata). Equipos con al menos min_dias días de historial."""
    reales, caros, n = [], [], 0
    for x in todos:
        h = hist.get(x['id'], {})
        if not x['os'] or x['eq'].get('refurb') or len(h) < min_dias:
            continue
        previos = [p for d, p in h.items() if d < hoy]
        if len(previos) < min_dias - 1:
            continue
        n += 1
        ahora, habitual, minimo = precio_tienda(x), statistics.median(previos), min(previos)
        d = {'x': x, 'ahora': ahora, 'habitual': habitual, 'minimo': minimo, 'ficha': urls[x['id']],
             'desde': min(d for d in h if d < hoy), 'dias': len(previos)}
        if ahora <= minimo and ahora <= habitual * 0.95 and habitual - ahora >= 3000:
            d['pct'] = (habitual - ahora) / habitual
            reales.append(d)
        elif ahora >= habitual * 1.10 and ahora - habitual >= 3000:
            d['pct'] = (ahora - habitual) / habitual
            caros.append(d)
    reales.sort(key=lambda d: -d['pct']); caros.sort(key=lambda d: -d['pct'])
    return {'reales': reales, 'caros': caros, 'n': n}


def _sobre_base(base, tit, desc, url, cuerpo, ld):
    """Arma una página nueva a partir del HTML de una guía (cambia título, descripción, datos para Google y el contenido)."""
    h = base
    for patron, nuevo in [(r'<title>.*?</title>', f'<title>{e(tit)}</title>'),
                          (r'<meta name="description" content=".*?">', f'<meta name="description" content="{e(desc)}">'),
                          (r'<link rel="canonical" href=".*?">', f'<link rel="canonical" href="{SITIO}{url}">'),
                          (r'<meta property="og:title" content=".*?">', f'<meta property="og:title" content="{e(tit)}">'),
                          (r'<meta property="og:description" content=".*?">', f'<meta property="og:description" content="{e(desc)}">'),
                          (r'<meta property="og:url" content=".*?">', f'<meta property="og:url" content="{SITIO}{url}">'),
                          (r'<script type="application/ld\+json">.*?</script>', '<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False).replace('</', '<\\/') + '</script>'),
                          (r'(?s)(<main[^>]*>).*(</main>)', None)]:
        if nuevo is None:
            h, k = re.subn(patron, lambda m: m.group(1) + cuerpo + m.group(2), h, count=1)
        else:
            h, k = re.subn(patron, lambda m: nuevo, h, count=1, flags=re.S)
        if not k:
            raise ValueError('plantilla de guía sin ' + patron)
    return _cabecera(h, '', None)


def pagina_ofertas_reales(base, r, fotos, hoy_txt, hoy, mov=None):
    """Página /ofertas-reales: qué equipos están hoy de verdad en el precio más bajo que hemos visto.
    No publica una lista de "equipos caros": un precio más alto suele ser que la tienda más barata se quedó sin stock, no un precio inflado."""
    url = '/ofertas-reales'
    reales, n = r['reales'], r['n']
    inicio = min((d['desde'] for d in reales), default=None)
    desde_txt = f'desde el {fecha_larga(inicio)}' if inicio else 'desde que empezamos a revisar'
    tit = 'Ofertas reales hoy en Chile: equipos en su precio más bajo | ¿Cuál me conviene?'
    desc = (f'De {n} equipos con historial de precios, {len(reales)} están hoy en el precio más bajo que hemos visto y al menos 5% bajo su precio habitual. '
            f'Revisado el {hoy_txt}.')

    def fila(d):
        x, u = d['x'], d['ficha']
        o = de_tienda(x)
        f, _ = foto_de(x['id'], fotos)
        img = f'<img src="{e(f)}" alt="" width="480" height="480" loading="lazy" decoding="async" referrerpolicy="no-referrer">' if f else ''
        linea = f'<li>{round(d["pct"] * 100)}% bajo su precio habitual ({plata(d["habitual"])})</li><li>Es el más bajo que hemos visto ({d["dias"]} días revisados)</li>'
        return (f'<li class="rkI"><a class="rkF" href="{u}" tabindex="-1" aria-hidden="true">{img}</a>'
                f'<div class="rkT"><h3><a href="{u}">{e(x["nombre"])}</a></h3><p class="sp">{e(CATS[x["k"]][0])} · {e(specs_cortas(x))}</p><ul class="gRaz">{linea}</ul></div>'
                f'<div class="rkP"><p class="precio">{plata(d["ahora"])}</p><p class="donde"><i style="background:{TIENDAS[o["s"]][1]}"></i>en {TIENDAS[o["s"]][0]}</p>'
                f'<a class="tb" href="{u}">Ver precios</a></div></li>')

    bloque_mov = ''
    if mov:
        t = mov['tot']
        pc = lambda v, n: round(v * 100 / n)
        filas = ''.join(f'<tr><td>{e(CATS[k][0])}</td><td>{v["n"]}</td><td>{pc(v["sube"], v["n"])}%</td><td>{pc(v["baja"], v["n"])}%</td><td>{pc(v["igual"], v["n"])}%</td></tr>' for k, v in mov['por'].items())
        bloque_mov = (f'<section class="bloque"><h2>Qué pasó con los precios desde el {e(fecha_larga(mov["ini"]))}</h2>'
                      f'<p>Comparamos el precio de <b>{t["n"]} equipos en la misma tienda</b> (sin cupones) entre el {e(fecha_larga(mov["ini"]))} y hoy: '
                      f'<b>{pc(t["sube"], t["n"])}% subió</b>, <b>{pc(t["baja"], t["n"])}% bajó</b> y <b>{pc(t["igual"], t["n"])}% sigue igual</b>. '
                      f'Seguimos esto cada día hasta el Black Friday (27 al 30 de noviembre) para ver cómo cambian los precios.</p>'
                      + (f'<table class="tabla"><thead><tr><th>Categoría</th><th>Equipos</th><th>Subió</th><th>Bajó</th><th>Igual</th></tr></thead><tbody>{filas}</tbody></table>' if filas else '') +
                      '<p class="nota">Solo cuenta equipos que ya seguíamos el primer día y que hoy siguen con stock en esa tienda. Es una muestra, no todo el mercado.</p></section>')
    pct_r = round(len(reales) * 100 / n) if n else 0
    lista = (f'<ol class="rk">{"".join(fila(d) for d in reales)}</ol>' if reales
             else '<p>Hoy ningún equipo está en su precio más bajo con al menos 5% bajo lo habitual. Vuelve mañana.</p>')
    txt = (f'Revisé {n} equipos en cualmeconviene.cl: {len(reales)} están hoy en el precio más bajo que hemos visto. Mira cuáles son ofertas reales:')
    cuerpo = (f'<h1>Ofertas reales hoy: equipos en su precio más bajo</h1>'
              f'<p class="sp">Comparamos el precio de hoy de cada equipo con todo lo que hemos visto {e(desde_txt)}. '
              f'De {n} equipos con historial, <b>{len(reales)}</b> ({pct_r}%) están en su precio más bajo y al menos 5% bajo lo habitual. '
              f'Revisado el {e(hoy_txt)}.</p>'
              f'<p class="gBtns">{compartir(txt, url, "Ofertas reales hoy en Chile")}</p>'
              f'{bloque_mov}'
              f'<section class="bloque"><h2>{len(reales)} equipos en su precio más bajo</h2>{lista}</section>'
              '<section class="bloque"><h2>Cómo calculamos esto</h2><ul class="gRaz">'
              '<li><b>Precio habitual:</b> la mediana de los precios más bajos que vimos de ese equipo en cada revisión, sin cupones ni tarjeta.</li>'
              '<li><b>En su precio más bajo:</b> hoy cuesta lo mismo o menos que lo más bajo que hemos visto, y al menos 5% menos que lo habitual.</li>'
              f'<li><b>Solo con historial:</b> usamos equipos nuevos con al menos 6 días de precios revisados. Nuestro historial parte el {e(fecha_larga(inicio or hoy))}, así que un equipo pudo estar más barato antes de eso.</li>'
              '<li><b>Una oferta que no aparece aquí no es necesariamente mala:</b> puede estar cerca de su mínimo, o no tener aún suficiente historial. Abre la ficha y mira el gráfico.</li></ul></section>')
    ld = {'@context': 'https://schema.org', '@graph': [
        {'@type': 'ItemList', 'name': 'Equipos en su precio más bajo hoy', 'url': SITIO + url, 'numberOfItems': min(len(reales), 40),
         'itemListElement': [{'@type': 'ListItem', 'position': k, 'url': SITIO + d['ficha']} for k, d in enumerate(reales[:40], 1)]},
        {'@type': 'BreadcrumbList', 'itemListElement': [
            {'@type': 'ListItem', 'position': 1, 'name': 'Inicio', 'item': SITIO + '/'},
            {'@type': 'ListItem', 'position': 2, 'name': 'Ofertas reales', 'item': SITIO + url}]}]}
    return _sobre_base(base, tit, desc, url, cuerpo, ld)


def movimiento(todos, hoy, margen=0.005):
    """Cómo cambió el precio de cada equipo en la MISMA tienda entre el primer día del historial y hoy (sin cupones).
    Comparar tienda contra tienda evita confundir un alza con que la tienda más barata se quedó sin stock."""
    if not SERIE_TIENDA:
        return None
    ini = min(d for v in SERIE_TIENDA.values() for d in v)
    k_de = {x['id']: x['k'] for x in todos}
    pares = []
    for (i, t), v in SERIE_TIENDA.items():
        if ini in v and hoy in v and i in k_de and v[ini]:
            pares.append((k_de[i], (v[hoy] - v[ini]) / v[ini]))
    if len(pares) < 30:
        return None

    def cuenta(xs):
        return {'n': len(xs), 'sube': sum(c > margen for _, c in xs), 'baja': sum(c < -margen for _, c in xs),
                'igual': sum(abs(c) <= margen for _, c in xs), 'mediana': statistics.median(c for _, c in xs)}
    tot = cuenta(pares)
    por = {k: cuenta([p for p in pares if p[0] == k]) for k in dict.fromkeys(k for k, _ in pares)}
    return {'ini': ini, 'tot': tot, 'por': {k: v for k, v in por.items() if v['n'] >= 15}}


def pagina_bajones(base, baj, urls, fotos, hoy_txt, hoy):
    """Página /bajones: lo que bajó de precio desde la revisión anterior. Usa como plantilla el HTML de una guía (base)."""
    url = '/bajones'
    n = len(baj)
    tit = f'Bajones de precio hoy en Chile: tecnología y electrodomésticos que bajaron | ¿Cuál me conviene?'
    desc = (f'{n} equipos bajaron de precio desde la revisión anterior en Chile. Mira cuánto costaban antes y cuánto cuestan hoy en notebooks, celulares, televisores y más. Precios revisados el {hoy_txt}.'
            if n else f'Los equipos que bajan de precio en Chile, con lo que costaban antes y lo que cuestan hoy. Precios revisados el {hoy_txt}.')

    def fila(b):
        x, u = b['x'], '/' + b['ficha']
        o = de_tienda(x)
        f, _ = foto_de(x['id'], fotos)
        img = f'<img src="{e(f)}" alt="" width="480" height="480" loading="lazy" decoding="async" referrerpolicy="no-referrer">' if f else ''
        tipo = CATS[x['k']][0]
        return (f'<li class="rkI"><a class="rkF" href="{u}" tabindex="-1" aria-hidden="true">{img}</a>'
                f'<div class="rkT"><h3><a href="{u}">{e(x["nombre"])}</a></h3><p class="sp">{e(tipo)} · {e(specs_cortas(x))}</p>'
                f'<ul class="gRaz"><li>Antes: {plata(b["antes"])} (revisión del {fecha_larga(b["desde"])})</li>'
                f'<li>Bajó {plata(b["antes"] - b["ahora"])}, un {round(b["pct"] * 100)}%</li></ul></div>'
                f'<div class="rkP"><p class="precio">{plata(b["ahora"])}</p><p class="donde"><i style="background:{TIENDAS[o["s"]][1]}"></i>en {TIENDAS[o["s"]][0]}</p>'
                f'<a class="tb" href="{u}">Ver precios</a></div></li>')

    if baj:
        lista = f'<ol class="rk">{"".join(fila(b) for b in baj[:40])}</ol>'
        top = baj[0]
        txt = (f'Hoy bajaron de precio {n} equipos en Chile. El mayor bajón: {top["x"]["nombre"]}, de {plata(top["antes"])} a {plata(top["ahora"])}. Míralos aquí:')
        comp = f'<p class="gBtns">{compartir(txt, url, "Bajones de precio de hoy")}</p>'
    else:
        lista = ('<p>Hoy no hay equipos con una baja clara desde la revisión anterior. Vuelve mañana o mira los precios de referencia del '
                 '<a href="/black-friday">Black Friday</a>.</p>')
        comp = ''
    cuerpo = (f'<h1>Bajones de precio de hoy</h1>'
              f'<p class="sp">Equipos que cuestan menos que en nuestra revisión anterior. Precios revisados el {e(hoy_txt)}. '
              'Contamos solo bajas de al menos 3% y $3.000, sin cupones, y dejamos fuera las caídas de más de 60%, que suelen ser errores de la tienda.</p>'
              f'{comp}<section class="bloque"><h2>{n} equipos que bajaron</h2>{lista}</section>'
              '<section class="bloque"><h2>Cómo leer esta lista</h2><ul class="gRaz">'
              '<li><b>Comparamos contra la revisión anterior.</b> Es el precio más bajo en tienda, sin cupón ni tarjeta, de la última vez que lo revisamos.</li>'
              '<li><b>Un bajón no siempre es una buena oferta.</b> Abre la ficha y mira el historial: te muestra si el precio ya estuvo más bajo antes.</li>'
              '<li><b>Los precios cambian durante el día.</b> Confirma el total en la tienda antes de pagar.</li></ul></section>')
    ld = {'@context': 'https://schema.org', '@graph': [
        {'@type': 'ItemList', 'name': 'Equipos que bajaron de precio hoy', 'url': SITIO + url, 'numberOfItems': min(n, 40),
         'itemListElement': [{'@type': 'ListItem', 'position': k, 'url': SITIO + '/' + b['ficha']} for k, b in enumerate(baj[:40], 1)]},
        {'@type': 'BreadcrumbList', 'itemListElement': [
            {'@type': 'ListItem', 'position': 1, 'name': 'Inicio', 'item': SITIO + '/'},
            {'@type': 'ListItem', 'position': 2, 'name': 'Bajones de precio', 'item': SITIO + url}]}]}
    h = base
    for patron, nuevo in [(r'<title>.*?</title>', f'<title>{e(tit)}</title>'),
                          (r'<meta name="description" content=".*?">', f'<meta name="description" content="{e(desc)}">'),
                          (r'<link rel="canonical" href=".*?">', f'<link rel="canonical" href="{SITIO}{url}">'),
                          (r'<meta property="og:title" content=".*?">', f'<meta property="og:title" content="{e(tit)}">'),
                          (r'<meta property="og:description" content=".*?">', f'<meta property="og:description" content="{e(desc)}">'),
                          (r'<meta property="og:url" content=".*?">', f'<meta property="og:url" content="{SITIO}{url}">'),
                          (r'<script type="application/ld\+json">.*?</script>', '<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False).replace('</', '<\\/') + '</script>'),
                          (r'(?s)(<main[^>]*>).*(</main>)', None)]:
        if nuevo is None:
            h, k = re.subn(patron, lambda m: m.group(1) + cuerpo + m.group(2), h, count=1)
        else:
            h, k = re.subn(patron, lambda m: nuevo, h, count=1, flags=re.S)
        if not k:
            raise ValueError('plantilla de guía sin ' + patron)
    return _cabecera(h, '', None)


def pagina_black_friday(base, todos, hist, urls, fotos, hoy_txt):
    """Página /black-friday: fechas y precios de referencia de cada día. Usa como plantilla el HTML de una guía (base)."""
    url = '/black-friday'
    tit = 'Black Friday 2026 Chile: fechas y cómo saber si la oferta es real | ¿Cuál me conviene?'
    desc = ('El Black Friday 2026 en Chile es del 27 al 30 de noviembre. Revisa el precio habitual y el más bajo que hemos visto '
            f'en notebooks, celulares y televisores para saber si la oferta es real. Precios revisados el {hoy_txt}.')

    def fila(x):
        h, o, u = hist[x['id']], x['os'][0], urls[x['id']]
        f, _ = foto_de(x['id'], fotos)
        img = f'<img src="{e(f)}" alt="" width="480" height="480" loading="lazy" decoding="async" referrerpolicy="no-referrer">' if f else ''
        return (f'<li class="rkI"><a class="rkF" href="{u}" tabindex="-1" aria-hidden="true">{img}</a>'
                f'<div class="rkT"><h3><a href="{u}">{e(x["nombre"])}</a></h3><p class="sp">{e(specs_cortas(x))}</p>'
                f'<ul class="gRaz"><li>Precio habitual: {plata(statistics.median(h.values()))}</li>'
                f'<li>Lo más bajo que vimos sin cupón: {plata(min(h.values()))}, desde el {fecha_larga(min(h))}</li></ul></div>'
                f'<div class="rkP"><p class="precio">{precio_html(o)}{pago(o)}</p><p class="donde"><i style="background:{TIENDAS[o["s"]][1]}"></i>en {TIENDAS[o["s"]][0]}</p>'
                f'<a class="tb" href="{u}">Ver precios</a></div></li>')

    grupos, lista_ld = '', []
    for k in ('nb', 'ph', 'tv', 'cs', 'lv', 'ac'):
        eqs = [x for x in todos if x['k'] == k and x['os'] and not x['eq'].get('refurb') and len(hist.get(x['id'], {})) >= 3]
        eqs.sort(key=lambda x: (-len(dict.fromkeys(o['s'] for o in x['os'])), x['os'][0]['p']))
        if eqs[:5]:
            tipo, _, slug = TIPOS[k]
            lista_ld += [urls[x['id']] for x in eqs[:5]]
            grupos += (f'<section class="bloque"><h2>{e(tipo)}: precios de referencia</h2><ol class="rk">{"".join(fila(x) for x in eqs[:5])}</ol>'
                       f'<p><a href="/{slug}">Ver y comparar todos</a></p></section>')
    consejos = [('Mira el precio de antes, no el porcentaje', 'Un descuento grande no sirve si se calcula sobre un precio que casi nunca se cobró. Compáralo con el precio habitual de esta página.'),
                ('Compara el mismo equipo en otras tiendas', 'La misma oferta puede costar menos en otra tienda. En cada ficha ves el precio de todas las que revisamos.'),
                ('Revisa si pide tarjeta o cupón', 'Te indicamos si un precio es con tarjeta o con cupón, y cuánto cuesta sin ellos. Confirma el total antes de pagar.'),
                ('Activa el aviso de precio', 'En la ficha de cada equipo puedes pedir un correo cuando baje de precio.')]
    preguntas = [('¿Cuándo es el Black Friday 2026 en Chile?', 'Parte el viernes 27 de noviembre a las 00:00 y termina el lunes 30 de noviembre a las 23:59. Las fechas las confirmó la Cámara de Comercio de Santiago.'),
                 ('¿Cuántos días dura?', 'Son cuatro días, con ofertas en línea y en tiendas físicas.'),
                 ('¿Conviene esperar al Black Friday?', 'Depende del equipo. Si hoy ya está cerca del precio más bajo que hemos visto, esperar puede no cambiar mucho. Si está sobre su precio habitual, conviene seguirlo y activar el aviso.')]
    cuerpo = (f'<h1>Black Friday 2026 en Chile: fechas y cómo saber si la oferta es real</h1>'
              f'<p class="sp">Parte el viernes 27 de noviembre y termina el lunes 30. Aquí tienes el precio habitual y el más bajo que hemos visto, para comparar antes de comprar. Precios revisados el {e(hoy_txt)}.</p>'
              f'<p class="gBtns">{compartir("Black Friday 2026 en Chile es del 27 al 30 de noviembre. Mira el precio habitual de cada equipo para saber si la oferta es real:", url, "Black Friday 2026 en Chile")}</p>'
              '<p><a href="/ofertas-reales">Mira qué equipos están hoy en el precio más bajo que hemos visto</a></p>'
              '<section class="bloque"><h2>Cómo saber si un descuento es real</h2><ul class="gRaz">'
              + ''.join(f'<li><b>{e(a)}.</b> {e(b)}</li>' for a, b in consejos) + '</ul></section>' + grupos +
              '<section class="bloque"><h2>Preguntas frecuentes</h2>' + ''.join(f'<h3>{e(a)}</h3><p>{e(b)}</p>' for a, b in preguntas) + '</section>')
    ld = {'@context': 'https://schema.org', '@graph': [
        {'@type': 'ItemList', 'name': 'Precios de referencia para el Black Friday 2026', 'url': SITIO + url, 'numberOfItems': len(lista_ld),
         'itemListElement': [{'@type': 'ListItem', 'position': k, 'url': SITIO + u} for k, u in enumerate(lista_ld, 1)]},
        {'@type': 'BreadcrumbList', 'itemListElement': [
            {'@type': 'ListItem', 'position': 1, 'name': 'Inicio', 'item': SITIO + '/'},
            {'@type': 'ListItem', 'position': 2, 'name': 'Black Friday 2026', 'item': SITIO + url}]}]}
    h = base
    for patron, nuevo in [(r'<title>.*?</title>', f'<title>{e(tit)}</title>'),
                          (r'<meta name="description" content=".*?">', f'<meta name="description" content="{e(desc)}">'),
                          (r'<link rel="canonical" href=".*?">', f'<link rel="canonical" href="{SITIO}{url}">'),
                          (r'<meta property="og:title" content=".*?">', f'<meta property="og:title" content="{e(tit)}">'),
                          (r'<meta property="og:description" content=".*?">', f'<meta property="og:description" content="{e(desc)}">'),
                          (r'<meta property="og:url" content=".*?">', f'<meta property="og:url" content="{SITIO}{url}">'),
                          (r'<script type="application/ld\+json">.*?</script>', '<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False).replace('</', '<\\/') + '</script>'),
                          (r'(?s)(<main[^>]*>).*(</main>)', None)]:
        if nuevo is None:
            h, n = re.subn(patron, lambda m: m.group(1) + cuerpo + m.group(2), h, count=1)
        else:
            h, n = re.subn(patron, lambda m: nuevo, h, count=1, flags=re.S)
        if not n:
            raise ValueError('plantilla de guía sin ' + patron)
    return _cabecera(h, '', None)


# ---------------- Guías "qué comprar": una por categoría, con los precios de hoy ----------------
# Cada una explica en pocas líneas qué mirar y muestra qué conviene hoy según el presupuesto o el tamaño.
# Los equipos salen de los datos del sitio (sin fórmulas inventadas): el más barato de cada tipo, o el de mejor rendimiento por precio.
def _unicos(xs, n):
    out, vistos = [], set()
    for x in xs:
        c = slugify(x['nombre'])
        if c not in vistos:
            vistos.add(c); out.append(x)
        if len(out) == n:
            break
    return out


def _nuevos(todos, k):
    return [x for x in todos if x['k'] == k and x['os'] and not x['eq'].get('refurb')]


def _barato(xs):
    return min(xs, key=lambda x: x['os'][0]['p']) if xs else None


def picks_tv(todos):
    tv = _nuevos(todos, 'tv')
    g = []
    for t, f in [('Hasta 43 pulgadas: pieza chica o dormitorio', lambda s: s <= 43), ('50 a 55 pulgadas: el tamaño más común', lambda s: 50 <= s <= 55),
                 ('65 pulgadas: living cómodo', lambda s: s == 65), ('75 pulgadas o más: cine en casa', lambda s: s >= 75)]:
        xs = [x for x in tv if f(x['eq']['size'])]
        sel = [('El más barato', _barato(xs)),
               ('El más barato con QLED, QNED o Mini LED', _barato([x for x in xs if x['eq'].get('panel') in ('QLED', 'QNED', 'Mini LED', 'NanoCell')])),
               ('El más barato con OLED', _barato([x for x in xs if x['eq'].get('panel') == 'OLED']))]
        pares, vistos = [], set()
        for et, x in sel:
            if x and x['id'] not in vistos:
                vistos.add(x['id']); pares.append((et, x))
        if pares:
            g.append((t, pares))
    return g


def _pot2(x, clave):
    return (x['eq'].get(clave) or 0) ** 2 / x['os'][0]['p']


def picks_ph(todos):
    ph = [x for x in _nuevos(todos, 'ph') if x['eq'].get('antutu')]
    g = []
    for t, a, b in [('Hasta $150.000', 0, 150000), ('De $150.000 a $300.000', 150000, 300000), ('De $300.000 a $600.000', 300000, 600000), ('Más de $600.000', 600000, 10 ** 9)]:
        xs = sorted([x for x in ph if a < x['os'][0]['p'] <= b], key=lambda x: -_pot2(x, 'antutu'))
        top = _unicos(xs, 3)
        if top:
            g.append((t, [(f'N° {i}', x) for i, x in enumerate(top, 1)]))
    return g


def picks_cs(todos):
    cs = _nuevos(todos, 'cs')
    fam = {}
    for x in sorted(cs, key=lambda x: x['os'][0]['p']):
        fam.setdefault(x['eq']['fam'], x)
    return [('Cada consola, a su precio más bajo hoy', [(f, x) for f, x in sorted(fam.items(), key=lambda a: a[1]['os'][0]['p'])])]


def picks_lv(todos):
    lv = _nuevos(todos, 'lv')
    g = []
    for t, f in [('Lavadoras de carga superior', lambda x: x['eq']['tipo'] == 'lavadora' and x['eq'].get('carga') == 'superior'),
                 ('Lavadoras de carga frontal', lambda x: x['eq']['tipo'] == 'lavadora' and x['eq'].get('carga') == 'frontal'),
                 ('Lavadoras-secadoras (lavaseca)', lambda x: x['eq']['tipo'] == 'lavaseca')]:
        xs = [x for x in lv if f(x)]
        sel = [('La más barata', _barato(xs)), ('La más barata con motor inverter', _barato([x for x in xs if x['eq'].get('inv')])),
               ('La de más capacidad bajo la mediana de precio',
                max([x for x in xs if x['os'][0]['p'] <= statistics.median(y['os'][0]['p'] for y in xs)], key=lambda x: (x['eq'].get('kg') or 0, -x['os'][0]['p']), default=None) if xs else None)]
        pares, vistos = [], set()
        for et, x in sel:
            if x and x['id'] not in vistos:
                vistos.add(x['id']); pares.append((et, x))
        if pares:
            g.append((t, pares))
    return g


def picks_as(todos):
    a = [x for x in _nuevos(todos, 'as') if x['eq'].get('tipo') == 'robot']
    sel = [('El robot más barato', _barato(a)),
           ('El más barato con mapeo láser (LiDAR)', _barato([x for x in a if 'LiDAR' in (x['eq'].get('nav') or '') or 'Láser' in (x['eq'].get('nav') or '')])),
           ('El más barato que también friega (mopa)', _barato([x for x in a if x['eq'].get('mopa')])),
           ('El más barato con mapeo láser y mopa', _barato([x for x in a if x['eq'].get('mopa') and 'Láser' in (x['eq'].get('nav') or '')])),
           ('El de más succión', max([x for x in a if x['eq'].get('pa')], key=lambda x: x['eq']['pa'], default=None))]
    pares, vistos = [], set()
    for et, x in sel:
        if x and x['id'] not in vistos:
            vistos.add(x['id']); pares.append((et, x))
    return [('Aspiradoras robot', pares)] if pares else []


CALCULADORAS = [('ac', '/calculadora-btu', '¿Cuántos BTU necesito?'), ('tv', '/calculadora-tamano-tv', '¿Qué tamaño de TV me sirve?')]

QUE_COMPRAR = [
    {'slug': 'que-notebook-comprar', 'k': 'nb', 'picks': lambda t: picks_nb(t), 'h1': '¿Qué notebook comprar en Chile?', 'corto': 'notebook',
     'intro': 'Elegir bien depende de qué vas a hacer con él y cuánto quieres gastar. Aquí tienes qué mirar y los que más rinden por su precio hoy, según tu presupuesto y uso.',
     'consejos': [('Memoria RAM: 8 GB mínimo, 16 GB cómodo', 'Con 8 GB funcionan Word, clases en línea y el navegador. Para programar o diseñar, 16 GB.'),
                  ('Almacenamiento: siempre SSD', 'Un SSD enciende el equipo y abre programas en segundos. 256 GB alcanzan con la nube; 512 GB dan más tranquilidad.'),
                  ('Procesador según el uso', 'Ryzen 3 o Core i3 para lo básico, Ryzen 5 o Core i5 para estudiar y trabajar varios años, Ryzen 7 o Core i7 para programar o editar.'),
                  ('Tarjeta de video solo si juegas o diseñas', 'Para juegos o edición de video necesitas una tarjeta dedicada (RTX o similar). Para todo lo demás bastan los gráficos integrados.'),
                  ('Tamaño y peso', '14 pulgadas para llevarlo todos los días, 15,6 para dejarlo en casa.')],
     'preguntas': [('¿Cuánto debo gastar?', 'Para estudiar y trabajar, entre $400.000 y $700.000 alcanza para uno que dure varios años. Bajo $400.000 sirve para lo básico.')]},
    {'slug': 'que-smart-tv-comprar', 'k': 'tv', 'picks': picks_tv, 'h1': '¿Qué smart TV comprar en Chile?', 'corto': 'smart TV',
     'intro': 'La pantalla correcta depende del tamaño de tu pieza, de cuánto te alejas y de si ves cine o fútbol. Aquí tienes qué mirar y el más barato de cada tipo, con los precios de hoy.',
     'consejos': [('Tamaño según la distancia', 'A unos 2 metros sirve un televisor de 43 a 50 pulgadas. A 3 metros, uno de 55 a 65. Más grande solo vale la pena si tienes espacio.'),
                  ('LED, QLED, Mini LED u OLED', 'LED es el más barato. QLED y Mini LED se ven más brillantes y con mejor color, y sirven bien con luz de día. OLED tiene los negros más profundos y es el mejor para ver películas con la luz apagada.'),
                  ('Frecuencia: 60 o 120 Hz', 'Para ver series y películas bastan 60 Hz. Si juegas en PS5 o Xbox, 120 Hz se nota más fluido.'),
                  ('Sistema operativo', 'Google TV, webOS, Tizen y otros tienen las mismas aplicaciones principales. Cambia el menú y cuánto tiempo recibe actualizaciones.'),
                  ('Resolución', 'Desde 43 pulgadas conviene 4K: casi todos los que se venden hoy lo son. Full HD solo en pantallas chicas.')],
     'preguntas': [('¿Qué es mejor, OLED o QLED?', 'OLED muestra negros más profundos y mejor contraste, y QLED o Mini LED brillan más. Para una pieza oscura conviene OLED; para un living con mucha luz, QLED o Mini LED.'),
                   ('¿Cuántas pulgadas necesito?', 'Una referencia simple: 43 pulgadas para 1,5 a 2 metros, 55 para 2 a 3 metros y 65 para más de 3 metros.')]},
    {'slug': 'que-celular-comprar', 'k': 'ph', 'picks': picks_ph, 'h1': '¿Qué celular comprar en Chile?', 'corto': 'celular',
     'intro': 'Elegir por presupuesto es lo más simple: dentro de cada rango te mostramos los tres que más rendimiento dan por lo que cuestan, según el puntaje AnTuTu, con los precios de hoy.',
     'consejos': [('Memoria: 128 GB es lo mínimo hoy', 'Con fotos, videos y WhatsApp, 128 GB se llena rápido. Si puedes, 256 GB.'),
                  ('RAM: 6 u 8 GB para que no se trabe', 'Con 4 GB funciona lo básico. Con 8 GB aguanta más años de actualizaciones.'),
                  ('Cámara no es solo megapíxeles', 'Importa más el sensor y el procesado de la marca que el número. Mira fotos reales de ese modelo.'),
                  ('Batería y carga', 'Desde 5.000 mAh dura todo el día. Revisa también la carga rápida y si el cargador viene en la caja.'),
                  ('Operador o liberado', 'Comprarlo liberado te deja elegir plan. Con operador, revisa la permanencia y lo que pagas en total.')],
     'preguntas': [('¿Qué significa el puntaje AnTuTu?', 'Es una prueba que mide la potencia del procesador. Mientras más alto, más rápido va el celular, pero no mide cámara ni batería.')]},
    {'slug': 'que-consola-comprar', 'k': 'cs', 'picks': picks_cs, 'h1': '¿Qué consola comprar en Chile?', 'corto': 'consola',
     'intro': 'PlayStation, Xbox o Nintendo: la mejor depende de qué juegos quieres y dónde juegas. Aquí tienes el precio de cada una hoy y cómo elegir.',
     'consejos': [('Elige por los juegos que quieres', 'Los exclusivos mandan: Mario y Zelda solo en Nintendo, God of War y Spider-Man en PlayStation, Halo y Forza en Xbox.'),
                  ('Si juegas en el sillón o viajas', 'Nintendo Switch 2 se usa en la tele y también como portátil.'),
                  ('Si buscas la mejor imagen', 'PlayStation 5 y PS5 Pro son las más potentes para ver juegos en 4K y con buenos cuadros por segundo.'),
                  ('La más barata para partir', 'Xbox Series S y Switch Lite son las más baratas. Revisa si incluyen juego, porque a veces el pack sale más conveniente.'),
                  ('Juegos digitales o en disco', 'Las versiones sin lector de discos son más baratas, pero no puedes comprar ni vender juegos usados.')],
     'preguntas': []},
    {'slug': 'que-lavadora-comprar', 'k': 'lv', 'picks': picks_lv, 'h1': '¿Qué lavadora comprar en Chile?', 'corto': 'lavadora',
     'intro': 'Antes de comparar marcas, decide el tipo y la capacidad. Después mira el motor y el consumo. Aquí tienes el más barato de cada tipo, con los precios de hoy.',
     'consejos': [('Carga superior o frontal', 'La superior es más barata y fácil de cargar. La frontal gasta menos agua y cuida más la ropa, pero cuesta más.'),
                  ('Capacidad según cuántos son', '8 a 9 kg para 1 o 2 personas, 10 a 12 kg para familias de 3 o 4 y 15 kg o más para familias grandes.'),
                  ('Motor inverter', 'Es más silencioso, dura más y gasta menos electricidad. Vale la pena si la vas a usar a diario.'),
                  ('Lavadora-secadora', 'Ocupa un solo espacio, pero seca más lento que una secadora aparte. Sirve en departamentos chicos.'),
                  ('Eficiencia energética', 'En la etiqueta, A es la que menos gasta y G la que más. Con A o B ahorras en la cuenta.')],
     'preguntas': [('¿Conviene una lavadora-secadora?', 'Si tienes poco espacio, sí. Si lavas mucho, una lavadora y una secadora por separado terminan más rápido.')]},
    {'slug': 'que-aspiradora-robot-comprar', 'k': 'as', 'picks': picks_as, 'h1': '¿Qué aspiradora robot comprar en Chile?', 'corto': 'aspiradora robot',
     'intro': 'No todos los robots son iguales: la diferencia está en cómo se orientan y si friegan. Aquí tienes el más barato según lo que necesitas, con los precios de hoy.',
     'consejos': [('Cómo se orienta', 'Los de mapeo láser (LiDAR) hacen mapas y limpian en filas ordenadas. Los de sensores simples van más al azar y pasan dos veces por el mismo lugar.'),
                  ('Con o sin mopa', 'Los que friegan sirven para piso flotante o cerámica. En alfombras suelen ser peores.'),
                  ('Succión', 'Mientras más pascales (Pa), más recoge. Con 2.000 Pa alcanza para polvo y pelos; sobre 5.000 Pa se nota con mascotas.'),
                  ('Estación de vaciado', 'Algunos se vacían solos y se friegan solos. Cuestan más, pero te olvidas por semanas.'),
                  ('Mascotas', 'Si tienes perro o gato, busca cepillo antienredo y filtro HEPA.')],
     'preguntas': []},
]


def _rank_nb(todos, uso, a, b, n=3):
    c = [r for r in ranking_guia({'k': 'nb', 'uso': uso, 'hasta': b}, todos, datos_nb()) if r['p'] > a]
    return [(f'N° {i}', r['x']) for i, r in enumerate(c[:n], 1)]


def picks_nb(todos):
    g = []
    for t, uso, a, b in [('Hasta $400.000: estudio y oficina', 'estudio', 0, 400000), ('De $400.000 a $700.000: estudio y trabajo', 'estudio', 400000, 700000),
                         ('De $700.000 a $1.200.000: rendimiento de sobra', 'estudio', 700000, 1200000),
                         ('Para jugar: los que más rinden por precio', 'juegos', 0, 10 ** 9), ('Para programar: los que más rinden por precio', 'prog', 0, 10 ** 9)]:
        r = _rank_nb(todos, uso, a, b)
        if r:
            g.append((t, r))
    return g


PANEL = {'OLED': 4, 'Mini LED': 3, 'QLED': 3, 'QNED': 3, 'Micro RGB': 4, 'NanoCell': 2, 'LED': 1}


def _tope(xs, clave, n=5):
    return [(f'N° {i}', x) for i, x in enumerate(_unicos(sorted(xs, key=clave), n), 1)]


def _presup(k, filtro, clave, n=5, titulo=None):
    def f(todos):
        xs = [x for x in _nuevos(todos, k) if filtro(x)]
        r = _tope(xs, clave, n)
        return [(titulo or 'Los que más convienen hoy', r)] if r else []
    return f


_p = lambda x: x['os'][0]['p']


def _tv_tamano(tam):
    def f(todos):
        xs = [x for x in _nuevos(todos, 'tv') if x['eq']['size'] == tam and x['eq'].get('res') == '4K']
        r = []
        for et, ps in [('El más barato: LED', ('LED',)), ('El más barato: QLED, QNED o NanoCell', ('QLED', 'QNED', 'NanoCell')),
                       ('El más barato: Mini LED', ('Mini LED',)), ('El más barato: OLED', ('OLED',))]:
            x = _barato([y for y in xs if y['eq'].get('panel') in ps])
            if x:
                r.append((et, x))
        return [('El más barato de cada tipo de pantalla', r)] if r else []
    return f
_nbp = lambda a, b: (lambda todos: [(('Los 5 que más rinden por su precio'), _rank_nb(todos, 'estudio', a, b, 5))])


def _pres(slug, k, h1, corto, intro, picks, base_slug):
    base = next(c for c in QUE_COMPRAR if c['slug'] == base_slug)
    return {'slug': slug, 'k': k, 'picks': picks, 'h1': h1, 'corto': corto, 'intro': intro, 'consejos': base['consejos'][:4], 'preguntas': []}


QUE_COMPRAR += [
    _pres('mejor-notebook-gamer-hasta-1-millon', 'nb', 'Mejor notebook gamer hasta $1.000.000 en Chile', 'notebook gamer hasta $1.000.000',
          'Para jugar necesitas tarjeta de video dedicada. Estos son los notebooks que más rinden para juegos por su precio hoy, hasta $1.000.000.',
          lambda t: [('Los 5 que más rinden para jugar', _rank_nb(t, 'juegos', 0, 1000000, 5))], 'que-notebook-comprar'),
    _pres('mejor-celular-hasta-200-mil', 'ph', 'Mejor celular hasta $200.000 en Chile', 'celular hasta $200.000',
          'Bajo $200.000 hay celulares que cumplen para WhatsApp, redes, fotos y videos. Estos son los que más rinden por su precio hoy, según su puntaje AnTuTu.',
          _presup('ph', lambda x: _p(x) <= 200000 and x['eq'].get('antutu'), lambda x: -_pot2(x, 'antutu'), 5), 'que-celular-comprar'),
    _pres('mejor-celular-hasta-400-mil', 'ph', 'Mejor celular hasta $400.000 en Chile', 'celular hasta $400.000',
          'Entre $200.000 y $400.000 están los celulares con mejor relación entre precio, cámara y batería. Estos son los que más rinden por su precio hoy.',
          _presup('ph', lambda x: 200000 < _p(x) <= 400000 and x['eq'].get('antutu'), lambda x: -_pot2(x, 'antutu'), 5), 'que-celular-comprar'),
    _pres('mejor-smart-tv-55-pulgadas', 'tv', 'Mejor smart TV de 55 pulgadas en Chile', 'smart TV de 55 pulgadas',
          'El de 55 pulgadas es el tamaño más vendido. Aquí tienes el más barato de cada tipo de pantalla (LED, QLED, Mini LED y OLED) para que compares cuánto cuesta cada salto.',
          _tv_tamano(55), 'que-smart-tv-comprar'),
    _pres('mejor-smart-tv-65-pulgadas', 'tv', 'Mejor smart TV de 65 pulgadas en Chile', 'smart TV de 65 pulgadas',
          'Los 65 pulgadas se ven muy bien desde 3 metros. Aquí tienes el más barato de cada tipo de pantalla (LED, QLED, Mini LED y OLED) para que compares cuánto cuesta cada salto.',
          _tv_tamano(65), 'que-smart-tv-comprar'),
    _pres('mejor-lavadora-hasta-250-mil', 'lv', 'Mejor lavadora hasta $250.000 en Chile', 'lavadora hasta $250.000',
          'Con este presupuesto hay lavadoras de buena capacidad. Las ordenamos por kilos de ropa que lavan por cada peso.',
          _presup('lv', lambda x: x['eq']['tipo'] == 'lavadora' and _p(x) <= 250000 and x['eq'].get('kg'), lambda x: -x['eq']['kg'] / _p(x), 5), 'que-lavadora-comprar'),
    _pres('mejor-aspiradora-robot-hasta-200-mil', 'as', 'Mejor aspiradora robot hasta $200.000 en Chile', 'aspiradora robot hasta $200.000',
          'Bajo $200.000 ya hay robots que friegan y hasta con mapeo láser. Los ordenamos primero por cómo se orientan y luego por precio.',
          _presup('as', lambda x: x['eq'].get('tipo') == 'robot' and _p(x) <= 200000, lambda x: (0 if 'Láser' in (x['eq'].get('nav') or '') else 1, -(x['eq'].get('mopa') or 0), _p(x)), 5), 'que-aspiradora-robot-comprar'),
]



def _picks_lavado(todos):
    lv = _nuevos(todos, 'lv')
    r = [('Lavadora-secadora más barata (2 en 1)', _barato([x for x in lv if x['eq']['tipo'] == 'lavaseca'])),
         ('Lavadora más barata (para combinar)', _barato([x for x in lv if x['eq']['tipo'] == 'lavadora'])),
         ('Secadora más barata (para combinar)', _barato([x for x in lv if x['eq']['tipo'] == 'secadora']))]
    return [('Cuánto cuesta cada opción hoy', [(a, x) for a, x in r if x])]


QUE_COMPRAR += [
    {'slug': 'oled-qled-o-mini-led', 'k': 'tv', 'picks': _tv_tamano(65), 'h1': '¿OLED, QLED o Mini LED? Cuál conviene en un smart TV', 'corto': 'televisor OLED, QLED o Mini LED',
     'intro': 'Los tres son pantallas 4K, pero se ven y cuestan distinto. Te explicamos la diferencia y cuánto cuesta cada tipo hoy en 65 pulgadas.',
     'consejos': [('OLED: los mejores negros', 'Cada punto de la pantalla se enciende solo, por eso el negro es negro de verdad. Es el mejor para películas con la luz apagada, pero es el más caro y brilla menos en una pieza muy iluminada.'),
                  ('QLED: color y brillo a buen precio', 'Usa una capa de puntos cuánticos delante de una luz LED. Se ve brillante y colorida, y cuesta menos que un OLED.'),
                  ('Mini LED: más brillo y mejor contraste', 'Tiene miles de luces diminutas atrás que se apagan por zonas. Se acerca al contraste del OLED con mucho más brillo, ideal para living con ventanales.'),
                  ('LED común', 'Es el más barato. Sirve para ver series y noticias, pero sus negros se ven grises y el contraste es menor.'),
                  ('Qué elegir', 'Pieza oscura y cine: OLED. Living con mucha luz: Mini LED o QLED. Presupuesto ajustado: QLED o LED.')],
     'preguntas': [('¿El OLED se quema?', 'Puede quedar marcado si dejas la misma imagen fija durante miles de horas, como el logo de un canal. Con uso normal, los OLED actuales lo evitan con funciones propias.')]},
    {'slug': 'ps5-o-switch-2', 'k': 'cs', 'picks': lambda t: [(a, [(f, x) for f, x in r if f in ('PlayStation 5', 'PlayStation 5 Pro', 'Nintendo Switch 2')]) for a, r in picks_cs(t)], 'h1': 'PS5 o Nintendo Switch 2: cuál conviene comprar', 'corto': 'consola PS5 o Switch 2',
     'intro': 'Son dos formas distintas de jugar: potencia en la tele o juegos para toda la familia que también se llevan de viaje. Mira sus diferencias y cuánto cuesta cada una hoy.',
     'consejos': [('PS5: más potencia y juegos grandes', 'Es más potente y sus juegos se ven mejor en una tele 4K. Tiene los exclusivos de PlayStation y un catálogo muy grande de juegos de acción y deportes.'),
                  ('Switch 2: portátil y familiar', 'Se juega en la tele o en la mano, y tiene los juegos de Mario, Zelda y Pokémon que no salen en otras consolas. Es ideal para jugar en familia.'),
                  ('Precio de los juegos', 'Los juegos de Nintendo suelen mantener su precio por más tiempo. Los de PlayStation bajan más rápido con ofertas.'),
                  ('Qué elegir', 'Si quieres la mejor imagen en la tele y juegos de acción, PS5. Si juegas con niños o quieres llevarla de viaje, Switch 2.')],
     'preguntas': []},
    {'slug': 'lavadora-secadora-o-por-separado', 'k': 'lv', 'picks': _picks_lavado, 'h1': '¿Lavadora-secadora o lavadora y secadora por separado?', 'corto': 'lavadora-secadora',
     'intro': 'La lavadora-secadora ocupa un solo espacio, pero tiene límites. Te contamos cuándo conviene cada opción y cuánto cuesta hoy.',
     'consejos': [('Lavadora-secadora: ideal si falta espacio', 'Lava y seca en el mismo tambor. Sirve en departamentos chicos, y te ahorras mover la ropa.'),
                  ('Su límite: la carga al secar', 'Seca menos ropa de la que lava (por ejemplo, 14 kg lava y 8 kg seca) y demora más, a veces más de 3 horas por ciclo.'),
                  ('Por separado: más rápido y para más ropa', 'Mientras una seca, la otra puede lavar. Sirve para familias numerosas, pero necesitas el doble de espacio y conexiones.'),
                  ('Qué elegir', 'Una o dos personas y poco espacio: lavadora-secadora. Familia de 3 o más: lavadora y secadora por separado.')],
     'preguntas': []},
]


def _cabecera(h, lista_slug, tipo):
    """Las guías nuevas parten del HTML de la guía de notebooks: ajusta buscador y menú a la categoría de cada una (tipo=None: sin categoría)."""
    t = tipo.lower() if tipo else 'equipos'
    h = re.sub(r'(<form class="search" action=")[^"]*(")', lambda m: m.group(1) + ('/' + lista_slug if tipo else '/notebooks') + m.group(2), h, count=1)
    h = h.replace('placeholder="Buscar notebooks" aria-label="Buscar notebooks"', f'placeholder="Buscar {t}" aria-label="Buscar {t}"')
    return re.sub(r'(<nav class="hd-cats" aria-label="Categorías">).*?(</nav>)', lambda m: m.group(1) + menu(lista_slug if tipo else '') + m.group(2), h, count=1, flags=re.S)


def pagina_que_comprar(base, c, todos, urls, fotos, hoy_txt, hoy):
    url = f'/guia/{c["slug"]}'
    mes = f'{MESES[hoy.month - 1]} {hoy.year}'
    tipo, _, lista_slug = TIPOS[c['k']]
    grupos = c['picks'](todos)
    nuevos = _nuevos(todos, c['k'])
    tit = f'{c["h1"]} Guía {mes} | ¿Cuál me conviene?'
    desde = min((x['os'][0]['p'] for x in nuevos), default=0)
    desc = (f'Cómo elegir {c["corto"]} en Chile y cuál conviene hoy según tu presupuesto. Desde {plata(desde)}. Precios revisados el {hoy_txt}.')

    def fila(et, x):
        o, u = x['os'][0], urls[x['id']]
        f, _ = foto_de(x['id'], fotos)
        img = f'<img src="{e(f)}" alt="" width="480" height="480" loading="lazy" decoding="async" referrerpolicy="no-referrer">' if f else ''
        return (f'<li class="rkI"><a class="rkF" href="{u}" tabindex="-1" aria-hidden="true">{img}</a>'
                f'<div class="rkT"><p class="rkN">{e(et)}</p><h3><a href="{u}">{e(x["nombre"])}</a></h3><p class="sp">{e(specs_cortas(x))}</p></div>'
                f'<div class="rkP"><p class="precio">{precio_html(o)}{pago(o)}</p><p class="donde"><i style="background:{TIENDAS[o["s"]][1]}"></i>en {TIENDAS[o["s"]][0]}</p>'
                f'<a class="tb" href="{u}">Ver precios</a></div></li>')

    secciones, lista_ld = '', []
    for t, pares in grupos:
        lista_ld += [urls[x['id']] for _, x in pares]
        secciones += f'<section class="bloque"><h2>{e(t)}</h2><ol class="rk">{"".join(fila(et, x) for et, x in pares)}</ol></section>'
    consejos = ''.join(f'<li><b>{e(a)}.</b> {e(b)}</li>' for a, b in c['consejos'])
    preguntas = ''.join(f'<h3>{e(a)}</h3><p>{e(b)}</p>' for a, b in c['preguntas'])
    otras = ''.join(f'<li><a href="/guia/{o["slug"]}">{e(o["h1"])}</a></li>' for o in QUE_COMPRAR if o['slug'] != c['slug'])
    cuerpo = (f'<p class="mc">Guía del puma · Actualizada el {fecha_larga(hoy)} de {hoy.year}</p><h1>{e(c["h1"])}</h1><p class="sp">{e(c["intro"])}</p>'
              f'<section class="bloque"><h2>Qué mirar antes de comprar</h2><ul class="gRaz">{consejos}</ul></section>'
              + secciones
              + (f'<section class="bloque"><h2>Preguntas frecuentes</h2>{preguntas}</section>' if preguntas else '')
              + f'<section class="bloque"><h2>Cómo armamos esta guía</h2><p class="nota">Los equipos salen de las {len(nuevos)} opciones nuevas que hoy revisamos en las tiendas de Chile. Mostramos el precio más bajo publicado en cada una, que a veces exige tarjeta de la tienda o cupón. No es una prueba de laboratorio ni asesoría profesional: confirma siempre el precio y el stock en la tienda antes de pagar. Precios revisados el {e(hoy_txt)}.</p>'
              f'<p class="nota"><a href="/{lista_slug}">Ver y comparar todos los equipos de {e(tipo.lower())}</a></p></section>'
              f'<section class="bloque"><h2>Otras guías</h2><ul class="gOtras">{otras}<li><a href="/guia/{GUIAS[0]["slug"]}">{e(GUIAS[0]["titulo"])}</a></li><li><a href="/black-friday">Black Friday 2026</a></li></ul></section>')
    ld = {'@context': 'https://schema.org', '@graph': [
        {'@type': 'ItemList', 'name': c['h1'], 'url': SITIO + url, 'numberOfItems': len(lista_ld),
         'itemListElement': [{'@type': 'ListItem', 'position': k, 'url': SITIO + u} for k, u in enumerate(lista_ld, 1)]},
        {'@type': 'BreadcrumbList', 'itemListElement': [
            {'@type': 'ListItem', 'position': 1, 'name': 'Inicio', 'item': SITIO + '/'},
            {'@type': 'ListItem', 'position': 2, 'name': tipo, 'item': SITIO + '/' + lista_slug},
            {'@type': 'ListItem', 'position': 3, 'name': c['h1'], 'item': SITIO + url}]}]}
    h = base
    for patron, nuevo in [(r'<title>.*?</title>', f'<title>{e(tit)}</title>'),
                          (r'<meta name="description" content=".*?">', f'<meta name="description" content="{e(desc)}">'),
                          (r'<link rel="canonical" href=".*?">', f'<link rel="canonical" href="{SITIO}{url}">'),
                          (r'<meta property="og:title" content=".*?">', f'<meta property="og:title" content="{e(c["h1"])}">'),
                          (r'<meta property="og:description" content=".*?">', f'<meta property="og:description" content="{e(desc)}">'),
                          (r'<meta property="og:url" content=".*?">', f'<meta property="og:url" content="{SITIO}{url}">'),
                          (r'<script type="application/ld\+json">.*?</script>', '<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False).replace('</', '<\\/') + '</script>'),
                          (r'(?s)(<main[^>]*>).*(</main>)', None)]:
        if nuevo is None:
            h, n = re.subn(patron, lambda m: m.group(1) + cuerpo + m.group(2), h, count=1)
        else:
            h, n = re.subn(patron, lambda m: nuevo, h, count=1, flags=re.S)
        if not n:
            raise ValueError('plantilla de guía sin ' + patron)
    return _cabecera(h, lista_slug, tipo)


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
    guias = ('<li><a href="/black-friday"><img src="/assets/puma-sello.webp" alt="" width="32" height="32" loading="lazy" decoding="async">'
             '<span><strong>Black Friday 2026: fechas y precios de referencia</strong><small>Del 27 al 30 de noviembre</small></span></a></li>') + guias
    guias += ''.join(f'<li><a href="{u}"><img src="/assets/puma-sello.webp" alt="" width="32" height="32" loading="lazy" decoding="async"><span><strong>{e(t)}</strong><small>Calculadora gratis</small></span></a></li>'
                     for kk, u, t in CALCULADORAS if kk == k)
    guias += ''.join(f'<li><a href="/guia/{c["slug"]}"><img src="/assets/puma-sello.webp" alt="" width="32" height="32" loading="lazy" decoding="async">'
                     f'<span><strong>{e(c["h1"])}</strong><small>Qué mirar y cuál conviene hoy</small></span></a></li>' for c in QUE_COMPRAR if c['k'] == k)
    items = ''.join(f'<li><a href="{urls[x["id"]]}">{e(x["nombre"])}</a> <span>{precio_html(x["os"][0])}</span></li>' for x in eqs)
    return (f'<section class="indice" aria-label="Guías y lista completa de {tipo.lower()}">'
            + (f'<h2 class="idxT">Guías del puma</h2><ul class="idxGuias">{guias}</ul>' if guias else '')
            + f'<details class="idxTodos"><summary>Lista completa: {len(eqs)} {tipo.lower()} con su precio más bajo de hoy</summary>'
            f'<ul class="idxLista">{items}</ul></details></section>')


def bloque_portada(rankings, fotos, urls):
    tarjetas = ('<a class="guiaC" href="/black-friday"><span class="guiaF"><img src="/assets/puma-sello.webp" alt="" width="480" height="480" loading="lazy" decoding="async"></span>'
                '<span class="guiaT"><small>Del 27 al 30 de noviembre</small><strong>Black Friday 2026: fechas y precios de referencia</strong>'
                '<span>Mira el precio habitual y el más bajo que hemos visto antes de comprar.</span><b>Ver precios de referencia</b></span></a>')
    tarjetas += ('<a class="guiaC" href="/bajones"><span class="guiaF"><img src="/assets/puma-sello.webp" alt="" width="480" height="480" loading="lazy" decoding="async"></span>'
                 '<span class="guiaT"><small>Se actualiza cada día</small><strong>Bajones de precio de hoy</strong>'
                 '<span>Los equipos que cuestan menos que ayer, con lo que valían antes.</span><b>Ver los bajones</b></span></a>')
    tarjetas += ('<a class="guiaC" href="/ofertas-reales"><span class="guiaF"><img src="/assets/puma-sello.webp" alt="" width="480" height="480" loading="lazy" decoding="async"></span>'
                 '<span class="guiaT"><small>Detector de ofertas</small><strong>¿Es una oferta real o un precio inflado?</strong>'
                 '<span>Qué equipos están hoy en el precio más bajo que hemos visto.</span><b>Ver ofertas reales</b></span></a>')
    for g in GUIAS:
        r = rankings.get(g['slug'])
        if not r:
            continue
        u = r[0]
        f, _ = foto_de(u['x']['id'], fotos)
        img = f'<img src="{e(f)}" alt="" width="480" height="480" loading="lazy" decoding="async" referrerpolicy="no-referrer">' if f else ''
        tarjetas += (f'<a class="guiaC" href="/guia/{g["slug"]}"><span class="guiaF">{img}</span><span class="guiaT">'
                     f'<small>{TIPOS[g["k"]][0]} · Guía del puma</small><strong>{e(g["titulo"])}</strong>'
                     f'<span>Hoy gana el {e(u["x"]["nombre"])}, a {precio_html(u["x"]["os"][0])}{pago(u["x"]["os"][0])} en {TIENDAS[u["x"]["os"][0]["s"]][0]}.</span>'
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
    CARP = {k: '/' + c[2] + '/' for k, c in CATS.items()}
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
    mins = minimos_historicos(todos, hist, hoy)
    for carpeta in [c[2] for c in CATS.values()]:
        os.makedirs(os.path.join(RAIZ, carpeta), exist_ok=True)
    escritas = 0
    for x in todos:
        ruta = os.path.join(RAIZ, urls[x['id']].lstrip('/') + '.html')
        nuevo = pagina(x, urls[x['id']], fotos, hist, todos, urls, hoy_txt, hoy, mins)
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
    g0 = GUIAS[0]
    bf = pagina_black_friday(pagina_guia(g0, rankings[g0['slug']], fotos, urls, hoy_txt, hoy), todos, hist, urls, fotos, hoy_txt)
    ruta = os.path.join(RAIZ, 'black-friday.html')
    if bf != (open(ruta, encoding='utf-8').read() if os.path.exists(ruta) else ''):
        open(ruta, 'w', encoding='utf-8').write(bf); escritas += 1
    bj = pagina_bajones(pagina_guia(g0, rankings[g0['slug']], fotos, urls, hoy_txt, hoy), bajadas(todos, hist, hoy, urls), urls, fotos, hoy_txt, hoy)
    ruta = os.path.join(RAIZ, 'bajones.html')
    if bj != (open(ruta, encoding='utf-8').read() if os.path.exists(ruta) else ''):
        open(ruta, 'w', encoding='utf-8').write(bj); escritas += 1
    orl = pagina_ofertas_reales(pagina_guia(g0, rankings[g0['slug']], fotos, urls, hoy_txt, hoy), ofertas_reales(todos, hist, hoy, urls), fotos, hoy_txt, hoy, movimiento(todos, hoy))
    ruta = os.path.join(RAIZ, 'ofertas-reales.html')
    if orl != (open(ruta, encoding='utf-8').read() if os.path.exists(ruta) else ''):
        open(ruta, 'w', encoding='utf-8').write(orl); escritas += 1
    base_g = pagina_guia(g0, rankings[g0['slug']], fotos, urls, hoy_txt, hoy)
    for c in QUE_COMPRAR:
        ruta = os.path.join(RAIZ, 'guia', c['slug'] + '.html')
        nuevo = pagina_que_comprar(base_g, c, todos, urls, fotos, hoy_txt, hoy)
        if nuevo != (open(ruta, encoding='utf-8').read() if os.path.exists(ruta) else ''):
            open(ruta, 'w', encoding='utf-8').write(nuevo); escritas += 1
    for k, (_, _, archivo) in TIPOS.items():
        if _poner_bloque(archivo + '.html', 'lista', bloque_categoria(k, todos, urls, rankings), '  <footer class="note">'):
            escritas += 1
    if _poner_bloque('index.html', 'guias', bloque_portada(rankings, fotos, urls), '  <section class="sec wrap" id="como"'):
        escritas += 1
    # Enlaces para las páginas que se arman en el navegador
    open(os.path.join(RAIZ, 'assets', 'fichas.js'), 'w', encoding='utf-8').write(
        '/* Generado por herramientas/fichas.py: dirección de la ficha de cada equipo y equipos en su mínimo histórico. */\n'
        'window.CMC_FICHAS = ' + json.dumps(urls, ensure_ascii=False, separators=(',', ':')) + ';\n'
        '/* Mínimo histórico: {ficha: [precio, primer día con precio]} (sello en las tarjetas, assets/cmc-ui.js) */\n'
        'window.CMC_MINIMOS = ' + json.dumps({urls[i]: [p, d.isoformat()] for i, (p, d) in mins.items()}, ensure_ascii=False, separators=(',', ':')) + ';\n')
    # Tiendas oficiales de cada marca, para todas las páginas (nombre y color; ver precios.OFICIALES)
    open(os.path.join(RAIZ, 'assets', 'oficiales.js'), 'w', encoding='utf-8').write(
        '/* Generado por herramientas/fichas.py desde precios.OFICIALES: tiendas oficiales de cada marca. */\n'
        'window.CMC_OFICIALES = ' + json.dumps(precios.OFICIALES, ensure_ascii=False, separators=(',', ':')) + ';\n')
    # Datos livianos para la portada: todas las categorías en un solo archivo (sin enlaces ni notas)
    port = []
    for x in todos:
        q = {k: v for k, v in x['eq'].items() if k != 'offers'}
        q['offers'] = [{k: o[k] for k in ('s', 'p', 'c', 'x', 'cup') if k in o} for o in x['eq']['offers']]
        port.append({'k': x['k'], **q})
    open(os.path.join(RAIZ, 'assets', 'portada.json'), 'w', encoding='utf-8').write(json.dumps(port, ensure_ascii=False, separators=(',', ':')))
    # Precio de hoy de cada ficha y bajadas del día, para los avisos por correo (functions/api/revisar-avisos.js).
    # Se ordena por dirección de ficha: así los avisos y comentarios siguen al equipo aunque cambie su id.
    # Los avisos siguen el precio de la tienda: un cupón no manda correos, porque el correo no explica el cupón
    eqs = {urls[x['id']].lstrip('/'): [precio_tienda(x) if x['os'] else None, x['nombre'], x['id'], TIENDAS[de_tienda(x)['s']][0] if x['os'] else '']
           for x in todos}
    baj = bajadas(todos, hist, hoy, urls)
    av = {'dia': hoy.isoformat(), 'equipos': eqs, 'bajadas': [[b['ficha'], b['antes'], b['ahora']] for b in baj[:12]]}
    av = {'v': hashlib.md5(json.dumps(av, sort_keys=True).encode()).hexdigest()[:12], **av}
    open(os.path.join(RAIZ, 'assets', 'avisos.json'), 'w', encoding='utf-8').write(json.dumps(av, ensure_ascii=False, separators=(',', ':')))
    # Mapa del sitio para Google
    lm = hoy.isoformat()
    filas = [f'  <url><loc>{SITIO}/</loc><lastmod>{lm}</lastmod><changefreq>daily</changefreq><priority>1.0</priority></url>',
            ] + [f'  <url><loc>{SITIO}/{c[1]}</loc><lastmod>{lm}</lastmod><changefreq>daily</changefreq><priority>0.9</priority></url>' for c in CATS.values()]
    filas += [f'  <url><loc>{SITIO}{u}</loc><lastmod>{lm}</lastmod><changefreq>monthly</changefreq><priority>0.7</priority></url>' for _, u, _ in CALCULADORAS]
    filas += [f'  <url><loc>{SITIO}/ofertas-reales</loc><lastmod>{lm}</lastmod><changefreq>daily</changefreq><priority>0.9</priority></url>']
    filas += [f'  <url><loc>{SITIO}/bajones</loc><lastmod>{lm}</lastmod><changefreq>daily</changefreq><priority>0.9</priority></url>']
    filas += [f'  <url><loc>{SITIO}/black-friday</loc><lastmod>{lm}</lastmod><changefreq>daily</changefreq><priority>0.9</priority></url>']
    filas += [f'  <url><loc>{SITIO}/guia/{c["slug"]}</loc><lastmod>{lm}</lastmod><changefreq>daily</changefreq><priority>0.8</priority></url>' for c in QUE_COMPRAR]
    filas += [f'  <url><loc>{SITIO}/guia/{g["slug"]}</loc><lastmod>{lm}</lastmod><changefreq>daily</changefreq><priority>0.8</priority></url>' for g in GUIAS]
    filas += [f'  <url><loc>{SITIO}{urls[x["id"]]}</loc><lastmod>{lm}</lastmod><changefreq>daily</changefreq><priority>0.7</priority></url>' for x in todos if x['os']]
    open(os.path.join(RAIZ, 'sitemap.xml'), 'w', encoding='utf-8').write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + '\n'.join(filas) + '\n</urlset>\n')
    print(f'Fichas: {len(todos)} equipos, {escritas} páginas nuevas o cambiadas. Imágenes para compartir nuevas: {n_og}. Historial: {len(hist)} equipos con datos. Bajadas del día: {len(baj)}. Mínimos históricos: {len(mins)}.')


if __name__ == '__main__':
    main()
