import { createUniverse } from "./universe.js";
import { Voice, stripSymbols } from "./voice.js";
import { el, renderCard, errorCard, safeUrl } from "./cards.js";

const $ = (id) => document.getElementById(id);
const store = {
  get(k, d) { try { const v = localStorage.getItem("jv_" + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem("jv_" + k, JSON.stringify(v)); } catch { /* private mode */ } },
};

const S = {
  user: "Prajwal", mode: "idle", handsFree: false, awaitUntil: 0, busy: false, abort: null,
  history: store.get("history", []), memory: store.get("memory", []),
  loc: store.get("loc", null), pin: store.get("pin", ""), activated: false,
};

/* ================================ universe ================================ */
const canvas = $("universe");
let universe = null;
try { universe = createUniverse(canvas, { photoUrl: "/static/img/prajwal.jpg", quality: store.get("fx", "auto") }); }
catch (err) { console.warn("Universe failed", err); }
if (!universe) { $("fallbackPortrait").hidden = false; document.body.classList.add("no-webgl"); }

/* ================================ voice ================================ */
const voice = new Voice({
  onFinal: (t) => onHeard(t),
  onInterim: (t) => showSubtitle(t, "YOU", false),
  onListening: (on) => { if (on && !S.busy && !voice.speaking) setMode("listening"); else if (!on && S.mode === "listening") setMode("idle"); },
  onSpeakStart: () => setMode("speaking"),
  onSpeakEnd: () => { if (!S.busy) setMode(voice.listening ? "listening" : "idle"); },
  onBoundary: () => universe?.kick(),
  onError: (e) => {
    const msg = {
      "not-allowed": "Microphone is blocked. Click the lock icon in the address bar and allow the microphone.",
      "service-not-allowed": "Microphone is blocked for this page.",
      network: "The browser's speech service can't be reached. Check your internet.",
      unsupported: "This browser can't listen. Use Chrome or Edge, or just type.",
      "audio-capture": "No microphone found.",
    }[e] || `Voice problem: ${e}`;
    setHands(false); say(msg, { speak: false, label: "SYSTEM" });
  },
  onVoices: fillVoices,
});
voice.lang = store.get("lang", "en-IN"); voice.rate = store.get("rate", 1);
voice.voiceName = store.get("voice", ""); voice.muted = store.get("muted", false);

/* ================================ UI helpers ================================ */
const STATUS = { idle: "ONLINE", listening: "LISTENING", thinking: "THINKING", speaking: "SPEAKING" };
function setMode(m) {
  S.mode = m;
  document.body.className = document.body.className.replace(/state-\w+/g, "").trim() + " state-" + m;
  $("statusText").textContent = m === "idle" && S.handsFree ? "SAY 'JARVIS'" : STATUS[m];
  universe?.setState(m);
  $("mic").classList.toggle("on", m === "listening");
}

let typer = null, fadeTimer = null;
function showSubtitle(text, label = "JARVIS", type = true) {
  clearInterval(typer); clearTimeout(fadeTimer);
  const box = $("subtitle"), p = $("subText");
  $("subLabel").textContent = label; box.classList.add("show");
  if (!type || text.length > 420) p.textContent = text;
  else {
    let i = 0; p.textContent = "";
    typer = setInterval(() => { i += 2; p.textContent = text.slice(0, i); if (i >= text.length) clearInterval(typer); }, 16);
  }
  fadeTimer = setTimeout(() => { if (S.mode === "idle") box.classList.remove("show"); }, 30000);
}

function addMsg(role, text, extra = {}) {
  const log = $("log");
  const m = el("div", { class: "msg " + role },
    el("div", { class: "who" }, role === "user" ? S.user.toUpperCase() : role === "system" ? "SYSTEM" : "JARVIS"),
    el("div", { class: "txt" }, text));
  if (extra.tools?.length) m.append(el("div", { class: "tools" }, [...new Set(extra.tools)].map((t) => el("span", {}, "⚡ " + t.replace(/_/g, " ")))));
  for (const a of extra.links || []) m.append(el("a", { class: "pill", href: a.url, target: "_blank", rel: "noopener noreferrer" }, `Open ${a.label} ↗`));
  log.append(m); log.scrollTop = log.scrollHeight;
  while (log.children.length > 80) log.firstChild.remove();
}

function say(text, { speak = true, label = "JARVIS" } = {}) {
  addMsg(label === "SYSTEM" ? "system" : "jarvis", text);
  showSubtitle(text, label);
  return speak ? voice.speak(text) : Promise.resolve();
}

/* ================================ talking to the backend ================================ */
async function api(path, opts = {}) {
  const headers = { "Content-Type": "application/json", ...(S.pin ? { "X-Jarvis-Pin": S.pin } : {}) };
  const res = await fetch(path, { ...opts, headers });
  if (res.status === 401) { const e = new Error("pin"); e.code = "pin"; throw e; }
  return res;
}

async function askPin() {
  const dlg = $("pinDialog");
  return new Promise((resolve) => {
    dlg.addEventListener("close", () => { S.pin = $("pinInput").value.trim(); store.set("pin", S.pin); resolve(!!S.pin); }, { once: true });
    dlg.showModal();
  });
}

const OPEN_INTENT = /\b(open|launch|go to|khol|kholo|play|chalao|search)\b/i;

async function ask(text) {
  text = text.trim();
  if (!text) return;
  if (/^(stop|quiet|shut up|chup|ruko|bas)\b/i.test(text)) { voice.cancelSpeech(); setMode("idle"); return; }
  if (/^(reset|clear) (the )?chat\b/i.test(text)) { clearChat(); return; }

  voice.cancelSpeech();
  S.abort?.abort(); S.abort = new AbortController();
  const signal = S.abort.signal, timer = setTimeout(() => S.abort.abort(), 70000);
  S.busy = true; setMode("thinking");
  addMsg("user", text); showSubtitle("Consulting my live sources...", "JARVIS", false);
  $("input").value = "";

  try {
    let res;
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        res = await api("/api/chat", { method: "POST", signal, body: JSON.stringify({
          message: text, history: S.history.slice(-14), memory: S.memory, location: S.loc }) });
        break;
      } catch (e) {
        if (e.code === "pin" && attempt === 0 && (await askPin())) continue;
        throw e;
      }
    }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || `Server error ${res.status}`);

    S.history.push({ role: "user", content: text }, { role: "assistant", content: data.reply });
    S.history = S.history.slice(-16); store.set("history", S.history);

    for (const card of data.cards || []) pushCard(renderCard(card), true);
    const links = [];
    for (const a of data.actions || []) {
      if (a.type === "open_url" && safeUrl(a.url)) {
        links.push(a);
        if (OPEN_INTENT.test(text)) window.open(a.url, "_blank", "noopener");
      } else if (a.type === "remember" && !S.memory.includes(a.fact)) { S.memory.push(a.fact); store.set("memory", S.memory); }
      else if (a.type === "forget") { S.memory = S.memory.filter((m) => !m.toLowerCase().includes(a.keyword.toLowerCase())); store.set("memory", S.memory); }
    }
    S.busy = false;
    addMsg("jarvis", data.reply, { tools: data.tools, links });
    showSubtitle(data.reply);
    await voice.speak(data.speech || stripSymbols(data.reply));
  } catch (err) {
    S.busy = false;
    if (err.name === "AbortError") { /* superseded by a newer question */ }
    else say(err.code === "pin" ? "That PIN didn't work. Open settings to set it again." : `I couldn't reach my server, ${S.user}. ${err.message || ""}`.trim(), { speak: false, label: "SYSTEM" });
  } finally {
    clearTimeout(timer); S.busy = false;
    if (!voice.speaking) setMode(voice.listening ? "listening" : "idle");
  }
}

