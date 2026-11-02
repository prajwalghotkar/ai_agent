# Prajwal J.A.R.V.I.S 2.0



---

## Abstract

Prajwal J.A.R.V.I.S 2.0 is a conversational AI agent that can answer almost any question, whether it is general knowledge, explanation, writing, reasoning, or something that depends on live information. It combines a large language model (LLM) with a set of real-time tools, so it does not have to guess when the answer lives in the outside world. The user speaks or types. The agent decides what it needs, fetches live data, and replies in natural, human-sounding speech. The whole experience sits in a cinematic interface: a black, slowly rotating galaxy with a holographic portrait of Prajwal at its core, floating glass panels, and neon state colours.

The system rests on four ideas:

1. **Reasoning by a language model.** Any question can be understood, planned and answered.
2. **Grounding by tools.** Weather, news, research papers, encyclopedic facts, currency and time come from live sources, not from memory.
3. **Speech that sounds human.** Every reply is cleaned so symbols and formatting are never read aloud.
4. **An interface that feels alive.** The visuals react to what the agent is doing: listening, thinking or speaking.

---

## 1. What it can do

| Area | What it handles | Source |
|---|---|---|
| **Any general question** | Explanations, summaries, writing, brainstorming, coding help, maths reasoning, translation, advice | Language model (Groq) |
| **Live news** | Top headlines, topic searches, categories, regional editions | Google News RSS (GNews optional) |
| **Weather** | Current conditions, up to 7-day forecast, air quality index | Open-Meteo |
| **Research papers** | Recent or most relevant papers with authors, year, abstract and link | arXiv + Semantic Scholar |
| **Encyclopedic facts** | People, places, events, concepts, with disambiguation | Wikipedia |
| **Currency** | Live exchange-rate conversion | open.er-api.com |
| **Date and time** | Time in any time zone | Built in |
| **Calculator** | Safe arithmetic and percentages | Built in |
| **Web actions** | Open known websites, YouTube or Google searches | Built in |
| **Personal memory** | Remember and forget facts about the user | Browser storage |

### The kinds of questions it answers

| Type | Examples |
|---|---|
| Live information | "What is the weather in Mumbai for the next five days?" "Top technology news today." |
| Research | "Find recent papers on AI agents." "Most cited papers on transformers." |
| Knowledge | "Who is Geoffrey Hinton?" "Explain how a black hole forms." |
| Reasoning and writing | "Explain recursion simply." "Draft an email asking for a day off." |
| Everyday tasks | "Convert 100 dollars to rupees." "What is 18 percent of 2450?" "What time is it in London?" |
| Actions | "Open YouTube and search lofi music." |
| Personal | "Remember that my birthday is 2 March." |
| Multi-part | "Tell me the weather in Pune and the latest AI papers." (both tools run at the same time) |

It understands English, Hindi and Hinglish, and can reply in the language it is spoken to.

**Honest boundaries.** It does not provide live stock or crypto prices or live sports scores, does not control the user's files or apps, and does not generate images or send emails and messages. When a tool cannot get data, it says so plainly instead of inventing an answer.

---

## 2. System architecture

The system has four layers. The browser handles voice and visuals. A small Python server guards and coordinates. The language model reasons. Live data sources supply facts.


<img width="1568" height="2372" alt="01_architecture" src="https://github.com/user-attachments/assets/ef0ccad9-03cd-443a-a8eb-e83968a282a3" />




**Design choices**

- **Stateless server.** The browser sends the recent conversation and the user's remembered facts with each request. The server stores nothing, so it is simple to scale and private by design.
- **No front-end libraries.** The 3D scene is written directly in WebGL, which keeps it fast to load and fully under control.
- **Model-agnostic tool calling.** The agent speaks the standard chat-completions and function-calling format, so the underlying model can be swapped without redesigning anything.

---

## 3. How a question becomes an answer

Take the request "Weather in Pune and the latest AI papers". Here is the full journey.



<img width="1568" height="948" alt="02_request_flow" src="https://github.com/user-attachments/assets/c63d1eca-3550-47d0-a4a8-b56ee08e15c3" />





1. The browser converts speech to text.
2. The server checks the optional PIN and the per-user rate limit.
3. The agent sends the model a system prompt, recent history and the list of available tools.
4. The model decides which tools it needs. Here it asks for weather and research papers.
5. Both tools run in parallel, each calling its live source.
6. The results go back to the model, which writes a plain-language answer.
7. The answer is cleaned for the screen and for the voice.
8. The browser shows cards and a typed caption and speaks the reply.

---

## 4. The agent loop

