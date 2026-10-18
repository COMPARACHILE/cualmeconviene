#!/usr/bin/env python3
"""Fotos de productos de ¿Cuál me conviene?

Cada equipo tiene una foto en assets/p/<id>.webp (cuadrada, fondo blanco, 480 px).
La foto original sale de la ficha de una tienda; la dirección queda en herramientas/fotos.json.

  python3 herramientas/fotos.py faltan
      Muestra los equipos de la página que todavía no tienen foto, con la ficha de la tienda
      que conviene abrir para sacarla (con herramientas/leer_fotos.js).

  python3 herramientas/fotos.py descargar [--todas]
      Descarga las fotos de fotos.json que faltan en assets/p/ (o todas) y las deja listas.
      Necesita Pillow (pip install pillow). En GitHub esto lo hace solo el flujo
      .github/workflows/fotos.yml cada vez que cambia fotos.json.
"""
import io, json, os, sys, time, urllib.request
from urllib.parse import urlparse

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAPA = os.path.join(RAIZ, 'herramientas', 'fotos.json')
CARPETA = os.path.join(RAIZ, 'assets', 'p')
LOG = os.path.join(RAIZ, 'herramientas', 'fotos-log.txt')
LADO, MARGEN = 480, 0.07
PREFERENCIA = ['falabella', 'pcfactory', 'paris', 'ripley', 'entel', 'movistar', 'claro', 'wom']
REFERER = {'media.falabella.com': 'https://www.falabella.com/', 'rimage.ripley.cl': 'https://simple.ripley.cl/',
           'assets.pcfactory.cl': 'https://www.pcfactory.cl/', 'miportal.entel.cl': 'https://miportal.entel.cl/',
           'catalogo.movistar.cl': 'https://catalogo.movistar.cl/'}


def equipos():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import precios
    _, _, nbs, _, _, phs = precios.cargar()
    return nbs + phs, precios.ruta


def faltan():
    mapa = json.load(open(MAPA, encoding='utf-8')) if os.path.exists(MAPA) else {}
    lst, ruta = equipos()
    por = {}
    for eq in lst:
        if eq['id'] in mapa and os.path.exists(os.path.join(CARPETA, eq['id'] + '.webp')):
            continue
        o = sorted(eq['offers'], key=lambda o: (o.get('x', 0), PREFERENCIA.index(o['s']) if o['s'] in PREFERENCIA else 99))[0]
        por.setdefault(o['s'], []).append([eq['id'], ruta(o) if o['s'] != 'pcfactory' else o['url']])
    if not por:
        print('Todos los equipos tienen foto.')
    for t, rs in por.items():
        print(f'## {t} ({len(rs)}) · abrir la tienda, pegar leer_fotos.js y: await fotos(RUTAS)')
        print('RUTAS =', json.dumps(rs, ensure_ascii=False, separators=(',', ':')))


def bajar(url):
    host = urlparse(url).netloc
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36',
        'Accept': 'image/avif,image/webp,image/png,image/jpeg,*/*;q=0.8',
        'Referer': REFERER.get(host, 'https://' + host + '/')})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read()


def preparar(datos):
    """Fondo blanco, recorta el borde blanco sobrante y centra en un cuadrado de LADO px."""
    from PIL import Image, ImageChops
    im = Image.open(io.BytesIO(datos))
    im.load()
    if im.mode in ('RGBA', 'LA', 'P'):
        im = im.convert('RGBA')
        fondo = Image.new('RGBA', im.size, (255, 255, 255, 255))
        im = Image.alpha_composite(fondo, im)
    im = im.convert('RGB')
    gris = ImageChops.difference(im, Image.new('RGB', im.size, (255, 255, 255))).convert('L').point(lambda v: 255 if v > 14 else 0)
    caja = gris.getbbox()
    if caja:
        im = im.crop(caja)
    util = int(LADO * (1 - 2 * MARGEN))
    im.thumbnail((util, util), Image.LANCZOS)
    lienzo = Image.new('RGB', (LADO, LADO), (255, 255, 255))
    lienzo.paste(im, ((LADO - im.width) // 2, (LADO - im.height) // 2))
    out = io.BytesIO()
    lienzo.save(out, 'WEBP', quality=80, method=6)
    return out.getvalue()


def descargar(todas=False):
    mapa = json.load(open(MAPA, encoding='utf-8'))
    os.makedirs(CARPETA, exist_ok=True)
    log, ok, mal = [], 0, 0
    for i, url in mapa.items():
        destino = os.path.join(CARPETA, i + '.webp')
        if os.path.exists(destino) and not todas:
            continue
        for intento in range(3):
            try:
                webp = preparar(bajar(url))
                open(destino, 'wb').write(webp)
                log.append(f'ok\t{i}\t{len(webp)//1024} KB'); ok += 1
                break
            except Exception as e:
                if intento == 2:
                    log.append(f'ERROR\t{i}\t{str(e)[:120]}\t{url}'); mal += 1
                else:
                    time.sleep(2 + 3 * intento)
    resumen = f'Fotos nuevas: {ok} · con error: {mal} · total en la carpeta: {len([f for f in os.listdir(CARPETA) if f.endswith(".webp")])}'
    open(LOG, 'w', encoding='utf-8').write(resumen + '\n' + '\n'.join(log) + '\n')
    print(resumen)
    for l in log:
        if l.startswith('ERROR'):
            print(l)


if __name__ == '__main__':
    if len(sys.argv) >= 2 and sys.argv[1] == 'faltan': faltan()
    elif len(sys.argv) >= 2 and sys.argv[1] == 'descargar': descargar('--todas' in sys.argv)
    else: print(__doc__)
