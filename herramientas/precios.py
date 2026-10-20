#!/usr/bin/env python3
"""Actualización de precios de ¿Cuál me conviene? (notebooks.html, celulares.html, tablets.html y televisores.html).

  python3 herramientas/precios.py lista
      Muestra, por tienda, qué abrir y qué rutas leer con herramientas/leer_precios.js.

  python3 herramientas/precios.py rutas
      Escribe herramientas/rutas.json ({tienda: [rutas]}, en el mismo orden que "lista"), para leerlo
      desde la pestaña de la tienda: fetch('https://raw.githubusercontent.com/COMPARACHILE/cualmeconviene/main/herramientas/rutas.json').
      El flujo de GitHub lo rehace solo cada vez que cambian los equipos.

  python3 herramientas/precios.py aplicar resultados/
      Lee los archivos <tienda>.json de esa carpeta (lo que devolvió leer_precios.js),
      actualiza precios, notas y fechas, y muestra el resumen.
"""
import json, re, sys, os, glob, datetime
from urllib.parse import urlparse

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NB, PH = os.path.join(RAIZ, 'notebooks.html'), os.path.join(RAIZ, 'celulares.html')
LISTADOS = {
    'claro': 'https://tienda.clarochile.cl/CategoryDisplay?ddkey=ProductListingView&fromPage=catalogEntryList&facet_2=ads_f12001_ntk_cs%253A%2522itemShow%2522&facet_1=ads_f11503_ntk_cs%253A%2522Liberados%2522&urlRequestType=Base&categoryId=3074457345616686668&catalogId=10052&resultType=products&showResultsPage=true&pageView=grid&beginIndex=0&pageSize=200&facetName_2=itemShow&facetName_1=Liberados&langId=-5&storeId=10151',
    'wom': 'https://store.wom.cl/equipos/?modalidad-de-compra=prepago',
}
PORTADAS = {'falabella': 'https://www.falabella.com/falabella-cl', 'paris': 'https://www.paris.cl/', 'ripley': 'https://simple.ripley.cl/',
            'entel': 'https://miportal.entel.cl/personas/catalogo/celulares', 'movistar': 'https://catalogo.movistar.cl/tienda/'}
# Sin stock o ficha borrada: la oferta se oculta en la página (x:1) hasta que vuelva
AGOTADO = {'sin stock', 'error 404', 'error 410'}
NOTA_ESTANDAR = re.compile(r'^(Con tarjeta CMR|Precio Internet|Con Tarjeta Cencosud|Con tarjeta Ripley|Transferencia o débito|Con transferencia o débito|Modalidad Prepago)')


# Categorías nuevas: mismo formato que celulares (lista JSON en una línea, "const EQUIPOS = [...];")
EXTRA = {'tb': ('tablets.html', 'tablet'), 'tv': ('televisores.html', 'televisor')}


def cargar_extra():
    """{k: (html, (inicio, fin), lista)} de tablets y televisores (solo las que existen)."""
    out = {}
    for k, (archivo, _) in EXTRA.items():
        ruta_a = os.path.join(RAIZ, archivo)
        if not os.path.exists(ruta_a):
            continue
        h = open(ruta_a, encoding='utf-8').read()
        s = h.index('const EQUIPOS = ') + len('const EQUIPOS = '); e = h.index(';\n', s)
        out[k] = (h, (s, e), json.loads(h[s:e]))
    return out


def cargar():
    nb_h = open(NB, encoding='utf-8').read()
    s = nb_h.index('const NOTEBOOKS = [') + len('const NOTEBOOKS = '); e = nb_h.index('\n];', s) + 2
    ph_h = open(PH, encoding='utf-8').read()
    s2 = ph_h.index('const PHONES = ') + len('const PHONES = '); e2 = ph_h.index(';\n', s2)
    return nb_h, (s, e), json.loads(nb_h[s:e]), ph_h, (s2, e2), json.loads(ph_h[s2:e2])


