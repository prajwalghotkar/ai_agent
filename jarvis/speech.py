"""Turn model output into text that sounds human when spoken.

The original project passed raw model text to the TTS engine, so Jarvis would literally say
"asterisk asterisk" or "hash". `clean_for_speech` removes/translates every symbol so
Jarvis talks like a person; `clean_for_display` strips markdown but keeps the text readable.
"""
import re
import unicodedata

_EMOJI = re.compile(
    "["
    "\U0001F000-\U0001FAFF"   # pictographs, emoticons, transport, symbols
    "\U00002600-\U000027BF"   # misc symbols, dingbats
    "\U00002190-\U000021FF"   # arrows
    "\U00002B00-\U00002BFF"
    "\U0000FE00-\U0000FE0F"   # variation selectors
    "\U0000200D"              # zero width joiner
    "]+",
    flags=re.UNICODE,
)

_CODE_FENCE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE = re.compile(r"`([^`]*)`")
_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]+)\]\((?:[^)]*)\)")
_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_HTML_TAG = re.compile(r"<[^>]+>")
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_CITATION = re.compile(r"\[\d+(?:,\s*\d+)*\]")


_ALLOWED_PUNCT = set(".,!?:;'-")


def _keep_speakable(text: str) -> str:
    """Keep letters, digits and combining marks of ANY script (Hindi vowel signs are 'marks',
    which a plain \\w regex would wrongly delete) plus gentle punctuation."""
    out = []
    for ch in text:
        cat = unicodedata.category(ch)
        if ch.isalnum() or cat[0] == "M" or ch.isspace() or ch in _ALLOWED_PUNCT:
            out.append(ch)
        else:
            out.append(" ")
    return "".join(out)


def strip_thinking(text: str) -> str:
    """Some reasoning models wrap their scratch-work in <think> tags - never show/say it."""
    return _THINK.sub("", text or "").strip()


def _common(text: str) -> str:
    text = strip_thinking(text)
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = _CODE_FENCE.sub(" ", text)
    text = _IMAGE.sub(r"\1", text)
    text = _LINK.sub(r"\1", text)
    text = _URL.sub("", text)
    text = _INLINE_CODE.sub(r"\1", text)
    text = _HTML_TAG.sub(" ", text)
    text = _CITATION.sub("", text)
    return text


