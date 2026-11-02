import requests

from conftest import resp
from jarvis import config, tools

GEO = {"results": [{"name": "Pune", "latitude": 18.5, "longitude": 73.8, "admin1": "Maharashtra",
                    "country": "India", "country_code": "IN"}]}
FORECAST = {
    "current": {"temperature_2m": 27.6, "apparent_temperature": 30.1, "relative_humidity_2m": 71, "is_day": 1,
                "precipitation": 0.2, "weather_code": 63, "wind_speed_10m": 11.4},
    "daily": {"time": ["2026-10-29", "2026-10-30"], "weather_code": [63, 2],
              "temperature_2m_max": [29.4, 31.0], "temperature_2m_min": [22.1, 21.9],
              "precipitation_probability_max": [80, 20],
              "sunrise": ["2026-10-29T06:21"], "sunset": ["2026-10-29T18:02"]},
}


def test_weather(net):
    net.on("geocoding-api", resp(data=GEO))
    net.on("api.open-meteo.com/v1/forecast", resp(data=FORECAST))
    net.on("air-quality", resp(data={"current": {"us_aqi": 112, "pm2_5": 40}}))
    d = tools.run_tool("get_weather", {"location": "Pune", "days": 2}, {})
    assert d["location"] == "Pune, Maharashtra, India"
    assert d["current"]["temp"] == 28 and d["current"]["condition"] == "rain"
    assert d["forecast"][0]["weekday"] == "Today" and d["forecast"][1]["max"] == 31
    assert d["air_quality"]["label"] == "unhealthy for sensitive groups"
    assert d["sunrise"] == "06:21"


def test_weather_uses_device_location_and_survives_aqi_failure(net):
    net.on("api.open-meteo.com/v1/forecast", lambda url, **kw: resp(data=FORECAST))
    net.on("air-quality", resp(500))
    d = tools.run_tool("get_weather", {}, {"lat": 18.5, "lon": 73.8})
    assert d["location"] == "your location" and d["air_quality"] is None
    forecast_call = [c for c in net.calls if "v1/forecast" in c[1]][0]
    assert forecast_call[2]["params"]["latitude"] == 18.5


def test_weather_unknown_city(net):
    net.on("geocoding-api", resp(data={}))
    assert "couldn't find" in tools.run_tool("get_weather", {"location": "Zzzzland"}, {})["error"]


def test_weather_network_down_gives_friendly_error(net):
    d = tools.run_tool("get_weather", {"location": "Pune"}, {})   # no route -> ConnectionError
    assert "error" in d and "internet" in d["error"]


RSS = """<?xml version="1.0"?><rss><channel>
<item><title>ISRO launches new satellite - The Hindu</title><link>https://n.example/1</link>
<pubDate>Thu, 29 Oct 2026 10:00:00 GMT</pubDate><source url="https://thehindu.com">The Hindu</source></item>
<item><title>Markets close higher - Reuters</title><link>https://n.example/2</link>
<pubDate>Thu, 29 Oct 2026 08:00:00 GMT</pubDate><source url="https://reuters.com">Reuters</source></item>
</channel></rss>"""


def test_news_rss(net):
    net.on("news.google.com", resp(content=RSS))
    d = tools.run_tool("get_news", {"topic": "ISRO", "count": 5}, {})
    assert [a["source"] for a in d["articles"]] == ["The Hindu", "Reuters"]
    assert d["articles"][0]["title"] == "ISRO launches new satellite"
    url = net.calls[0][1]
    assert "search?q=ISRO+when%3A7d" in url and "gl=IN" in url


def test_news_category_and_gnews_preferred(net, monkeypatch):
    monkeypatch.setattr(config, "GNEWS_API_KEY", "k")
    net.on("gnews.io", resp(data={"articles": [{"title": "T", "source": {"name": "S"},
                                                 "publishedAt": "2026-10-29T10:00:00Z", "url": "u",
                                                 "description": "d"}]}))
    d = tools.run_tool("get_news", {"category": "technology"}, {})
    assert d["articles"][0]["source"] == "S" and "category" in net.calls[0][2]["params"]


def test_news_gnews_failure_falls_back_to_rss(net, monkeypatch):
    monkeypatch.setattr(config, "GNEWS_API_KEY", "k")
    net.on("gnews.io", resp(429))
    net.on("news.google.com", resp(content=RSS))
    assert len(tools.run_tool("get_news", {}, {})["articles"]) == 2


ARXIV = """<feed xmlns="http://www.w3.org/2005/Atom"><entry>
<title>Attention Is All
 You Need</title><summary>We propose the Transformer.   It is great.</summary>
<published>2017-06-12T17:57:34Z</published>
<author><name>A. Vaswani</name></author><author><name>N. Shazeer</name></author>
<author><name>N. Parmar</name></author><author><name>J. Uszkoreit</name></author>
<link href="http://arxiv.org/abs/1706.03762" rel="alternate"/>
<link title="pdf" href="http://arxiv.org/pdf/1706.03762" rel="related"/></entry></feed>"""


