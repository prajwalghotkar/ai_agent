/* The AI universe: a dependency-free WebGL scene.
 *  - spiral galaxy (tens of thousands of particles) that rotates, and can be dragged / zoomed
 *  - nebula clouds, deep star field, orbiting aura particles
 *  - Prajwal's portrait as a holographic disc in the core, ringed by tilted HUD rings
 *  - reacts to Jarvis' state: idle / listening / thinking / speaking (colour, speed, pulse)
 */

const STATES = {
  idle:      { c: [0.15, 0.83, 1.00], spin: 1.0, glow: 0.55 },
  listening: { c: [0.24, 1.00, 0.71], spin: 1.8, glow: 0.78 },
  thinking:  { c: [0.69, 0.42, 1.00], spin: 4.2, glow: 0.85 },
  speaking:  { c: [1.00, 0.54, 0.24], spin: 2.2, glow: 0.95 },
};

/* ---------- tiny matrix library (column-major) ---------- */
const m4 = {
  id: () => new Float32Array([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]),
  mul(a, b) {
    const o = new Float32Array(16);
    for (let c = 0; c < 4; c++) for (let r = 0; r < 4; r++) {
      let s = 0;
      for (let k = 0; k < 4; k++) s += a[k * 4 + r] * b[c * 4 + k];
      o[c * 4 + r] = s;
    }
    return o;
  },
  persp(f, asp, n, fa) {
    const t = 1 / Math.tan(f / 2), o = new Float32Array(16);
    o[0] = t / asp; o[5] = t; o[10] = (fa + n) / (n - fa); o[11] = -1; o[14] = (2 * fa * n) / (n - fa);
    return o;
  },
  trans(x, y, z) { const o = m4.id(); o[12] = x; o[13] = y; o[14] = z; return o; },
  scale(x, y = x, z = x) { const o = m4.id(); o[0] = x; o[5] = y; o[10] = z; return o; },
  rx(a) { const c = Math.cos(a), s = Math.sin(a), o = m4.id(); o[5] = c; o[6] = s; o[9] = -s; o[10] = c; return o; },
  ry(a) { const c = Math.cos(a), s = Math.sin(a), o = m4.id(); o[0] = c; o[2] = -s; o[8] = s; o[10] = c; return o; },
  rz(a) { const c = Math.cos(a), s = Math.sin(a), o = m4.id(); o[0] = c; o[1] = s; o[4] = -s; o[5] = c; return o; },
};
const chain = (...ms) => ms.reduce((a, b) => m4.mul(a, b));

/* ---------- shaders ---------- */
const PRECISION = `
#ifdef GL_FRAGMENT_PRECISION_HIGH
precision highp float;
#else
precision mediump float;
#endif`;

const POINTS_VS = `
attribute vec3 a_pos; attribute vec3 a_col; attribute vec2 a_misc;
uniform mat4 u_mvp; uniform float u_time, u_scale, u_pulse, u_tintAmt; uniform vec3 u_tint;
varying vec3 v_col;
void main(){
  vec4 p = u_mvp * vec4(a_pos * (1.0 + u_pulse), 1.0);
  gl_Position = p;
  float tw = 0.72 + 0.28 * sin(u_time * 1.7 + a_misc.y * 6.2831);
  v_col = mix(a_col, u_tint, u_tintAmt) * tw;
  gl_PointSize = clamp(a_misc.x * u_scale / max(p.w, 0.1), 1.0, 26.0);
}`;
const POINTS_FS = `${PRECISION}
varying vec3 v_col; uniform float u_alpha;
void main(){
  float r = length(gl_PointCoord - 0.5) * 2.0;
  if (r > 1.0) discard;
  float a = (1.0 - r); a *= a;
  gl_FragColor = vec4(v_col * a * u_alpha, a * u_alpha);
}`;