def ruta(o):
    u = urlparse(o['url'])
    if o['s'] == 'pcfactory':
        return '/producto/' + u.path.split('/producto/')[1].split('-')[0]
    return u.path


def rutas_por_tienda():
    _, _, nbs, _, _, phs = cargar()
    por = {}
    for eq in nbs + phs + [x for _, _, l in cargar_extra().values() for x in l]:
        for o in eq['offers']:
            por.setdefault(o['s'], set()).add(ruta(o))
    return {t: sorted(rs) for t, rs in por.items()}


def lista():
    for t, rs in sorted(rutas_por_tienda().items()):
        if t == 'pcfactory':
            # La búsqueda pagina y repite equipos entre páginas: se lee en tandas de 48 (caben en una página)
            ids = [r.split('/')[-1] for r in rs]
            for n, k in enumerate(range(0, len(ids), 48), 1):
                print(f'## pcfactory-{n} · abrir https://www.pcfactory.cl/busqueda?productos={",".join(ids[k:k + 48])}&size=60 · luego leerListado("pcfactory", RUTAS) · guardar como pcfactory-{n}.json')
        elif t == 'entel':
            print(f'## entel · abrir {PORTADAS[t]} · luego await leerEntel(RUTAS)')
        elif t == 'wom':
            print(f'## wom · abrir {LISTADOS[t]} · luego await leerWom(RUTAS)')
        elif t in LISTADOS:
            print(f'## {t} · abrir {LISTADOS[t]} · bajar hasta el final · luego leerListado("{t}", RUTAS)')
        else:
            print(f'## {t} · abrir {PORTADAS[t]} · luego await leer("{t}", RUTAS)')
        print(f'RUTAS ({len(rs)}) =', json.dumps(rs, ensure_ascii=False, separators=(',', ':')))


def nota(t, c, x):
    """Nota estándar según la tienda. None = no tocar la nota."""
    if t == 'falabella': return 'Con tarjeta CMR' if c else 'Precio Internet'
    if t == 'paris': return 'Con Tarjeta Cencosud Scotiabank' if c else ''
    if t == 'ripley': return ('Con tarjeta Ripley · sin tarjeta $' + f'{x:,}'.replace(',', '.')) if c and x else 'Precio Internet'
    if t == 'pcfactory': return ('Transferencia o débito · otros medios $' + f'{x:,}'.replace(',', '.')) if x else None
    return None


