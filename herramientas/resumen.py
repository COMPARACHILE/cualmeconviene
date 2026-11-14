"""Arma el resumen diario de precios (el mismo que entregaba Claude) a partir de la salida de `precios.py aplicar`.

Uso: python3 herramientas/resumen.py <salida_de_aplicar.txt> <carpeta_lectura> [origen]
Escribe assets/resumen-precios.json = {dia, v, asunto, texto, html}. La función /api/resumen-precios lo envía
por correo una sola vez por versión (v). Incluye enlaces con marca y modelo de lo que bajó bastante y de los
mínimos históricos, y la lista de tiendas que no se pudieron leer.
"""
import sys, os, re, json, glob, html, datetime, hashlib
sys.path.insert(0, os.path.dirname(__file__))
import precios as P

salida, carpeta = sys.argv[1], sys.argv[2]
origen = sys.argv[3] if len(sys.argv) > 3 else ''
L = open(salida, encoding='utf-8').read().split('\n')

_, _, nbs, _, _, phs = P.cargar()
grupos = [('notebook', nbs), ('celular', phs)] + [(P.EXTRA[k][1], l) for k, (_, _, l) in P.cargar_extra().items()]
enl = {}
for g, lst in grupos:
    for eq in lst:
        n = eq['name'] + (f" {eq['gb']} GB" if g in ('celular', 'tablet') else '')
        for o in eq['offers']:
            enl.setdefault((n, o['s']), o['url'])

# Informe de lectura de cada tienda (lo deja leer.mjs): tiendas que fallaron o que no trajeron precios
fallas = []
for f in glob.glob(os.path.join(carpeta, '**', 'informe*.json'), recursive=True):
    for r in json.load(open(f, encoding='utf-8')):
        if r.get('err'):
            fallas.append(f"{r['t']}: {r['err']}")
fallas += [x.strip() for x in open(os.path.join(carpeta, 'descartadas.txt'), encoding='utf-8')] if os.path.exists(os.path.join(carpeta, 'descartadas.txt')) else []

secciones, actual = {}, None
for x in L:
    if not x.startswith('  '):
        actual = x.split(' (')[0].split(':')[0].strip()
        secciones[actual] = [x]
    elif actual:
        secciones[actual].append(x)

def con_enlace(linea):
    m = re.match(r'\s+(.+?) · ([\w-]+): ', linea)
    u = enl.get((m[1], m[2])) if m else None
    return linea.strip(), u

cab = L[0] if L else ''
n_camb = (re.search(r'cambiaron: (\d+)', cab) or [0, '0'])[1]
dia = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-3))).strftime('%d-%m-%Y')
bajas = secciones.get('REVISAR, precios sospechosamente bajos', [])
minimos = next((v for k, v in secciones.items() if k.startswith('Mínimos históricos')), [])
ocultos = next((v for k, v in secciones.items() if k.startswith('Ocultos')), [])
norev = next((v for k, v in secciones.items() if k.startswith('No revisados')), [])
cup = next((v for k, v in secciones.items() if k.startswith('Cupones')), [])

def lista(lineas, enlaces=True):
    t, h = [], []
    # "no apareció en la lectura" = tienda que no se leyó en esta vuelta: se resume en una línea por tienda
    faltan = {}
    for x in lineas[1:]:
        m = re.match(r'\s+.+ · ([\w-]+): no apareció en la lectura', x)
        if m: faltan[m[1]] = faltan.get(m[1], 0) + 1
    if faltan:
        s = 'No leídas en esta vuelta: ' + ', '.join(f'{k} ({v})' for k, v in sorted(faltan.items()))
        t.append('- ' + s); h.append('<li>' + html.escape(s) + '</li>')
    for x in lineas[1:]:
        if 'no apareció en la lectura' in x: continue
        s, u = con_enlace(x) if enlaces else (x.strip(), None)
        t.append('- ' + s + (f'\n  {u}' if u else ''))
        h.append('<li>' + html.escape(s) + (f' · <a href="{html.escape(u)}">ver</a>' if u else '') + '</li>')
    return '\n'.join(t), '<ul>' + ''.join(h) + '</ul>'

partes = [
    ('Bajaron bastante (revisar)', bajas, True),
    ('Mínimos históricos', minimos, True),
    ('Ocultos por falta de stock', ocultos, False),
    ('No revisados', norev, False),
]
texto = [f'Precios del {dia}{" · " + origen if origen else ""}: {n_camb} cambios.']
cuerpo = [f'<h2>Precios del {dia}{" · " + html.escape(origen) if origen else ""}</h2><p><b>{n_camb}</b> precios cambiaron.</p>']
if fallas:
    texto.append('\nTiendas que no se pudieron leer (quedan con el precio anterior):\n' + '\n'.join('- ' + f for f in fallas))
    cuerpo.append('<h3>Tiendas que no se pudieron leer</h3><ul>' + ''.join(f'<li>{html.escape(f)}</li>' for f in fallas) + '</ul>')
if cup:
    texto.append('\n' + cup[0]); cuerpo.append('<p>' + html.escape(cup[0]) + '</p>')
for titulo, lineas, e in partes:
    if len(lineas) > 1:
        t, h = lista(lineas, e)
        texto.append(f'\n{titulo}:\n{t}')
        cuerpo.append(f'<h3>{titulo}</h3>{h}')

res = {'dia': dia, 'v': dia + '-' + hashlib.md5('\n'.join(L).encode()).hexdigest()[:8] + '-' + origen,
       'asunto': f'Precios del {dia}{" (" + origen + ")" if origen else ""}: {n_camb} cambios' + (f', {len(bajas) - 1} bajas fuertes' if len(bajas) > 1 else ''),
       'texto': '\n'.join(texto), 'html': '\n'.join(cuerpo)}
json.dump(res, open(os.path.join(os.path.dirname(__file__), '..', 'assets', 'resumen-precios.json'), 'w', encoding='utf-8'), ensure_ascii=False)
print(res['asunto'])
