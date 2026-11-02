/* Rich cards for the LIVE FEED panel. All text goes through textContent (no innerHTML) so
 * nothing from the internet can inject code into the page. */

export function el(tag, attrs = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === "class") n.className = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) {
    if (kid == null || kid === false) continue;
    n.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return n;
}

export const safeUrl = (u) => (/^https?:\/\//i.test(u || "") ? u : "");
const link = (href, text, cls = "") =>
  safeUrl(href) ? el("a", { href: safeUrl(href), target: "_blank", rel: "noopener noreferrer", class: cls }, text) : el("span", { class: cls }, text);

const ICON = [
  [/thunder/, "⛈️"], [/snow/, "❄️"], [/rain|drizzle|shower/, "🌧️"],
  [/fog/, "🌫️"], [/overcast/, "☁️"], [/partly/, "⛅"], [/mainly clear/, "🌤️"],
  [/clear/, "☀️"],
];
const icon = (cond) => (ICON.find(([re]) => re.test(cond || "")) || [0, "🌡️"])[1];
const AQI_CLASS = (v) => (v <= 50 ? "good" : v <= 100 ? "mod" : v <= 150 ? "sens" : "bad");

const head = (title, sub, badge) =>
  el("div", { class: "card-head" }, el("span", { class: "card-title" }, title), sub && el("span", { class: "card-sub" }, sub), badge);

function weather(d) {
  const c = d.current, u = "°" + d.unit;
  return el("article", { class: "card weather" },
    head("WEATHER", d.location),
    el("div", { class: "wx-main" },
      el("div", { class: "wx-icon" }, icon(c.condition)),
      el("div", { class: "wx-temp" }, `${c.temp}${u}`),
      el("div", { class: "wx-meta" }, el("b", {}, c.condition), el("span", {}, `Feels like ${c.feels_like}${u}`))),
    el("div", { class: "wx-stats" },
      el("span", {}, `💧 ${c.humidity_percent ?? "-"}%`),
      el("span", {}, `💨 ${c.wind_kmh} km/h`),
      d.sunrise && el("span", {}, `🌅 ${d.sunrise}`),
      d.sunset && el("span", {}, `🌇 ${d.sunset}`),
      d.air_quality && el("span", { class: "aqi " + AQI_CLASS(d.air_quality.us_aqi) }, `AQI ${d.air_quality.us_aqi} ${d.air_quality.label}`)),
    el("div", { class: "wx-days" }, d.forecast.map((f) =>
      el("div", { class: "wx-day" }, el("small", {}, f.weekday.slice(0, 3)), el("span", {}, icon(f.condition)),
        el("b", {}, `${f.max}°`), el("em", {}, `${f.min}°`),
        f.rain_chance_percent != null && el("i", {}, `${f.rain_chance_percent}%`)))));
}

function news(d) {
  return el("article", { class: "card news" }, head("NEWS", d.topic, el("span", { class: "tag" }, d.country)),
    el("ul", { class: "list" }, d.articles.map((a) =>
      el("li", {}, link(a.url, a.title, "item-title"),
        el("div", { class: "item-meta" }, [a.source, a.age].filter(Boolean).join(" · ")),
        a.summary && el("p", { class: "item-sum" }, a.summary)))));
}

function papers(d) {
  return el("article", { class: "card papers" }, head("RESEARCH", d.query, el("span", { class: "tag" }, d.sorted_by)),
    el("ul", { class: "list" }, d.papers.map((p) =>
      el("li", {}, link(p.url, p.title, "item-title"),
        el("div", { class: "item-meta" }, [p.authors, p.year, p.source, p.citations != null ? `${p.citations.toLocaleString()} citations` : ""].filter(Boolean).join(" · ")),
        p.abstract && el("p", { class: "item-sum" }, p.abstract),
        safeUrl(p.pdf) && link(p.pdf, "PDF ↗", "pill")))));
}

function wikipedia(d) {
  return el("article", { class: "card wiki" }, head("WIKIPEDIA", d.description),
    el("div", { class: "wiki-body" },
      safeUrl(d.thumbnail) && el("img", { src: safeUrl(d.thumbnail), alt: "", loading: "lazy", referrerpolicy: "no-referrer" }),
      el("div", {}, el("h3", {}, d.title), el("p", {}, d.summary), d.url && link(d.url, "Read on Wikipedia ↗", "pill"),
        d.related?.length ? el("div", { class: "item-meta" }, "Related: " + d.related.join(", ")) : null)));
}

const currency = (d) => el("article", { class: "card calc" }, head("CURRENCY", d.updated),
  el("div", { class: "big" }, `${d.amount.toLocaleString()} ${d.from} = ${d.result.toLocaleString()} ${d.to}`),
  el("div", { class: "item-meta" }, `1 ${d.from} = ${d.rate} ${d.to}`));
const time = (d) => el("article", { class: "card calc" }, head("TIME", d.timezone), el("div", { class: "big" }, d.time), el("div", { class: "item-meta" }, d.date));
const calc = (d) => el("article", { class: "card calc" }, head("CALCULATOR"), el("div", { class: "big" }, `${d.expression} = ${d.result}`));

const RENDERERS = { weather, news, papers, wikipedia, currency, time, calc };

export function renderCard(card) {
  try {
    return RENDERERS[card.type]?.(card.data) || null;
  } catch (err) {
    console.warn("card render failed", card.type, err);
    return null;
  }
}

export const errorCard = (title, msg, onRetry) =>
  el("article", { class: "card error" }, head(title), el("p", {}, msg), onRetry && el("button", { class: "pill", onclick: onRetry }, "Retry"));
