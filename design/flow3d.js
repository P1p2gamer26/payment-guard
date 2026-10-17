/* Payment Guard · escena 3D del flujo del agente (v2).
 * Script clásico (window.mountFlow); requiere THREE global (three@0.160.0 build/three.min.js).
 *   const h = mountFlow(el, {reducedMotion, items?, onItem?});   // items: ver SEQ (las 25 facturas del demo)
 *   if (!h) -> mostrar fallback SVG.   h.destroy()
 * Colores: lee las variables CSS --ac --ac2 --pay --stop --esc --ink --ink-2 --line --surface --stage
 * de :root y se actualiza solo al cambiar data-theme / data-palette / prefers-color-scheme.
 * Flujo: documentos (sobre / burbuja / hoja) -> LLM extrae (los campos saltan al nodo) -> doble llave
 *   (dos llaves que encajan o no) -> motor: túnel de 13 anillos etiquetados que se encienden en orden
 *   -> 3 carriles -> ESCALAR: persona (re-chequeo) -> borrador draft_not_executed.
 * Móvil / aspecto vertical: el mundo gira 90° y el flujo corre de arriba a abajo. */
(function (root) {
  'use strict';
  const SEQ = [{"id":"01","k":"correo","d":"P","r":"OK","i":13,"s":1,"t":""},{"id":"02","k":"hoja","d":"P","r":"OK","i":13,"s":1,"t":""},{"id":"03","k":"cfdi","d":"P","r":"OK","i":13,"s":1,"t":""},{"id":"04","k":"chat","d":"P","r":"OK","i":13,"s":1,"t":""},{"id":"05","k":"hoja","d":"P","r":"OK","i":13,"s":1,"t":""},{"id":"06","k":"correo","d":"P","r":"OK","i":13,"s":1,"t":""},{"id":"07","k":"hoja","d":"P","r":"OK","i":13,"s":1,"t":""},{"id":"08","k":"cfdi","d":"P","r":"OK","i":13,"s":1,"t":""},{"id":"09","k":"chat","d":"P","r":"OK","i":13,"s":0,"t":""},{"id":"10","k":"hoja","d":"P","r":"OK","i":13,"s":1,"t":""},{"id":"11","k":"chat","d":"P","r":"OK","i":13,"s":0,"t":""},{"id":"12","k":"hoja","d":"P","r":"OK","i":13,"s":1,"t":""},{"id":"13","k":"correo","d":"P","r":"OK","i":13,"s":0,"t":""},{"id":"14","k":"chat","d":"P","r":"OK","i":13,"s":1,"t":""},{"id":"15","k":"hoja","d":"F","r":"R_DUPLICADO","i":7,"s":1,"t":""},{"id":"16","k":"correo","d":"F","r":"R_DUPLICADO","i":7,"s":0,"t":""},{"id":"17","k":"hoja","d":"E","r":"R_BENEFICIARIO","i":5,"s":1,"t":"block"},{"id":"18","k":"cfdi","d":"E","r":"R_CONTRATO","i":9,"s":1,"t":"block"},{"id":"19","k":"correo","d":"E","r":"R_UMBRAL","i":11,"s":1,"t":"block"},{"id":"20","k":"hoja","d":"F","r":"R_LIMITE","i":10,"s":1,"t":""},{"id":"21","k":"hoja","d":"F","r":"R_PRESUPUESTO","i":12,"s":1,"t":""},{"id":"22","k":"correo","d":"F","r":"R_MONEDA","i":4,"s":1,"t":""},{"id":"23","k":"hoja","d":"F","r":"R_FECHA","i":8,"s":1,"t":""},{"id":"24","k":"hoja","d":"E","r":"R_SOSPECHA","i":1,"s":1,"t":"inj"},{"id":"25","k":"correo","d":"E","r":"R_CUENTA","i":6,"s":0,"t":"draft"}]; // {id,k:kind,d:P|F|E,r:regla,i:índice 1-13,s:1 si regex lee,t:''|inj|draft|block}
  const RULE_SHORT = ['SOSPECHA', 'CONFIAN.', 'DOBLE', 'MONEDA', 'BENEF.', 'CUENTA', 'DUPLIC.', 'FECHA', 'CONTRATO', 'LÍMITE', 'UMBRAL', 'PRESUP.', 'OK'];
  const KLABEL = { correo: 'CORREO', chat: 'CHAT', cfdi: 'CFDI', hoja: 'COBRO' };
  const X = { start: -11.5, llm: -7.6, key: -4.3, e0: -1.6, e1: 4.0, branch: 6.2 };
  const LZ = { P: -2.4, F: 0, E: 2.4 };
  const SPEED = 2.6, GAP = 1.3, NR = 13;
  const PERSON = { x: 10.9 }, DRAFT_END = 14.2;

  function mountFlow(el, opts) {
    opts = opts || {};
    const THREE = root.THREE;
    if (opts.reducedMotion || !THREE) return null;
    let renderer;
    try { renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'low-power' }); } catch (e) { return null; }
    const items0 = opts.items || SEQ;
    renderer.setPixelRatio(Math.min(root.devicePixelRatio || 1, 2));
    renderer.domElement.style.cssText = 'display:block;width:100%;height:100%';
    renderer.domElement.setAttribute('aria-hidden', 'true');
    el.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const world = new THREE.Group(); scene.add(world);
    const camera = new THREE.PerspectiveCamera(24, 2, 0.1, 300);
    scene.add(new THREE.AmbientLight(0xffffff, 0.9));
    const sun = new THREE.DirectionalLight(0xffffff, 0.85); sun.position.set(-6, 12, 8); scene.add(sun);

    // ---------- paleta desde CSS ----------
    const P = {};
    const cssc = (n, fb) => { try { const v = getComputedStyle(document.documentElement).getPropertyValue(n).trim(); return new THREE.Color(v || fb); } catch (e) { return new THREE.Color(fb); } };
    const hex = (c) => '#' + c.getHexString();
    function readPal() {
      P.ac = cssc('--ac', '#1f55d0'); P.ac2 = cssc('--ac2', '#8a97a6'); P.pay = cssc('--pay', '#12784f'); P.stop = cssc('--stop', '#b8322c');
      P.esc = cssc('--esc', '#c2800a'); P.ink = cssc('--ink', '#14181d'); P.ink2 = cssc('--ink-2', '#4a5561'); P.line = cssc('--line', '#d3d9df');
      P.surface = cssc('--surface', '#ffffff'); P.stage = cssc('--stage', '#eef0f2'); P.dark = (P.stage.r + P.stage.g + P.stage.b) / 3 < 0.35;
      P.paper = P.dark ? new THREE.Color('#e9eef2') : new THREE.Color('#ffffff');
    }
    readPal();
    const dcol = (d) => (d === 'P' ? P.pay : d === 'F' ? P.stop : P.esc);

    const mats = []; // {m, role, mix}
    const own = [];
    const mat = (role, o, mix) => { const m = new THREE.MeshBasicMaterial(Object.assign({ color: 0xffffff }, o || {})); m.color.copy(P[role]); if (mix) m.color.lerp(P.paper, mix); mats.push({ m, role, mix }); own.push(m); return m; };
    const std = (role, mix) => { const m = new THREE.MeshStandardMaterial({ roughness: 0.85 }); m.color.copy(P[role]); if (mix) m.color.lerp(P.paper, mix); mats.push({ m, role, mix }); own.push(m); return m; };
    const geo = (g) => { own.push(g); return g; };
    const BOX = geo(new THREE.BoxGeometry(1, 1, 1));

    // ---------- sprites de texto ----------
    const redraws = [];
    const SANS = '600 {s}px Geist, "Segoe UI", system-ui, sans-serif', MONO = '500 {s}px "Geist Mono", ui-monospace, Consolas, monospace';
    const F = (t, s) => t.replace('{s}', s);
    function sprite(w, h, sw, sh, draw) {
      const cv = document.createElement('canvas'); cv.width = w; cv.height = h;
      const tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 4;
      const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false }));
      sp.scale.set(sw, sh, 1); sp.renderOrder = 10;
      sp.userData.redraw = (st) => { const g = cv.getContext('2d'); g.clearRect(0, 0, w, h); draw(g, w, h, st || sp.userData.st); tex.needsUpdate = true; };
      sp.userData.redraw(); sp.userData.tex = tex;
      return sp;
    }
    function label(title, sub, x, y, z, roleOrFn) {
      const sp = sprite(1024, 256, 5.2, 1.3, (g, w) => {
        g.textAlign = 'center'; g.fillStyle = roleOrFn ? hex(typeof roleOrFn === 'string' ? P[roleOrFn] : roleOrFn()) : hex(P.ink);
        g.font = F(SANS, 84); g.fillText(title, w / 2, 112); g.fillStyle = hex(P.ink2); g.font = F(MONO, 46); g.fillText(sub, w / 2, 190);
      });
      sp.position.set(x, y, z); world.add(sp); redraws.push(sp); return sp;
    }
    function pill(text, getColor, filled) {
      const sp = sprite(512, 128, 2.3, 0.575, (g, w, h, st) => {
        const t = (st && st.text) || text, c = (st && st.color) || getColor();
        g.fillStyle = hex(c); const r = 24, x0 = 6, y0 = 22, ww = w - 12, hh = h - 44;
        g.beginPath(); g.moveTo(x0 + r, y0); g.arcTo(x0 + ww, y0, x0 + ww, y0 + hh, r); g.arcTo(x0 + ww, y0 + hh, x0, y0 + hh, r); g.arcTo(x0, y0 + hh, x0, y0, r); g.arcTo(x0, y0, x0 + ww, y0, r); g.fill();
        g.fillStyle = (c.r * 0.299 + c.g * 0.587 + c.b * 0.114) > 0.55 ? '#10151a' : '#ffffff'; g.font = F(MONO, 48); g.textAlign = 'center'; g.fillText(t, w / 2, 77);
      });
      return sp;
    }

    // ---------- suelo, carriles ----------
    const grid = new THREE.GridHelper(60, 60, 0xffffff, 0xffffff); grid.position.y = -0.03; grid.material.transparent = true; grid.material.opacity = 0.35; world.add(grid);
    const strips = [];
    function strip(x1, z1, x2, z2, w, role, op) {
      const m = new THREE.Mesh(BOX, mat(role, { transparent: true, opacity: op }));
      m.scale.set(Math.hypot(x2 - x1, z2 - z1), 0.04, w); m.position.set((x1 + x2) / 2, 0, (z1 + z2) / 2); m.rotation.y = -Math.atan2(z2 - z1, x2 - x1); world.add(m); strips.push(m); return m;
    }
    strip(X.start, 0, X.branch, 0, 1.1, 'line', 0.7);
    strip(X.branch, 0, 10.2, 0, 1.1, 'stop', 0.28);
    strip(X.branch, 0, 7.9, LZ.P, 1.1, 'pay', 0.28); strip(7.9, LZ.P, 10.8, LZ.P, 1.1, 'pay', 0.28);
    strip(X.branch, 0, 7.9, LZ.E, 1.1, 'esc', 0.28); strip(7.9, LZ.E, DRAFT_END, LZ.E, 1.1, 'esc', 0.28);
    const PATH = { P: [[X.start, 0], [X.branch, 0], [7.9, LZ.P], [10.6, LZ.P]], F: [[X.start, 0], [9.6, 0]], E: [[X.start, 0], [X.branch, 0], [7.9, LZ.E], [PERSON.x - 1.0, LZ.E]] };
    function pinfo(pts) { const cum = [0]; for (let i = 1; i < pts.length; i++) cum.push(cum[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1])); return { pts, cum, total: cum[cum.length - 1] }; }
    const PI = { P: pinfo(PATH.P), F: pinfo(PATH.F), E: pinfo(PATH.E) };
    function at(info, s) { s = Math.min(s, info.total); let i = 1; while (i < info.cum.length - 1 && s > info.cum[i]) i++; const a = info.pts[i - 1], b = info.pts[i], u = (s - info.cum[i - 1]) / (info.cum[i] - info.cum[i - 1] || 1); return [a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u]; }

    // ---------- nodo 1: LLM ----------
    const llmRing = new THREE.Mesh(geo(new THREE.TorusGeometry(1.0, 0.05, 12, 56)), mat('ac')); llmRing.rotation.y = Math.PI / 2; llmRing.position.set(X.llm, 0.55, 0); world.add(llmRing);
    const llmCore = new THREE.LineSegments(geo(new THREE.EdgesGeometry(new THREE.IcosahedronGeometry(0.66, 0))), mat('ink')); llmCore.position.set(X.llm, 2.15, 0); world.add(llmCore);
    const llmGlow = new THREE.Mesh(geo(new THREE.IcosahedronGeometry(0.3, 0)), mat('ac', { transparent: true, opacity: 0.9 })); llmGlow.position.copy(llmCore.position); world.add(llmGlow);
    const llmBeam = new THREE.Mesh(BOX, mat('ac', { transparent: true, opacity: 0.35 })); llmBeam.scale.set(0.05, 1.3, 0.05); llmBeam.position.set(X.llm, 1.25, 0); world.add(llmBeam);

    // ---------- nodo 2: doble llave ----------
    const gate = new THREE.Group(); gate.position.set(X.key, 0, 0); world.add(gate);
    [-1.0, 1.0].forEach((z) => { const post = new THREE.Mesh(BOX, mat('ink')); post.scale.set(0.12, 1.7, 0.12); post.position.set(0, 0.85, z); gate.add(post); });
    const bar = new THREE.Mesh(BOX, mat('ink')); bar.scale.set(0.12, 0.12, 2.12); bar.position.set(0, 1.7, 0); gate.add(bar);
    const lockGlow = new THREE.Mesh(geo(new THREE.CylinderGeometry(0.22, 0.22, 0.05, 20)), mat('line', { transparent: true, opacity: 0.9 })); lockGlow.position.set(0, 1.62, 0); gate.add(lockGlow);
    function makeKey(role) {
      const g = new THREE.Group(); const m = mat(role);
      const head = new THREE.Mesh(geo(new THREE.TorusGeometry(0.2, 0.065, 10, 24)), m); head.rotation.y = Math.PI / 2; head.position.z = 0; g.add(head);
      const shaft = new THREE.Mesh(BOX, m); shaft.scale.set(0.09, 0.09, 0.7); shaft.position.z = 0.45; g.add(shaft);
      [0.62, 0.78].forEach((z, i) => { const t = new THREE.Mesh(BOX, m); t.scale.set(0.09, 0.2 - i * 0.05, 0.08); t.position.set(0, -0.12 + i * 0.03, z); g.add(t); });
      g.position.y = 1.7; return g;
    }
    const keyA = makeKey('ac'), keyB = makeKey('ac2'); keyA.position.z = -1.7; keyA.rotation.y = 0; keyB.position.z = 1.7; keyB.rotation.y = Math.PI; gate.add(keyA, keyB);
    const keyState = { a: 0, b: 0, ok: 0, spin: 0 }; // a,b: 0 lejos, 1 encajada

    // ---------- nodo 3: motor (túnel de 13 anillos) ----------
    const rings = [], ringLv = new Float32Array(NR), ringCol = [];
    const ringGeo = geo(new THREE.TorusGeometry(0.66, 0.028, 8, 36));
    for (let i = 0; i < NR; i++) {
      const x = X.e0 + 0.3 + i * ((X.e1 - X.e0 - 0.6) / (NR - 1));
      const rm = new THREE.MeshBasicMaterial({ color: P.line.clone() }); own.push(rm); const r = new THREE.Mesh(ringGeo, rm); r.rotation.y = Math.PI / 2; r.position.set(x, 0.58, 0); world.add(r); rings.push(r); ringCol.push(P.ac);
      const side = i % 2 === 0 ? -1 : 1, lz = side * (1.35 + (Math.floor(i / 2) % 3) * 0.6);
      const ln = new THREE.Mesh(BOX, mat('line', { transparent: true, opacity: 0.8 })); ln.scale.set(0.014, 0.014, Math.abs(lz) - 0.7); ln.position.set(x, 0.08, side * (Math.abs(lz) + 0.7) / 2); world.add(ln);
      const sp = sprite(384, 96, 2.4, 0.6, (g, w, h) => { g.textAlign = 'center'; g.fillStyle = hex(P.ink); g.font = F(MONO, 48); g.fillText((i + 1) + ' ' + RULE_SHORT[i], w / 2, 64); });
      sp.position.set(x, 0.12, lz); world.add(sp); redraws.push(sp);
    }
    const tunnelBase = new THREE.Mesh(BOX, mat('ac', { transparent: true, opacity: 0.1 })); tunnelBase.scale.set(X.e1 - X.e0, 0.05, 1.4); tunnelBase.position.set((X.e0 + X.e1) / 2, 0.03, 0); world.add(tunnelBase);

    // ---------- destinos ----------
    const person = new THREE.Group(); const pm = mat('ink');
    const pb = new THREE.Mesh(geo(new THREE.CylinderGeometry(0.34, 0.44, 0.95, 20)), pm); pb.position.y = 0.48;
    const ph = new THREE.Mesh(geo(new THREE.SphereGeometry(0.27, 20, 16)), pm); ph.position.y = 1.28;
    const ps = new THREE.Mesh(BOX, mat('ac')); ps.scale.set(0.9, 0.06, 0.34); ps.position.set(0, 0.82, 0.05);
    person.add(pb, ph, ps); person.position.set(PERSON.x, 0, LZ.E); world.add(person);
    const halo = new THREE.Mesh(geo(new THREE.RingGeometry(0.6, 0.74, 40)), mat('esc', { transparent: true, opacity: 0, side: THREE.DoubleSide })); halo.rotation.x = -Math.PI / 2; halo.position.set(PERSON.x, 0.03, LZ.E); world.add(halo);
    const mark = new THREE.Group(); mark.position.set(PERSON.x, 2.1, LZ.E); mark.visible = false; world.add(mark);
    const markMats = [mat('stop'), mat('pay')];
    const xA = new THREE.Mesh(BOX, markMats[0]), xB = new THREE.Mesh(BOX, markMats[0]); xA.scale.set(0.5, 0.09, 0.09); xB.scale.set(0.5, 0.09, 0.09); xA.rotation.z = Math.PI / 4; xB.rotation.z = -Math.PI / 4;
    const cA = new THREE.Mesh(BOX, markMats[1]), cB = new THREE.Mesh(BOX, markMats[1]); cA.scale.set(0.24, 0.09, 0.09); cB.scale.set(0.5, 0.09, 0.09); cA.rotation.z = -Math.PI / 4; cA.position.set(-0.17, -0.1, 0); cB.rotation.z = Math.PI / 4; cB.position.set(0.1, 0, 0);
    const xg = new THREE.Group(); xg.add(xA, xB); const cg = new THREE.Group(); cg.add(cA, cB); mark.add(xg, cg);
    const barrier = new THREE.Mesh(BOX, mat('stop', { transparent: true, opacity: 0.85 })); barrier.scale.set(0.14, 0.9, 1.3); barrier.position.set(10.0, 0.45, 0); world.add(barrier);
    const bin = new THREE.Mesh(BOX, mat('pay', { transparent: true, opacity: 0.35 })); bin.scale.set(1.6, 0.06, 1.5); bin.position.set(11.3, 0, LZ.P); world.add(bin);

    label('Facturas', 'sobre · burbuja · hoja', -10.0, 1.2, 0);
    label('1 · LLM extrae', 'solo lee, no decide', X.llm, 3.45, 0);
    label('2 · Doble llave', 'regex ≟ LLM: monto y moneda', X.key, 2.75, 0);
    label('3 · Motor de reglas', 'default-deny · 13 pasos en orden', (X.e0 + X.e1) / 2, 0.3, -4.3);
    label('PAGAR', 'dentro de reglas', 13.0, 0.9, LZ.P, 'pay');
    label('FRENAR', 'inválido, sin discusión', 12.4, 0.9, 0, 'stop');
    label('ESCALAR', 'persona aprueba · re-chequea', PERSON.x, 2.6, LZ.E, 'esc');
    label('draft_not_executed', 'no mueve dinero', 13.1, 0.8, LZ.E + 1.3);

    // ---------- documentos ----------
    const topTex = {};
    function mkTex(name) {
      const cv = document.createElement('canvas'); cv.width = 192; cv.height = 132; const g = cv.getContext('2d');
      g.fillStyle = '#fff'; g.fillRect(0, 0, 192, 132); g.fillStyle = '#1b2430'; g.fillRect(0, 0, 192, 28);
      g.fillStyle = '#fff'; g.font = '600 17px "Geist Mono", ui-monospace, Consolas, monospace'; g.fillText(name, 10, 20);
      g.fillStyle = '#c9d2da'; [48, 64, 80].forEach((y, i) => g.fillRect(10, y, 120 - i * 22, 7)); g.fillStyle = '#1b2430'; g.fillRect(112, 100, 70, 14);
      const t = new THREE.CanvasTexture(cv); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; own.push(t); return t;
    }
    ['CFDI', 'COBRO'].forEach((n) => { topTex[n] = new THREE.MeshStandardMaterial({ map: mkTex(n), roughness: 0.9 }); own.push(topTex[n]); });
    const paperSide = std('line');
    const envMat = std('surface'); const envFlap = std('line', 0.0);
    const bubMat = std('ac', 0.78);
    function bubbleGeo() {
      const w = 1.3, h = 0.85, r = 0.2, s = new THREE.Shape(); const x0 = -w / 2, y0 = -h / 2;
      s.moveTo(x0 + r, y0); s.lineTo(x0 + 0.35, y0); s.lineTo(x0 + 0.1, y0 - 0.22); s.lineTo(x0 + 0.62, y0); s.lineTo(x0 + w - r, y0); s.quadraticCurveTo(x0 + w, y0, x0 + w, y0 + r); s.lineTo(x0 + w, y0 + h - r); s.quadraticCurveTo(x0 + w, y0 + h, x0 + w - r, y0 + h); s.lineTo(x0 + r, y0 + h); s.quadraticCurveTo(x0, y0 + h, x0, y0 + h - r); s.lineTo(x0, y0 + r); s.quadraticCurveTo(x0, y0, x0 + r, y0);
      const g = new THREE.ExtrudeGeometry(s, { depth: 0.07, bevelEnabled: false }); g.rotateX(-Math.PI / 2); return geo(g);
    }
    const BUB = bubbleGeo();
    const flapGeo = (() => { const s = new THREE.Shape(); s.moveTo(-0.65, 0.45); s.lineTo(0.65, 0.45); s.lineTo(0, -0.05); s.closePath(); const g = new THREE.ShapeGeometry(s); g.rotateX(-Math.PI / 2); return geo(g); })();
    const foldGeo = (() => { const s = new THREE.Shape(); s.moveTo(0, 0); s.lineTo(0.28, 0); s.lineTo(0, 0.28); s.closePath(); const g = new THREE.ShapeGeometry(s); g.rotateX(-Math.PI / 2); return geo(g); })();
    function makeDoc(kind) {
      const g = new THREE.Group(); let top = 0.06;
      if (kind === 'correo') {
        const b = new THREE.Mesh(BOX, envMat); b.scale.set(1.3, 0.08, 0.9); g.add(b);
        const f = new THREE.Mesh(flapGeo, envFlap); f.position.y = 0.045; g.add(f); top = 0.05;
      } else if (kind === 'chat') {
        const b = new THREE.Mesh(BUB, bubMat); b.position.y = 0.0; g.add(b);
        [0, 1, 2].forEach((i) => { const l = new THREE.Mesh(BOX, matChatLine); l.scale.set(0.8 - i * 0.18, 0.02, 0.07); l.position.set(-0.12, 0.085, -0.16 + i * 0.17); g.add(l); }); top = 0.07;
      } else {
        const b = new THREE.Mesh(BOX, [paperSide, paperSide, topTex[kind === 'cfdi' ? 'CFDI' : 'COBRO'], paperSide, paperSide, paperSide]); b.scale.set(1.15, 0.07, 1.0); g.add(b);
        const fd = new THREE.Mesh(foldGeo, matFold); fd.position.set(0.575 - 0.28, 0.04, -0.5); g.add(fd);
      }
      return { g, top };
    }
    const matBar = mat('ac'), matBarEsc = mat('esc'), matChatLine = mat('surface'), matFold = mat('ac2', null, 0.2);
    const items = [], flights = [];
    const kindOk = (k) => (k === 'correo' || k === 'chat' || k === 'cfdi' ? k : 'hoja');
    function spawn(def) {
      const { g, top } = makeDoc(kindOk(def.k));
      const chipM = new THREE.MeshBasicMaterial({ color: P.ac2.clone() }); own.push(chipM); const chip = new THREE.Mesh(BOX, chipM); chip.scale.set(0.28, 0.05, 0.14); chip.position.set(0.42, top + 0.03, 0.34); g.add(chip);
      const bars = new THREE.Group(); bars.visible = false;
      for (let i = 0; i < 3; i++) { const b = new THREE.Mesh(BOX, def.t === 'inj' ? matBarEsc : matBar); b.scale.set(0.46 - i * 0.08, 0.035, 0.06); b.position.set(-0.28, top + 0.05, -0.2 + i * 0.16); bars.add(b); }
      g.add(bars);
      const tag = pill('#' + def.id, () => P.ink2); tag.userData.st = { text: '#' + def.id, color: P.ink2 }; tag.userData.redraw(); tag.position.set(0, 0.95, 0); tag.scale.set(1.3, 0.33, 1); g.add(tag);
      world.add(g);
      const it = { def, g, chip, chipM, chipRole: 'ac2', bars, tag, s: 0, t: 0, state: 'move', info: PI[def.d], decided: false, fl: 0, keyDone: false, top };
      items.push(it); return it;
    }
    function spawnDraft() {
      const g = new THREE.Group(); const b = new THREE.Mesh(BOX, [paperSide, paperSide, std('surface'), paperSide, paperSide, paperSide]); b.scale.set(1.2, 0.07, 0.85); g.add(b);
      const edge = new THREE.LineSegments(geo(new THREE.EdgesGeometry(new THREE.BoxGeometry(1.2, 0.07, 0.85))), mat('ac')); g.add(edge);
      [0, 1].forEach((i) => { const l = new THREE.Mesh(BOX, mat('ac')); l.scale.set(0.7 - i * 0.25, 0.02, 0.06); l.position.set(-0.15, 0.05, -0.15 + i * 0.16); g.add(l); });
      g.position.set(PERSON.x + 0.9, 0.06, LZ.E); world.add(g); items.push({ draft: true, g, x: PERSON.x + 0.9, state: 'move', t: 0 });
    }

    // ---------- partículas de rastro ----------
    const NP = 140, pPos = new Float32Array(NP * 3), pCol = new Float32Array(NP * 3), pLife = new Float32Array(NP), pBase = new Float32Array(NP * 3); let pHead = 0;
    const pGeo = new THREE.BufferGeometry(); pGeo.setAttribute('position', new THREE.BufferAttribute(pPos, 3)); pGeo.setAttribute('color', new THREE.BufferAttribute(pCol, 3)); own.push(pGeo);
    const pts = new THREE.Points(pGeo, new THREE.PointsMaterial({ size: 0.13, vertexColors: true, sizeAttenuation: true })); pts.frustumCulled = false; world.add(pts); own.push(pts.material);
    for (let i = 0; i < NP; i++) pPos[i * 3 + 1] = -50;
    function emit(x, y, z, c) { const i = pHead++ % NP; pPos[i * 3] = x + (Math.random() - 0.5) * 0.3; pPos[i * 3 + 1] = y; pPos[i * 3 + 2] = z + (Math.random() - 0.5) * 0.3; pBase[i * 3] = c.r; pBase[i * 3 + 1] = c.g; pBase[i * 3 + 2] = c.b; pLife[i] = 1; }

    // ---------- bucle ----------
    let spawnT = 0.2, seqI = 0, running = true, visible = true, raf = 0, clock = performance.now(), time = 0, rotated = false;
    let haloLv = 0, binLv = 0, barShake = 0, llmPulse = 0, markT = 0, markKind = 0;
    const tmpC = new THREE.Color();
    function setChip(it, role) { it.chipRole = role; it.chipM.color.copy(P[role]); }
    function decide(it) {
      it.decided = true; const d = it.def; const col = d.r === 'OK' ? P.pay : dcol(d.d);
      setChip(it, d.r === 'OK' ? 'pay' : d.d === 'F' ? 'stop' : 'esc');
      it.tag.userData.st = { text: '#' + d.id + ' · ' + d.r, color: col }; it.tag.scale.set(d.t === 'inj' ? 3.5 : 2.9, 0.62, 1); it.tag.userData.redraw();
      if (d.t === 'inj') it.tag.userData.st.text = '#24 · R_SOSPECHA · inyección';
      it.tag.userData.redraw(); if (opts.onItem) { try { opts.onItem(d); } catch (e) { } }
    }
    function frame(now) {
      raf = 0; if (!running || !visible) return;
      const dt = Math.min(0.05, (now - clock) / 1000); clock = now; time += dt;
      spawnT -= dt; if (spawnT <= 0) { spawn(items0[seqI % items0.length]); seqI++; spawnT = GAP; }
      for (let i = 0; i < NR; i++) ringLv[i] = Math.max(0, ringLv[i] - dt * 1.8);
      let keyActive = false;

      for (let n = items.length - 1; n >= 0; n--) {
        const it = items[n];
        if (it.draft) {
          if (it.state === 'move') { it.x += SPEED * dt * 0.9; it.g.position.x = it.x; if (it.x > DRAFT_END - 0.6) { it.state = 'sink'; it.t = 0; } }
          else { it.t += dt; it.g.scale.setScalar(Math.max(0.001, 1 - it.t / 0.6)); if (it.t > 0.6) { world.remove(it.g); items.splice(n, 1); } }
          emit(it.g.position.x, 0.2, LZ.E, P.ac); continue;
        }
        const d = it.def;
        if (it.state === 'move') {
          it.s += SPEED * dt; const [x, z] = at(it.info, it.s); it.g.position.set(x, 0.06, z);
          if (Math.random() < 0.5 && x < X.branch + 3) emit(x - 0.6, 0.1, z, it.decided ? dcol(d.d) : P.ac);
          // campos saltan al LLM
          if (!it.fl && x > X.llm - 0.9) { it.fl = 1; for (let k = 0; k < 3; k++) { const m = new THREE.Mesh(BOX, matBar); m.scale.set(0.2, 0.06, 0.06); world.add(m); flights.push({ m, k, t: -k * 0.16, from: new THREE.Vector3(), it }); } }
          if (it.fl === 1 && x > X.llm + 0.5) { it.bars.visible = true; it.fl = 2; }
          // doble llave
          if (x > X.key - 2.6 && x < X.key + 1.2) { keyActive = true; if (!it.keyDone && x > X.key - 2.2) { it.keyDone = true; keyState.sr = d.s; keyState.t0 = time; } }
          // motor
          if (x > X.e0 && x < X.e1) {
            const p = (x - X.e0) / (X.e1 - X.e0), upto = Math.min(NR, Math.ceil(p * NR + 1e-4));
            for (let i = 0; i < Math.min(upto, d.i); i++) { const fired = i === d.i - 1; if (ringLv[i] < 0.8 || fired) { ringLv[i] = 1; ringCol[i] = fired ? (d.r === 'OK' ? P.pay : dcol(d.d)) : P.ac; } }
          }
          if (!it.decided && x > X.e1 - 0.05) decide(it);
          if (it.s >= it.info.total) { it.state = 'end'; it.t = 0; if (d.d === 'P') binLv = 1; if (d.d === 'F') barShake = 1; if (d.d === 'E') { haloLv = 1; mark.visible = true; markT = 1.2; markKind = d.t === 'draft' ? 1 : 0; xg.visible = !markKind; cg.visible = !!markKind; } }
        } else if (it.state === 'end') {
          it.t += dt; const hold = d.d === 'E' ? 1.2 : d.d === 'F' ? 0.5 : 0.12;
          if (d.d === 'F') it.g.position.x = 9.5 - Math.abs(Math.sin(it.t * 18)) * 0.08 * Math.max(0, 1 - it.t * 2);
          if (it.t >= hold) { if (d.t === 'draft') spawnDraft(); it.state = 'sink'; it.t = 0; }
        } else {
          it.t += dt; it.tag.visible = false; const sc = Math.max(0.001, 1 - it.t / 0.45); it.g.scale.setScalar(sc); if (d.d === 'P') it.g.position.y = 0.06 - it.t * 0.4;
          if (it.t > 0.45) { world.remove(it.g); it.tag.material.map.dispose(); it.tag.material.dispose(); items.splice(n, 1); }
        }
      }
      // vuelo de campos
      for (let n = flights.length - 1; n >= 0; n--) {
        const f = flights[n]; f.t += dt; if (f.t < 0) { f.m.visible = false; continue; } f.m.visible = true;
        const u = Math.min(1, f.t / 0.7); const src = f.it.g.position; const dst = llmCore.position;
        f.m.position.set(src.x + (dst.x - src.x) * u - 0.2 * (1 - u) + (f.k - 1) * 0.08, 0.2 + (dst.y - 0.2) * u + Math.sin(u * Math.PI) * 0.9, src.z * (1 - u));
        f.m.scale.setScalar(1 - u * 0.6); emit(f.m.position.x, f.m.position.y, f.m.position.z, P.ac);
        if (u >= 1) { llmPulse = 1; world.remove(f.m); flights.splice(n, 1); }
      }
      // llaves: encajan si regex leyó; la B se queda a medias si se abstiene
      const sr = keyState.sr, tgtA = keyActive ? 1 : 0, tgtB = keyActive ? (sr ? 1 : 0.35) : 0;
      keyState.a += (tgtA - keyState.a) * Math.min(1, dt * 4); keyState.b += (tgtB - keyState.b) * Math.min(1, dt * 4);
      keyState.spin += dt * (keyActive ? 1.2 : 3);
      keyA.position.z = -1.7 + keyState.a * 1.22; keyB.position.z = 1.7 - keyState.b * 1.22;
      keyA.rotation.z = keyActive && keyState.a > 0.9 ? 0 : keyState.spin; keyB.rotation.z = keyActive && keyState.b > 0.9 ? 0 : -keyState.spin;
      keyA.rotation.x = 0; keyB.rotation.x = 0;
      const lg = lockGlow.material; lg.color.copy(keyActive && keyState.a > 0.9 && keyState.b > 0.9 ? P.pay : keyActive && keyState.b > 0.2 ? P.esc : P.line);

      // anillos
      for (let i = 0; i < NR; i++) { const lv = ringLv[i], r = rings[i]; r.material.color.copy(lv > 0.03 ? tmpC.copy(ringCol[i]).lerp(P.line, 1 - Math.min(1, lv * 1.4)) : P.line); r.scale.setScalar(1 + lv * 0.12); }
      // partículas
      for (let i = 0; i < NP; i++) { if (pLife[i] > 0) { pLife[i] -= dt * 1.4; const l = Math.max(0, pLife[i]); pCol[i * 3] = P.stage.r + (pBase[i * 3] - P.stage.r) * l; pCol[i * 3 + 1] = P.stage.g + (pBase[i * 3 + 1] - P.stage.g) * l; pCol[i * 3 + 2] = P.stage.b + (pBase[i * 3 + 2] - P.stage.b) * l; if (l <= 0) pPos[i * 3 + 1] = -50; } }
      pGeo.attributes.position.needsUpdate = true; pGeo.attributes.color.needsUpdate = true;
      llmCore.rotation.y += dt * 0.9; llmCore.rotation.x += dt * 0.4; llmPulse = Math.max(0, llmPulse - dt * 3); llmGlow.scale.setScalar(1 + Math.sin(time * 3) * 0.12 + llmPulse * 0.8);
      haloLv = Math.max(0, haloLv - dt * 0.8); halo.material.opacity = haloLv; halo.scale.setScalar(1 + (1 - haloLv) * 0.6);
      markT = Math.max(0, markT - dt); if (markT <= 0) mark.visible = false; mark.position.y = 2.1 + Math.sin(time * 6) * 0.04;
      binLv = Math.max(0, binLv - dt * 2); bin.material.opacity = 0.35 + binLv * 0.5; barShake = Math.max(0, barShake - dt * 2); barrier.position.x = 10.0 + Math.sin(time * 40) * 0.04 * barShake;
      // cámara con leve vaivén
      const sw = Math.sin(time * 0.22) * 0.07; camera.position.copy(camBase).addScaledVector(camSide, sw * camDist * 0.5); camera.position.y += Math.sin(time * 0.17) * 0.25; camera.lookAt(target);
      renderer.render(scene, camera); raf = requestAnimationFrame(frame);
    }
    function kick() { if (!raf && running && visible) { clock = performance.now(); raf = requestAnimationFrame(frame); } }

    // ---------- cámara / tamaño ----------
    const target = new THREE.Vector3(), camBase = new THREE.Vector3(), camSide = new THREE.Vector3(1, 0, 0); let camDist = 30;
    function resize() {
      const w = Math.max(el.clientWidth, 1), h = Math.max(el.clientHeight, 1), a = w / h; renderer.setSize(w, h, false); camera.aspect = a;
      const tf = 2 * Math.tan((camera.fov * Math.PI) / 360); let dist, dir;
      if (a < 1.05) { // vertical: el flujo corre de arriba a abajo
        world.rotation.y = -Math.PI / 2; rotated = true; target.set(-1.2, 0, 0.8); dir = new THREE.Vector3(0.0, 0.93, 0.36).normalize();
        dist = Math.max(14.5 / (tf * a), 31 / tf / 1.05); if (a < 0.9) dist = Math.max(14.5 / (tf * a), 29 / tf);
      } else {
        world.rotation.y = 0; rotated = false; target.set(1.5, 0.0, 0.5); dir = new THREE.Vector3(0.0, 0.86, 0.5).normalize(); dist = Math.max(31 / (tf * a), 10.5 / tf);
      }
      camDist = dist; camBase.copy(target).addScaledVector(dir, dist); camSide.set(dir.z, 0, -dir.x).normalize(); camera.position.copy(camBase); camera.lookAt(target); camera.updateProjectionMatrix();
      if (!running) renderer.render(scene, camera);
    }
    const ro = new ResizeObserver(resize); ro.observe(el);
    const io = new IntersectionObserver((e) => { visible = e[0].isIntersecting; kick(); }); io.observe(el);

    // ---------- tema ----------
    function applyTheme() {
      readPal();
      mats.forEach((r) => { if (P[r.role]) { r.m.color.copy(P[r.role]); if (r.mix) r.m.color.lerp(P.paper, r.mix); } });
      grid.material.color.copy(P.line); grid.material.opacity = P.dark ? 0.16 : 0.5; grid.material.needsUpdate = true;
      redraws.forEach((s) => s.userData.redraw());
      items.forEach((it) => { if (!it.draft) { it.chipM.color.copy(P[it.chipRole] || P.ac2); if (it.decided) { it.tag.userData.st.color = it.def.r === 'OK' ? P.pay : dcol(it.def.d); } else it.tag.userData.st.color = P.ink2; it.tag.userData.redraw(); } });
    }
    const mo = new MutationObserver(applyTheme); mo.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme', 'data-palette'] });
    const mq = root.matchMedia ? root.matchMedia('(prefers-color-scheme: dark)') : null; if (mq && mq.addEventListener) mq.addEventListener('change', applyTheme);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => redraws.forEach((s) => s.userData.redraw()));
    applyTheme(); resize();
    for (let i = 0; i < 5; i++) { const it = spawn(items0[seqI % items0.length]); seqI++; it.s = 2 + i * GAP * SPEED; }
    kick();
    return { destroy() { running = false; cancelAnimationFrame(raf); ro.disconnect(); io.disconnect(); mo.disconnect(); if (mq && mq.removeEventListener) mq.removeEventListener('change', applyTheme); own.forEach((d) => d.dispose && d.dispose()); renderer.dispose(); if (renderer.domElement.parentNode) renderer.domElement.parentNode.removeChild(renderer.domElement); } };
  }
  root.mountFlow = mountFlow;
})(typeof window !== 'undefined' ? window : this);
