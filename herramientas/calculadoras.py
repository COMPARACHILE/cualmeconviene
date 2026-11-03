"""Arma las calculadoras (calculadora-btu.html y calculadora-tamano-tv.html) con la cabecera y el pie de una guía.
Uso: python3 herramientas/fichas.py && python3 herramientas/calculadoras.py   (lee guia/que-smart-tv-comprar.html como plantilla)"""
import os, re, json, html
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITIO = 'https://cualmeconviene.cl'
e = html.escape

ESTILO = '''<style>
.calc{display:grid;gap:14px;max-width:560px;margin:18px 0}
.calc label{display:grid;gap:6px;font-weight:600}
.calc input,.calc select{font:inherit;padding:12px 14px;border:1.5px solid #c9cfe6;border-radius:12px;background:#fff;color:#0E1533;min-height:46px}
.calc button{font:inherit;font-weight:700;padding:13px 18px;border:0;border-radius:12px;background:#FFD84D;color:#0E1533;cursor:pointer;min-height:46px}
.calc button:focus-visible,.calc input:focus-visible,.calc select:focus-visible{outline:3px solid #3B4FD6;outline-offset:2px}
.res{border:2px solid #0E1533;border-radius:16px;padding:16px 18px;margin:14px 0;background:#fff}
.res[hidden]{display:none}
.res .gran{font-size:1.9rem;font-weight:800;margin:0}
</style>'''