def aplicar(carpeta):
    nb_h, (s, e), nbs, ph_h, (s2, e2), phs = cargar()
    extra = cargar_extra()
    res, RT = {}, rutas_por_tienda()
    for f in sorted(glob.glob(os.path.join(carpeta, '*.json'))):
        t = os.path.basename(f)[:-5].split('-')[0]  # pcfactory-1.json, pcfactory-2.json... = pcfactory
        for i, p, c, x in json.load(open(f, encoding='utf-8')):
            u = RT[t][i]
            if not p and res.get((t, u), {}).get('p'):
                continue  # otra tanda ya trajo el precio
            res[(t, u)] = {'e': x or 'sin precio'} if not p else {'p': p, 'c': c, 'n': nota(t, c, x)}
    hoy = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-3))).strftime('%d-%m-%Y')
    cambios, bajos, sin, ocultos = [], [], [], []
    grupos = [('notebook', nbs), ('celular', phs)] + [(EXTRA[k][1], l) for k, (_, _, l) in extra.items()]
    for grupo, lst in grupos:
        for eq in lst:
            nombre = eq['name'] + (f" {eq['gb']} GB" if grupo in ('celular', 'tablet') else '')
            for o in eq['offers']:
                r = res.get((o['s'], ruta(o)))
                if r is None:
                    sin.append(f"{nombre} · {o['s']}: no apareció en la lectura"); continue
                if r.get('e') in AGOTADO:
                    o['x'] = 1; ocultos.append(f"{nombre} · {o['s']}: {r['e']}"); continue
                if r.get('e') or not r.get('p'):
                    sin.append(f"{nombre} · {o['s']}: {r.get('e', 'sin precio')}"); continue
                o.pop('x', None)
                nuevo, viejo = int(r['p']), o['p']
                if nuevo != viejo:
                    cambios.append((abs(nuevo - viejo), f"{nombre} · {o['s']}: {viejo:,} → {nuevo:,}".replace(',', '.')))
                    if nuevo < viejo * 0.5:
                        bajos.append(f"{nombre} · {o['s']}: {viejo:,} → {nuevo:,}".replace(',', '.'))
                o['p'] = nuevo
                if r['c'] or o['s'] in ('falabella', 'paris', 'ripley', 'pcfactory'):
                    if r['c']: o['c'] = 1
                    else: o.pop('c', None)
                if r['n'] is not None:
                    vieja = o.get('note', '')
                    if not vieja or (NOTA_ESTANDAR.match(vieja) and 'Incluye' not in vieja):
                        if r['n']: o['note'] = r['n']
                        else: o.pop('note', None)
            if grupo == 'notebook':
                eq['seen'] = hoy
            else:
                eq['offers'].sort(key=lambda x: x['p'])
    nb_txt = '[\n' + ',\n'.join('  ' + json.dumps(n, ensure_ascii=False) for n in nbs) + '\n]'
    nb_h = nb_h[:s] + nb_txt + nb_h[e:]
    nb_h = re.sub(r"const SEEN_GAMER = '[\d-]+', SEEN_OTHER = '[\d-]+';", f"const SEEN_GAMER = '{hoy}', SEEN_OTHER = '{hoy}';", nb_h)
    nb_h = re.sub(r'Todos los precios se revisaron el \d\d-\d\d-\d{4}', f'Todos los precios se revisaron el {hoy}', nb_h)
    ph_h = ph_h[:s2] + json.dumps(phs, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/') + ph_h[e2:]
    ph_h = re.sub(r"const SEEN = '[\d-]+';", f"const SEEN = '{hoy}';", ph_h)
    ph_h = re.sub(r'(operadoras de Chile · )\d\d-\d\d-\d{4}', rf'\g<1>{hoy}', ph_h)
    ph_h = re.sub(r'(ficha de cada tienda u operadora el )\d\d-\d\d-\d{4}', rf'\g<1>{hoy}', ph_h)
    open(NB, 'w', encoding='utf-8').write(nb_h)
    open(PH, 'w', encoding='utf-8').write(ph_h)
    for k, (h, (a, b), l) in extra.items():
        h = h[:a] + json.dumps(l, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/') + h[b:]
        h = re.sub(r"const SEEN = '[\d-]+';", f"const SEEN = '{hoy}';", h)
        open(os.path.join(RAIZ, EXTRA[k][0]), 'w', encoding='utf-8').write(h)
    cambios.sort(reverse=True)
    print(f'Fecha: {hoy}. Precios que cambiaron: {len(cambios)}')
    if bajos: print('REVISAR, bajaron a menos de la mitad:\n  ' + '\n  '.join(bajos))
    print('Cambios más grandes:\n  ' + '\n  '.join(c[1] for c in cambios[:5]))
    print(f'Ocultos por falta de stock ({len(ocultos)}):\n  ' + '\n  '.join(ocultos))
    print(f'No revisados ({len(sin)}):\n  ' + '\n  '.join(sin))


def escribir_rutas():
    json.dump(rutas_por_tienda(), open(os.path.join(RAIZ, 'herramientas', 'rutas.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))


if __name__ == '__main__':
    if len(sys.argv) >= 2 and sys.argv[1] == 'lista': lista()
    elif len(sys.argv) >= 2 and sys.argv[1] == 'rutas': escribir_rutas()
    elif len(sys.argv) >= 3 and sys.argv[1] == 'aplicar': aplicar(sys.argv[2])
    else: print(__doc__)