def clean_for_display(text: str) -> str:
    """Readable on screen: no markdown noise, bullets become a simple dot."""
    text = _common(text)
    lines = []
    for line in text.splitlines():
        line = re.sub(r"^\s{0,3}#{1,6}\s*", "", line)          # headings
        line = re.sub(r"^\s*>\s?", "", line)                    # quotes
        line = re.sub(r"^\s*[-*+•]\s+", "• ", line)   # bullets
        if re.fullmatch(r"\s*[-*_=]{3,}\s*", line):             # horizontal rules
            continue
        line = re.sub(r"(\*\*|__|~~)", "", line)                # bold / strike
        line = re.sub(r"(?<!\w)\*(?=\S)|(?<=\S)\*(?!\w)", "", line)  # italics
        lines.append(line.rstrip())
    out = "\n".join(lines)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def clean_for_speech(text: str) -> str:
    """Plain, natural sentences: symbols are spoken as words or dropped."""
    if not text:
        return ""
    t = _common(text)

    # --- line-level markdown ------------------------------------------------
    lines = []
    for line in t.splitlines():
        line = re.sub(r"^\s{0,3}#{1,6}\s*", "", line)
        line = re.sub(r"^\s*>\s?", "", line)
        line = re.sub(r"^\s*[-*+•]\s+", "", line)
        if re.fullmatch(r"\s*[-*_=|:\s]{3,}\s*", line):
            continue
        line = line.replace("|", ", ")
        lines.append(line.strip())
    t = "\n".join(lines)

    # --- math / arrows before emphasis markers are stripped -------------------
    t = re.sub(r"(?<=\d)\s*[*×]\s*(?=\d)", " times ", t)
    t = re.sub(r"(?<=\d)\s*÷\s*(?=\d)", " divided by ", t)
    t = re.sub(r"(?<=\d)\s*\+\s*(?=\d)", " plus ", t)
    t = re.sub(r"(?<=\d)\s+-\s+(?=\d)", " minus ", t)
    t = t.replace("<=", " less than or equal to ").replace(">=", " greater than or equal to ")
    t = re.sub(r"(->|=>|→|⇒)", " to ", t)

    # --- emphasis markers -----------------------------------------------------
    t = re.sub(r"(\*\*|__|~~|\*)", "", t)
    t = t.replace("_", " ")

    # --- units ---------------------------------------------------------------------
    t = re.sub(r"(\d)\s*°\s*C\b", r"\1 degrees Celsius", t)
    t = re.sub(r"(\d)\s*°\s*F\b", r"\1 degrees Fahrenheit", t)
    t = t.replace("°C", " degrees Celsius").replace("°F", " degrees Fahrenheit")
    t = t.replace("°", " degrees ")
    t = re.sub(r"\bkm\s*/\s*h\b|\bkmph\b|\bkph\b", "kilometres per hour", t, flags=re.IGNORECASE)
    t = re.sub(r"\bm\s*/\s*s\b", "metres per second", t)
    t = re.sub(r"\bmph\b", "miles per hour", t, flags=re.IGNORECASE)
    t = re.sub(r"\bmm\b", "millimetres", t)
    t = re.sub(r"\b24\s*/\s*7\b", "twenty four seven", t)
    t = re.sub(r"(?<=\d)\s*%", " percent", t)
    t = t.replace("%", " percent ")

    # --- money ---------------------------------------------------------------------
    money = {"₹": "rupees", "$": "dollars", "€": "euros", "£": "pounds"}
    t = re.sub(
        r"([₹$€£])\s?(\d[\d,]*(?:\.\d+)?)",
        lambda m: f"{m.group(2)} {money[m.group(1)]}",
        t,
    )
    for sym, word in money.items():
        t = t.replace(sym, f" {word} ")

    # --- remaining symbols ---------------------------------------------------------
    t = re.sub(r"#(?=\d)", "number ", t)
    t = t.replace("#", " ")
    t = t.replace("&", " and ").replace("@", " at ").replace("=", " equals ")
    t = re.sub(r"(?<=\d)\s*~\s*(?=\d)", " to ", t)
    t = re.sub(r"~\s*(?=\d)", "about ", t)
    t = t.replace("~", " ")
    t = t.replace("+", " plus ")
    t = t.replace("…", ". ")
    t = re.sub(r"\s[-–—]+\s|[–—]", ", ", t)   # dashes become a pause
    t = re.sub(r"(rupees|dollars|euros|pounds|percent)\s*/\s*(?=[A-Za-z])", r"\1 per ", t)
    t = re.sub(r"(?<=\d)\s*/\s*(?=[A-Za-z])", " per ", t)
    t = re.sub(r"(?<=[A-Za-z])\s*/\s*(?=[A-Za-z])", " or ", t)
    t = t.replace("/", " ").replace("\\", " ")
    t = t.replace("(", ", ").replace(")", ", ")
    t = t.replace("[", " ").replace("]", " ").replace("{", " ").replace("}", " ")
    t = t.replace("<", " ").replace(">", " ").replace("^", " ").replace("`", " ").replace('"', " ")

    t = _EMOJI.sub(" ", t)

    # --- line breaks become sentence pauses ----------------------------------------
    parts = []
    for line in t.splitlines():
        line = line.strip()
        if not line:
            continue
        if line[-1] not in ".!?:;,":
            line += "."
        parts.append(line)
    t = " ".join(parts)

    # --- last safety net: keep only letters/digits (any language) and gentle punctuation
    t = _keep_speakable(t)
    t = re.sub(r"\s+([.,!?:;])", r"\1", t)
    t = re.sub(r"([.,!?:;])(?:\s*[.,:;])+", r"\1", t)      # ", ." / ",," -> single mark
    t = re.sub(r"(?<![^\W_])-+|-+(?![^\W_])", " ", t)         # stray hyphens
    t = re.sub(r"\s+", " ", t).strip(" ,;:")
    return t


def split_for_tts(text: str, max_len: int = 180) -> list[str]:
    """Split long speech into sentence-sized chunks (browser/engine TTS cut off long text)."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks, cur = [], ""
    for s in sentences:
        if len(cur) + len(s) + 1 <= max_len:
            cur = f"{cur} {s}".strip()
        else:
            if cur:
                chunks.append(cur)
            while len(s) > max_len:
                cut = s.rfind(" ", 0, max_len)
                cut = cut if cut > 0 else max_len
                chunks.append(s[:cut].strip())
                s = s[cut:].strip()
            cur = s
    if cur:
        chunks.append(cur)
    return [c for c in chunks if c]