const QUAD_VS = `
attribute vec2 a_pos; uniform mat4 u_mvp; varying vec2 v_p;
void main(){ v_p = a_pos; gl_Position = u_mvp * vec4(a_pos, 0.0, 1.0); }`;
const QUAD_FS = `${PRECISION}
varying vec2 v_p;
uniform float u_mode, u_time, u_amp, u_alpha, u_spin, u_seed;
uniform vec3 u_color; uniform vec4 u_ring; uniform sampler2D u_tex, u_neb;
float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p){
  vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x), f.y);
}
float fbm(vec2 p){ float s = 0.0, a = 0.5; for (int i = 0; i < 4; i++){ s += a * noise(p); p = p * 2.03 + 17.0; a *= 0.5; } return s; }
void main(){
  float r = length(v_p);
  if (u_mode < 0.5) {                                   // ---- holographic portrait
    vec2 uv = v_p * 0.5 + 0.5; uv.y = 1.0 - uv.y;
    vec3 c = texture2D(u_tex, (uv - 0.5) * 0.955 + 0.5).rgb;     // crop the photo's white border ring
    float mask = 1.0 - smoothstep(0.965, 1.0, r);
    c *= 0.93 + 0.07 * (0.5 + 0.5 * sin(uv.y * 560.0 - u_time * 4.0));   // scanlines
    float rim = smoothstep(0.55, 1.0, r);
    c += u_color * rim * (0.30 + 0.55 * u_amp);                  // glowing rim in the state colour
    float sweep = smoothstep(0.045, 0.0, abs(fract(u_time * 0.2) * 2.6 - 1.3 - v_p.y));
    c += u_color * sweep * 0.22;                                  // scanning beam
    c *= 1.0 + 0.10 * u_amp;
    gl_FragColor = vec4(c * mask, mask);
  } else if (u_mode < 1.5) {                            // ---- soft halo
    float g = exp(-r * r * 3.0);
    gl_FragColor = vec4(u_color * g * u_alpha, g * u_alpha);
  } else if (u_mode < 2.5) {                            // ---- HUD ring (solid / dashed / arcs)
    float mid = (u_ring.x + u_ring.y) * 0.5, hw = (u_ring.y - u_ring.x) * 0.5;
    float d = abs(r - mid);
    float line = 1.0 - smoothstep(hw * 0.6, hw * 1.4, d);
    float glow = exp(-d * d / (hw * hw * 40.0)) * 0.5;
    float vis = 1.0;
    if (u_ring.z > 0.5) {
      float seg = fract((atan(v_p.y, v_p.x) / 6.2831853 + 0.5 + u_spin) * u_ring.z);
      vis = smoothstep(0.0, 0.02, seg) * (1.0 - smoothstep(u_ring.w - 0.02, u_ring.w, seg));
    }
    float v = (line + glow) * vis;
    gl_FragColor = vec4(u_color * v * u_alpha, v * u_alpha);
  } else if (u_mode < 3.5) {                            // ---- nebula noise (rendered ONCE into a texture)
    float n = fbm(v_p * 2.1 + u_seed);
    float a = smoothstep(0.0, 1.0, 1.0 - r); a = a * (0.2 + 1.15 * n);
    gl_FragColor = vec4(a, a, a, 1.0);
  } else {                                              // ---- nebula cloud (cheap: just samples the baked texture)
    float a = texture2D(u_neb, v_p * 0.5 + 0.5).r * u_alpha;
    gl_FragColor = vec4(u_color * a, a);
  }
}`;

function compile(gl, type, src) {
  const s = gl.createShader(type);
  gl.shaderSource(s, src); gl.compileShader(s);
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
  return s;
}
function makeProgram(gl, vs, fs, attribs) {
  const p = gl.createProgram();
  gl.attachShader(p, compile(gl, gl.VERTEX_SHADER, vs));
  gl.attachShader(p, compile(gl, gl.FRAGMENT_SHADER, fs));
  attribs.forEach((a, i) => gl.bindAttribLocation(p, i, a));
  gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p));
  const u = {};
  for (let i = 0, n = gl.getProgramParameter(p, gl.ACTIVE_UNIFORMS); i < n; i++) {
    const info = gl.getActiveUniform(p, i);
    u[info.name] = gl.getUniformLocation(p, info.name);
  }
  return { p, u };
}

