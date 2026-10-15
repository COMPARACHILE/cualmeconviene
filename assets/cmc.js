/* ¿Cuál me conviene? — capa compartida (ver cmc.css). Sin dependencias. */
(() => {
  const reduce = matchMedia('(prefers-reduced-motion: reduce)');
  const fmt = n => '$' + Math.round(n).toLocaleString('es-CL');

  /* ---------- Altura de la cabecera fija, para que "ir a sección" no tape el título ---------- */
  const top = document.querySelector('header.top');
  const setHdr = () => {
    const sticky = top && getComputedStyle(top).position === 'sticky';
    document.documentElement.style.setProperty('--hdr', sticky ? top.offsetHeight + 'px' : '0px');
  };
  setHdr();
  addEventListener('resize', setHdr, { passive: true });

  /* ---------- Resaltar la sección a la que se salta ---------- */
  const flash = el => {
    if (!el) return;
    el.classList.remove('flash'); void el.offsetWidth; el.classList.add('flash');
    clearTimeout(el._fl); el._fl = setTimeout(() => el.classList.remove('flash'), 2000);
  };
  document.addEventListener('click', e => {
    const g = e.target.closest('[data-go]');
    if (!g) return;
    const id = g.dataset.go;
    // Espera a que la página termine de desplazarse para que el resaltado se vea
    setTimeout(() => {
      const el = document.getElementById(id);
      if (!el || el.hidden) return;
      const head = el.querySelector('h2, h1') || el;
      if (head !== el) head.setAttribute('tabindex', '-1');
      head.focus({ preventScroll: true });
      flash(el);
    }, reduce.matches ? 30 : 420);
  });

  /* ---------- 1. Filtro de precio de dos puntos ---------- */
  const duals = [...document.querySelectorAll('[data-dual]')];
  const sync = () => duals.forEach(d => {
    const [lo, hi] = d.querySelectorAll('input[type=range]');
    const max = +hi.max || 1;
    if (+lo.value > +hi.value) lo.value = hi.value;
    d.style.setProperty('--a', (+lo.value / max) * 100 + '%');
    d.style.setProperty('--b', (+hi.value / max) * 100 + '%');
    // Si ambos puntos quedan juntos en el extremo derecho, el mínimo debe poder tomarse
    lo.classList.toggle('up', +lo.value >= max * 0.5);
    hi.classList.toggle('up', +lo.value < max * 0.5);
    lo.setAttribute('aria-valuetext', fmt(lo.value));
    hi.setAttribute('aria-valuetext', fmt(hi.value));
  });
  duals.forEach(d => {
    const [lo, hi] = d.querySelectorAll('input[type=range]');
    // En captura: corrige el cruce antes de que la página lea los valores
    d.addEventListener('input', e => {
      if (e.target === lo && +lo.value > +hi.value) lo.value = hi.value;
      if (e.target === hi && +hi.value < +lo.value) hi.value = lo.value;
      sync();
    }, true);
    // Tocar la barra (fuera de los puntos) mueve el punto más cercano
    d.addEventListener('pointerdown', e => {
      if (e.target.tagName === 'INPUT') return;
      const r = d.getBoundingClientRect();
      const step = +hi.step || 1;
      const v = Math.round(Math.min(1, Math.max(0, (e.clientX - r.left - 11) / (r.width - 22))) * +hi.max / step) * step;
      const near = Math.abs(v - lo.value) <= Math.abs(v - hi.value) && v <= +hi.value ? lo : hi;
      near.value = v; near.focus();
      near.dispatchEvent(new Event('input', { bubbles: true }));
      near.dispatchEvent(new Event('change', { bubbles: true }));
    });
  });
  window.cmcSync = sync;
  sync();
  document.addEventListener('click', () => setTimeout(sync, 0));

  /* ---------- 8. Los ojos del puma siguen el cursor (solo con mouse) ---------- */
  if (!reduce.matches && matchMedia('(hover: hover) and (pointer: fine)').matches) {
    const big = document.querySelector('.mascot');
    let raf = 0;
    addEventListener('pointermove', e => {
      if (!big || raf) return;
      raf = requestAnimationFrame(() => {
        raf = 0;
        const r = big.getBoundingClientRect();
        const dx = (e.clientX - (r.left + r.width / 2)) / innerWidth;
        const dy = (e.clientY - (r.top + r.height * 0.35)) / innerHeight;
        document.querySelectorAll('#pumaHead .pupils').forEach(p => {
          p.setAttribute('transform', `translate(${(dx * 5).toFixed(2)} ${(dy * 4).toFixed(2)})`);
        });
      });
    }, { passive: true });
  }

  /* ---------- 8. Aparición escalonada, una sola vez, al entrar en pantalla ---------- */
  if ('IntersectionObserver' in window && !reduce.matches) {
    const io = new IntersectionObserver(es => es.forEach(en => {
      if (en.isIntersecting) { en.target.classList.add('stag'); io.unobserve(en.target); }
    }), { rootMargin: '0px 0px -10% 0px' });
    window.cmcStagger = el => { if (el) io.observe(el); };
  } else window.cmcStagger = () => {};

  /* ---------- 9. Opiniones ---------- */
  const PAGE = location.pathname.replace(/\.html$/, '').replace(/\/$/, '') || '/';
  const UP = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7 11v9H4v-9z"/><path d="M7 11l4-7c1.4 0 2.3 1 2 2.4L12.5 10H18a2 2 0 0 1 2 2.3l-1.2 6A2 2 0 0 1 16.8 20H7"/></svg>';
  const DOWN = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="transform:rotate(180deg)"><path d="M7 11v9H4v-9z"/><path d="M7 11l4-7c1.4 0 2.3 1 2 2.4L12.5 10H18a2 2 0 0 1 2 2.3l-1.2 6A2 2 0 0 1 16.8 20H7"/></svg>';
  const head = '<svg viewBox="0 0 120 120" aria-hidden="true"><use href="#pumaHead"/></svg>';

  const btn = document.createElement('button');
  btn.type = 'button'; btn.className = 'fb-open'; btn.setAttribute('aria-haspopup', 'dialog');
  btn.innerHTML = head + '<span class="t">¿Qué te parece?</span>';
  btn.setAttribute('aria-label', 'Danos tu opinión sobre la página');
  const box = document.createElement('div');
  box.className = 'fb'; box.hidden = true; box.setAttribute('role', 'dialog'); box.setAttribute('aria-labelledby', 'fbT');
  box.innerHTML = `
    <button type="button" class="fb-x" aria-label="Cerrar">&times;</button>
    <form novalidate>
      <h2 id="fbT">¿Te sirvió la página?</h2>
      <p class="sub">Tu opinión decide qué agregamos después. Es anónima.</p>
      <div class="fb-vote" role="group" aria-label="¿Te gustó?">
        <button type="button" data-v="1" aria-pressed="false">${UP}Me gustó</button>
        <button type="button" data-v="-1" aria-pressed="false">${DOWN}No me convenció</button>
      </div>
      <label for="fbTxt">¿Qué mejorarías o te gustaría que agregáramos?</label>
      <textarea id="fbTxt" maxlength="600" placeholder="Ej.: comparar tablets, avisarme cuando baje un precio, más tiendas…"></textarea>
      <div class="hp" aria-hidden="true"><label>No llenar<input name="web" tabindex="-1" autocomplete="off"></label></div>
      <div class="row"><span class="cnt" aria-live="polite">0/600</span><button type="submit" class="fb-send" disabled>Enviar opinión</button></div>
      <p class="msg" aria-live="polite"></p>
    </form>`;
  document.body.append(btn, box);

  const form = box.querySelector('form'), ta = box.querySelector('textarea'), send = box.querySelector('.fb-send'), msg = box.querySelector('.msg'), cnt = box.querySelector('.cnt');
  let vote = 0;
  const ready = () => { send.disabled = !(vote || ta.value.trim().length >= 3); };
  const open = () => { box.hidden = false; btn.hidden = true; (box.querySelector('.fb-vote button') || ta).focus(); };
  const close = () => { box.hidden = true; btn.hidden = false; btn.focus(); };
  btn.addEventListener('click', open);
  box.querySelector('.fb-x').addEventListener('click', close);
  box.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });
  box.querySelectorAll('.fb-vote button').forEach(b => b.addEventListener('click', () => {
    vote = +b.dataset.v;
    box.querySelectorAll('.fb-vote button').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
    ready();
  }));
  ta.addEventListener('input', () => { cnt.textContent = ta.value.length + '/600'; ready(); });
  form.addEventListener('submit', async e => {
    e.preventDefault();
    if (send.disabled) return;
    send.disabled = true; send.textContent = 'Enviando…'; msg.textContent = ''; msg.className = 'msg';
    try {
      const r = await fetch('/api/opinion', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ v: vote, t: ta.value.trim(), p: PAGE, w: form.web.value })
      });
      if (!r.ok && r.status !== 204) throw new Error(r.status);
      form.innerHTML = `<div class="ok">${head.replace('aria-hidden="true"', 'aria-hidden="true" style="width:72px;height:72px"')}<h2>¡Gracias!</h2><p class="sub">Leemos cada opinión. Si nos dejaste una idea, la vamos a considerar para las próximas mejoras.</p></div>`;
      try { localStorage.setItem('cmc-fb', Date.now()); } catch (_) {}
      setTimeout(() => { if (!box.hidden) close(); }, 4000);
    } catch (_) {
      send.disabled = false; send.textContent = 'Enviar opinión';
      msg.className = 'msg err';
      msg.textContent = 'No se pudo enviar. Revisa tu conexión e inténtalo de nuevo.';
    }
  });
  // Si ya opinó en los últimos 30 días, el botón queda más discreto (solo el puma)
  try { if (Date.now() - (+localStorage.getItem('cmc-fb') || 0) < 2592e6) btn.querySelector('.t').remove(); } catch (_) {}
})();
