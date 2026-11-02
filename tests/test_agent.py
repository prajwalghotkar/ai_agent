import json
import re

from conftest import resp
from jarvis import config
from jarvis.agent import build_system_prompt, run_agent

FORECAST = {
    "current": {"temperature_2m": 27.6, "apparent_temperature": 30, "relative_humidity_2m": 71, "is_day": 1,
                "precipitation": 0, "weather_code": 2, "wind_speed_10m": 9},
    "daily": {"time": ["2026-10-29"], "weather_code": [2], "temperature_2m_max": [30], "temperature_2m_min": [22],
              "precipitation_probability_max": [10], "sunrise": ["2026-10-29T06:21"], "sunset": ["2026-10-29T18:02"]},
}


def groq_reply(content=None, tool_calls=None):
    msg = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return resp(data={"choices": [{"message": msg}]})


def tc(id_, name, args):
    return {"id": id_, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


def test_full_tool_loop_weather_and_speech_is_symbol_free(net):
    net.on("geocoding-api", resp(data={"results": [{"name": "Pune", "latitude": 1, "longitude": 2, "country": "India"}]}))
    net.on("v1/forecast", resp(data=FORECAST))
    net.on("air-quality", resp(500))
    sent = []

    def groq(url, **kw):
        sent.append(kw["json"])
        if len(sent) == 1:
            return groq_reply(None, [tc("c1", "get_weather", {"location": "Pune"}),
                                     tc("c2", "calculate", {"expression": "2+2"})])
        return groq_reply("**Pune** is 28°C & partly cloudy ✨\n- carry water #1")

    net.on("groq.com", groq)
    out = run_agent("weather in pune and 2+2", [{"role": "user", "content": "hi"}], ["Likes chai"], {})
    assert out["tools"] == ["get_weather", "calculate"] and not out["error"]
    assert [c["type"] for c in out["cards"]] == ["weather", "calc"]
    assert not re.search(r"[*#&°✨]", out["speech"]) and "degrees Celsius" in out["speech"]
    assert "*" not in out["reply"] and "• carry water" in out["reply"]
    # the second LLM call must contain both tool results
    roles = [m["role"] for m in sent[1]["messages"]]
    assert roles.count("tool") == 2 and roles[0] == "system"
    assert "Likes chai" in sent[0]["messages"][0]["content"]


def test_action_tools_return_actions(net):
    state = {"n": 0}

    def groq(url, **kw):
        state["n"] += 1
        if state["n"] == 1:
            return groq_reply(None, [tc("a", "open_website", {"site": "youtube", "query": "lofi"}),
                                     tc("b", "remember_fact", {"fact": "Birthday is 2 March"})])
        return groq_reply("Done.")

    net.on("groq.com", groq)
    out = run_agent("open youtube lofi and remember my birthday", [], [], {})
    assert [a["type"] for a in out["actions"]] == ["open_url", "remember"] and out["cards"] == []


def test_model_fallback_on_rate_limit_and_decommission(net, monkeypatch):
    monkeypatch.setattr(config, "GROQ_MODEL", "m1")
    monkeypatch.setattr(config, "GROQ_FALLBACK_MODELS", ["m2", "m3"])
    models = []

    def groq(url, **kw):
        m = kw["json"]["model"]
        models.append(m)
        if m == "m1":
            return resp(429, data={"error": {"message": "rate", "code": "rate_limit_exceeded"}})
        if m == "m2":
            return resp(400, data={"error": {"message": "gone", "code": "model_decommissioned"}})
        return groq_reply("Hello from m3")

    net.on("groq.com", groq)
    out = run_agent("hi", [], [], {})
    assert out["reply"] == "Hello from m3" and out["model"] == "m3" and models == ["m1", "m2", "m3"]


def test_tool_use_failed_retries_same_model_once(net, monkeypatch):
    monkeypatch.setattr(config, "GROQ_FALLBACK_MODELS", [])
    n = {"c": 0}

    def groq(url, **kw):
        n["c"] += 1
        if n["c"] == 1:
            return resp(400, data={"error": {"message": "bad tool call", "code": "tool_use_failed"}})
        return groq_reply("ok now")

    net.on("groq.com", groq)
    assert run_agent("hi", [], [], {})["reply"] == "ok now" and n["c"] == 2


def test_friendly_errors(net, monkeypatch):
    net.on("groq.com", resp(401, data={"error": {"message": "Invalid API Key"}}))
    out = run_agent("hi", [], [], {})
    assert out["error"] and "Groq API key" in out["reply"] and "Prajwal" in out["reply"]

    net.routes.clear()
    net.on("groq.com", resp(429, data={"error": {"message": "slow down", "code": "rate_limit_exceeded"}}))
    assert "usage limit" in run_agent("hi", [], [], {})["reply"]

    net.routes.clear()                                    # no route -> ConnectionError
    assert "internet" in run_agent("hi", [], [], {})["reply"]

    monkeypatch.setattr(config, "GROQ_API_KEY", "")
    assert "Groq API key" in run_agent("hi", [], [], {})["reply"]


def test_tool_loop_is_capped(net):
    """A model that asks for tools forever must still end with a text answer."""
    def groq(url, **kw):
        if "tools" in kw["json"]:
            return groq_reply(None, [tc("x", "get_datetime", {})])
        return groq_reply("Finished anyway.")

    net.on("groq.com", groq)
    out = run_agent("loop", [], [], {})
    assert out["reply"] == "Finished anyway." and len(out["tools"]) <= 6


def test_prompt_injection_text_is_marked_untrusted_and_prompt_is_personal():
    p = build_system_prompt(["Likes cricket"], {})
    assert "Prajwal" in p and "untrusted" in p and "Likes cricket" in p and "Harry" not in p