CALCS = [
    {'archivo': 'calculadora-btu.html', 'url': '/calculadora-btu', 'cat': ('Aires acondicionados', '/aires-acondicionados'),
     'titulo': '¿Cuántos BTU necesito? Calculadora de aire acondicionado',
     'h1': '¿Cuántos BTU necesito para mi aire acondicionado?',
     'desc': 'Calcula cuántos BTU necesita tu pieza según los metros cuadrados, el sol y las personas, y mira qué aires acondicionados hay hoy en Chile con esa capacidad.',
     'intro': 'Responde cuatro datos de la pieza y te decimos qué capacidad de aire acondicionado necesitas, con los modelos que hoy tienen ese tamaño en las tiendas de Chile.',
     'form': '''<form class="calc" id="f" novalidate>
  <label>Metros cuadrados de la pieza<input id="m2" type="number" inputmode="decimal" min="5" max="120" step="0.5" value="15" required></label>
  <label>Personas que suelen estar<input id="pers" type="number" inputmode="numeric" min="1" max="12" value="2"></label>
  <label>Sol en la pieza<select id="sol"><option value="0">Poco sol o piso intermedio</option><option value="1" selected>Le da sol una parte del día</option><option value="2">Mucho sol de tarde o último piso</option></select></label>
  <label>Equipos que dan calor<select id="eq"><option value="0">Ninguno importante</option><option value="1">Computador o televisor grande</option><option value="2">Cocina abierta o varios equipos</option></select></label>
  <button type="submit">Calcular</button>
</form>''',
     'extra': ['Qué significa BTU', 'BTU es la unidad que mide cuánto calor puede sacar o poner un aire acondicionado en una hora. Mientras más grande la pieza, más BTU necesitas.',
               'Si me paso o me quedo corto', 'Uno muy chico trabaja siempre al máximo y no logra enfriar. Uno muy grande se enciende y apaga seguido, gasta más y deshumidifica mal. Lo mejor es el tamaño comercial que más se acerque al resultado.',
               'Inverter o no', 'El inverter ajusta su velocidad y gasta menos electricidad. Es más caro, pero se paga con las cuentas si lo usas a diario.',
               'Aviso', 'Es una estimación para una pieza con altura normal (2,4 m). Para casas con techos altos, muchos ventanales o más de una pieza, pide una evaluación a un instalador.'],
     'js': '''
const m2 = +$('m2').value || 0, pers = +$('pers').value || 1, sol = +$('sol').value, eq = +$('eq').value;
if (m2 < 5) { return; }
let btu = m2 * 600 + Math.max(0, pers - 2) * 600 + eq * 600;
btu *= [1, 1.1, 1.2][sol];
const TAM = [9000, 12000, 18000, 24000, 30000, 36000];
const tam = TAM.find(t => t >= btu * 0.95) || TAM[TAM.length - 1];
$('r').hidden = false;
$('r').innerHTML = '<p class="gran">' + tam.toLocaleString('es-CL') + ' BTU</p><p>Tu pieza necesita unos ' + (Math.round(btu / 100) * 100).toLocaleString('es-CL') + ' BTU. El tamaño comercial más cercano es de <b>' + tam.toLocaleString('es-CL') + ' BTU</b>.</p>';
mostrar(ALL.filter(x => x.k === 'ac' && x.tipo !== 'portatil' && x.btu === tam), x => (x.inv ? 0 : 1), 'Los más baratos de ' + tam.toLocaleString('es-CL') + ' BTU hoy', x => (x.inv ? 'inverter' : 'sin inverter') + ', ' + (x.calor ? 'frío y calor' : 'solo frío'));
'''},
    {'archivo': 'calculadora-tamano-tv.html', 'url': '/calculadora-tamano-tv', 'cat': ('Televisores', '/televisores'),
     'titulo': '¿Qué tamaño de TV me sirve? Calculadora de pulgadas',
     'h1': '¿Qué tamaño de televisor me sirve?',
     'desc': 'Calcula cuántas pulgadas de televisor te convienen según la distancia al sillón, y mira los smart TV 4K más baratos de ese tamaño hoy en Chile.',
     'intro': 'Dinos a qué distancia te sientas y te decimos qué tamaño de pantalla se ve mejor, con los smart TV 4K más baratos de ese tamaño hoy.',
     'form': '''<form class="calc" id="f" novalidate>
  <label>Distancia del sillón a la tele (en metros)<input id="d" type="number" inputmode="decimal" min="1" max="8" step="0.1" value="3" required></label>
  <label>Qué vas a ver más<select id="uso"><option value="0">Series, noticias y de todo un poco</option><option value="1">Películas y juegos (más inmersivo)</option></select></label>
  <button type="submit">Calcular</button>
</form>''',
     'extra': ['La regla simple', 'Divide la distancia en pulgadas entre 1,8. Por ejemplo, a 3 metros (118 pulgadas) conviene una pantalla de unas 65 pulgadas.',
               'Si te quedas entre dos tamaños', 'En 4K puedes sentarte cerca sin ver los puntos, así que si dudas elige el más grande. Mide el espacio del mueble y de la pared antes de comprar.',
               'Resolución', 'Desde 43 pulgadas conviene 4K. Casi todos los que se venden hoy lo son.',
               'Aviso', 'Es una guía general. Mide el espacio disponible: una pantalla de 65 pulgadas mide cerca de 145 cm de ancho.'],
     'js': '''
const d = +$('d').value || 0, uso = +$('uso').value;
if (d < 1) { return; }
const diag = d * 100 / 2.54 / (uso ? 1.5 : 1.8);
const TAM = [32, 43, 50, 55, 65, 75, 85, 98];
const tam = TAM.reduce((a, b) => Math.abs(b - diag) < Math.abs(a - diag) ? b : a);
$('r').hidden = false;
$('r').innerHTML = '<p class="gran">' + tam + ' pulgadas</p><p>A ' + String(d).replace('.', ',') + ' metros, el tamaño ideal es de unas ' + Math.round(diag) + ' pulgadas. El tamaño comercial más cercano es de <b>' + tam + ' pulgadas</b>.</p>';
mostrar(ALL.filter(x => x.k === 'tv' && x.size === tam && x.res === '4K'), x => 0, 'Los smart TV 4K de ' + tam + ' pulgadas más baratos hoy', x => (x.panel || '') + (x.hz ? ', ' + x.hz + ' Hz' : ''));
'''},
]

JS_BASE = '''<script>
(function () {
  const $ = id => document.getElementById(id);
  const CLP = n => '$' + Math.round(n).toLocaleString('es-CL');
  let ALL = [];
  const precio = x => Math.min(...x.offers.map(o => (o.cup && o.cup.pc && o.cup.pc < o.p && !(Date.parse(o.cup.v) <= Date.now())) ? o.cup.pc : o.p));
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  function mostrar(xs, orden, titulo, detalle) {
    xs = xs.filter(x => x.offers && x.offers.length && !x.refurb).sort((a, b) => orden(a) - orden(b) || precio(a) - precio(b)).slice(0, 5);
    $('lista').innerHTML = xs.length ? '<h2>' + esc(titulo) + '</h2><ol class="rk">' + xs.map(x =>
      '<li class="rkI"><div class="rkT"><h3><a href="' + esc((window.CMC_FICHAS && CMC_FICHAS[x.id]) || '#') + '">' + esc(x.name) + '</a></h3><p class="sp">' + esc(detalle(x)) + '</p></div>' +
      '<div class="rkP"><p class="precio">' + CLP(precio(x)) + '</p><a class="tb" href="' + esc((window.CMC_FICHAS && CMC_FICHAS[x.id]) || '#') + '">Ver precios</a></div></li>').join('') + '</ol>'
      : '<p class="nota">Hoy no encontramos equipos de ese tamaño en las tiendas. Mira la <a href="__CAT__">lista completa</a>.</p>';
  }
  $('f').addEventListener('submit', ev => {
    ev.preventDefault();
    const go = () => { __JS__ };
    if (ALL.length) return go();
    fetch('/assets/portada.json').then(r => r.json()).then(d => { ALL = d; go(); }).catch(() => { $('r').hidden = false; $('r').textContent = 'No pudimos cargar los precios. Intenta de nuevo.'; });
  });
})();
</script>'''