/* ================================ hearing: push-to-talk + hands-free ================================ */
const WAKE = /\b(jarvis|jarvish|jarves|jarwis|garvis)\b[\s,.!?:-]*/i;
function onHeard(text) {
  if (!text) return;
  if (!S.handsFree) { voice.stop(); ask(text); return; }
  const m = text.match(WAKE);
  if (!m && Date.now() > S.awaitUntil) return;                      // not addressed to Jarvis: ignore
  const cmd = m ? text.slice(m.index + m[0].length).trim() : text;
  if (!cmd) { S.awaitUntil = Date.now() + 8000; say(`Yes, ${S.user}?`); return; }
  S.awaitUntil = 0; ask(cmd);
}

function setHands(on) {
  S.handsFree = on; $("btnHands").setAttribute("aria-pressed", on); $("btnHands").classList.toggle("active", on);
  if (on) { if (!voice.start(true)) S.handsFree = false; } else voice.stop();
  setMode(S.mode === "listening" && !on ? "idle" : S.mode);
}

$("mic").addEventListener("click", () => {
  if (voice.speaking) { voice.cancelSpeech(); return; }
  if (voice.listening) { voice.stop(); return; }
  if (!voice.sttSupported) { voice.h.onError("unsupported"); return; }
  voice.start(S.handsFree);
});
$("btnHands").addEventListener("click", () => setHands(!S.handsFree));

