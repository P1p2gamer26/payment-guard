/* Payment Guard · escena 3D del flujo del agente.
 * Uso: <script src="three@0.160.0/build/three.min.js"> y luego
 *      const h = mountFlow(el, {reducedMotion: matchMedia('(prefers-reduced-motion: reduce)').matches});
 *      if (!h) -> mostrar fallback SVG.  h.destroy() para desmontar.
 * Script clásico (window.mountFlow) para que funcione también desde file://.
 * Flujo: facturas -> LLM extrae -> doble llave -> motor de reglas (13) -> 3 carriles
 *        ESCALAR -> persona -> borrador draft_not_executed.
 * Tema: lee <html data-theme="light|dark"> o prefers-color-scheme. */
(function (root) {
  'use strict';

  const C = { teal: 0x2b9cae, blue: 0x2350a9, pay: 0x2fbf8a, stop: 0xe5484d, esc: 0xf5a524, neutral: 0x9fb3bf };
  const CSS = (n) => '#' + n.toString(16).padStart(6, '0');
  const PAL = {
    light: { line: 0xb3c4cf, lane: 0.22, grid: 0xc7d5de, ink: '#04243C', mut: '#47657A', card: 0xffffff, side: 0xcfdbe3, node: 0x04243c, person: 0x04243c },
    dark: { line: 0x2c5673, lane: 0.3, grid: 0x163650, ink: '#E8F2F7', mut: '#8DB1C4', card: 0xeef5f8, side: 0x6f93a8, node: 0x7fd8e6, person: 0x9fdbe6 },
  };
  const KINDS = ['CORREO', 'CFDI', 'CHAT', 'COBRO'];
  // Cada ítem: tipo de documento, regla que decide, carril, índice (1-13) de la regla que dispara.
  const SEQ = [
    { k: 0, r: 'OK', d: 'P', idx: 13 },
    { k: 1, r: 'OK', d: 'P', idx: 13 },
    { k: 2, r: 'R_DUPLICADO', d: 'F', idx: 7 },
    { k: 3, r: 'OK', d: 'P', idx: 13 },
    { k: 0, r: 'R_UMBRAL', d: 'E', idx: 11, draft: true },
    { k: 1, r: 'OK', d: 'P', idx: 13 },
    { k: 2, r: 'R_LIMITE', d: 'F', idx: 10 },
    { k: 3, r: 'R_SOSPECHA', d: 'E', idx: 1, inj: true },
    { k: 0, r: 'OK', d: 'P', idx: 13 },
    { k: 1, r: 'R_CUENTA', d: 'E', idx: 6, draft: true },
  ];
  const X = { start: -10, llm: -6.2, key: -2.6, eng: 1.6, engHalf: 1.45, branch: 4.3 };
  const LANE_Z = { P: -2.3, F: 0, E: 2.3 };
  const SPEED = 2.5, GAP = 1.55, NRULES = 13;

  function mountFlow(el, opts) {
    opts = opts || {};
    const THREE = root.THREE;
    if (opts.reducedMotion || !THREE) return null;
    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'low-power' });
    } catch (e) { return null; }

    renderer.setPixelRatio(Math.min(root.devicePixelRatio || 1, 2));
    renderer.domElement.style.cssText = 'display:block;width:100%;height:100%';
    renderer.domElement.setAttribute('aria-hidden', 'true');
    el.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(24, 2, 0.1, 200);
    scene.add(new THREE.AmbientLight(0xffffff, 0.85));
    const sun = new THREE.DirectionalLight(0xffffff, 0.9);
    sun.position.set(-6, 12, 8);
    scene.add(sun);

    const darkMQ = root.matchMedia ? root.matchMedia('(prefers-color-scheme: dark)') : null;
    const isDark = () => {
      const t = document.documentElement.getAttribute('data-theme');
      return t ? t === 'dark' : !!(darkMQ && darkMQ.matches);
    };
    let pal = isDark() ? PAL.dark : PAL.light;

    // ---------- utilidades de lienzo/etiqueta ----------
    const labels = []; // {sprite, draw}
    function canvasSprite(w, h, sw, sh, draw) {
      const cv = document.createElement('canvas');
      cv.width = w; cv.height = h;
      const tex = new THREE.CanvasTexture(cv);
      tex.colorSpace = THREE.SRGBColorSpace;
      const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false });
      const sp = new THREE.Sprite(mat);
      sp.scale.set(sw, sh, 1);
      sp.renderOrder = 10;
      const redraw = () => {
        const g = cv.getContext('2d');
        g.clearRect(0, 0, w, h);
        draw(g, w, h);
        tex.needsUpdate = true;
      };
      redraw();
      labels.push(redraw);
      return sp;
    }
    const SANS = '600 {s}px Geist, "Segoe UI", system-ui, sans-serif';
    const MONO = '500 {s}px "Geist Mono", ui-monospace, Consolas, monospace';
    const f = (t, s) => t.replace('{s}', s);
    function label(title, sub, x, y, z, color) {
      const sp = canvasSprite(1024, 256, 5.2, 1.3, (g, w) => {
        g.textAlign = 'center';
        g.fillStyle = color ? CSS(color) : pal.ink;
        g.font = f(SANS, 84);
        g.fillText(title, w / 2, 112);
        g.fillStyle = pal.mut;
        g.font = f(MONO, 46);
        g.fillText(sub, w / 2, 190);
      });
      sp.position.set(x, y, z);
      scene.add(sp);
      return sp;
    }
    const tagCache = {};
    function tagSprite(rule, color) {
      const sp = canvasSprite(512, 128, 2.2, 0.55, (g, w, h) => {
        g.fillStyle = CSS(color);
        const r = 26, x0 = 6, y0 = 22, ww = w - 12, hh = h - 44;
        g.beginPath();
        g.moveTo(x0 + r, y0); g.arcTo(x0 + ww, y0, x0 + ww, y0 + hh, r); g.arcTo(x0 + ww, y0 + hh, x0, y0 + hh, r);
        g.arcTo(x0, y0 + hh, x0, y0, r); g.arcTo(x0, y0, x0 + ww, y0, r); g.fill();
        g.fillStyle = color === C.esc || color === C.pay ? '#04243C' : '#fff';
        g.font = f(MONO, 50);
        g.textAlign = 'center';
        g.fillText(rule, w / 2, 77);
      });
      return sp;
    }

    // ---------- geometrías y materiales compartidos ----------
    const disposables = [];
    const own = (o) => { disposables.push(o); return o; };
    const boxGeo = own(new THREE.BoxGeometry(1, 1, 1));
    const matBasic = (c, o) => own(new THREE.MeshBasicMaterial(Object.assign({ color: c }, o || {})));

    // Grilla de piso
    const grid = new THREE.GridHelper(40, 40, pal.grid, pal.grid);
    grid.position.y = -0.03;
    grid.material.transparent = true; grid.material.opacity = 0.35;
    scene.add(grid);

    // Carriles
    const laneMats = [];
    function strip(x1, z1, x2, z2, w, color, opacity) {
      const len = Math.hypot(x2 - x1, z2 - z1);
      const m = new THREE.Mesh(boxGeo, matBasic(color, { transparent: true, opacity }));
      m.scale.set(len, 0.04, w);
      m.position.set((x1 + x2) / 2, 0, (z1 + z2) / 2);
      m.rotation.y = -Math.atan2(z2 - z1, x2 - x1);
      scene.add(m);
      laneMats.push(m.material);
      return m;
    }
    strip(X.start, 0, X.branch, 0, 1.5, 0x000000, 0);
    const mainStrip = scene.children[scene.children.length - 1];
    mainStrip.material.color.setHex(pal.line); mainStrip.material.opacity = 0.55;
    const PATH = {
      P: [[X.start, 0], [X.branch, 0], [5.9, LANE_Z.P], [7.4, LANE_Z.P]],
      F: [[X.start, 0], [7.0, 0]],
      E: [[X.start, 0], [X.branch, 0], [5.9, LANE_Z.E], [7.0, LANE_Z.E]],
    };
    const laneColor = { P: C.pay, F: C.stop, E: C.esc };
    strip(X.branch, 0, 7.4, 0, 1.1, C.stop, 0.3);
    strip(X.branch, 0, 5.9, LANE_Z.P, 1.1, C.pay, 0.3);
    strip(5.9, LANE_Z.P, 8.4, LANE_Z.P, 1.1, C.pay, 0.3);
    strip(X.branch, 0, 5.9, LANE_Z.E, 1.1, C.esc, 0.3);
    strip(5.9, LANE_Z.E, 10.2, LANE_Z.E, 1.1, C.esc, 0.3);

    // ---------- nodos ----------
    const nodeMats = [];
    function ring(x, color, r) {
      const m = new THREE.Mesh(own(new THREE.TorusGeometry(r || 0.95, 0.05, 12, 56)), matBasic(color));
      m.rotation.y = Math.PI / 2; m.position.set(x, 0.55, 0);
      scene.add(m);
      return m;
    }
    ring(X.llm, C.teal, 1.0);
    const llmCore = new THREE.LineSegments(own(new THREE.EdgesGeometry(new THREE.IcosahedronGeometry(0.62, 0))), matBasic(pal.node));
    nodeMats.push(llmCore.material);
    llmCore.position.set(X.llm, 2.15, 0);
    scene.add(llmCore);
    const llmGlow = new THREE.Mesh(own(new THREE.IcosahedronGeometry(0.3, 0)), matBasic(C.teal, { transparent: true, opacity: 0.85 }));
    llmGlow.position.copy(llmCore.position);
    scene.add(llmGlow);
    const llmBeam = new THREE.Mesh(boxGeo, matBasic(C.teal, { transparent: true, opacity: 0.35 }));
    llmBeam.scale.set(0.05, 1.2, 0.05); llmBeam.position.set(X.llm, 1.3, 0);
    scene.add(llmBeam);

    const keyA = ring(X.key - 0.5, C.teal, 0.95);
    const keyB = ring(X.key + 0.5, C.blue, 0.95);

    const engBox = new THREE.LineSegments(own(new THREE.EdgesGeometry(new THREE.BoxGeometry(X.engHalf * 2, 1.5, 1.7))), matBasic(pal.node));
    nodeMats.push(engBox.material);
    engBox.position.set(X.eng, 0.75, 0);
    scene.add(engBox);
    const ticks = [];
    const tickMats = [];
    for (let i = 0; i < NRULES; i++) {
      const t = new THREE.Mesh(boxGeo, matBasic(pal.line));
      t.scale.set(0.11, 0.15, 0.11);
      t.position.set(X.eng - X.engHalf + 0.12 + i * ((X.engHalf * 2 - 0.24) / (NRULES - 1)), 0.1, 1.2);
      scene.add(t);
      ticks.push(t); tickMats.push(t.material);
    }

    // Persona (ESCALAR)
    const person = new THREE.Group();
    const pm = matBasic(pal.person); nodeMats.push(pm);
    const body = new THREE.Mesh(own(new THREE.CylinderGeometry(0.34, 0.42, 0.95, 20)), pm); body.position.y = 0.48;
    const head = new THREE.Mesh(own(new THREE.SphereGeometry(0.27, 20, 16)), pm); head.position.y = 1.28;
    person.add(body, head);
    person.position.set(8.2, 0, LANE_Z.E);
    scene.add(person);
    const personHalo = new THREE.Mesh(own(new THREE.RingGeometry(0.55, 0.68, 40)), matBasic(C.esc, { transparent: true, opacity: 0, side: THREE.DoubleSide }));
    personHalo.rotation.x = -Math.PI / 2; personHalo.position.set(8.2, 0.03, LANE_Z.E);
    scene.add(personHalo);
    // Barrera FRENAR y bin PAGAR
    const barrier = new THREE.Mesh(boxGeo, matBasic(C.stop, { transparent: true, opacity: 0.8 }));
    barrier.scale.set(0.14, 0.9, 1.5); barrier.position.set(7.55, 0.45, 0);
    scene.add(barrier);
    const bin = new THREE.Mesh(boxGeo, matBasic(C.pay, { transparent: true, opacity: 0.35 }));
    bin.scale.set(1.5, 0.06, 1.5); bin.position.set(8.3, 0.0, LANE_Z.P);
    scene.add(bin);

    // Etiquetas de nodo
    label('Facturas', 'correo · chat · CFDI · cobro', -9.0, 0.9, 0);
    label('1 · LLM extrae', 'solo lee, no decide', X.llm, 3.3, 0);
    label('2 · Doble llave', 'regex ≟ LLM: monto y moneda', X.key, 2.55, 0);
    label('3 · Motor de reglas', 'default-deny · 13 reglas', X.eng, 2.45, 0);
    label('PAGAR', 'dentro de reglas', 8.6, 1.1, LANE_Z.P, C.pay);
    label('FRENAR', 'inválido, sin discusión', 8.9, 1.0, 0, C.stop);
    label('ESCALAR', 'persona aprueba · re-chequea', 8.2, 2.1, LANE_Z.E, C.esc);
    label('draft_not_executed', 'no mueve dinero', 10.0, 0.9, LANE_Z.E + 1.7);

    // ---------- tarjetas ----------
    const kindTex = KINDS.map((name) => {
      const cv = document.createElement('canvas'); cv.width = 192; cv.height = 132;
      const g = cv.getContext('2d');
      g.fillStyle = '#ffffff'; g.fillRect(0, 0, 192, 132);
      g.fillStyle = '#04243C'; g.fillRect(0, 0, 192, 28);
      g.fillStyle = '#fff'; g.font = '600 17px "Geist Mono", ui-monospace, Consolas, monospace'; g.fillText(name, 10, 20);
      g.fillStyle = '#C9D6DE';
      [48, 64, 80].forEach((y, i) => g.fillRect(10, y, 120 - i * 22, 7));
      g.fillStyle = '#04243C'; g.fillRect(112, 100, 70, 14);
      const t = new THREE.CanvasTexture(cv); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4;
      return own(t);
    });
    const topMats = kindTex.map((t) => own(new THREE.MeshStandardMaterial({ map: t, roughness: 0.9 })));
    const sideMat = own(new THREE.MeshStandardMaterial({ color: pal.side, roughness: 0.9 }));
    const draftTex = (() => {
      const cv = document.createElement('canvas'); cv.width = 192; cv.height = 132;
      const g = cv.getContext('2d');
      g.fillStyle = '#ffffff'; g.fillRect(0, 0, 192, 132);
      g.strokeStyle = '#2B9CAE'; g.lineWidth = 6; g.setLineDash([10, 6]); g.strokeRect(5, 5, 182, 122);
      g.fillStyle = '#2B9CAE'; g.font = '600 19px "Geist Mono", ui-monospace, Consolas, monospace'; g.fillText('TRANSFER', 14, 40);
      g.fillStyle = '#C9D6DE'; g.fillRect(14, 62, 120, 7); g.fillRect(14, 80, 90, 7);
      g.save(); g.translate(112, 108); g.rotate(-0.15); g.fillStyle = '#2B9CAE'; g.font = '600 15px "Geist Mono", ui-monospace, Consolas, monospace'; g.fillText('DRAFT', 0, 0); g.restore();
      const t = new THREE.CanvasTexture(cv); t.colorSpace = THREE.SRGBColorSpace;
      return own(t);
    })();
    const draftTop = own(new THREE.MeshStandardMaterial({ map: draftTex, roughness: 0.9 }));
    const fieldGeo = boxGeo;

    function pathInfo(pts) {
      const cum = [0];
      for (let i = 1; i < pts.length; i++) cum.push(cum[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
      return { pts, cum, total: cum[cum.length - 1] };
    }
    const PI = { P: pathInfo(PATH.P), F: pathInfo(PATH.F), E: pathInfo(PATH.E) };
    function at(info, s) {
      s = Math.min(s, info.total);
      let i = 1;
      while (i < info.cum.length - 1 && s > info.cum[i]) i++;
      const a = info.pts[i - 1], b = info.pts[i], u = (s - info.cum[i - 1]) / (info.cum[i] - info.cum[i - 1] || 1);
      return [a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u];
    }

    const items = [];
    function spawn(def) {
      const g = new THREE.Group();
      const card = new THREE.Mesh(boxGeo, [sideMat, sideMat, topMats[def.k], sideMat, sideMat, sideMat]);
      card.scale.set(1.3, 0.07, 0.92);
      const chip = new THREE.Mesh(boxGeo, matBasic(C.neutral));
      chip.scale.set(0.3, 0.05, 0.16); chip.position.set(0.42, 0.06, 0.3);
      const fields = new THREE.Group();
      for (let i = 0; i < 3; i++) {
        const b = new THREE.Mesh(fieldGeo, matBasic(def.inj ? C.esc : C.teal));
        b.scale.set(0.44 - i * 0.08, 0.04, 0.07); b.position.set(-0.28, 0.07, -0.05 + i * 0.16);
        fields.add(b);
      }
      fields.visible = false;
      g.add(card, chip, fields);
      const outcomeColor = laneColor[def.d];
      const tag = tagSprite(def.inj ? 'R_SOSPECHA · inyección' : def.r, def.r === 'OK' ? C.pay : outcomeColor);
      tag.visible = false; tag.position.set(0, 0.95, 0);
      if (def.inj) tag.scale.set(3.3, 0.55, 1);
      g.add(tag);
      scene.add(g);
      const it = { def, g, chip, fields, tag, s: 0, t: 0, state: 'move', info: PI[def.d], done: false, scale: 1, decided: false };
      items.push(it);
      return it;
    }
    function spawnDraft(from) {
      const g = new THREE.Group();
      const card = new THREE.Mesh(boxGeo, [sideMat, sideMat, draftTop, sideMat, sideMat, sideMat]);
      card.scale.set(1.2, 0.07, 0.85);
      g.add(card); g.position.set(from, 0.05, LANE_Z.E);
      scene.add(g);
      items.push({ draft: true, g, x: from, state: 'move', t: 0, scale: 1 });
    }

    // ---------- bucle ----------
    let spawnT = 0, seqI = 0, running = true, visible = true, raf = 0, clock = performance.now(), time = 0;
    let personPulse = 0, binPulse = 0, barrierShake = 0;
    const tickLevel = new Float32Array(NRULES);
    const tickColor = new Array(NRULES).fill(C.teal);

    function frame(now) {
      raf = 0;
      if (!running || !visible) return;
      const dt = Math.min(0.05, (now - clock) / 1000); clock = now; time += dt;
      spawnT -= dt;
      if (spawnT <= 0) { spawn(SEQ[seqI % SEQ.length]); seqI++; spawnT = GAP; }

      // decaimiento de ticks; se re-ilumina según tarjetas en la zona
      for (let i = 0; i < NRULES; i++) tickLevel[i] = Math.max(0, tickLevel[i] - dt * 2.2);

      for (let n = items.length - 1; n >= 0; n--) {
        const it = items[n];
        if (it.draft) {
          if (it.state === 'move') {
            it.x += SPEED * dt * 0.9; it.g.position.x = it.x;
            if (it.x > 10.0) { it.state = 'sink'; it.t = 0; }
          } else { it.t += dt; it.scale = Math.max(0, 1 - it.t / 0.7); it.g.scale.setScalar(Math.max(it.scale, 0.001)); if (it.t > 0.7) { scene.remove(it.g); items.splice(n, 1); } }
          continue;
        }
        const d = it.def;
        if (it.state === 'move') {
          it.s += SPEED * dt;
          const [x, z] = at(it.info, it.s);
          it.g.position.set(x, 0.06, z);
          if (x > X.llm - 0.2) it.fields.visible = true;
          // ticks (zona del motor)
          const e0 = X.eng - X.engHalf, e1 = X.eng + X.engHalf;
          if (x > e0 && x < e1) {
            const p = (x - e0) / (e1 - e0), upto = Math.min(NRULES, Math.ceil(p * NRULES + 0.0001));
            for (let i = 0; i < Math.min(upto, d.idx); i++) {
              if (tickLevel[i] < 0.8) { tickLevel[i] = 1; tickColor[i] = i === d.idx - 1 ? (d.r === 'OK' ? C.pay : laneColor[d.d]) : C.teal; }
              else if (i === d.idx - 1) tickColor[i] = d.r === 'OK' ? C.pay : laneColor[d.d];
            }
          }
          if (!it.decided && x > e1 - 0.1) {
            it.decided = true; it.chip.material.color.setHex(laneColor[d.d]); it.tag.visible = true;
          }
          if (it.s >= it.info.total) { it.state = 'end'; it.t = 0; if (d.d === 'P') binPulse = 1; if (d.d === 'F') barrierShake = 1; if (d.d === 'E') personPulse = 1; }
        } else if (it.state === 'end') {
          it.t += dt;
          const hold = d.d === 'E' ? 1.1 : d.d === 'F' ? 0.45 : 0.1;
          if (d.d === 'F') it.g.position.x = 6.9 - Math.abs(Math.sin(it.t * 18)) * 0.08 * Math.max(0, 1 - it.t * 2);
          if (it.t >= hold) {
            if (d.d === 'E' && d.draft) spawnDraft(8.9);
            it.state = 'sink'; it.t = 0;
          }
        } else {
          it.t += dt;
          it.tag.visible = false;
          it.scale = Math.max(0, 1 - it.t / 0.45); it.g.scale.setScalar(Math.max(it.scale, 0.001));
          if (d.d === 'P') it.g.position.y = 0.06 - it.t * 0.4;
          if (it.t > 0.45) { scene.remove(it.g); items.splice(n, 1); }
        }
      }

      for (let i = 0; i < NRULES; i++) {
        const lv = tickLevel[i], m = ticks[i];
        m.scale.y = 0.15 + lv * 0.75; m.position.y = m.scale.y / 2 + 0.02;
        m.material.color.setHex(lv > 0.02 ? tickColor[i] : pal.line);
      }
      llmCore.rotation.y += dt * 0.9; llmCore.rotation.x += dt * 0.4;
      llmGlow.scale.setScalar(1 + Math.sin(time * 3) * 0.15);
      keyA.rotation.x += dt * 1.1; keyB.rotation.x -= dt * 1.1;
      personPulse = Math.max(0, personPulse - dt * 0.8);
      personHalo.material.opacity = personPulse; personHalo.scale.setScalar(1 + (1 - personPulse) * 0.6);
      binPulse = Math.max(0, binPulse - dt * 2); bin.material.opacity = 0.35 + binPulse * 0.5;
      barrierShake = Math.max(0, barrierShake - dt * 2); barrier.material.opacity = 0.8 + barrierShake * 0.2;
      barrier.position.x = 7.55 + Math.sin(time * 40) * 0.04 * barrierShake;

      renderer.render(scene, camera);
      raf = requestAnimationFrame(frame);
    }
    function kick() { if (!raf && running && visible) { clock = performance.now(); raf = requestAnimationFrame(frame); } }

    // ---------- tamaño / cámara ----------
    const target = new THREE.Vector3(1.0, 0.0, 0.5);
    const dir = new THREE.Vector3(0.14, 0.78, 0.62).normalize();
    function resize() {
      const w = Math.max(el.clientWidth, 1), h = Math.max(el.clientHeight, 1);
      renderer.setSize(w, h, false);
      const a = w / h; camera.aspect = a;
      const needW = 22, needH = 11;
      const dW = needW / (2 * Math.tan((camera.fov * Math.PI) / 360) * a);
      const dH = needH / (2 * Math.tan((camera.fov * Math.PI) / 360));
      camera.position.copy(target).addScaledVector(dir, Math.max(dW, dH));
      camera.lookAt(target);
      camera.updateProjectionMatrix();
      if (!running) renderer.render(scene, camera);
    }
    const ro = new ResizeObserver(resize); ro.observe(el);
    const io = new IntersectionObserver((e) => { visible = e[0].isIntersecting; kick(); });
    io.observe(el);

    // ---------- tema ----------
    function applyTheme() {
      pal = isDark() ? PAL.dark : PAL.light;
      grid.material.color.setHex(pal.grid);
      mainStrip.material.color.setHex(pal.line);
      nodeMats.forEach((m) => m.color.setHex(m === pm ? pal.person : pal.node));
      sideMat.color.setHex(pal.side);
      labels.forEach((r) => r());
    }
    const mo = new MutationObserver(applyTheme);
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    if (darkMQ && darkMQ.addEventListener) darkMQ.addEventListener('change', applyTheme);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => labels.forEach((r) => r()));
    applyTheme();
    resize();
    // Precalentar: ya hay 3 tarjetas en pantalla al montar
    for (let i = 0; i < 4; i++) { const it = spawn(SEQ[seqI % SEQ.length]); seqI++; it.s = 3.2 + i * GAP * SPEED * 1.0; }
    kick();

    return {
      destroy() {
        running = false; cancelAnimationFrame(raf); ro.disconnect(); io.disconnect(); mo.disconnect();
        if (darkMQ && darkMQ.removeEventListener) darkMQ.removeEventListener('change', applyTheme);
        disposables.forEach((d) => d.dispose && d.dispose());
        renderer.dispose(); if (renderer.domElement.parentNode) renderer.domElement.parentNode.removeChild(renderer.domElement);
      },
    };
  }

  root.mountFlow = mountFlow;
})(typeof window !== 'undefined' ? window : this);
