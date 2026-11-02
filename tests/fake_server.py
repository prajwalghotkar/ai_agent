"""Run the real app with a FAKE internet, so the whole UI can be tried (and tested) offline.

    python tests/fake_server.py        ->  http://localhost:8765
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from conftest import FakeNet, resp  # noqa: E402
from jarvis import config, http  # noqa: E402

config.GROQ_API_KEY = "fake"

net = FakeNet()
net.on("geocoding-api", resp(data={"results": [{"name": "Pune", "latitude": 18.5, "longitude": 73.8, "admin1": "Maharashtra", "country": "India"}]}))
net.on("v1/forecast", resp(data={
    "current": {"temperature_2m": 27.6, "apparent_temperature": 30, "relative_humidity_2m": 71, "is_day": 1, "precipitation": 0.2, "weather_code": 63, "wind_speed_10m": 11},
    "daily": {"time": ["2026-10-30", "2026-10-31", "2026-11-01"], "weather_code": [63, 2, 0], "temperature_2m_max": [29, 31, 32], "temperature_2m_min": [22, 21, 21],
              "precipitation_probability_max": [80, 20, 5], "sunrise": ["2026-10-30T06:21"], "sunset": ["2026-10-30T18:02"]}}))
net.on("air-quality", resp(data={"current": {"us_aqi": 112, "pm2_5": 40}}))
net.on("news.google.com", resp(content="""<rss><channel>
<item><title>ISRO launches new earth observation satellite - The Hindu</title><link>https://example.com/1</link><pubDate>Fri, 30 Oct 2026 09:00:00 GMT</pubDate><source url="x">The Hindu</source></item>
<item><title>Sensex ends higher as IT stocks rally - Reuters</title><link>https://example.com/2</link><pubDate>Fri, 30 Oct 2026 07:30:00 GMT</pubDate><source url="x">Reuters</source></item>
<item><title>India's AI mission announces new compute grants - Mint</title><link>https://example.com/3</link><pubDate>Thu, 29 Oct 2026 20:00:00 GMT</pubDate><source url="x">Mint</source></item>
</channel></rss>"""))
net.on("arxiv.org/api", resp(content="""<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Scaling Laws for Agentic Language Models</title>
<summary>We study how tool-using agents scale with compute and data and show predictable gains.</summary><published>2026-10-20T10:00:00Z</published>
<author><name>A. Researcher</name></author><author><name>B. Scientist</name></author>
<link href="http://arxiv.org/abs/2610.00001" rel="alternate"/><link title="pdf" href="http://arxiv.org/pdf/2610.00001" rel="related"/></entry></feed>"""))
net.on("semanticscholar", resp(data={"data": [{"title": "Attention Is All You Need", "authors": [{"name": "A. Vaswani"}], "year": 2017, "abstract": "The Transformer architecture.", "citationCount": 120000, "url": "https://example.com/p"}]}))
net.on("w/api.php", resp(data={"query": {"search": [{"title": "Geoffrey Hinton"}, {"title": "Deep learning"}]}}))
net.on("rest_v1/page/summary", resp(data={"type": "standard", "title": "Geoffrey Hinton", "description": "British-Canadian computer scientist",
                                         "extract": "Geoffrey Everest Hinton is a British-Canadian computer scientist and cognitive psychologist known for his work on artificial neural networks. He shared the 2024 Nobel Prize in Physics.",
                                         "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Geoffrey_Hinton"}}}))
net.on("er-api.com", resp(data={"result": "success", "rates": {"INR": 83.5}, "time_last_update_utc": "Fri, 30 Oct 2026 00:00:01 +0000"}))


def tc(i, name, args):
    return {"id": i, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


def groq(url, **kw):
    msgs = kw["json"]["messages"]
    last_user = next(m["content"] for m in reversed(msgs) if m["role"] == "user").lower()
    got_tools = msgs[-1]["role"] == "tool"
    if not got_tools:
        calls = []
        if "weather" in last_user: calls = [tc("w", "get_weather", {"location": "Pune"})]
        elif "news" in last_user: calls = [tc("n", "get_news", {"category": "technology"})]
        elif "paper" in last_user or "research" in last_user: calls = [tc("p", "search_research_papers", {"query": "ai agents", "count": 3})]
        elif "who is" in last_user: calls = [tc("k", "wikipedia_lookup", {"query": "Geoffrey Hinton"})]
        elif "usd" in last_user: calls = [tc("c", "convert_currency", {"amount": 100, "from_currency": "USD", "to_currency": "INR"})]
        elif "youtube" in last_user: calls = [tc("y", "open_website", {"site": "youtube"})]
        if calls:
            return resp(data={"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": calls}}]})
        text = "Sure Prajwal! **Here's a test** with symbols: 50% done & ready @ home #1 — see https://x.com ✨"
    else:
        text = ("**Pune** is 28°C & raining lightly. Carry an umbrella! ☔\n- Humidity is 71%\n- Wind is 11 km/h"
                if "weather" in last_user else "Here is what I found for you, Prajwal. The details are on your screen.")
    return resp(data={"choices": [{"message": {"role": "assistant", "content": text}}]})


net.on("groq.com", groq)
http.get, http.post = net.get, net.post

if __name__ == "__main__":
    import uvicorn
    from app import app
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")
