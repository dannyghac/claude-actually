#!/usr/bin/env python3
"""Build a gated field-test page for claudeactually.ai.

Takes a self-contained FIELD-TEST.html, wraps it in the terminal lock screen
(scripts/gate_template.html), and emits a phase page. The visitor sees only
the encoded access code; the test body is base64-encoded and the password is
stored as a SHA-256 hash, so neither view-source nor a crawler spoils the
game. Plaintext passwords never touch the repo -- they only exist on the
command line.

Usage:
  python3 scripts/build_field_test.py \
      --source /path/to/FIELD-TEST.html \
      --phase 1 \
      --title "FIELD TEST" \
      --password CorrectHorse \
      --encoding hex \
      --out field-tests/phase-1.html

Encodings: hex, rot13. Add new ones in ENCODERS as later phases need them.
The password check is case-insensitive (input and password are lowercased
before hashing) so a kid typing "correcthorse" still gets in.

The same gate template is embedded in the Coach Kit's mission-config.html
(see build_coach_kit.py), which fills the @@TOKENS@@ in the browser instead.
Keep the token set in sync between the two scripts.
"""

import argparse
import base64
import codecs
import hashlib
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
TEMPLATE = HERE / "gate_template.html"

MORSE = {
    "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.",
    "G": "--.", "H": "....", "I": "..", "J": ".---", "K": "-.-", "L": ".-..",
    "M": "--", "N": "-.", "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.",
    "S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--", "X": "-..-",
    "Y": "-.--", "Z": "--..", "0": "-----", "1": ".----", "2": "..---",
    "3": "...--", "4": "....-", "5": ".....", "6": "-....", "7": "--...",
    "8": "---..", "9": "----.",
}


def _atbash(s):
    def flip(c):
        if "a" <= c <= "z":
            return chr(ord("z") - (ord(c) - ord("a")))
        if "A" <= c <= "Z":
            return chr(ord("Z") - (ord(c) - ord("A")))
        return c
    return "".join(flip(c) for c in s)


def _caesar3(s):
    def shift(c):
        if "a" <= c <= "z":
            return chr((ord(c) - ord("a") + 3) % 26 + ord("a"))
        if "A" <= c <= "Z":
            return chr((ord(c) - ord("A") + 3) % 26 + ord("A"))
        return c
    return "".join(shift(c) for c in s)


ENCODERS = {
    "hex": {
        "encode": lambda s: s.encode("utf-8").hex(),
        "label": "HEX",
        "hint": "Paste the code into your AI and ask what it says. Or, if you're feeling like a hacker, crack it yourself in Terminal.",
    },
    "rot13": {
        "encode": lambda s: codecs.encode(s, "rot13"),
        "label": "ROT13",
        "hint": "Paste the code into your AI and ask what it says. It's an old cipher &mdash; Julius Caesar could have cracked this one.",
    },
    "binary": {
        "encode": lambda s: " ".join(format(b, "08b") for b in s.encode("utf-8")),
        "label": "BINARY",
        "hint": "No letters this time. This is the rawest form a computer speaks. Paste it into your AI and ask what it says.",
    },
    "morse": {
        "encode": lambda s: " ".join(MORSE[c] for c in s.upper()),
        "label": "MORSE",
        "hint": "This code is older than computers, older than the lightbulb. People sent it across oceans with beeps. Paste it into your AI and ask what it says.",
    },
    "atbash": {
        "encode": _atbash,
        "label": "ATBASH",
        "hint": "The alphabet, looking into a mirror: the first letter trades with the last, the second with the second-to-last, all the way through. Ancient scribes used it. Paste it into your AI and ask what it says.",
    },
    "caesar3": {
        "encode": _caesar3,
        "label": "CAESAR",
        "hint": "The oldest trick in the book. A general used it to send battle orders two thousand years ago, and it held, because his enemies couldn't read it. You can. Paste it into your AI and ask what it says.",
    },
}

SITE_PARENTS_NOTE = (
    '<p class="g-parents"><b>Parent?</b> This is a playable demo. The full program guide is '
    '<a href="../founder-kit.html">here</a>. Stuck on the code? Crack it the same way your kid '
    'will &mdash; paste it into Claude or ChatGPT and ask what it is.</p>'
)
SITE_BACK_LINK = '<p class="g-back"><a href="index.html">&#8592; ALL FIELD TESTS</a></p>'


def extract(source_html):
    css = re.search(r"<style>(.*?)</style>", source_html, re.S)
    body = re.search(r"<body>(.*?)</body>", source_html, re.S)
    if not css or not body:
        sys.exit("source file missing <style> or <body> block")
    return css.group(1).strip("\n"), body.group(1).strip("\n")


def render(tokens):
    page = TEMPLATE.read_text(encoding="utf-8")
    for key, value in tokens.items():
        page = page.replace(f"@@{key}@@", value)
    leftover = re.findall(r"@@[A-Z_]+@@", page)
    if leftover:
        sys.exit(f"unfilled template tokens: {leftover}")
    return page


def build_tokens(source_html, phase, title, password, encoding,
                 parents_note=SITE_PARENTS_NOTE, back_link=SITE_BACK_LINK,
                 ls_prefix="ca_ft_phase"):
    enc = ENCODERS[encoding]
    source_css, source_body = extract(source_html)
    return {
        "PHASE": str(phase),
        "TITLE": title,
        "SOURCE_CSS": source_css,
        "ENC_LABEL": enc["label"],
        "ENC_HINT": enc["hint"],
        "ACCESS_CODE": enc["encode"](password),
        "PW_HASH": hashlib.sha256(password.lower().encode("utf-8")).hexdigest(),
        "PAYLOAD": base64.b64encode(source_body.encode("utf-8")).decode("ascii"),
        "LS_KEY": f"{ls_prefix}{phase}",
        "PARENTS_NOTE": parents_note,
        "BACK_LINK": back_link,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--phase", required=True)
    ap.add_argument("--title", default="FIELD TEST")
    ap.add_argument("--password", required=True)
    ap.add_argument("--encoding", required=True, choices=sorted(ENCODERS))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    source_html = pathlib.Path(args.source).read_text(encoding="utf-8")
    page = render(build_tokens(source_html, args.phase, args.title,
                               args.password, args.encoding))
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(f"built {out}  (code: {ENCODERS[args.encoding]['encode'](args.password)})")


if __name__ == "__main__":
    main()
