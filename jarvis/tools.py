"""Jarvis's abilities. Every tool is a plain function; the LLM chooses which to call.

Free + keyless by default:
  weather ........ Open-Meteo (forecast, geocoding, air quality)
  news ........... Google News RSS (optional upgrade: GNews key)
  research ....... arXiv + Semantic Scholar
  wikipedia ...... Wikipedia REST API
  currency ....... open.er-api.com
"""
from __future__ import annotations

import ast
import inspect
import math
import operator
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote, quote_plus
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests

from . import config, http

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _trim(text: str, n: int) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= n else text[: n - 1].rsplit(" ", 1)[0] + "..."


def _now(tz_name: str | None = None) -> datetime:
    try:
        return datetime.now(ZoneInfo(tz_name or config.TIMEZONE))
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        return datetime.now().astimezone()      # Windows without tzdata -> local clock


def _age(dt: datetime | None) -> str:
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    secs = (datetime.now(timezone.utc) - dt).total_seconds()
    if secs < 0:
        return "just now"
    if secs < 3600:
        m = max(1, int(secs // 60))
        return f"{m} minute{'s' if m != 1 else ''} ago"
    if secs < 86400:
        h = int(secs // 3600)
        return f"{h} hour{'s' if h != 1 else ''} ago"
    d = int(secs // 86400)
    return f"{d} day{'s' if d != 1 else ''} ago"


# ---------------------------------------------------------------------------
# WEATHER  (Open-Meteo - free, no key)
# ---------------------------------------------------------------------------

WMO = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "foggy", 48: "foggy with frost", 51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    56: "freezing drizzle", 57: "heavy freezing drizzle", 61: "light rain", 63: "rain", 65: "heavy rain",
    66: "freezing rain", 67: "heavy freezing rain", 71: "light snow", 73: "snow", 75: "heavy snow",
    77: "snow grains", 80: "light rain showers", 81: "rain showers", 82: "violent rain showers",
    85: "snow showers", 86: "heavy snow showers", 95: "thunderstorm", 96: "thunderstorm with hail",
    99: "severe thunderstorm with hail",
}


def _aqi_label(v: float | None) -> str:
    if v is None:
        return ""
    for limit, label in ((50, "good"), (100, "moderate"), (150, "unhealthy for sensitive groups"),
                         (200, "unhealthy"), (300, "very unhealthy")):
        if v <= limit:
            return label
    return "hazardous"


def _geocode(name: str) -> dict | None:
    parts = [p.strip() for p in name.split(",") if p.strip()]
    if not parts:
        return None
    r = http.get("https://geocoding-api.open-meteo.com/v1/search",
                 params={"name": parts[0], "count": 5, "language": "en", "format": "json"})
    r.raise_for_status()
    results = r.json().get("results") or []
    if not results:
        return None
    hint = " ".join(parts[1:]).lower()
    if hint:
        for res in results:
            blob = f"{res.get('country', '')} {res.get('admin1', '')} {res.get('country_code', '')}".lower()
            if hint in blob or blob.strip() and any(tok in blob for tok in hint.split()):
                return res
    return results[0]


def get_weather(ctx: dict | None = None, location: str = "", days: int = 3, units: str = "celsius") -> dict:
    ctx = ctx or {}
    days = max(1, min(int(days or 3), 7))
    fahrenheit = str(units).lower().startswith("f")

    if location:
        place = _geocode(location)
        if not place:
            return {"error": f"I couldn't find a place called {location}."}
    elif ctx.get("lat") is not None and ctx.get("lon") is not None:
        place = {"name": "your location", "latitude": float(ctx["lat"]), "longitude": float(ctx["lon"])}
    else:
        place = _geocode(config.DEFAULT_CITY)
        if not place:
            return {"error": "I couldn't work out which city to check."}

    lat, lon = place["latitude"], place["longitude"]
    r = http.get("https://api.open-meteo.com/v1/forecast", params={
        "latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": days,
        "temperature_unit": "fahrenheit" if fahrenheit else "celsius",
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset",
    })
    r.raise_for_status()
    data = r.json()
    cur, daily = data.get("current", {}), data.get("daily", {})

    forecast = []
    for i, date in enumerate(daily.get("time", [])):
        try:
            weekday = datetime.strptime(date, "%Y-%m-%d").strftime("%A")
        except ValueError:
            weekday = date
        forecast.append({
            "date": date, "weekday": "Today" if i == 0 else weekday,
            "condition": WMO.get(daily["weather_code"][i], "unknown"),
            "max": round(daily["temperature_2m_max"][i]), "min": round(daily["temperature_2m_min"][i]),
            "rain_chance_percent": (daily.get("precipitation_probability_max") or [None] * (i + 1))[i],
        })

    air = None
    try:
        a = http.get("https://air-quality-api.open-meteo.com/v1/air-quality",
                     params={"latitude": lat, "longitude": lon, "current": "us_aqi,pm2_5"})
        if a.status_code == 200:
            c = a.json().get("current", {})
            if c.get("us_aqi") is not None:
                air = {"us_aqi": round(c["us_aqi"]), "pm2_5": c.get("pm2_5"), "label": _aqi_label(c["us_aqi"])}
    except (requests.RequestException, ValueError):
        pass

    label = ", ".join(x for x in (place.get("name"), place.get("admin1"), place.get("country")) if x)
    sunrise = (daily.get("sunrise") or [""])[0][-5:]
    sunset = (daily.get("sunset") or [""])[0][-5:]
    return {
        "location": label,
        "unit": "F" if fahrenheit else "C",
        "current": {
            "temp": round(cur.get("temperature_2m", 0)),
            "feels_like": round(cur.get("apparent_temperature", 0)),
            "humidity_percent": cur.get("relative_humidity_2m"),
            "wind_kmh": round(cur.get("wind_speed_10m", 0)),
            "rain_mm": cur.get("precipitation"),
            "condition": WMO.get(cur.get("weather_code"), "unknown"),
            "is_day": bool(cur.get("is_day", 1)),
        },
        "sunrise": sunrise, "sunset": sunset,
        "forecast": forecast, "air_quality": air,
    }


# ---------------------------------------------------------------------------
# NEWS  (Google News RSS - free, no key;  GNews if you add a key)
# ---------------------------------------------------------------------------

_EDITIONS = {
    "in": ("en-IN", "IN", "IN:en"), "us": ("en-US", "US", "US:en"), "gb": ("en-GB", "GB", "GB:en"),
    "uk": ("en-GB", "GB", "GB:en"), "au": ("en-AU", "AU", "AU:en"), "ca": ("en-CA", "CA", "CA:en"),
}
_CATEGORIES = {
    "world": "WORLD", "business": "BUSINESS", "technology": "TECHNOLOGY", "tech": "TECHNOLOGY",
    "entertainment": "ENTERTAINMENT", "sports": "SPORTS", "sport": "SPORTS", "science": "SCIENCE",
    "health": "HEALTH", "nation": "NATION", "national": "NATION",
}
_GNEWS_CATEGORY = {"world": "world", "business": "business", "technology": "technology", "tech": "technology",
                   "entertainment": "entertainment", "sports": "sports", "sport": "sports", "science": "science",
                   "health": "health", "nation": "nation", "national": "nation"}


def _news_gnews(topic: str, category: str, country: str, count: int) -> list[dict]:
    base = "https://gnews.io/api/v4"
    params = {"lang": "en", "country": country, "max": count, "apikey": config.GNEWS_API_KEY}
    if topic:
        r = http.get(f"{base}/search", params={**params, "q": topic})
    else:
        r = http.get(f"{base}/top-headlines", params={**params, "category": _GNEWS_CATEGORY.get(category, "general")})
    r.raise_for_status()
    items = []
    for a in r.json().get("articles", [])[:count]:
        try:
            dt = datetime.fromisoformat(a["publishedAt"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            dt = None
        items.append({"title": a.get("title", ""), "source": (a.get("source") or {}).get("name", ""),
                      "age": _age(dt), "url": a.get("url", ""), "summary": _trim(a.get("description", ""), 220)})
    return items


def _news_rss(topic: str, category: str, country: str, count: int, recent: bool = True) -> list[dict]:
    hl, gl, ceid = _EDITIONS.get(country, _EDITIONS["us"])
    tail = f"hl={hl}&gl={gl}&ceid={ceid}"
    if topic:
        q = topic + (" when:7d" if recent else "")
        url = f"https://news.google.com/rss/search?q={quote_plus(q)}&{tail}"
    elif category in _CATEGORIES:
        url = f"https://news.google.com/rss/headlines/section/topic/{_CATEGORIES[category]}?{tail}"
    else:
        url = f"https://news.google.com/rss?{tail}"
    r = http.get(url)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    items = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        src_el = it.find("source")
        source = (src_el.text or "").strip() if src_el is not None else ""
        if source and title.endswith(f" - {source}"):
            title = title[: -len(source) - 3]
        elif not source and " - " in title:
            title, source = title.rsplit(" - ", 1)
        try:
            dt = parsedate_to_datetime(it.findtext("pubDate") or "")
        except (TypeError, ValueError):
            dt = None
        items.append({"title": title, "source": source, "age": _age(dt),
                      "url": (it.findtext("link") or "").strip(), "summary": ""})
        if len(items) >= count:
            break
    return items


def get_news(ctx: dict | None = None, topic: str = "", category: str = "", country: str = "", count: int = 5) -> dict:
    count = max(1, min(int(count or 5), 8))
    country = (country or config.DEFAULT_COUNTRY or "in").lower()
    category = (category or "").lower().strip()
    topic = (topic or "").strip()
    items: list[dict] = []
    if config.GNEWS_API_KEY:
        try:
            items = _news_gnews(topic, category, country, count)
        except (requests.RequestException, ValueError, KeyError):
            items = []
    if not items:
        items = _news_rss(topic, category, country, count)
        if not items and topic:                                  # topic too narrow for last 7 days
            items = _news_rss(topic, category, country, count, recent=False)
    if not items:
        return {"error": "I couldn't find any news on that right now."}
    label = topic or (category.title() if category else "Top headlines")
    return {"topic": label, "country": country.upper(), "articles": items}


# ---------------------------------------------------------------------------
# RESEARCH PAPERS  (arXiv + Semantic Scholar - free)
# ---------------------------------------------------------------------------

_ATOM = "{http://www.w3.org/2005/Atom}"


def _authors(names: list[str]) -> str:
    names = [n for n in names if n]
    return ", ".join(names[:3]) + (" et al." if len(names) > 3 else "")


def _papers_arxiv(query: str, count: int, latest: bool) -> list[dict]:
    words = re.findall(r"[\w\-]+", query)[:8]
    if not words:
        return []
    search = " AND ".join(f"all:{w}" for w in words)
    r = http.get("https://export.arxiv.org/api/query", params={
        "search_query": search, "start": 0, "max_results": count,
        "sortBy": "submittedDate" if latest else "relevance", "sortOrder": "descending"})
    r.raise_for_status()
    root = ET.fromstring(r.content)
    out = []
    for e in root.findall(f"{_ATOM}entry"):
        link = pdf = ""
        for l in e.findall(f"{_ATOM}link"):
            if l.get("title") == "pdf":
                pdf = l.get("href", "")
            elif l.get("rel") == "alternate":
                link = l.get("href", "")
        out.append({
            "title": _trim(e.findtext(f"{_ATOM}title") or "", 200),
            "authors": _authors([a.findtext(f"{_ATOM}name") or "" for a in e.findall(f"{_ATOM}author")]),
            "year": (e.findtext(f"{_ATOM}published") or "")[:4],
            "abstract": _trim(e.findtext(f"{_ATOM}summary") or "", 380),
            "url": link or pdf, "pdf": pdf, "source": "arXiv", "citations": None,
        })
    return out


def _papers_s2(query: str, count: int) -> list[dict]:
    headers = {"x-api-key": config.SEMANTIC_SCHOLAR_API_KEY} if config.SEMANTIC_SCHOLAR_API_KEY else {}
    r = http.get("https://api.semanticscholar.org/graph/v1/paper/search", headers=headers, params={
        "query": query, "limit": count,
        "fields": "title,authors,year,abstract,citationCount,url,openAccessPdf,venue"})
    r.raise_for_status()
    out = []
    for p in r.json().get("data", []) or []:
        out.append({
            "title": _trim(p.get("title") or "", 200),
            "authors": _authors([a.get("name", "") for a in p.get("authors", [])]),
            "year": str(p.get("year") or ""),
            "abstract": _trim(p.get("abstract") or "", 380),
            "url": p.get("url", ""), "pdf": (p.get("openAccessPdf") or {}).get("url", ""),
            "source": "Semantic Scholar" + (f" ({p['venue']})" if p.get("venue") else ""),
            "citations": p.get("citationCount"),
        })
    return out


def search_research_papers(ctx: dict | None = None, query: str = "", count: int = 5, sort: str = "relevance") -> dict:
    query = (query or "").strip()
    if not query:
        return {"error": "Tell me which research topic to search."}
    count = max(1, min(int(count or 5), 8))
    latest = str(sort).lower() in ("latest", "newest", "recent", "date")
    papers: list[dict] = []
    errors = 0
    try:
        papers += _papers_arxiv(query, count, latest)
    except (requests.RequestException, ET.ParseError):
        errors += 1
    if len(papers) < count:
        try:
            papers += _papers_s2(query, count - len(papers) if papers else count)
        except (requests.RequestException, ValueError):
            errors += 1
    seen, unique = set(), []
    for p in papers:                                            # drop duplicates across the two sources
        key = re.sub(r"\W+", "", p["title"].lower())[:60]
        if key and key not in seen:
            seen.add(key)
            unique.append(p)
    if not unique:
        return {"error": "The research databases didn't answer." if errors else "I found no papers on that topic."}
    return {"query": query, "sorted_by": "latest" if latest else "relevance", "papers": unique[:count]}


# ---------------------------------------------------------------------------
# WIKIPEDIA
# ---------------------------------------------------------------------------

def wikipedia_lookup(ctx: dict | None = None, query: str = "", lang: str = "en") -> dict:
    query = (query or "").strip()
    if not query:
        return {"error": "Tell me what to look up."}
    lang = lang if re.fullmatch(r"[a-z]{2,3}", (lang or "en").lower()) else "en"
    lang = lang.lower()
    api = f"https://{lang}.wikipedia.org/w/api.php"
    r = http.get(api, params={"action": "query", "list": "search", "srsearch": query, "srlimit": 5,
                              "format": "json", "utf8": 1})
    r.raise_for_status()
    hits = r.json().get("query", {}).get("search", [])
    if not hits:
        return {"error": f"Wikipedia has nothing on {query}."}
    title = hits[0]["title"]
    s = http.get(f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{quote(title.replace(' ', '_'), safe='')}")
    s.raise_for_status()
    d = s.json()
    related = [h["title"] for h in hits[1:4]]
    if d.get("type") == "disambiguation":
        return {"title": d.get("title", title), "description": "disambiguation page",
                "summary": f"{title} can mean several things. Options: " + ", ".join(related), "url": "", "related": related}
    return {
        "title": d.get("title", title), "description": d.get("description", ""),
        "summary": _trim(d.get("extract", ""), 1100),
        "url": (d.get("content_urls", {}).get("desktop", {}) or {}).get("page", ""),
        "thumbnail": (d.get("thumbnail") or {}).get("source", ""), "related": related,
    }


# ---------------------------------------------------------------------------
# CURRENCY, TIME, MATH
# ---------------------------------------------------------------------------

def convert_currency(ctx: dict | None = None, amount: float = 1, from_currency: str = "USD", to_currency: str = "INR") -> dict:
    src, dst = str(from_currency).upper().strip(), str(to_currency).upper().strip()
    if not (re.fullmatch(r"[A-Z]{3}", src) and re.fullmatch(r"[A-Z]{3}", dst)):
        return {"error": "Use 3-letter currency codes such as USD, INR, EUR."}
    amount = float(amount)
    r = http.get(f"https://open.er-api.com/v6/latest/{src}")
    r.raise_for_status()
    data = r.json()
    rate = (data.get("rates") or {}).get(dst)
    if data.get("result") != "success" or rate is None:
        return {"error": f"I couldn't get a rate for {src} to {dst}."}
    return {"amount": amount, "from": src, "to": dst, "rate": round(rate, 4),
            "result": round(amount * rate, 2), "updated": (data.get("time_last_update_utc") or "")[:16]}


def get_datetime(ctx: dict | None = None, timezone_name: str = "") -> dict:
    now = _now(timezone_name or None)
    return {"timezone": timezone_name or config.TIMEZONE, "date": now.strftime("%A, %d %B %Y"),
            "time": now.strftime("%I:%M %p").lstrip("0"), "iso": now.isoformat(timespec="seconds"),
            "hour24": now.hour}


def _safe_pow(a, b):
    if abs(b) > 1000 or abs(a) > 1e12:
        raise ValueError("number too large")
    return a ** b


_BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: _safe_pow}
_UN = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUNCS = {"sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan, "log": math.log,
          "ln": math.log, "log10": math.log10, "abs": abs, "round": round, "floor": math.floor,
          "ceil": math.ceil, "min": min, "max": max, "pow": _safe_pow,
          "factorial": lambda n: math.factorial(int(n)) if 0 <= n <= 170 else (_ for _ in ()).throw(ValueError("too big"))}
_CONST = {"pi": math.pi, "e": math.e}


def _eval(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN:
        return _BIN[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UN:
        return _UN[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.Name) and node.id in _CONST:
        return _CONST[node.id]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCS and not node.keywords:
        return _FUNCS[node.func.id](*[_eval(a) for a in node.args])
    raise ValueError("unsupported expression")


def calculate(ctx: dict | None = None, expression: str = "") -> dict:
    expr = (expression or "").strip()[:200]
    if not expr:
        return {"error": "No expression given."}
    e = expr.replace("^", "**").replace("×", "*").replace("÷", "/").replace(" x ", " * ")
    e = re.sub(r"(?<=\d),(?=\d{3})", "", e)
    e = re.sub(r"(\d+(?:\.\d+)?)\s*%\s*of\s*", r"(\1/100)*", e)
    try:
        val = _eval(ast.parse(e, mode="eval"))
    except (ValueError, SyntaxError, ZeroDivisionError, TypeError, OverflowError) as exc:
        return {"error": f"I couldn't calculate that ({exc})."}
    if isinstance(val, float):
        val = int(val) if val.is_integer() and abs(val) < 1e15 else round(val, 10)
    return {"expression": expr, "result": val}


# ---------------------------------------------------------------------------
# ACTIONS that happen in the browser / on the device
# ---------------------------------------------------------------------------

_SITES = {
    "youtube": "https://www.youtube.com", "google": "https://www.google.com", "wikipedia": "https://www.wikipedia.org",
    "github": "https://github.com", "gmail": "https://mail.google.com", "linkedin": "https://www.linkedin.com",
    "instagram": "https://www.instagram.com", "twitter": "https://x.com", "x": "https://x.com",
    "whatsapp": "https://web.whatsapp.com", "netflix": "https://www.netflix.com", "spotify": "https://open.spotify.com",
    "maps": "https://www.google.com/maps", "google maps": "https://www.google.com/maps", "claude": "https://claude.ai",
    "stackoverflow": "https://stackoverflow.com", "stack overflow": "https://stackoverflow.com",
    "arxiv": "https://arxiv.org", "reddit": "https://www.reddit.com", "amazon": "https://www.amazon.in",
    "flipkart": "https://www.flipkart.com", "drive": "https://drive.google.com", "google drive": "https://drive.google.com",
    "facebook": "https://www.facebook.com", "hugging face": "https://huggingface.co", "groq": "https://console.groq.com",
}


def open_website(ctx: dict | None = None, site: str = "", query: str = "") -> dict:
    name = (site or "").lower().strip()
    query = (query or "").strip()
    url = ""
    if name in ("youtube",) and query:
        url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
    elif name in ("google",) and query:
        url = f"https://www.google.com/search?q={quote_plus(query)}"
    elif name in _SITES:
        url = _SITES[name]
    elif re.fullmatch(r"(https?://)?[\w.-]+\.[a-z]{2,}(/\S*)?", name):
        url = name if name.startswith("http") else f"https://{name}"
    elif query or name:
        url = f"https://www.google.com/search?q={quote_plus(query or name)}"
    if not url.lower().startswith(("http://", "https://")):
        return {"error": "I can only open normal web addresses."}
    label = name.title() if name in _SITES else (query or name)
    return {"opened": label, "_action": {"type": "open_url", "url": url, "label": label}}


def remember_fact(ctx: dict | None = None, fact: str = "") -> dict:
    fact = _trim(fact, 200)
    if not fact:
        return {"error": "Nothing to remember."}
    return {"saved": fact, "_action": {"type": "remember", "fact": fact}}


def forget_fact(ctx: dict | None = None, keyword: str = "") -> dict:
    keyword = _trim(keyword, 80)
    if not keyword:
        return {"error": "Tell me what to forget."}
    return {"forgot": keyword, "_action": {"type": "forget", "keyword": keyword}}


# ---------------------------------------------------------------------------
# registry exposed to the LLM
# ---------------------------------------------------------------------------

def _spec(name: str, description: str, props: dict, required: list[str] | None = None) -> dict:
    return {"type": "function", "function": {"name": name, "description": description,
            "parameters": {"type": "object", "properties": props, "required": required or []}}}


TOOL_SPECS = [
    _spec("get_weather", "Current weather, multi-day forecast and air quality for any city. Omit location to use the user's own location.",
          {"location": {"type": "string", "description": "City, e.g. 'Mumbai' or 'Paris, France'. Empty = user's location."},
           "days": {"type": "integer", "description": "Forecast days 1-7 (default 3)"},
           "units": {"type": "string", "enum": ["celsius", "fahrenheit"]}}),
    _spec("get_news", "Live news headlines. Use for 'latest news', news on a topic, or a category.",
          {"topic": {"type": "string", "description": "Search topic e.g. 'ISRO', 'stock market'. Empty for top headlines."},
           "category": {"type": "string", "enum": ["world", "business", "technology", "entertainment", "sports", "science", "health", "nation"]},
           "country": {"type": "string", "description": "2-letter edition: in, us, gb, au, ca (default in)"},
           "count": {"type": "integer", "description": "1-8 stories (default 5)"}}),
    _spec("search_research_papers", "Find scientific research papers (arXiv and Semantic Scholar) with authors, year, abstract and links.",
          {"query": {"type": "string", "description": "Research topic, e.g. 'diffusion models'"},
           "count": {"type": "integer", "description": "1-8 papers (default 5)"},
           "sort": {"type": "string", "enum": ["relevance", "latest"]}}, ["query"]),
    _spec("wikipedia_lookup", "Look up a person, place, concept, event or organisation on Wikipedia and get a trusted summary.",
          {"query": {"type": "string", "description": "What to look up"},
           "lang": {"type": "string", "description": "Wikipedia language code, default 'en' ('hi' for Hindi)"}}, ["query"]),
    _spec("convert_currency", "Live currency conversion.",
          {"amount": {"type": "number"}, "from_currency": {"type": "string", "description": "3-letter code e.g. USD"},
           "to_currency": {"type": "string", "description": "3-letter code e.g. INR"}}, ["amount", "from_currency", "to_currency"]),
    _spec("get_datetime", "Current date and time, optionally in another timezone (IANA name like 'America/New_York').",
          {"timezone_name": {"type": "string"}}),
    _spec("calculate", "Accurate maths. Supports + - * / ^ sqrt sin cos tan log factorial pi and 'X% of Y'.",
          {"expression": {"type": "string"}}, ["expression"]),
    _spec("open_website", "Open a website in the user's browser, optionally with a YouTube or Google search.",
          {"site": {"type": "string", "description": "Name like 'youtube' or a domain like 'github.com'"},
           "query": {"type": "string", "description": "Optional search text for youtube or google"}}, ["site"]),
    _spec("remember_fact", "Save a personal fact the user wants remembered (birthday, preference, goal).",
          {"fact": {"type": "string"}}, ["fact"]),
    _spec("forget_fact", "Forget remembered facts that contain a keyword.", {"keyword": {"type": "string"}}, ["keyword"]),
]

REGISTRY = {
    "get_weather": get_weather, "get_news": get_news, "search_research_papers": search_research_papers,
    "wikipedia_lookup": wikipedia_lookup, "convert_currency": convert_currency, "get_datetime": get_datetime,
    "calculate": calculate, "open_website": open_website, "remember_fact": remember_fact, "forget_fact": forget_fact,
}

CARD_TYPES = {"get_weather": "weather", "get_news": "news", "search_research_papers": "papers",
              "wikipedia_lookup": "wikipedia", "convert_currency": "currency", "get_datetime": "time",
              "calculate": "calc"}


def run_tool(name: str, args: dict | None, ctx: dict | None = None) -> dict:
    """Execute a tool safely. Always returns a dict; failures become {'error': '...'}."""
    fn = REGISTRY.get(name)
    if fn is None:
        return {"error": f"Unknown tool {name}."}
    args = args if isinstance(args, dict) else {}
    allowed = set(inspect.signature(fn).parameters) - {"ctx"}
    clean = {k: v for k, v in args.items() if k in allowed}
    try:
        return fn(ctx or {}, **clean)
    except requests.exceptions.Timeout:
        return {"error": "That service took too long to answer."}
    except requests.exceptions.ConnectionError:
        return {"error": "I couldn't reach that service. The internet may be down."}
    except requests.exceptions.HTTPError as exc:
        code = exc.response.status_code if exc.response is not None else "?"
        return {"error": f"That service returned an error ({code})."}
    except (ValueError, TypeError, KeyError, ET.ParseError) as exc:
        return {"error": f"I couldn't read the answer from that service ({type(exc).__name__})."}
