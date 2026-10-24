/* A living branching system behind the main page, after Anthony Fu's plum drawing in character but alive. Trees root only on the four
   viewport edges and grow inward as dendrites in straight runs with sharp kinks: each internode is a straight line, and at each node the
   direction breaks to one side or the other. Each fork adds a generation, and with each generation the internodes shorten, the stroke thins
   from 1 CSS px to a hairline, the alpha falls, the kinks and fork angles narrow and the fork odds rise, so trees fan out from their edge and
   the tips burst into short spines. Every branch grows, holds and withdraws on its own lifetime, on a slow breathing tempo, bending away from
   the text column. Every few seconds a tree fires: a signal leaves its root at about 420 px a second, splits into every child at each fork
   (where a small node blooms), and where one of its tips comes within 40 px of another tree's tip it jumps the gap and fires that tree from
   the tip inward and out through its forks, up to three hops, never the same tree twice in one cascade. Two canvases: a settled layer holding branches
   that have finished growing and hold, fading as a whole over about 40 s so old growth clears before it tangles, and a live layer redrawn at 30 fps for every branch still growing
   or withdrawing. The radial mask sits on both. The drawing never answers the pointer; the pointer glow rides the live layer and the
   pointer state is published on window.mwmLand for the blob. Hidden tabs pause and resume where they were. Under prefers-reduced-motion one
   settled population is drawn once, with no firings. Touch devices run at half population.
   Review parameters, all optional and free when absent: ?land=off removes the drawing, ?land=<alpha> overrides the base stroke alpha,
   ?period=<s> the breath (30), ?life=<s> the median branch lifetime (18), ?pulse=<s> the mean gap between firings (6.5), ?pop=<n> the live
   population cap, ?seeds=<n> the trunk budget (40), ?glow=off the pointer glow. The defaults are the owner's choices. */