$("composer").addEventListener("submit", (e) => { e.preventDefault(); ask($("input").value); });
addEventListener("keydown", (e) => {
  if (e.key === "/" && document.activeElement.tagName !== "INPUT") { e.preventDefault(); $("input").focus(); }
  if (e.key === "Escape") voice.cancelSpeech();
});

const CHIPS = ["Weather today", "Top news today", "Latest AI research papers", "Who is Geoffrey Hinton?",
  "Convert 100 USD to INR", "Open YouTube", "What time is it?"];
CHIPS.forEach((c) => $("chips").append(el("button", { type: "button", class: "chip", onclick: () => ask(c) }, c)));

/* ================================ live feed ================================ */
const cardsBox = $("cards");
function pushCard(node, fromChat = false) {
  if (!node) return;
  if (fromChat) node.classList.add("fresh");
  cardsBox.prepend(node);
  while (cardsBox.children.length > 7) cardsBox.lastChild.remove();
  cardsBox.scrollTop = 0;
}

let feedWx = null, feedNews = null;
async function loadFeed() {
  const q = S.loc ? `?lat=${S.loc.lat}&lon=${S.loc.lon}` : "";
  const [w, n] = await Promise.allSettled([api("/api/weather" + q), api("/api/news")]);
  const take = async (r, type, title, retry) => {
    try {
      if (r.status !== "fulfilled") throw r.reason;
      const data = await r.value.json();
      if (!r.value.ok) throw new Error(data.error || "unavailable");
      return renderCard({ type, data });
    } catch (e) {
      if (e.code === "pin") return null;
      return errorCard(title, "Couldn't load right now.", retry);
    }
  };
  feedWx?.remove(); feedNews?.remove();
  feedNews = await take(n, "news", "NEWS", loadFeed);
  feedWx = await take(w, "weather", "WEATHER", loadFeed);
  [feedNews, feedWx].forEach((c) => c && (c.classList.add("pinned"), cardsBox.append(c)));
}
$("btnRefresh").addEventListener("click", loadFeed);
$("btnLocate").addEventListener("click", () => {
  if (!navigator.geolocation) return say("This browser can't share a location.", { speak: false, label: "SYSTEM" });
  navigator.geolocation.getCurrentPosition(
    (p) => { S.loc = { lat: +p.coords.latitude.toFixed(3), lon: +p.coords.longitude.toFixed(3) }; store.set("loc", S.loc); loadFeed(); say(`Location locked, ${S.user}. Weather is now for where you are.`); },
    () => say("Location permission was denied.", { speak: false, label: "SYSTEM" }), { timeout: 10000 });
});

/* ================================ chat / settings ================================ */
function clearChat() { S.history = []; store.set("history", []); $("log").replaceChildren(); showSubtitle("Conversation cleared.", "SYSTEM", false); }
$("btnClear").addEventListener("click", clearChat);

$("btnMute").addEventListener("click", () => {
  voice.muted = !voice.muted; store.set("muted", voice.muted);
  $("btnMute").setAttribute("aria-pressed", voice.muted); $("btnMute").classList.toggle("muted", voice.muted);
  if (voice.muted) voice.cancelSpeech();
});
$("btnMute").classList.toggle("muted", voice.muted);
$("btnFeed").addEventListener("click", () => { $("feed").classList.toggle("open"); $("chatPanel").classList.remove("open"); });
$("btnChat").addEventListener("click", () => { $("chatPanel").classList.toggle("open"); $("feed").classList.remove("open"); });

