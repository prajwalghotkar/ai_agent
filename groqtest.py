"""Replacement for the old openaitest.py - a 5-second check that Groq answers.
Run:  python groqtest.py
"""
from jarvis import config, http

if not config.GROQ_API_KEY:
    raise SystemExit("No GROQ_API_KEY found. Copy .env.example to .env and paste your free key from console.groq.com/keys")

resp = http.post(
    f"{config.GROQ_BASE_URL}/chat/completions",
    headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
    json={"model": config.GROQ_MODEL, "max_tokens": 200,
          "messages": [{"role": "user", "content": "Write a two line email to my boss asking for a day off."}]},
    timeout=(6, 40),
)
print(resp.status_code)
print(resp.json()["choices"][0]["message"]["content"] if resp.ok else resp.text)
