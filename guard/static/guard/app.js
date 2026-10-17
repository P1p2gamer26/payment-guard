/* Payment Guard v2 · interacciones mínimas: tema/paleta, biblioteca (filtros, pasos, evidencia), registro y escena 3D.
 * Todo texto dinámico se inserta con textContent: nunca innerHTML con datos de facturas. */
(function () {
  'use strict';
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var root = document.documentElement;

  /* tema + paleta */
  function isDark() { return root.dataset.theme ? root.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches; }
  function paint() {
    var t = $('#themeTxt'); if (t) t.textContent = isDark() ? 'Modo claro' : 'Modo oscuro';
    $$('.pal button').forEach(function (b) { b.setAttribute('aria-pressed', String(b.dataset.p === root.dataset.palette)); });
  }
  function save(k, v) { try { localStorage.setItem(k, v); } catch (e) { } }
  var th = $('#theme');
  if (th) th.addEventListener('click', function () { root.dataset.theme = isDark() ? 'light' : 'dark'; save('pg-theme', root.dataset.theme); paint(); });
  $$('.pal button').forEach(function (b) { b.addEventListener('click', function () { root.dataset.palette = b.dataset.p; save('pg-palette', b.dataset.p); paint(); }); });
  paint();

  /* biblioteca */
  var lib = $('.lib');
  if (lib) {
    var st = { q: '', est: '', fmt: '', route: '' };
    var items = $$('#dl li[data-q]');
    var applyFilter = function () {
      var n = 0;
      items.forEach(function (li) {
        var ok = (!st.q || li.dataset.q.indexOf(st.q) >= 0) && (!st.est || li.dataset.d === st.est) &&
          (!st.fmt || li.dataset.kind === st.fmt) && (!st.route || li.dataset.route === st.route);
        li.hidden = !ok; if (ok) n++;
      });
      $('#dcount').textContent = n + ' de ' + items.length; $('#dempty').hidden = n > 0;
    };
    $('#q').addEventListener('input', function (e) { st.q = e.target.value.trim().toLowerCase(); applyFilter(); });
    $('#fEst').addEventListener('change', function (e) { st.est = e.target.value; applyFilter(); });
    $('#fFmt').addEventListener('change', function (e) { st.fmt = e.target.value; applyFilter(); });
    $$('#routes button').forEach(function (b) {
      b.addEventListener('click', function () {
        st.route = st.route === b.dataset.r ? '' : b.dataset.r;
        $$('#routes button').forEach(function (x) { x.setAttribute('aria-pressed', String(x.dataset.r === st.route)); });
        applyFilter();
      });
    });
    var cur = $('.di[aria-current="true"]'); if (cur && cur.scrollIntoView) cur.scrollIntoView({ block: 'nearest' });

    var steps = $$('#stepper button'), panels = $$('#rbody [data-step]');
    var goStep = function (n) {
      steps.forEach(function (b) { b.setAttribute('aria-selected', String(+b.dataset.s === n)); b.classList.toggle('done', +b.dataset.s < n); });
      panels.forEach(function (p) { p.hidden = +p.dataset.step !== n; });
    };
    steps.forEach(function (b) { b.addEventListener('click', function () { goStep(+b.dataset.s); }); });
    goStep(+($('#stepper [aria-selected="true"]') || steps[1]).dataset.s);

    var marks = $$('#doc mark'), flds = $$('#rbody .fld');
    var pick = function (k, scroll) {
      flds.forEach(function (f) { f.setAttribute('aria-pressed', String(f.dataset.k === k)); });
      marks.forEach(function (m) { m.classList.toggle('on', m.dataset.k === k); });
      var m = $('#doc mark.on'); if (scroll && m && m.scrollIntoView) m.scrollIntoView({ block: 'center', behavior: 'smooth' });
    };
    flds.forEach(function (f) { f.addEventListener('click', function () { pick(f.dataset.k, true); }); });
    marks.forEach(function (m) {
      var go = function () { goStep(2); pick(m.dataset.k, false); var f = $('.fld[data-k="' + m.dataset.k + '"]'); if (f && f.scrollIntoView) f.scrollIntoView({ block: 'nearest' }); };
      m.addEventListener('click', go);
      m.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } });
    });
    var first = flds.filter(function (f) { return f.querySelector('.ev b'); })[0];
    var amt = $('.fld[data-k="amount"]');
    pick(((amt && amt.querySelector('.ev b')) ? amt : first || flds[0] || { dataset: {} }).dataset.k, false);
  }

  /* registro */
  var rg = $('#rgF');
  if (rg) rg.addEventListener('change', function () { $$('#logt tbody tr').forEach(function (tr) { tr.hidden = !!rg.value && tr.dataset.ev !== rg.value; }); });

  /* escena 3D */
  var stage = $('#stage'), data = $('#scene-data');
  if (stage && data) {
    var items3 = []; try { items3 = JSON.parse(data.textContent); } catch (e) { }
    var rm = matchMedia('(prefers-reduced-motion: reduce)').matches, h = null;
    var live = $('#liveTxt');
    var counts = { PAGAR: 0, FRENAR: 0, ESCALAR: 0 }; items3.forEach(function (x) { counts[x.o] = (counts[x.o] || 0) + 1; });
    try {
      if (window.mountFlow && items3.length) h = window.mountFlow(stage, {
        reducedMotion: rm, items: items3,
        onItem: function (d) {
          if (!live) return;
          live.textContent = '';
          var b1 = document.createElement('b'); b1.textContent = '#' + d.id;
          var b2 = document.createElement('b'); b2.textContent = d.r;
          live.append(b1, ' ' + d.n + ' · ' + d.a + ' → ', b2, ' → ' + d.o);
        }
      });
    } catch (e) { if (window.console) console.warn('flow3d', e); }
    if (!h) {
      stage.classList.add('nofx');
      var note = $('#stageNote'); if (note) note.textContent = rm ? 'Movimiento reducido: diagrama estático' : 'Diagrama estático (WebGL no disponible)';
      if (live) live.textContent = 'Lote de ' + items3.length + ' facturas: ' + counts.PAGAR + ' PAGAR · ' + counts.FRENAR + ' FRENAR · ' + counts.ESCALAR + ' ESCALAR';
      var dot = $('.live .dot'); if (dot) dot.style.display = 'none';
    }
  }
})();