(function () {
  'use strict';
  if (!document.getElementById('intro') || !window.requestAnimationFrame) return;
  var P = new URLSearchParams(location.search), num = function (k, d) { var v = parseFloat(P.get(k)); return isNaN(v) ? d : v; };
  if (P.get('land') === 'off') return;
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches, touch = window.matchMedia('(hover: none)').matches, glowOn = P.get('glow') !== 'off';
  var alphaOverride = P.get('land') !== null && !isNaN(parseFloat(P.get('land'))) ? parseFloat(P.get('land')) : null;
  var PERIOD = num('period', 30), LIFE = num('life', 18), AWAY = 8 * Math.PI / 180, PULSE = num('pulse', 6.5), SEEDS = num('seeds', 40);
  var popParam = P.get('pop');
  var EASE = 240, RADIUS = 240, HOLD_MS = 4000, STEPS_PER_S = 3, BURST = 3.2, BURST_MS = 8000, LIVE_FPS = 30, DEG = Math.PI / 180;
  var base = document.createElement('canvas'); base.id = 'land'; base.setAttribute('aria-hidden', 'true');
  var live = document.createElement('canvas'); live.id = 'land-live'; live.setAttribute('aria-hidden', 'true');
  var anchor = document.getElementById('goo') || document.body.firstChild;
  document.body.insertBefore(base, anchor); document.body.insertBefore(live, anchor);
  var ctx = base.getContext('2d'), lctx = live.getContext('2d');
  var W = 0, H = 0, DPR = 1, color = '', alpha = 0.1, light = false, POP = 60, LIVE_CAP = 2500, branches = [], trees = new Map(), settledOrder = [], firings = [], pending = [], tipGrid = new Map(), segsLive = 0;
  var raf = null, running = false, lastFrame = 0, lastLive = 0, lastFade = 0, lastSweep = 0, nextPulse = 0, startedAt = -1, phase = 0, lastPhaseT = -1, glowImg = null, glowF = 0;
  var pointer = { x: -1e4, y: -1e4, f: 0, target: 0, lastMove: -1e9, at: 0, from: 0 };
  var stats = { settled: 0, born: 0, withdrawn: 0, firings: 0, hops: 0 };
  var SPEED = 420, TAIL = 40, NODE_MS = 400, GAP = 40, JUMP_MS = 120, HOPS = 3, KEEP_TREES = 120;
  window.mwmLand = { pointer: pointer, radius: RADIUS, stats: function () { var g = [0, 0, 0, 0, 0, 0]; branches.forEach(function (b) { g[Math.min(5, b.gen)]++; }); return { live: branches.length, growing: branches.filter(function (b) { return b.phase === 'grow'; }).length, withdrawing: branches.filter(function (b) { return b.phase === 'withdraw'; }).length, liveSegments: segsLive, settled: stats.settled, born: stats.born, withdrawn: stats.withdrawn, firings: stats.firings, hops: stats.hops, activeFirings: firings.length, trees: trees.size, byGeneration: g, tempo: +tempo().toFixed(2), alpha: alpha, pop: POP, cap: LIVE_CAP, since: startedAt < 0 ? 0 : Math.round(performance.now() - startedAt), running: running, f: +pointer.f.toFixed(3), glow: +glowF.toFixed(3) }; } };

  // ---- the dendrite's character by generation ----
  var lerp = function (a, b, t) { return a + (b - a) * Math.max(0, Math.min(1, t)); };
  function segLen(g) { return Math.max(4, (8 + Math.random() * 12) * Math.pow(0.8, g)); }   // a straight internode of 8 to 20 px, shorter in later generations
  function strokeW(g) { return lerp(1, 1 / DPR, g / 3); }                       // CSS px: 1 on trunks, one device pixel by generation 3
  function genAlpha(g) { var a = light ? lerp(0.16, 0.06, g / 5) : lerp(0.14, 0.05, g / 5); return alphaOverride !== null ? a * alphaOverride / 0.10 : a; }
  function kink(g) { return lerp(15, 10, g / 4) * DEG + Math.random() * lerp(20, 10, g / 4) * DEG; }   // 15 to 35 degrees at a node, narrowing to 10 to 20 by generation 4
  function forkAngle(g) { return lerp(40, 18, g / 4) * DEG; }
  function forkP(g) { return lerp(0.35, 0.6, g / 3); }   // forking near the root, so trees fan out from their edge
  function maxSteps(g) { return Math.max(2, Math.round(13 * Math.pow(0.65, g))); }   // nodes per branch: trunks about a third of their former length, twigs short

  function isLight() { var t = document.documentElement.getAttribute('data-theme'); return t === 'light' || (t !== 'dark' && window.matchMedia('(prefers-color-scheme: light)').matches); }
  function tokens() {
    var cs = getComputedStyle(document.documentElement);
    color = cs.getPropertyValue('--text').trim() || '#ECECEA'; light = isLight();
    alpha = alphaOverride !== null ? alphaOverride : (light ? 0.12 : 0.10);
    [ctx, lctx].forEach(function (c) { c.strokeStyle = color; c.fillStyle = color; c.lineCap = 'round'; c.lineJoin = 'round'; });
    if (glowOn) {
      var mc = cs.getPropertyValue('--muted').trim(), m = /^#([0-9a-f]{6})$/i.exec(mc), rgb = m ? [parseInt(m[1].slice(0, 2), 16), parseInt(m[1].slice(2, 4), 16), parseInt(m[1].slice(4, 6), 16)] : [154, 154, 152];
      glowImg = document.createElement('canvas'); glowImg.width = glowImg.height = 480;
      var ic = glowImg.getContext('2d'), grad = ic.createRadialGradient(240, 240, 0, 240, 240, 240);
      grad.addColorStop(0, 'rgba(' + rgb.join(',') + ',0.08)'); grad.addColorStop(0.5, 'rgba(' + rgb.join(',') + ',0.03)'); grad.addColorStop(1, 'rgba(' + rgb.join(',') + ',0)');
      ic.fillStyle = grad; ic.fillRect(0, 0, 480, 480);
    }
  }
  function size(c) { c.width = Math.round(W * DPR); c.height = Math.round(H * DPR); c.style.width = W + 'px'; c.style.height = H + 'px'; c.getContext('2d').setTransform(DPR, 0, 0, DPR, 0, 0); }
  function resize() {
    DPR = window.devicePixelRatio || 1; W = window.innerWidth; H = window.innerHeight;
    size(base); size(live); tokens();
    POP = popParam !== null && !isNaN(parseFloat(popParam)) ? parseFloat(popParam) : (W < 600 ? 30 : 60); if (touch && popParam === null) POP = Math.round(POP / 2);
    LIVE_CAP = W < 600 ? 1200 : 2500;
    ctx.clearRect(0, 0, W, H); branches = []; trees = new Map(); settledOrder = []; firings = []; pending = []; tipGrid = new Map(); segsLive = 0;
  }

  // ---- geometry: the text column ----
  var colHalf = function () { return Math.min(W, 1100) / 2; };
  function inColumn(x) { return Math.abs(x - W / 2) < colHalf(); }

  // ---- tempo: a breath between 0.5 and 1.6 on a period that drifts between 20 and 40 s; plus the opening burst ----
  function tempo() {
    var t = performance.now();
    if (lastPhaseT < 0) lastPhaseT = t;
    var period = PERIOD * (1 + 0.33 * Math.sin(t / 97000 * 6.2832));
    phase += (t - lastPhaseT) / (period * 1000); lastPhaseT = t;
    var breath = 1.05 + 0.55 * Math.sin(phase * 6.2832);
    var since = startedAt < 0 ? 1e9 : performance.now() - startedAt, burst = since < BURST_MS ? 1 + (BURST - 1) * (1 - since / BURST_MS) : 1;
    return breath * burst;
  }

  // ---- branches ----
  function lognormal(median, sigma) { var u = 0, v = 0; while (u === 0) u = Math.random(); while (v === 0) v = Math.random(); var z = Math.sqrt(-2 * Math.log(u)) * Math.cos(6.2832 * v); return median * Math.exp(sigma * z); }
  var treeSeq = 0;
  function born(x, y, a, lifeMs, gen, parent, parentAt, tree) {
    var life = Math.max(1500, lifeMs), b = { pts: [[x, y]], a: a, life: life, t: 0, speed: 0.5 + Math.random() * 1.5, phase: 'grow', growEnd: life * 5 / 12, holdEnd: life * 8 / 12, settles: Math.random() < 0.4, erased: 0, acc: 0,
      gen: gen, parent: parent || null, parentAt: parentAt || 0, children: [], tree: tree != null ? tree : ++treeSeq, steps: 0, max: Math.round(maxSteps(gen) * (0.7 + Math.random() * 0.6)), settled: false };
    if (parent) parent.children.push(b);
    var tr = trees.get(b.tree); if (!tr) { tr = { id: b.tree, branches: [], settledAt: 0 }; trees.set(b.tree, tr); } tr.branches.push(b);
    b.live = true; branches.push(b); stats.born++; return b;
  }
  function seedEdge() {   // a trunk on one edge, heading inward within 35 degrees of the edge normal
    var e = Math.floor(Math.random() * 4), t = Math.random(), sp = (Math.random() * 2 - 1) * 35 * DEG;
    var p = e === 0 ? [t * W, -1, Math.PI / 2 + sp] : e === 1 ? [W + 1, t * H, Math.PI + sp] : e === 2 ? [t * W, H + 1, -Math.PI / 2 + sp] : [-1, t * H, sp];
    born(p[0], p[1], p[2], lognormal(LIFE, 0.75) * 1000, 0);
  }
  function turnToward(a, target, limit, gain) { var d = Math.atan2(Math.sin(target - a), Math.cos(target - a)); return a + Math.max(-limit, Math.min(limit, d * gain)); }   // a gentle bend, proportional to the angle and capped
  function step(b) {   // one straight internode; at its start the direction kinks to one side, steered off the text column; perhaps a fork
    var tip = b.pts[b.pts.length - 1], len = segLen(b.gen);
    if (b.steps > 0) b.a += (Math.random() < 0.5 ? -1 : 1) * kink(b.gen);
    var depth = colHalf() - Math.abs(tip[0] - W / 2);   // how far inside the text column the tip has reached
    if (depth > 0) { var k = Math.min(1, depth / 240), edge = tip[0] < W / 2 ? W / 2 - colHalf() : W / 2 + colHalf(); b.a = turnToward(b.a, Math.atan2(0, edge - tip[0]), AWAY * k, 0.08 * k); }   // steer away from the text column, harder the deeper in
    var nx = tip[0] + Math.cos(b.a) * len, ny = tip[1] + Math.sin(b.a) * len;
    if (nx < -6 || ny < -6 || nx > W + 6 || ny > H + 6) { b.growEnd = b.t; return; }   // off the viewport: growth ends here
    b.pts.push([nx, ny]); segsLive++; b.steps++;
    if (b.steps >= b.max) { b.growEnd = Math.min(b.growEnd, b.t); return; }
    if (Math.random() < forkP(b.gen) && branches.length < POP * 5 && segsLive < LIVE_CAP) {
      var rem = b.life - b.t;
      if (rem > 1500) born(nx, ny, b.a + (Math.random() < 0.5 ? 1 : -1) * forkAngle(b.gen) * (0.8 + Math.random() * 0.4), rem * (0.45 + Math.random() * 0.4), b.gen + 1, b, b.pts.length - 1, b.tree);
    }
  }
  function strokeBranch(c, b, upto, a) {
    c.globalAlpha = Math.min(1, a); c.lineWidth = strokeW(b.gen); c.beginPath(); c.moveTo(b.pts[0][0], b.pts[0][1]);
    for (var i = 1; i <= upto; i++) c.lineTo(b.pts[i][0], b.pts[i][1]);
    c.stroke();
  }
  function stamp(b) {   // a branch that has grown and holds goes to the settled layer, faded slowly as a whole
    if (b.pts.length < 2) return;
    strokeBranch(ctx, b, b.pts.length - 1, genAlpha(b.gen)); stats.settled++; b.settled = true;   // its geometry stays in its tree, for signals
  }
  function advance(dt, rate) {
    for (var i = branches.length - 1; i >= 0; i--) {
      var b = branches[i]; b.t += dt;
      if (b.phase === 'grow') {
        if (b.t >= b.growEnd) { if (b.settles) { stamp(b); segsLive -= b.pts.length - 1; b.live = false; branches.splice(i, 1); continue; } b.phase = 'hold'; continue; }
        b.acc += STEPS_PER_S * rate * b.speed * dt / 1000;
        while (b.acc >= 1 && b.phase === 'grow' && b.t < b.growEnd) { b.acc -= 1; step(b); }
      } else if (b.phase === 'hold') { if (b.t >= b.holdEnd) b.phase = 'withdraw'; }
      else {   // withdraw: erased from the tip back toward the root over the phase, fading as it goes
        var f = Math.min(1, (b.t - b.holdEnd) / Math.max(1, b.life - b.holdEnd)); b.erased = f * (b.pts.length - 1);
        if (f >= 1) { segsLive -= b.pts.length - 1; b.live = false; branches.splice(i, 1); stats.withdrawn++; drop(b); }
      }
    }
  }
  // trunks living at once: a third of the seeds parameter at 1440, fewer on narrower screens and on touch, so the forks have room to fill
  function trunkTarget() { return Math.max(3, Math.round(SEEDS / 3 * Math.min(1, W / 1440) * (touch && popParam === null ? 0.5 : 1))); }
  function tendPopulation() {   // new trunks from the edges as old growth leaves
    var trunks = 0; for (var i = 0; i < branches.length; i++) if (branches[i].gen === 0) trunks++;
    for (var k = 0; k < trunkTarget() - trunks && k < 2; k++) seedEdge();
  }

  // ---- trees: withdrawn branches leave their tree; trees with nothing live are kept, most recent 120, for signals to travel ----
  function drop(b) {
    b.gone = true; var tr = trees.get(b.tree); if (tr) { var k = tr.branches.indexOf(b); if (k >= 0) tr.branches.splice(k, 1); if (!tr.branches.length) trees.delete(b.tree); }
    if (b.parent) { var j = b.parent.children.indexOf(b); if (j >= 0) b.parent.children.splice(j, 1); }
  }
  function sweep(now) {   // once a second: retire trees with nothing live into the kept list, trim it, and rebuild the grid of tips
    if (now - lastSweep < 1000) return; lastSweep = now;
    trees.forEach(function (tr) { if (!tr.settledAt && !tr.branches.some(function (b) { return b.live; })) { tr.settledAt = now; settledOrder.push(tr.id); } });
    while (settledOrder.length > KEEP_TREES) trees.delete(settledOrder.shift());
    settledOrder = settledOrder.filter(function (id) { return trees.has(id); });
    tipGrid = new Map();
    trees.forEach(function (tr) { tr.branches.forEach(function (b) { if (b.pts.length < 2) return; var t = b.pts[b.pts.length - 1], key = Math.floor(t[0] / GAP) + ',' + Math.floor(t[1] / GAP); var cell = tipGrid.get(key); if (!cell) tipGrid.set(key, cell = []); cell.push(b); }); });
  }
  function nearTip(x, y, cascade, selfTree) {   // a tip of another tree within GAP px that this cascade has not fired
    var cx = Math.floor(x / GAP), cy = Math.floor(y / GAP), best = null, bd = GAP;
    for (var i = -1; i <= 1; i++) for (var j = -1; j <= 1; j++) {
      var cell = tipGrid.get((cx + i) + ',' + (cy + j)); if (!cell) continue;
      for (var k = 0; k < cell.length; k++) { var b = cell[k]; if (b.gone || b.tree === selfTree || cascade.fired.has(b.tree)) continue; var t = b.pts[b.pts.length - 1], d = Math.hypot(t[0] - x, t[1] - y); if (d < bd) { bd = d; best = b; } }
    }
    return best;
  }
  // ---- firing: distances along the tree from the source, so one signal front lights every branch as it reaches it ----
  function cumulative(pts) { var c = [0]; for (var i = 1; i < pts.length; i++) c.push(c[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1])); return c; }
  function fire(branch, fromIdx, now, cascade) {
    var f = { items: [], nodes: [], tips: [], start: now, max: 0, cascade: cascade, tree: branch.tree, origin: branch.pts[fromIdx].slice() };
    (function visit(b, entry, entryDist, from) {
      if (b.gone || b.pts.length < 2) return;
      var cum = cumulative(b.pts), dist = new Array(cum.length), lo = Infinity, hi = 0;
      for (var i = 0; i < cum.length; i++) { dist[i] = entryDist + Math.abs(cum[i] - cum[entry]); if (dist[i] < lo) lo = dist[i]; if (dist[i] > hi) hi = dist[i]; }
      f.items.push({ b: b, dist: dist, lo: lo, hi: hi }); if (hi > f.max) f.max = hi;
      f.tips.push({ b: b, d: dist[dist.length - 1], done: false });
      b.children.forEach(function (c) { if (c === from || c.gone) return; var at = Math.min(c.parentAt, dist.length - 1); f.nodes.push({ x: b.pts[at][0], y: b.pts[at][1], d: dist[at] }); visit(c, 0, dist[at], b); });
      if (b.parent && b.parent !== from && !b.parent.gone) { f.nodes.push({ x: b.pts[0][0], y: b.pts[0][1], d: dist[0] }); visit(b.parent, Math.min(b.parentAt, b.parent.pts.length - 1), dist[0], b); }
    })(branch, fromIdx, 0, null);
    cascade.fired.add(branch.tree); firings.push(f);
  }
  function startFiring(now) {   // a random tree fires from its root, never within 300 px of another firing's start
    var pool = []; trees.forEach(function (tr) { var root = tr.branches.filter(function (b) { return b.gen === 0 && !b.gone && b.pts.length > 8; })[0]; if (root) pool.push(root); });
    for (var tries = 0; tries < 8 && pool.length; tries++) {
      var r = pool[Math.floor(Math.random() * pool.length)], o = r.pts[0], clash = false;
      for (var i = 0; i < firings.length; i++) if (Math.hypot(firings[i].origin[0] - o[0], firings[i].origin[1] - o[1]) < 300) { clash = true; break; }
      if (!clash) { fire(r, 0, now, { hops: 0, fired: new Set() }); stats.firings++; return; }
    }
  }
  function tendFirings(now) {
    for (var p = pending.length - 1; p >= 0; p--) if (now >= pending[p].at) { var q = pending[p]; pending.splice(p, 1); if (!q.b.gone) fire(q.b, q.b.pts.length - 1, now, q.cascade); }
    firings = firings.filter(function (f) {
      var head = SPEED * (now - f.start) / 1000;
      f.tips.forEach(function (t) {   // a tip the front has reached may jump the gap to another tree
        if (t.done || head < t.d) return; t.done = true;
        if (f.cascade.hops >= HOPS || t.b.gone) return;
        var tip = t.b.pts[t.b.pts.length - 1], other = nearTip(tip[0], tip[1], f.cascade, f.tree);
        if (other) { f.cascade.hops++; f.cascade.fired.add(other.tree); stats.hops++; pending.push({ at: now + JUMP_MS, b: other, cascade: f.cascade }); }
      });
      return head < f.max + TAIL + SPEED * NODE_MS / 1000;
    });
  }
  function drawFirings(now) {
    var base0 = alphaOverride !== null ? alphaOverride : (light ? 0.12 : 0.10);
    firings.forEach(function (f) {
      var head = SPEED * (now - f.start) / 1000;
      f.items.forEach(function (it) {
        if (it.hi < head - TAIL || it.lo > head) return;
        var b = it.b, n = b.pts.length - 1; if (b.live && b.phase === 'withdraw') n = Math.floor(n - b.erased);
        var a3 = genAlpha(b.gen) * 3; lctx.lineWidth = strokeW(b.gen);
        for (var i = 1; i <= n && i < it.dist.length; i++) {
          var d = Math.max(it.dist[i], it.dist[i - 1]); if (d > head || d < head - TAIL) continue;
          lctx.globalAlpha = Math.min(1, a3 * (1 - (head - d) / TAIL)); lctx.beginPath(); lctx.moveTo(b.pts[i - 1][0], b.pts[i - 1][1]); lctx.lineTo(b.pts[i][0], b.pts[i][1]); lctx.stroke();
        }
      });
      f.nodes.forEach(function (nd) {   // a node at each fork the front passes: 2 px across at five times base alpha, blooming to 4 px as it fades
        var age = (head - nd.d) / SPEED * 1000; if (age < 0 || age > NODE_MS) return;
        var k = age / NODE_MS; lctx.globalAlpha = Math.min(1, base0 * 5 * (1 - k)); lctx.beginPath(); lctx.arc(nd.x, nd.y, 1 + k, 0, 6.2832); lctx.fill();
      });
    });
  }

  // ---- the live layer, redrawn at 30 fps ----
  function drawLive(now) {
    lctx.clearRect(0, 0, W, H);
    for (var i = 0; i < branches.length; i++) {
      var b = branches[i], n = b.pts.length - 1; if (n < 1) continue;
      var visible = b.phase === 'withdraw' ? n - b.erased : n, whole = Math.floor(visible); if (visible <= 0) continue;
      var a = genAlpha(b.gen);
      if (whole >= 1) strokeBranch(lctx, b, whole, a);
      if (b.phase === 'withdraw' && whole < n) {   // the erase front fades over its last segments
        lctx.lineWidth = strokeW(b.gen);
        for (var m = Math.max(1, whole - 3); m <= Math.min(n, whole + 1); m++) { lctx.globalAlpha = a * Math.max(0, Math.min(1, (visible - m) / 3 + 1)); lctx.beginPath(); lctx.moveTo(b.pts[m - 1][0], b.pts[m - 1][1]); lctx.lineTo(b.pts[m][0], b.pts[m][1]); lctx.stroke(); }
      }
    }
    drawFirings(now);
    if (glowOn && glowF > 0) { lctx.globalAlpha = glowF; lctx.drawImage(glowImg, pointer.x - 240, pointer.y - 240); }
  }
  function fadeSettled(now) {   // once a second: the settled layer loses a share of its alpha, so a full fade takes about 40 s
    if (now - lastFade < 1000) return; lastFade = now;
    ctx.globalCompositeOperation = 'destination-out'; ctx.globalAlpha = 0.094; ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H); ctx.globalCompositeOperation = 'source-over'; ctx.fillStyle = color;
  }

  function updatePointer(now) {
    if (pointer.target === 1 && now - pointer.lastMove > HOLD_MS) { pointer.target = 0; pointer.from = pointer.f; pointer.at = now; }
    var t = Math.min(1, (now - pointer.at) / EASE), e = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
    pointer.f = pointer.from + (pointer.target - pointer.from) * e;
    if (glowOn) { var target = now - pointer.lastMove < 100 ? 1 : 0; glowF = Math.max(0, Math.min(1, glowF + (target > glowF ? 1 : -1) * 16 / EASE)); }
  }
  function pointerTo(x, y, now) { pointer.x = x; pointer.y = y; pointer.lastMove = now; if (pointer.target !== 1) { pointer.target = 1; pointer.from = pointer.f; pointer.at = now; } }

  function frame(now) {
    raf = null; if (!running) return;
    var dt = Math.min(50, now - lastFrame); lastFrame = now;
    if (startedAt < 0) { startedAt = now; nextPulse = now + 4000; for (var sd = 0; sd < trunkTarget(); sd++) seedEdge(); }
    advance(dt, tempo()); tendPopulation();
    sweep(now); tendFirings(now);
    if (now >= nextPulse) { startFiring(now); nextPulse = now + (4 + Math.random() * 5) * 1000 * (PULSE / 6.5); }
    updatePointer(now); fadeSettled(now);
    if (now - lastLive >= 1000 / LIVE_FPS - 2) { lastLive = now; drawLive(now); }
    raf = requestAnimationFrame(frame);
  }
  function start() { if (running) return; running = true; lastFrame = performance.now(); lastPhaseT = -1; if (!raf) raf = requestAnimationFrame(frame); }
  function stop() { running = false; }

  resize();
  if (reduce) {   // one settled population, drawn once: a while of growth with no withdrawal
    for (var r = 0; r < 60; r++) { tendPopulation(); for (var q = 0; q < 30; q++) advance(16.7, 1.2); }
    branches.forEach(function (b) { stamp(b); }); branches = []; return;
  }
  var curtain = document.getElementById('curtain');
  var covered = function () { return curtain && getComputedStyle(curtain).display !== 'none' && !performance.getEntriesByName('hero-lift').length; };
  if (covered()) { var wait = setInterval(function () { if (!covered()) { clearInterval(wait); start(); } }, 50); } else start();
  window.addEventListener('resize', function () { if (window.innerWidth === W && window.innerHeight === H) return; resize(); });
  document.addEventListener('visibilitychange', function () { if (document.hidden) stop(); else start(); });
  new MutationObserver(function () { tokens(); }).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  if (!touch) {
    window.addEventListener('pointermove', function (e) { pointerTo(e.clientX, e.clientY, performance.now()); }, { passive: true });
    document.addEventListener('mouseleave', function () { pointer.lastMove = -1e9; });
  } else window.addEventListener('scroll', function () { pointerTo(W / 2, H / 2, performance.now()); }, { passive: true });
})();