function fillVoices(list) {
  const sel = $("setVoice"), keep = store.get("voice", "");   // can run inside Voice's constructor, so don't touch `voice` here
  sel.replaceChildren(el("option", { value: "" }, "Auto (best male voice)"));
  list.filter((v) => /^(en|hi)/i.test(v.lang)).forEach((v) => sel.append(el("option", { value: v.name }, `${v.name} (${v.lang})`)));
  sel.value = keep;
}
function renderMemory() {
  $("memList").replaceChildren(...(S.memory.length ? S.memory.map((m) => el("li", {}, m)) : [el("li", { class: "empty" }, "Nothing yet. Say: Jarvis, remember that my birthday is 2 March.")]));
}
$("btnSettings").addEventListener("click", () => {
  $("setLang").value = voice.lang; $("setVoice").value = voice.voiceName; $("setRate").value = voice.rate;
  $("setFx").value = store.get("fx", "auto"); $("setPin").value = S.pin; renderMemory(); $("settings").showModal();
});
$("setLang").addEventListener("change", (e) => { voice.lang = e.target.value; store.set("lang", voice.lang); });
$("setVoice").addEventListener("change", (e) => { voice.voiceName = e.target.value; store.set("voice", voice.voiceName); voice.speak(`This is my voice, ${S.user}.`); });
$("setRate").addEventListener("input", (e) => { voice.rate = +e.target.value; store.set("rate", voice.rate); });
$("setFx").addEventListener("change", (e) => { store.set("fx", e.target.value); universe?.setQuality(e.target.value); });
$("setPin").addEventListener("change", (e) => { S.pin = e.target.value.trim(); store.set("pin", S.pin); });
$("memClear").addEventListener("click", () => { S.memory = []; store.set("memory", []); renderMemory(); });

/* clock */
const tick = () => { $("clock").textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); };
tick(); setInterval(tick, 15000);

/* ================================ boot sequence ================================ */
async function boot() {
  const log = $("bootlog"), btn = $("activate");
  const line = (t) => new Promise((r) => { log.textContent += t + "\n"; setTimeout(r, 170); });
  await line("> waking neural core ...");
  await line(universe ? `> holographic universe ......... ONLINE (${universe.level})` : "> holographic universe ......... LITE MODE");
  let health = null;
  try { health = await (await fetch("/api/health")).json(); S.user = health.user || S.user; } catch { /* offline */ }
  if (!health) { await line("> server ...................... OFFLINE"); btn.textContent = "SERVER NOT REACHABLE"; return; }
  await line("> server ...................... ONLINE");
  await line(health.llm_ready ? "> language core (Groq) ........ READY" : "> language core (Groq) ........ KEY MISSING");
  await line(voice.sttSupported ? "> voice input ................ READY" : "> voice input ................ TYPE ONLY (use Chrome/Edge)");
  await line("> live tools: weather, news, research, wikipedia");
  if (health.pin_required && !S.pin) await askPin();
  btn.disabled = false; btn.textContent = `ACTIVATE ${S.user.toUpperCase()}'S JARVIS`;
  btn.focus();
}

$("activate").addEventListener("click", async () => {
  S.activated = true;
  $("boot").classList.add("gone");
  setTimeout(() => $("boot").remove(), 900);
  loadFeed(); setInterval(loadFeed, 10 * 60 * 1000);
  const h = new Date().getHours();
  const tod = h < 12 ? "morning" : h < 17 ? "afternoon" : "evening";
  const greet = `Good ${tod}, ${S.user}. All systems are online. Ask me about the weather, the news, research papers, or anything on Wikipedia.`;
  S.history.length || addMsg("system", "Tip: tap the mic and speak, or turn on Hands-free and say 'Jarvis' followed by your question.");
  await say(greet);
});

boot();
window.__jarvis = { S, ask, universe, voice };   // handy for debugging in the browser console