function rng(seed) {                                     // deterministic, so the galaxy looks the same every visit
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/* ---------- point clouds: [x y z  r g b  size phase] ---------- */
function makeGalaxy(n) {
  const rand = rng(7), R = 17, arms = 4, out = new Float32Array(n * 8);
  const core = [0.62, 0.9, 1.0], mid = [0.55, 0.45, 1.0], edge = [0.85, 0.25, 0.9], pink = [1.0, 0.35, 0.65];
  for (let i = 0; i < n; i++) {
    const r = Math.pow(rand(), 1.55) * R;
    const branch = ((i % arms) / arms) * Math.PI * 2, spin = r * 0.36;
    const spread = (k) => Math.pow(rand(), 3) * (rand() < 0.5 ? 1 : -1) * k * (0.35 + r * 0.06);
    const x = Math.cos(branch + spin) * r + spread(1), z = Math.sin(branch + spin) * r + spread(1);
    const y = spread(0.5) * (1 - r / (R * 1.1));
    const t = r / R;
    let c = t < 0.4 ? lerp3(core, mid, t / 0.4) : lerp3(mid, edge, (t - 0.4) / 0.6);
    if (rand() < 0.14) c = pink;
    const b = 0.8 + rand() * 0.2;
    out.set([x, y, z, c[0] * b, c[1] * b, c[2] * b, 0.9 + rand() * 2.2 + (t < 0.15 ? 0.7 : 0), rand()], i * 8);
  }
  return out;
}
function makeStars(n) {
  const rand = rng(99), out = new Float32Array(n * 8), pal = [[1, 1, 1], [0.7, 0.85, 1], [1, 0.8, 0.9], [0.8, 0.75, 1]];
  for (let i = 0; i < n; i++) {
    const r = 28 + rand() * 60, th = rand() * Math.PI * 2, ph = Math.acos(2 * rand() - 1), c = pal[(rand() * pal.length) | 0];
    const b = 0.35 + rand() * 0.65;
    out.set([r * Math.sin(ph) * Math.cos(th), r * Math.cos(ph), r * Math.sin(ph) * Math.sin(th), c[0] * b, c[1] * b, c[2] * b, 1.2 + rand() * 2.4, rand()], i * 8);
  }
  return out;
}
function makeAura(n) {                                   // particles swarming around the portrait
  const rand = rng(31), out = new Float32Array(n * 8);
  for (let i = 0; i < n; i++) {
    const r = 2.3 + Math.pow(rand(), 1.4) * 2.2, th = rand() * Math.PI * 2, y = (rand() - 0.5) * 1.5 * (1 - (r - 2.3) / 3);
    out.set([Math.cos(th) * r, y, Math.sin(th) * r, 0.5, 0.9, 1, 0.9 + rand() * 1.6, rand()], i * 8);
  }
  return out;
}
const lerp3 = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

/* =========================================================================================== */
export function createUniverse(canvas, { photoUrl, quality = "auto" } = {}) {
  const gl = canvas.getContext("webgl", { antialias: true, alpha: false, powerPreference: "high-performance" })
    || canvas.getContext("experimental-webgl");
  if (!gl) return null;

  let pts, quad;
  try {
    pts = makeProgram(gl, POINTS_VS, POINTS_FS, ["a_pos", "a_col", "a_misc"]);
    quad = makeProgram(gl, QUAD_VS, QUAD_FS, ["a_pos"]);
  } catch (err) {
    console.warn("WebGL shader failed:", err);
    return null;
  }

  const quadBuf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, quadBuf);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);

  const upload = (data, usage = gl.STATIC_DRAW) => {
    const buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, data, usage);
    return { buf, count: data.length / 8 };
  };


  /* ---- bake the nebula clouds once (256x256 each) so no per-frame noise maths is needed ---- */
  const NEB_SEEDS = [1.3, 4.1, 7.7, 9.2, 2.2];
  const nebTex = {};
  {
    const fbo = gl.createFramebuffer();
    gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);
    gl.viewport(0, 0, 256, 256);
    gl.disable(gl.BLEND);
    for (const seed of NEB_SEEDS) {
      const t2 = gl.createTexture();
      gl.bindTexture(gl.TEXTURE_2D, t2);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 256, 256, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, t2, 0);
      gl.bindTexture(gl.TEXTURE_2D, null);          // never sample the texture we are drawing into (feedback loop)
      gl.useProgram(quad.p);
      gl.bindBuffer(gl.ARRAY_BUFFER, quadBuf);
      gl.enableVertexAttribArray(0); gl.disableVertexAttribArray(1); gl.disableVertexAttribArray(2);
      gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
      gl.uniformMatrix4fv(quad.u.u_mvp, false, m4.id());
      gl.uniform1f(quad.u.u_mode, 3);
      gl.uniform1f(quad.u.u_seed, seed);
      gl.uniform1f(quad.u.u_time, 0); gl.uniform1f(quad.u.u_amp, 0); gl.uniform1f(quad.u.u_alpha, 1); gl.uniform1f(quad.u.u_spin, 0);
      gl.uniform3fv(quad.u.u_color, [1, 1, 1]); gl.uniform4fv(quad.u.u_ring, [0, 0, 0, 0]);
      gl.uniform1i(quad.u.u_tex, 0); gl.uniform1i(quad.u.u_neb, 1);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      nebTex[seed] = t2;
    }
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.bindTexture(gl.TEXTURE_2D, null);
  }

  /* photo texture (a dark placeholder until the image arrives) */
  const tex = gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D, tex);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array([8, 14, 30, 255]));
  const setTexParams = () => {
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  };
  setTexParams();
  let photoLoaded = false;
  if (photoUrl) {
    const img = new Image();
    img.onload = () => {
      gl.bindTexture(gl.TEXTURE_2D, tex);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img);
      setTexParams();
      photoLoaded = true;
    };
    img.src = photoUrl;
  }

  /* ---- scene data (rebuilt when quality changes) ---- */
  const isSmall = Math.min(screen.width, screen.height) < 700 || (navigator.hardwareConcurrency || 8) <= 4;
  let level = quality === "auto" ? (isSmall ? "low" : "high") : quality;
  let galaxy, stars, aura;
  const orbiters = { buf: gl.createBuffer(), data: new Float32Array(3 * 8) };
  const build = () => {
    const k = level === "low" ? 0.5 : 1;
    galaxy = upload(makeGalaxy(Math.round(30000 * k)));
    stars = upload(makeStars(Math.round(4200 * k)));
    aura = upload(makeAura(Math.round(1600 * k)));
  };
  build();

  /* ---- state ---- */
  let state = "idle", t = 0, last = performance.now(), running = true, lost = false;
  const col = [...STATES.idle.c];
  let spin = 1, glow = 0.55, amp = 0, kick = 0, ampExternal = null;
  let mx = 0, my = 0, px = 0, py = 0;
  let galYaw = 0, galPitch = 0, velYaw = 0, camZ = 9.6, camZTarget = 9.6, drag = null;
  let ringSpin = 0, galSpin = 0, orbit = 0;
  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
  let dpr = 1, W = 1, H = 1, frames = 0, slowFrames = 0;

  const resize = () => {
    dpr = Math.min(window.devicePixelRatio || 1, level === "low" ? 1 : 1.75);
    W = Math.max(2, Math.floor(canvas.clientWidth * dpr));
    H = Math.max(2, Math.floor(canvas.clientHeight * dpr));
    if (canvas.width !== W || canvas.height !== H) { canvas.width = W; canvas.height = H; }
    gl.viewport(0, 0, W, H);
  };
  window.addEventListener("resize", resize);
  resize();

  canvas.addEventListener("webglcontextlost", (e) => { e.preventDefault(); lost = true; });
  canvas.addEventListener("webglcontextrestored", () => location.reload());

  /* ---- interaction: parallax, drag to rotate the universe, wheel to zoom ---- */
  canvas.addEventListener("pointerdown", (e) => { drag = { x: e.clientX, y: e.clientY }; canvas.setPointerCapture?.(e.pointerId); canvas.classList.add("dragging"); });
  const endDrag = () => { drag = null; canvas.classList.remove("dragging"); };
  canvas.addEventListener("pointerup", endDrag);
  canvas.addEventListener("pointercancel", endDrag);
  window.addEventListener("pointermove", (e) => {
    mx = (e.clientX / innerWidth) * 2 - 1; my = (e.clientY / innerHeight) * 2 - 1;
    if (drag) {
      velYaw = (e.clientX - drag.x) * 0.0045;
      galPitch = clamp(galPitch + (e.clientY - drag.y) * 0.003, -0.7, 0.7);
      galYaw += velYaw; drag.x = e.clientX; drag.y = e.clientY;
    }
  });
  canvas.addEventListener("wheel", (e) => { camZTarget = clamp(camZTarget + e.deltaY * 0.004, 6.5, 15); }, { passive: true });

  /* ---- drawing helpers ---- */
  const attribs = (n) => { for (let i = 0; i < 3; i++) (i < n ? gl.enableVertexAttribArray(i) : gl.disableVertexAttribArray(i)); };

  function drawPoints(set, mvp, o = {}) {
    gl.useProgram(pts.p);
    gl.bindBuffer(gl.ARRAY_BUFFER, set.buf);
    attribs(3);
    gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 32, 0);
    gl.vertexAttribPointer(1, 3, gl.FLOAT, false, 32, 12);
    gl.vertexAttribPointer(2, 2, gl.FLOAT, false, 32, 24);
    gl.uniformMatrix4fv(pts.u.u_mvp, false, mvp);
    gl.uniform1f(pts.u.u_time, t);
    gl.uniform1f(pts.u.u_scale, H * 0.03);
    gl.uniform1f(pts.u.u_pulse, o.pulse || 0);
    gl.uniform1f(pts.u.u_tintAmt, o.tintAmt || 0);
    gl.uniform3fv(pts.u.u_tint, col);
    gl.uniform1f(pts.u.u_alpha, o.alpha ?? 1);
    gl.drawArrays(gl.POINTS, 0, o.count ?? set.count);
  }

  function drawQuad(mvp, mode, o = {}) {
    gl.useProgram(quad.p);
    gl.bindBuffer(gl.ARRAY_BUFFER, quadBuf);
    attribs(1);
    gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    gl.uniformMatrix4fv(quad.u.u_mvp, false, mvp);
    gl.uniform1f(quad.u.u_mode, mode);
    gl.uniform1f(quad.u.u_time, t);
    gl.uniform1f(quad.u.u_amp, amp);
    gl.uniform1f(quad.u.u_alpha, o.alpha ?? 1);
    gl.uniform1f(quad.u.u_spin, o.spin || 0);
    gl.uniform1f(quad.u.u_seed, o.seed || 0);
    gl.uniform3fv(quad.u.u_color, o.color || col);
    gl.uniform4fv(quad.u.u_ring, o.ring || [0, 0, 0, 0]);
    gl.uniform1i(quad.u.u_tex, 0);
    gl.uniform1i(quad.u.u_neb, 1);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
  }

  const additive = () => gl.blendFunc(gl.ONE, gl.ONE);
  const alphaBlend = () => gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

  const NEBULAE = [
    { c: [0.50, 0.14, 1.00], p: [-9, 3, -30], s: 30, a: 0.34, seed: 1.3, rot: 0.2 },
    { c: [0.08, 0.50, 1.00], p: [11, -4, -34], s: 34, a: 0.28, seed: 4.1, rot: -0.3 },
    { c: [1.00, 0.14, 0.60], p: [2, 8, -38], s: 32, a: 0.24, seed: 7.7, rot: 0.5 },
    { c: [0.12, 0.80, 0.95], p: [-12, -9, -36], s: 28, a: 0.20, seed: 9.2, rot: 1.1 },
  ];

  function frame(now) {
    if (!running) return;
    requestAnimationFrame(frame);
    if (lost) return;
    const dtRaw = (now - last) / 1000;
    last = now;
    const dt = Math.min(0.05, dtRaw);
    t += dt;

    /* auto-degrade on slow machines: first ~2 s decide whether we need the light version */
    if (++frames > 20 && frames < 140 && quality === "auto" && level === "high") {
      if (dtRaw > 0.034) slowFrames++;
      if (frames === 139 && slowFrames > 70) { level = "low"; build(); resize(); }
    }

    const S = STATES[state], k = Math.min(1, dt * 3.5);
    for (let i = 0; i < 3; i++) col[i] += (S.c[i] - col[i]) * k;
    spin += (S.spin * (reduceMotion ? 0.3 : 1) - spin) * k;
    glow += (S.glow - glow) * k;

    let target = 0.1;
    if (state === "speaking") target = 0.35 + 0.28 * Math.sin(t * 9) * Math.sin(t * 2.7 + 1);
    else if (state === "thinking") target = 0.3 + 0.2 * Math.sin(t * 5);
    else if (state === "listening") target = 0.18 + 0.12 * Math.sin(t * 3);
    if (ampExternal != null) target = ampExternal;
    kick *= Math.pow(0.04, dt);
    amp += (clamp(target + kick * 0.5, 0, 1.2) - amp) * Math.min(1, dt * 10);

    px += (mx - px) * Math.min(1, dt * 3); py += (my - py) * Math.min(1, dt * 3);
    camZ += (camZTarget - camZ) * Math.min(1, dt * 4);
    if (!drag) { galYaw += velYaw; velYaw *= 0.94; }
    galSpin += dt * 0.045 * spin; ringSpin += dt * 0.12 * spin; orbit += dt * 0.9 * spin;

    resize();
    const aspect = W / H;
    const zFit = camZ * (aspect < 1 ? 1 / Math.max(0.62, aspect * 1.25) : 1);
    const proj = m4.persp(0.88, aspect, 0.1, 220);
    const view = chain(m4.trans(0, 0, -zFit), m4.rx(py * 0.09), m4.ry(px * 0.13));

    gl.clearColor(0.006, 0.01, 0.026, 1);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.disable(gl.DEPTH_TEST);
    gl.enable(gl.BLEND);
    additive();

    /* nebulae (far back, slowly turning) */
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, tex);
    const useNeb = (seed) => { gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, nebTex[seed]); gl.activeTexture(gl.TEXTURE0); };
    for (const n of NEBULAE) {
      useNeb(n.seed);
      drawQuad(chain(proj, view, m4.trans(...n.p), m4.rz(n.rot + t * 0.01), m4.scale(n.s)), 4, { color: n.c, alpha: n.a });
    }
    useNeb(2.2);
    drawQuad(chain(proj, view, m4.trans(0, 0.3, -7), m4.scale(15)), 4, { color: col.map((c) => c * 0.55), alpha: 0.28 * glow + 0.06 });

    /* far stars */
    drawPoints(stars, chain(proj, view, m4.ry(t * 0.004), m4.rx(0.2)), { alpha: 0.9 });

    /* the galaxy - tilted disc, rotating; dragging adds your own rotation */
    const galModel = chain(m4.trans(0, -0.2, -1.5), m4.rx(1.12 + galPitch), m4.rz(-0.18), m4.ry(galSpin + galYaw));
    drawPoints(galaxy, chain(proj, view, galModel), { alpha: 0.95, tintAmt: 0.10 + 0.06 * amp });

    /* portrait group sits slightly above centre so the caption has room underneath */
    const group = chain(m4.trans(0, 0.28, 0));
    drawPoints(aura, chain(proj, view, group, m4.ry(-t * 0.35 * spin), m4.rx(0.18)),
      { alpha: 0.85, tintAmt: 0.85, pulse: amp * 0.10 });

    additive();
    drawQuad(chain(proj, view, group, m4.trans(0, 0, -0.1), m4.scale(5.2 + amp * 0.7)), 1, { alpha: 0.42 * glow + 0.45 * amp });

    alphaBlend();
    const tilt = chain(m4.rx(-py * 0.12), m4.ry(px * 0.2));
    drawQuad(chain(proj, view, group, tilt, m4.scale(1.55 * (1 + amp * 0.025))), 0, {});
    additive();

    const A = glow;
    const rings = [
      { s: 1.95, ring: [0.905, 0.92, 0, 0], a: 0.95 * A, rot: [0, 0, 0], spin: 0 },
      { s: 2.28, ring: [0.93, 0.95, 36, 0.58], a: 0.85 * A, rot: [0, 0, 0], spin: -ringSpin * 0.9 },
      { s: 2.75, ring: [0.955, 0.972, 3, 0.26], a: 1.0 * A, rot: [1.15, 0.25, 0.3], spin: ringSpin * 1.7 },
      { s: 3.15, ring: [0.97, 0.982, 90, 0.35], a: 0.7 * A, rot: [-0.95, -0.3, 0.9], spin: -ringSpin * 1.2 },
      { s: 3.7, ring: [0.975, 0.985, 2, 0.4], a: 0.55 * A, rot: [0.45, 0.8, -0.4], spin: ringSpin * 0.8 },
    ];
    for (const r of rings) {
      drawQuad(chain(proj, view, group, m4.rx(r.rot[0]), m4.ry(r.rot[1]), m4.rz(r.rot[2]), m4.scale(r.s)), 2,
        { ring: r.ring, alpha: r.a * (0.85 + 0.3 * amp), spin: r.spin });
    }

    /* three glowing satellites riding the tilted ring */
    const R = 2.75 * 0.9635, d = orbiters.data;
    for (let i = 0; i < 3; i++) {
      const a = orbit + (i * Math.PI * 2) / 3;
      d.set([Math.cos(a) * R, Math.sin(a) * R, 0, 1, 1, 1, 7 + 3 * amp, i / 3], i * 8);
    }
    gl.bindBuffer(gl.ARRAY_BUFFER, orbiters.buf);
    gl.bufferData(gl.ARRAY_BUFFER, d, gl.DYNAMIC_DRAW);
    drawPoints({ buf: orbiters.buf, count: 3 }, chain(proj, view, group, m4.rx(1.15), m4.ry(0.25), m4.rz(0.3)), { tintAmt: 0.65, alpha: 1 });
  }
  requestAnimationFrame(frame);

  return {
    setState(s) { if (STATES[s]) state = s; },
    kick() { kick = 1; },                                 // call on every spoken word for a lip-sync style pulse
    setAmp(v) { ampExternal = v; },
    setQuality(q) { quality = q; level = q === "auto" ? (isSmall ? "low" : "high") : q; build(); resize(); },
    get level() { return level; },
    get photoLoaded() { return photoLoaded; },
    destroy() { running = false; window.removeEventListener("resize", resize); },
  };
}