The agent is a bounded loop. The model may call tools, read what they return, and call more if needed, until it can give a final answer.




<img width="1568" height="2462" alt="03_agent_loop" src="https://github.com/user-attachments/assets/4883db43-db2d-45f0-8156-db5d8f050d52" />






| Mechanism | Behaviour |
|---|---|
| Tool rounds | At most 4 rounds per question, with at most 6 tool calls |
| Parallelism | Tools in the same round run concurrently (up to 4 workers) |
| Memory window | The most recent 16 messages are sent with each request |
| Retry | A malformed tool call from the model is retried once |
| Model fallback | If the main model is missing, rate-limited or failing, the agent moves to a backup model automatically |
| Hidden reasoning | Any internal "think" text is stripped before display or speech |
| Friendly errors | Failures become short, spoken explanations, never raw error codes |

### Tool design

Each tool has a strict schema, validated arguments and a short human-readable error message.

| Tool | Notes |
|---|---|
| Weather | Geocodes the place, then returns current conditions, a forecast of up to 7 days and a US air quality index |
| News | Headlines by topic, category or edition (India, US, UK, Australia, Canada) |
| Research | Searches arXiv and Semantic Scholar, removes duplicates, ranks by relevance or recency |
| Wikipedia | Concise summaries, with handling for ambiguous titles and validated language codes |
| Currency | Live rates between any two currencies |
| Time | Any time zone, with a safe fallback |
| Calculator | Parses expressions with a restricted syntax tree, never executes arbitrary code |
| Open website | Known sites plus YouTube and Google searches, http and https only |
| Memory | Stores facts in the browser, so the server stays stateless |

---

## 5. Human-sounding speech

Language models write for the eye: bold marks, bullets, links, emoji, units. Read aloud, these sound robotic. Every reply therefore passes through a speech cleaner before it reaches the voice engine. The screen text and the spoken text are produced separately.


<img width="1568" height="122" alt="04_speech_pipeline" src="https://github.com/user-attachments/assets/b26ba662-5035-498f-854c-ffc2917a6276" />




| Written form | Spoken as |
|---|---|
| `**bold**`, `#`, `*`, bullets, tables | Removed |
| Links and URLs | Removed |
| Emoji, arrows, brackets | Removed |
| `&` | "and" |
| `%` | "percent" |
| `@` | "at" |
| `28°C` | "28 degrees Celsius" |
| `km/h` | "kilometres per hour" |
| `₹1,500` | "1,500 rupees" |

The cleaner keeps every script, so Hindi and other languages pass through safely. The system prompt also instructs the model to write in short, natural sentences, and long replies are split at sentence boundaries so speech starts quickly and sounds paced.

---

## 6. Voice interaction

| Capability | Detail |
|---|---|
| Speech recognition | Browser Web Speech API (Chrome and Edge) |
| Speech synthesis | Browser speech engine, with a preference for a male voice |
| Hands-free mode | Say "Jarvis, ..." and the wake word is detected, including common mishearings |
| Barge-in | Saying "stop" or pressing Esc interrupts the reply at once |
| Languages | English (India, US, UK) and Hindi |
| Reliability | A watchdog timer prevents a stalled speech engine from freezing the assistant |

---

## 7. The visual system

The interface is designed to feel like a living machine rather than a chat box.


<img width="1568" height="388" alt="05_states" src="https://github.com/user-attachments/assets/7c272f71-83b9-46db-9c72-c05698d12d85" />




| Layer | What the user sees |
|---|---|
| Star field | Thousands of distant stars |
| Nebula clouds | Soft coloured clouds, with the noise computed once and cached as textures for speed |
| Spiral galaxy | Up to 30,000 particles, rotating slowly. Drag to rotate, scroll to zoom |
| Aura | Particles swirling closely around the portrait |
| Halo | A glow that pulses with the speech |
| Holographic portrait | Prajwal's photo with scanlines, rim glow and a moving scan beam |
| HUD rings | Five rings with three orbiting satellites |
| Glass interface | Live-feed cards, conversation log, caption, quick-action chips and settings |

### The assistant has visible states

The whole scene changes colour and motion with what the agent is doing, so the user always knows what it is up to.


<img width="672" height="2558" alt="06_scene_layers" src="https://github.com/user-attachments/assets/fec1dcd3-f904-4091-a2a8-bc0a24d1ebc2" />



| State | Colour | Motion |
|---|---|---|
| Idle | Cyan | Slow rotation |
| Listening | Green | Faster rotation |
| Thinking | Violet | Rapid orbit |
| Speaking | Orange | Pulses with every spoken word |