def test_papers_arxiv_plus_semantic_scholar_dedup(net):
    net.on("arxiv.org/api", resp(content=ARXIV))
    net.on("semanticscholar", resp(data={"data": [
        {"title": "Attention is all you need", "authors": [{"name": "Vaswani"}], "year": 2017,
         "abstract": "dup", "citationCount": 100000, "url": "s2"},
        {"title": "BERT", "authors": [{"name": "Devlin"}], "year": 2018, "abstract": "bidirectional",
         "citationCount": 90000, "url": "s2b", "openAccessPdf": {"url": "pdf"}, "venue": "NAACL"}]}))
    d = tools.run_tool("search_research_papers", {"query": "transformer attention", "count": 3}, {})
    titles = [p["title"] for p in d["papers"]]
    assert titles == ["Attention Is All You Need", "BERT"]          # duplicate removed
    p0 = d["papers"][0]
    assert p0["authors"] == "A. Vaswani, N. Shazeer, N. Parmar et al." and p0["year"] == "2017"
    assert p0["pdf"].endswith("1706.03762") and "Transformer" in p0["abstract"]
    assert "all:transformer AND all:attention" == net.calls[0][2]["params"]["search_query"]


def test_papers_arxiv_down_uses_semantic_scholar(net):
    net.on("arxiv.org/api", resp(503))
    net.on("semanticscholar", resp(data={"data": [{"title": "X", "authors": [], "year": 2020, "url": "u"}]}))
    assert tools.run_tool("search_research_papers", {"query": "x"}, {})["papers"][0]["source"] == "Semantic Scholar"


def test_papers_all_down(net):
    net.on("arxiv.org/api", resp(503))
    net.on("semanticscholar", resp(429))
    assert "didn't answer" in tools.run_tool("search_research_papers", {"query": "x"}, {})["error"]


def test_wikipedia(net):
    net.on("w/api.php", resp(data={"query": {"search": [{"title": "Alan Turing"}, {"title": "Turing test"}]}}))
    net.on("rest_v1/page/summary", resp(data={
        "type": "standard", "title": "Alan Turing", "description": "English computer scientist",
        "extract": "Alan Mathison Turing was an English mathematician.",
        "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Alan_Turing"}},
        "thumbnail": {"source": "https://img/x.jpg"}}))
    d = tools.run_tool("wikipedia_lookup", {"query": "alan turing"}, {})
    assert d["title"] == "Alan Turing" and d["related"] == ["Turing test"] and d["url"].endswith("Alan_Turing")
    assert "Alan_Turing" in net.calls[1][1]


def test_wikipedia_disambiguation_and_missing(net):
    net.on("w/api.php", resp(data={"query": {"search": [{"title": "Mercury"}, {"title": "Mercury (planet)"}]}}))
    net.on("rest_v1/page/summary", resp(data={"type": "disambiguation", "title": "Mercury"}))
    assert "several things" in tools.run_tool("wikipedia_lookup", {"query": "mercury"}, {})["summary"]
    net.routes.clear()
    net.on("w/api.php", resp(data={"query": {"search": []}}))
    assert "nothing on" in tools.run_tool("wikipedia_lookup", {"query": "qqqqq"}, {})["error"]


def test_wikipedia_lang_is_validated(net):
    net.on("w/api.php", resp(data={"query": {"search": []}}))
    tools.run_tool("wikipedia_lookup", {"query": "x", "lang": "evil.com/"}, {})
    assert net.calls[0][1].startswith("https://en.wikipedia.org/")


def test_currency(net):
    net.on("er-api.com", resp(data={"result": "success", "rates": {"INR": 83.5},
                                    "time_last_update_utc": "Thu, 29 Oct 2026 00:00:01 +0000"}))
    d = tools.run_tool("convert_currency", {"amount": 10, "from_currency": "usd", "to_currency": "inr"}, {})
    assert d["result"] == 835.0 and d["to"] == "INR"
    assert "3-letter" in tools.run_tool("convert_currency", {"amount": 1, "from_currency": "x/../y", "to_currency": "INR"}, {})["error"]


def test_calculator():
    c = lambda e: tools.calculate({}, e)  # noqa: E731
    assert c("2+2*3")["result"] == 8
    assert c("20% of 500")["result"] == 100
    assert c("sqrt(144) + 2^3")["result"] == 20
    assert c("1,250 * 4")["result"] == 5000
    assert c("10/4")["result"] == 2.5
    for bad in ("__import__('os').system('x')", "9**9**9", "open('f')", "1/0", "2 +"):
        assert "error" in c(bad), bad


def test_datetime_and_bad_timezone():
    d = tools.get_datetime({})
    assert "date" in d and "time" in d
    assert "date" in tools.get_datetime({}, "Not/AZone")        # falls back, never crashes


def test_open_website():
    d = tools.open_website({}, "youtube", "lofi music")
    assert d["_action"]["url"] == "https://www.youtube.com/results?search_query=lofi+music"
    assert tools.open_website({}, "github.com")["_action"]["url"] == "https://github.com"
    assert tools.open_website({}, "javascript:alert(1)")["_action"]["url"].startswith("https://www.google.com/search")


def test_run_tool_ignores_unknown_args_and_unknown_tools():
    assert tools.run_tool("calculate", {"expression": "1+1", "junk": 1}, {})["result"] == 2
    assert "Unknown tool" in tools.run_tool("rm_rf", {}, {})["error"]
    assert "error" in tools.run_tool("calculate", None, {})


def test_timeout_message(net):
    def boom(url, **kw):
        raise requests.exceptions.Timeout()
    net.on("geocoding", boom)
    assert "too long" in tools.run_tool("get_weather", {"location": "x"}, {})["error"]
