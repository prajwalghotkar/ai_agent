# Prajwal J.A.R.V.I.S 2.0

A voice-first personal AI assistant that lives inside a rotating 3D "AI universe", with **Prajwal's portrait at the core**.
Ask it anything out loud or by typing. It answers like a person, and for live questions it calls real tools:

| Ability | Source | Key needed? |
|---|---|---|
| Live **news** (headlines, topics, categories) | Google News RSS (GNews optional) | No |
| Current **weather**, 7-day forecast, air quality | Open-Meteo | No |
| **Research papers** (authors, year, abstract, PDF) | arXiv + Semantic Scholar | No |
| **Wikipedia** facts on people, places, ideas | Wikipedia REST API | No |
| Currency conversion, date and time, maths | open.er-api.com, built-in | No |
| Open websites / YouTube searches, remember facts | Built-in | No |
| The brain (chat + tool calling) | **Groq** (free) | **Yes, free** |

Only one key is required: your free Groq key.

---

## 1. Get the free keys

| Key | Needed? | Link |
|---|---|---|
| **Groq** (the AI brain) | **Required** | https://console.groq.com/keys (sign in, click *Create API Key*) |
| GNews (better news) | Optional | https://gnews.io (register for the free plan) |
| Semantic Scholar (more paper results) | Optional | https://www.semanticscholar.org/product/api |

