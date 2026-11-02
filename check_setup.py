"""Run this first:  python check_setup.py
Tests your Groq key and every free data source, and tells you exactly what is working."""
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from jarvis import config, http, tools  # noqa: E402


def line(ok: bool, name: str, detail: str = ""):
    print(f"  [{'OK' if ok else 'FAIL'}] {name:<22} {detail}")
    return ok

NOT_CHAT = ("whisper", "orpheus", "guard", "tts", "safeguard", "embed")


def check_groq() -> bool:
    """Tests the main model, then the fallbacks. If none work, lists the models YOUR key can use."""
    if not config.GROQ_API_KEY:
        return line(False, "Groq API key", "missing -> copy .env.example to .env and paste your key")
    headers = {"Authorization": f"Bearer {config.GROQ_API_KEY}"}
    last = ""
    for i, model in enumerate(config.groq_models()):
        try:
            r = http.post(f"{config.GROQ_BASE_URL}/chat/completions", headers=headers, timeout=(6, 30),
                          json={"model": model, "max_tokens": 8, "messages": [{"role": "user", "content": "Say OK"}]})
        except Exception as exc:  # noqa: BLE001 - diagnostic script
            return line(False, "Groq LLM", f"cannot connect ({type(exc).__name__})")
        if r.status_code == 200:
            if i == 0:
                return line(True, "Groq LLM", f"model {model}")
            ok = line(True, "Groq LLM", f"works with {model} (fallback)")
            print(f"         NOTE: your main model {config.GROQ_MODEL} is not available to you.")
            print(f"         Add this line to your .env file to make {model} the main model:  GROQ_MODEL={model}")
            return ok
        if r.status_code in (401, 403):
            return line(False, "Groq LLM", "key rejected - create a new one at console.groq.com/keys")
        if r.status_code == 429:
            return line(True, "Groq LLM", f"key works, but {model} is rate limited right now (wait a minute)")
        last = f"HTTP {r.status_code}"

    line(False, "Groq LLM", f"your key is valid, but none of {config.groq_models()} is available ({last})")
    try:
        data = http.get(f"{config.GROQ_BASE_URL}/models", headers=headers, timeout=(6, 20)).json().get("data", [])
        ids = sorted(m["id"] for m in data if not any(k in m["id"].lower() for k in NOT_CHAT))
    except Exception:  # noqa: BLE001
        ids = []
    if ids:
        print("         Models your key can use:")
        for m in ids:
            print(f"           {m}")
        print("         Pick one and put it in .env like:  GROQ_MODEL=<model name>")
    return False


def main() -> int:
    print(f"\nChecking {config.USER_NAME}'s {config.ASSISTANT_NAME} setup...\n")
    results = []

    results.append(check_groq())

    # --- free tools ---------------------------------------------------------------
    probes = [
        ("Weather (Open-Meteo)", "get_weather", {"location": config.DEFAULT_CITY, "days": 1},
         lambda d: f"{d['location']}: {d['current']['temp']} degrees, {d['current']['condition']}"),
        ("News (Google News)", "get_news", {"count": 1},
         lambda d: d["articles"][0]["title"][:70]),
        ("Research (arXiv)", "search_research_papers", {"query": "transformers", "count": 1},
         lambda d: d["papers"][0]["title"][:70]),
        ("Wikipedia", "wikipedia_lookup", {"query": "Alan Turing"},
         lambda d: d["title"] + " - " + d["description"]),
        ("Currency", "convert_currency", {"amount": 1, "from_currency": "USD", "to_currency": "INR"},
         lambda d: f"1 USD = {d['rate']} INR"),
    ]
    for label, name, args, show in probes:
        out = tools.run_tool(name, args, {})
        if "error" in out:
            results.append(line(False, label, out["error"]))
        else:
            results.append(line(True, label, show(out)))

    print(f"\n  GNews key (optional): {'set' if config.GNEWS_API_KEY else 'not set - using free Google News RSS'}")
    print(f"  Access PIN:           {'set' if config.APP_PIN else 'not set (fine for local use)'}")
    ok = all(results)
    print("\n  All good! Start Jarvis with:  python app.py\n" if ok else
          "\n  Fix the FAIL lines above, then run this again.\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())