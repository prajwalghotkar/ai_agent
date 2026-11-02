/* Voice I/O using the browser's built-in speech engines (free, no API key).
 * Speech-to-text: Web Speech API (Chrome / Edge). Text-to-speech: speechSynthesis.
 * Everything Jarvis says passes through a symbol cleaner so he never reads * # & aloud.
 */

const SR = window.SpeechRecognition || window.webkitSpeechRecognition;

/** Safety net: the server already sends clean `speech`, this guards any other text. */
export function stripSymbols(text) {
  return (text || "")
    .replace(/https?:\/\/\S+/g, " ")
    .replace(/[\u{1F000}-\u{1FAFF}\u{2190}-\u{21FF}\u{2600}-\u{27BF}\u{2B00}-\u{2BFF}\u{FE0F}]/gu, " ")
    .replace(/&/g, " and ").replace(/%/g, " percent ").replace(/@/g, " at ")
    .replace(/[*#_~`|<>\[\]{}\\^=]/g, " ")
    .replace(/\s+/g, " ").trim();
}

export function splitForTts(text, max = 170) {
  const sentences = text.trim().split(/(?<=[.!?।])\s+/);
  const out = [];
  let cur = "";
  for (let s of sentences) {
    if ((cur + " " + s).trim().length <= max) { cur = (cur + " " + s).trim(); continue; }
    if (cur) out.push(cur);
    while (s.length > max) {
      let cut = s.lastIndexOf(" ", max);
      if (cut < 1) cut = max;
      out.push(s.slice(0, cut).trim());
      s = s.slice(cut).trim();
    }
    cur = s;
  }
  if (cur) out.push(cur);
  return out.filter(Boolean);
}

export class Voice {
  constructor(h = {}) {
    this.h = h;
    this.rec = null; this.want = false; this.continuous = false; this.listening = false;
    this.lang = "en-IN"; this.voiceName = ""; this.rate = 1; this.muted = false;
    this.speaking = false; this._token = 0; this._resolve = null; this.voices = [];
    if ("speechSynthesis" in window) {
      this._loadVoices();
      speechSynthesis.onvoiceschanged = () => this._loadVoices();
    }
  }

  get sttSupported() { return !!SR; }
  get ttsSupported() { return "speechSynthesis" in window; }

  _loadVoices() { this.voices = speechSynthesis.getVoices(); this.h.onVoices?.(this.voices); }

  /* ------------------------------ listening ------------------------------ */
  start(continuous = false) {
    if (!SR) { this.h.onError?.("unsupported"); return false; }
    this.continuous = continuous; this.want = true;
    this._begin();
    return true;
  }

  _begin() {
    if (this.rec || this.speaking) return;
    const rec = new SR();
    rec.lang = this.lang; rec.interimResults = true; rec.continuous = this.continuous; rec.maxAlternatives = 1;
    rec.onstart = () => { this.listening = true; this.h.onListening?.(true); };
    rec.onresult = (e) => {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i], txt = r[0].transcript;
        if (r.isFinal) this.h.onFinal?.(txt.trim()); else interim += txt;
      }
      if (interim) this.h.onInterim?.(interim.trim());
    };
    rec.onerror = (e) => {
      if (e.error === "no-speech" || e.error === "aborted") return;
      if (e.error === "not-allowed" || e.error === "service-not-allowed") this.want = false;
      this.h.onError?.(e.error);
    };
    rec.onend = () => {
      this.rec = null; this.listening = false; this.h.onListening?.(false);
      if (this.continuous && this.want && !this.speaking) setTimeout(() => this.want && this._begin(), 300);
      else if (!this.continuous) this.want = false;
    };
    this.rec = rec;
    try { rec.start(); } catch { this.rec = null; }
  }

  stop() {
    this.want = false;
    if (this.rec) { try { this.rec.abort(); } catch { /* already stopped */ } }
  }

  /* ------------------------------ speaking ------------------------------ */
  _pick(text) {
    const hindi = /[ऀ-ॿ]/.test(text);
    if (this.voiceName && !hindi) {
      const chosen = this.voices.find((v) => v.name === this.voiceName);
      if (chosen) return chosen;
    }
    const pool = this.voices.filter((v) => v.lang.toLowerCase().startsWith(hindi ? "hi" : "en"));
    const prefer = hindi
      ? ["hemant", "google हिन्दी", "google hindi", "madhur"]
      : ["ravi", "prabhat", "google uk english male", "microsoft guy", "microsoft david", "microsoft mark", "daniel", "alex", "rishi", "google us english"];
    for (const p of prefer) {
      const v = pool.find((x) => x.name.toLowerCase().includes(p));
      if (v) return v;
    }
    return pool.find((v) => /^(en|hi)-in$/i.test(v.lang)) || pool[0] || null;
  }

  speak(text) {
    this.cancelSpeech();
    return new Promise((resolve) => {
      const clean = stripSymbols(text);
      if (this.muted || !clean || !this.ttsSupported) { resolve(); return; }
      const token = ++this._token;
      this._resolve = resolve;
      const chunks = splitForTts(clean);
      const voice = this._pick(clean);
      const hindi = /[ऀ-ॿ]/.test(clean);
      this.speaking = true;
      if (this.rec) { try { this.rec.abort(); } catch { /* ignore */ } }   // don't listen to ourselves
      this.h.onSpeakStart?.();
      let i = 0;
      const finish = () => {
        if (token !== this._token) return;
        this.speaking = false; this._resolve = null;
        this.h.onSpeakEnd?.();
        if (this.continuous && this.want) this._begin();
        resolve();
      };
      const next = () => {
        if (token !== this._token) return;
        if (i >= chunks.length) { finish(); return; }
        const u = new SpeechSynthesisUtterance(chunks[i++]);
        if (voice) u.voice = voice;
        u.lang = voice ? voice.lang : hindi ? "hi-IN" : "en-IN";
        u.rate = this.rate; u.pitch = 0.95;
        u.onboundary = () => this.h.onBoundary?.();
        // Watchdog: some engines never fire "end" (no voice installed, Linux, locked tab).
        // Without it Jarvis would look like he is speaking forever.
        let moved = false;
        const advance = () => { if (moved) return; moved = true; clearTimeout(guard); next(); };
        const guard = setTimeout(() => { try { speechSynthesis.cancel(); } catch { /* ignore */ } advance(); }, 4000 + chunks[i - 1].length * 110);
        u.onend = advance; u.onerror = advance;
        speechSynthesis.speak(u);
      };
      next();
    });
  }

  cancelSpeech() {
    this._token++;
    if (this.ttsSupported) { try { speechSynthesis.cancel(); } catch { /* ignore */ } }
    if (this.speaking) { this.speaking = false; this.h.onSpeakEnd?.(); }
    if (this._resolve) { this._resolve(); this._resolve = null; }
  }
}
