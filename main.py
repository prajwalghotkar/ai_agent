"""Prajwal's JARVIS - desktop voice mode (works on Windows, macOS and Linux).

This is the upgraded version of the original main.py. Say "Jarvis ..." and he answers out loud.
The web version (python app.py) has the full 3D interface; this one is the lightweight voice-only mode.

    pip install -r requirements-desktop.txt
    python main.py
"""
import datetime
import json
import os
import sys
import webbrowser
from pathlib import Path

import speech_recognition as sr

from jarvis import config
from jarvis.agent import run_agent
from jarvis.speech import clean_for_speech

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MEMORY_FILE = Path(__file__).with_name("memory.json")
WAKE = config.ASSISTANT_NAME.lower()

history: list[dict] = []
memory: list[str] = json.loads(MEMORY_FILE.read_text("utf-8")) if MEMORY_FILE.exists() else []

# ---- text to speech (offline, built into the OS) -------------------------------
_engine = None


def say(text: str) -> None:
    """Speak after cleaning symbols so Jarvis never says 'asterisk' or 'hash'."""
    global _engine
    spoken = clean_for_speech(text)
    print(f"{config.ASSISTANT_NAME}: {spoken}")
    try:
        if _engine is None:
            import pyttsx3
            _engine = pyttsx3.init()
            _engine.setProperty("rate", 175)
            for v in _engine.getProperty("voices"):
                if any(k in v.name.lower() for k in ("david", "mark", "male", "ravi", "english")):
                    _engine.setProperty("voice", v.id)
                    break
        _engine.say(spoken)
        _engine.runAndWait()
    except Exception as exc:  # noqa: BLE001
        print(f"(voice engine unavailable: {exc})")


def listen() -> str:
    r = sr.Recognizer()
    with sr.Microphone() as source:
        r.adjust_for_ambient_noise(source, duration=0.4)
        print("Listening...")
        audio = r.listen(source, phrase_time_limit=15)
    try:
        text = r.recognize_google(audio, language="en-in")
        print(f"{config.USER_NAME}: {text}")
        return text
    except sr.UnknownValueError:
        return ""
    except sr.RequestError:
        print("Speech service unreachable - check internet.")
        return ""


def save_memory() -> None:
    MEMORY_FILE.write_text(json.dumps(memory, ensure_ascii=False, indent=2), "utf-8")


def handle_actions(actions: list[dict]) -> None:
    for a in actions:
        if a["type"] == "open_url":
            webbrowser.open(a["url"])
        elif a["type"] == "remember" and a["fact"] not in memory:
            memory.append(a["fact"])
            save_memory()
        elif a["type"] == "forget":
            memory[:] = [m for m in memory if a["keyword"].lower() not in m.lower()]
            save_memory()


def play_music() -> None:
    path = config.MUSIC_PATH
    if not path or not os.path.exists(path):
        say(f"Set MUSIC PATH in the dot env file first, {config.USER_NAME}.")
        return
    say("Playing your music.")
    if sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        os.system(f'open "{path}"')
    else:
        os.system(f'xdg-open "{path}"')


def main() -> None:
    global history
    hour = datetime.datetime.now().hour
    tod = "morning" if hour < 12 else "afternoon" if hour < 17 else "evening"
    say(f"Good {tod}, {config.USER_NAME}. All systems are online. Say {config.ASSISTANT_NAME} followed by your question.")
    while True:
        heard = listen().strip()
        if not heard:
            continue
        low = heard.lower()
        if WAKE not in low:
            continue                                              # ignore chatter without the wake word
        command = low.split(WAKE, 1)[1].strip(" ,.!?") or ""
        if not command:
            say(f"Yes, {config.USER_NAME}?")
            command = listen().strip().lower()
            if not command:
                continue

        # ---- instant local commands (no internet/LLM needed) ----------------------
        if command in ("quit", "exit", "stop", "goodbye", "good bye", "shutdown", "shut down"):
            say(f"Goodbye {config.USER_NAME}. Shutting down.")
            break
        if "reset chat" in command or "clear chat" in command:
            history = []
            say("Conversation cleared.")
            continue
        if "play music" in command or "open music" in command:
            play_music()
            continue

        # ---- everything else: the AI agent with live tools --------------------------
        result = run_agent(command, history, memory, {})
        handle_actions(result["actions"])
        say(result["reply"])
        history += [{"role": "user", "content": command}, {"role": "assistant", "content": result["reply"]}]
        history = history[-16:]


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBye.")
