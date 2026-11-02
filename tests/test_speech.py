import re

from jarvis.speech import clean_for_display, clean_for_speech, split_for_tts, strip_thinking

SYMBOLS = re.compile(r"[*#@&%_~`|<>\[\]{}\\^=+$₹°]")


def test_no_symbols_survive():
    raw = ("# Weather\n**Pune** is 28°C & humid (60%) — see https://x.com/a?b=1 ✨\n"
           "- item *one*\n- item `two`\n> quote #1 @home\n| a | b |\n2 * 3 = 6 and 5+5")
    out = clean_for_speech(raw)
    assert not SYMBOLS.search(out), out
    assert "http" not in out
    assert "degrees Celsius" in out and "percent" in out and " and " in out
    assert "number 1" in out and " at home" in out and "times" in out and "plus" in out


def test_money_units_arrows():
    out = clean_for_speech("Price ₹1,500 or $20 at 12 km/h, wind 3 m/s -> done → ok \U0001F600")
    assert "1,500 rupees" in out and "20 dollars" in out
    assert "kilometres per hour" in out and "metres per second" in out
    assert not SYMBOLS.search(out) and "\U0001F600" not in out


def test_hindi_survives():
    out = clean_for_speech("**नमस्ते** प्रज्वल, आज मौसम अच्छा है!")
    assert "नमस्ते" in out and "*" not in out


def test_links_citations_and_code():
    out = clean_for_speech("Read [the paper](https://arxiv.org/abs/1) now [1][2] ```print(1)``` ok")
    assert out == "Read the paper now ok.", out


def test_think_tags_removed():
    assert strip_thinking("<think>secret plan</think>Hello") == "Hello"
    assert "secret" not in clean_for_speech("<think>secret plan</think>Hello there")


def test_display_keeps_structure_without_markdown():
    out = clean_for_display("## Title\n**Bold** text\n- one\n* two")
    assert "#" not in out and "*" not in out and "• one" in out and "• two" in out


def test_empty_and_split():
    assert clean_for_speech("") == ""
    chunks = split_for_tts("One. " * 100, 60)
    assert all(len(c) <= 60 for c in chunks) and len(chunks) > 3