These need **no key at all**: [Open-Meteo](https://open-meteo.com/) (weather), [Google News RSS](https://news.google.com/rss), [arXiv API](https://info.arxiv.org/help/api/index.html), [Wikipedia API](https://www.mediawiki.org/wiki/API:Main_page), [ExchangeRate-API open endpoint](https://www.exchangerate-api.com/docs/free).

---

## 2. Run it in VS Code (Windows)

1. Install **Python 3.10 or newer** from https://www.python.org/downloads/ (tick **Add Python to PATH**) and **VS Code** from https://code.visualstudio.com/ with its *Python* extension.
2. Unzip this project. In VS Code: **File > Open Folder** and choose the folder.
3. Open the terminal: **Terminal > New Terminal**, then run:

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

If PowerShell blocks `activate`, run `Set-ExecutionPolicy -Scope Process Bypass` first, then activate again.
(macOS / Linux: `source venv/bin/activate`.)

4. Create your settings file:

```powershell
copy .env.example .env
```

Open `.env` in VS Code and paste your key after `GROQ_API_KEY=`. Optionally set `DEFAULT_CITY` to your city.

5. Check that everything is connected:

```powershell
python check_setup.py
```

You should see `[OK]` for Groq, Weather, News, Research, Wikipedia and Currency.

6. Start Jarvis:

```powershell
python app.py
```

7. Open **http://localhost:8000** in **Chrome or Edge**, click **ACTIVATE**, and allow the microphone.

### How to talk to him

* Click the mic and speak, or type in the box.
* Turn on **HANDS-FREE** and say *"Jarvis, what's the weather in Mumbai?"*
* Examples: *"latest news on ISRO"*, *"top technology news"*, *"find recent research papers on diffusion models"*, *"who is Geoffrey Hinton"*, *"convert 500 dollars to rupees"*, *"open YouTube and search lofi music"*, *"remember that my birthday is 2 March"*, *"what is 18 percent of 2450"*.
* Say *"stop"* or press **Esc** to interrupt him. Drag the background to rotate the universe, scroll to zoom.
* Hindi and Hinglish work too: change **Settings > Speech language** to Hindi.

### Optional: voice-only desktop mode

```powershell
pip install -r requirements-desktop.txt
python main.py
```

(Say "Jarvis ..." then your question. If `PyAudio` fails to install on Windows, run `pip install pipwin` then `pipwin install pyaudio`.)

---

## 3. Why he sounds human now

Everything he says passes through `jarvis/speech.py` before it reaches the voice engine. Symbols are translated or removed:
`**bold**`, `#`, `*`, bullets, links, emojis and brackets are dropped; `&` becomes "and", `%` becomes "percent", `28°C` becomes "28 degrees Celsius", `₹1,500` becomes "1,500 rupees", `km/h` becomes "kilometres per hour". The system prompt also tells the model to speak in short natural sentences. Hindi text is preserved correctly.

---

## 4. Host it free

The app is a Python server, so it needs a host that runs Python (GitHub Pages, Netlify and similar static hosts cannot run it). Browsers only allow the microphone on HTTPS, which every host below provides automatically.

**First, put the project on GitHub** (never upload `.env`; `.gitignore` already excludes it):

```powershell
git init
git add .
git commit -m "Prajwal Jarvis"
git branch -M main
git remote add origin https://github.com/YOUR_NAME/prajwal-jarvis.git
git push -u origin main
```

### Option A: Render (recommended)

1. Sign up at https://render.com and click **New + > Blueprint**, then pick your GitHub repo (it reads `render.yaml`).
   Or **New + > Web Service** with Build `pip install -r requirements.txt` and Start `uvicorn app:app --host 0.0.0.0 --port $PORT`.
2. In **Environment**, add `GROQ_API_KEY` and, strongly recommended, `APP_PIN` (any secret PIN).
3. Deploy. You get a link like `https://prajwal-jarvis.onrender.com`.

Render's free plan sleeps after 15 minutes without traffic and takes about a minute to wake, and includes 750 free instance hours a month ([Render free-plan docs](https://render.com/docs/free)).

### Option B: Hugging Face Spaces (Docker)

1. Create an account at https://huggingface.co, then **New Space**, choose **Docker**.
2. Upload this project's files (or `git push` to the Space repo). Put this block at the very top of `README.md` in the Space:

```yaml
---
title: Prajwal Jarvis
emoji: 🤖
sdk: docker
app_port: 7860
---
```

3. **Settings > Variables and secrets**: add `GROQ_API_KEY` and `APP_PIN` as **Secrets**.

Free Spaces also sleep when unused. Check the current plan details on the [Spaces overview](https://huggingface.co/docs/hub/spaces-overview), since free-tier rules change.

> **Protect your quota.** Anyone with your public link can use your free Groq key. Set `APP_PIN` (Jarvis asks for it once) and keep `RATE_LIMIT_PER_MIN` low.

---

## 5. Project layout

```
app.py              web server (Starlette): /api/chat, /api/weather, /api/news, /api/health
jarvis/agent.py     Groq tool-calling loop, model fallback, friendly errors
jarvis/tools.py     weather, news, research, wikipedia, currency, time, maths, open site, memory
jarvis/speech.py    symbol-free speech and clean on-screen text
jarvis/config.py    all settings from .env
static/             the 3D universe (WebGL), voice, cards, UI
main.py             optional voice-only desktop mode
check_setup.py      tests your keys and every data source
tests/              automated tests (python -m pytest tests)
tests/fake_server.py  runs the full UI offline with a fake internet
```

## 6. What changed from the original project

* OpenAI `text-davinci-003` (retired) replaced by **Groq** with tool calling and automatic fallback models.
* The name **Harry** is now **Prajwal** everywhere, and the assistant is Prajwal's Jarvis.
* Removed macOS-only `say`, `open` and hard-coded `/Users/harry/...` paths; it now works on Windows, macOS and Linux.
* API key moved from `config.py` into `.env` (so it can't leak to GitHub).
* Added error handling, conversation memory, the web UI, and all the live tools above.

## 7. Troubleshooting

| Problem | Fix |
|---|---|
| "language core isn't connected" | Put your Groq key in `.env`, restart `python app.py`. |
| Mic does nothing | Use Chrome or Edge, open via `localhost` or `https`, click the lock icon and allow the microphone. |
| Voice sounds robotic / wrong | **Settings > Jarvis voice**; on Windows install an extra voice in *Settings > Time & language > Speech*. |
| Animation is slow | **Settings > Visual quality > Light**. |
| "usage limit" message | Free Groq limits reached. Wait a minute, or add a different `GROQ_MODEL`. |
| A model was retired | Change `GROQ_MODEL` in `.env` to one listed at https://console.groq.com/docs/models |

Run the tests any time with `python -m pytest tests`.