def main():
    base = os.path.join(RAIZ, 'guia', 'que-smart-tv-comprar.html')
    h = open(base, encoding='utf-8').read()
    i, j = h.index('<main'), h.index('</main>') + 7
    cab, pie = h[:i], h[j:]
    for c in CALCS:
        url = SITIO + c['url']
        ld = {'@context': 'https://schema.org', '@graph': [
            {'@type': 'WebPage', 'name': c['titulo'], 'url': url, 'inLanguage': 'es-CL', 'description': c['desc']},
            {'@type': 'BreadcrumbList', 'itemListElement': [
                {'@type': 'ListItem', 'position': 1, 'name': 'Inicio', 'item': SITIO + '/'},
                {'@type': 'ListItem', 'position': 2, 'name': c['cat'][0], 'item': SITIO + c['cat'][1]},
                {'@type': 'ListItem', 'position': 3, 'name': c['h1'], 'item': url}]}]}
        x = cab
        for patron, nuevo in [(r'<title>.*?</title>', f'<title>{e(c["titulo"])} | ¿Cuál me conviene?</title>'),
                              (r'<meta name="description" content=".*?">', f'<meta name="description" content="{e(c["desc"])}">'),
                              (r'<link rel="canonical" href=".*?">', f'<link rel="canonical" href="{url}">'),
                              (r'<meta property="og:title" content=".*?">', f'<meta property="og:title" content="{e(c["h1"])}">'),
                              (r'<meta property="og:description" content=".*?">', f'<meta property="og:description" content="{e(c["desc"])}">'),
                              (r'<meta property="og:url" content=".*?">', f'<meta property="og:url" content="{url}">'),
                              (r'<script type="application/ld\+json">.*?</script>', '<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False).replace('</', '<\\/') + '</script>' + ESTILO)]:
            x, n = re.subn(patron, lambda m: nuevo, x, count=1, flags=re.S)
            if not n:
                raise SystemExit('plantilla sin ' + patron)
        x = re.sub(r' aria-current="page"', '', x)
        x = x.replace('<script defer src="/assets/cmc.js"></script>', '<script src="/assets/fichas.js"></script>\n<script defer src="/assets/cmc.js"></script>', 1)
        extra = ''.join(f'<h3>{e(a)}</h3><p>{e(b)}</p>' for a, b in zip(c['extra'][::2], c['extra'][1::2]))
        main = (f'<main class="wrap gPag"><nav class="migas" aria-label="Ruta"><a href="/">Inicio</a><span aria-hidden="true">›</span><a href="{c["cat"][1]}">{e(c["cat"][0])}</a><span aria-hidden="true">›</span><span aria-current="page">Calculadora</span></nav>'
                f'<h1>{e(c["h1"])}</h1><p class="sp">{e(c["intro"])}</p>{c["form"]}<div class="res" id="r" hidden aria-live="polite"></div><section class="bloque" id="lista" aria-live="polite"></section>'
                f'<section class="bloque"><h2>Cómo usar el resultado</h2>{extra}</section>'
                f'<p class="nota"><a href="{c["cat"][1]}">Ver y comparar todos: {e(c["cat"][0].lower())}</a></p></main>')
        js = JS_BASE.replace('__JS__', c['js'].replace('return;', 'return;').strip()).replace('__CAT__', c['cat'][1])
        open(os.path.join(RAIZ, c['archivo']), 'w', encoding='utf-8').write(x + main + pie.replace('</body>', js + '\n</body>', 1) if False else x + main + pie.replace('<script>', js + '\n<script>', 1))
        print('escrita', c['archivo'])


if __name__ == '__main__':
    main()