**Performance and fallbacks.** Quality adapts automatically. If the frame rate drops, the particle count is reduced. If WebGL is unavailable, a static portrait is shown, and the layout is responsive down to phone width.

---

## 8. Live feed cards

Alongside the spoken answer, the assistant shows structured cards that are easy to scan.

| Card | Content |
|---|---|
| Weather | Temperature, conditions, forecast, air quality |
| News | Headlines with sources and links |
| Papers | Title, authors, year, abstract snippet and link |
| Wikipedia | Summary and link |
| Currency | Converted amount and rate |
| Time | Time and time zone |
| Calculator | Expression and result |

---

## 9. Security and reliability

| Concern | Measure |
|---|---|
| Unauthorised use | Optional access PIN, compared in constant time |
| Abuse and quota drain | Per-IP sliding-window rate limit |
| Browser attacks | Security headers, text-only rendering of replies (no HTML injection), only http and https links are opened |
| Prompt injection | Tool output is treated as untrusted data and never as instructions |
| Safe maths | Expression parser accepts only arithmetic |
| Secrets | API keys are read from environment settings, never stored in code |
| Privacy | Stateless server, memory held in the user's own browser |
| Upstream failure | Every tool has timeouts and friendly fallbacks, and the model layer has backup models |

---

## 10. Technology stack

| Layer | Technology |
|---|---|
| Backend | Python, Starlette, Uvicorn |
| Language model | Groq (OpenAI-compatible chat completions with tool calling), default Llama 3.3 70B with automatic fallbacks |
| Live data | Open-Meteo, Google News RSS, arXiv, Semantic Scholar, Wikipedia REST, open.er-api.com |
| Frontend | HTML, CSS, vanilla JavaScript, raw WebGL |
| Voice | Web Speech API for recognition and synthesis |
| Deployment targets | Render, Hugging Face Spaces (Docker) |

---

## 11. Verification

| Test area | Coverage |
|---|---|
| Speech cleaning | Symbols, units, URLs, markdown and Hindi text |
| Tools | Every tool, including errors and edge cases, against a simulated internet |
| Agent | Tool calling, retries, model fallback, history and memory |
| Setup checks | Diagnostics for keys and data sources |
| User interface | 13 automated browser checks covering boot, 3D scene, cards, state changes, drag and zoom, settings and mobile layout |

In all, 37 automated tests and the browser checks pass against a simulated internet, so the logic is verified deterministically. Real third-party services were not called during testing, so live behaviour depends on their availability.

---

## 12. Limitations

- Answer quality depends on the language model, which can still make mistakes. It is strongest when a tool provides the facts.
- Voice recognition depends on the browser, with best support in Chrome and Edge.
- Free-tier model and data services have usage limits.
- Hosting on a free tier can add a short wake-up delay after idle periods.
- No live financial markets or sports data, and no control of the user's own computer.

## 13. Future work

- Long-term memory stored securely across devices
- Streaming responses, so speech starts while the model is still writing
- More tools: stock markets, sports, maps, calendar and email connectors
- Document and image understanding
- Natural neural voices for higher-quality speech
- Multiple selectable personas

---

## 14. Project structure

```
app.py              Web server: chat, weather, news, health endpoints
jarvis/agent.py     The agent loop, model fallback, friendly errors
jarvis/tools.py     Weather, news, research, Wikipedia, currency, time, maths, web, memory
jarvis/speech.py    Speech and on-screen text cleaning
jarvis/config.py    Settings
static/             3D universe, voice, cards and interface
tests/              Automated tests
docs/diagrams/      Diagram sources and images used in this document
```

---

## Conclusion

Prajwal J.A.R.V.I.S 2.0 shows that a capable personal assistant needs three things working together: a strong reasoning model, real tools for the facts, and a voice and interface that make it feel natural. Together they give one assistant that can chat, research, report the news and weather, and answer almost anything, in a voice that sounds human.

----

## Try asking Jarvis

1. What is the weather in Pune today, and will it rain this week?
2. Give me the top technology news right now.
3. Find recent research papers on AI agents.
4. Who is Geoffrey Hinton, and why is he famous?
5. Convert 500 US dollars to Indian rupees.
6. What is 18 percent of 2450?
7. What time is it in London right now?
8. Explain recursion in simple words.
9. Open YouTube and search for lofi music.
10. Remember that my birthday is 2 March.

"For a more impressive demo, you can add a multi-part question:"

----

## Authors

Created by **Prajwal** · Deployed by **Aman**

Built with ❤️ and a lot of playing with Python 🐍
