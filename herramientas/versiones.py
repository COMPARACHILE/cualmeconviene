#!/usr/bin/env python3
"""Pone un número de versión (?v=<huella>) a los archivos compartidos del sitio en todas las páginas.

Las páginas .html se piden de nuevo en cada visita, pero los navegadores guardan
assets/fotos.js, fichas.js, cmc.js y las hojas de estilo hasta 4 horas. Sin versión, quien
visitó el sitio hace poco sigue viendo la lista vieja de fotos (equipos nuevos sin imagen).
Con ?v=<huella del contenido>, cada cambio en esos archivos obliga al navegador a bajarlos de nuevo.

  python3 herramientas/versiones.py      (lo corre solo el flujo .github/workflows/sitio.yml)
"""
import glob, hashlib, os, re

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVOS = ['fotos.js', 'fichas.js', 'cmc.js', 'cmc-ui.js', 'cmc.css', 'ficha.css', 'comentarios.js', 'panel.js']


def huella(nombre):
    ruta = os.path.join(RAIZ, 'assets', nombre)
    return hashlib.md5(open(ruta, 'rb').read()).hexdigest()[:8] if os.path.exists(ruta) else None


def main():
    hs = {n: huella(n) for n in ARCHIVOS}
    hs = {n: h for n, h in hs.items() if h}
    patron = re.compile(r'((?:src|href)="/assets/)(' + '|'.join(re.escape(n) for n in hs) + r')(\?v=[0-9a-f]+)?"')
    paginas = glob.glob(os.path.join(RAIZ, '*.html')) + glob.glob(os.path.join(RAIZ, '*', '*.html'))
    cambiadas = 0
    for p in paginas:
        if os.sep + 'herramientas' + os.sep in p or os.sep + 'resultados' in p:
            continue
        txt = open(p, encoding='utf-8').read()
        nuevo = patron.sub(lambda m: f'{m.group(1)}{m.group(2)}?v={hs[m.group(2)]}"', txt)
        if nuevo != txt:
            open(p, 'w', encoding='utf-8').write(nuevo)
            cambiadas += 1
    print('Versiones:', ' '.join(f'{n}={h}' for n, h in hs.items()), f'· páginas actualizadas: {cambiadas}')


if __name__ == '__main__':
    main()
