#!/usr/bin/env python3
"""Build a gated field-test page for claudeactually.ai.

Takes a self-contained FIELD-TEST.html, wraps it in the terminal lock screen,
and emits a phase page for field-tests/. The visitor sees only the encoded
access code; the test body is base64-encoded and the password is stored as a
SHA-256 hash, so neither view-source nor a crawler spoils the game. Plaintext
passwords never touch the repo -- they only exist on the command line.

Usage:
  python3 scripts/build_field_test.py \
      --source /path/to/FIELD-TEST.html \
      --phase 1 \
      --codename "FIELD TEST" \
      --password CorrectHorse \
      --encoding hex \
      --out field-tests/phase-1.html

Encodings: hex, rot13. Add new ones in ENCODERS as later phases need them.
The password check is case-insensitive (input and password are lowercased
before hashing) so a kid typing "correcthorse" still gets in.
"""

import argparse
import base64
import codecs
import hashlib
import pathlib
import re
import sys

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
}

PROGRAM_GUIDE_URL = "../founder-kit.html"

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex, nofollow">
<title>PHASE {phase} // {codename} &middot; Claude, Actually</title>
<style>
{source_css}
</style>
<style>
  /* ----- gate (lock screen) ----- */
  body{{flex-direction:column;align-items:center;gap:0}}
  .g-card{{width:min(680px,100%);background:linear-gradient(180deg, rgba(11,16,32,.92), rgba(5,7,13,.92));
    border:1px solid rgba(255,107,107,.25);border-radius:14px;overflow:hidden;
    box-shadow:0 0 0 1px rgba(255,255,255,.02), 0 40px 120px rgba(0,0,0,.6)}}
  .g-bar{{display:flex;align-items:center;gap:10px;padding:14px 18px;border-bottom:1px solid rgba(255,107,107,.25);
    font-size:12px;letter-spacing:.18em;color:var(--dim)}}
  .g-dot{{width:11px;height:11px;border-radius:50%;background:#1e2740;border:1px solid rgba(255,255,255,.06)}}
  .g-dot.r{{background:#ff6b6b;box-shadow:0 0 12px #ff6b6b}}
  .g-bar .g-id{{margin-left:auto;color:#ff6b6b;white-space:nowrap;flex:0 0 auto}}
  .g-bar .g-file{{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
  .g-body{{padding:28px 26px 30px}}
  .g-stamp{{font-family:var(--display);font-weight:800;font-size:clamp(24px,6vw,40px);line-height:1.05;
    letter-spacing:-.02em;color:#ff6b6b;text-shadow:0 0 26px rgba(255,107,107,.3);margin-bottom:8px}}
  .g-sub{{color:var(--dim);font-size:13.5px;line-height:1.65;font-family:var(--display);margin-bottom:20px}}
  .g-sub b{{color:var(--ink)}}
  .g-codebox{{border:1px solid var(--line);border-radius:10px;padding:14px 16px;background:rgba(39,245,160,.04);margin-bottom:8px}}
  .g-codebox h3{{font-family:var(--mono);font-size:11px;letter-spacing:.2em;color:var(--green);margin-bottom:10px}}
  .g-code{{font-family:var(--mono);font-size:clamp(14px,3.4vw,19px);letter-spacing:.06em;color:var(--amber);
    word-break:break-all;user-select:all;-webkit-user-select:all;line-height:1.5}}
  .g-copy{{margin-top:10px;font-family:var(--mono);font-size:11px;letter-spacing:.14em;color:var(--green);
    background:none;border:1px solid var(--green);border-radius:6px;padding:6px 12px;cursor:pointer}}
  .g-copy:active{{background:rgba(39,245,160,.15)}}
  .g-hint{{font-family:var(--display);font-size:13px;color:var(--dim);line-height:1.6;margin:14px 0 20px}}
  .g-hint b{{color:var(--ink)}}
  .g-form{{display:flex;gap:10px;flex-wrap:wrap}}
  .g-input{{flex:1 1 200px;font-family:var(--mono);font-size:16px;color:var(--ink);background:rgba(255,255,255,.05);
    border:1px solid var(--line);border-radius:8px;padding:12px 14px;outline:none;letter-spacing:.04em}}
  .g-input:focus{{border-color:var(--green);box-shadow:0 0 0 2px rgba(39,245,160,.15)}}
  .g-btn{{font-family:var(--mono);font-size:13px;letter-spacing:.16em;color:#05070d;background:var(--green);
    border:0;border-radius:8px;padding:12px 22px;cursor:pointer;font-weight:700}}
  .g-btn:active{{transform:translateY(1px)}}
  .g-msg{{margin-top:14px;font-family:var(--mono);font-size:13px;letter-spacing:.12em;min-height:18px}}
  .g-msg.deny{{color:#ff6b6b;animation:g-shake .3s}}
  .g-msg.grant{{color:var(--green)}}
  @keyframes g-shake{{25%{{transform:translateX(-5px)}}75%{{transform:translateX(5px)}}}}
  .g-parents{{margin-top:22px;padding-top:16px;border-top:1px dashed rgba(91,107,140,.3);
    font-family:var(--display);font-size:12.5px;line-height:1.6;color:var(--dim)}}
  .g-parents a{{color:var(--green);text-decoration:none;border-bottom:1px dotted var(--green)}}
  .g-back{{margin:18px 0 0;font-family:var(--mono);font-size:12px;letter-spacing:.14em}}
  .g-back a{{color:var(--dim);text-decoration:none}}
  .g-back a:hover{{color:var(--green)}}
  #test{{width:100%;display:none;justify-content:center}}
  #test.on{{display:flex}}
  .g-relock{{margin:16px 0 0;font-family:var(--mono);font-size:11px;letter-spacing:.14em;text-align:center;width:100%}}
  .g-relock a{{color:var(--dim);text-decoration:none;cursor:pointer}}
</style>
</head>
<body>
  <div id="gate">
    <main class="g-card">
      <div class="g-bar">
        <span class="g-dot r"></span><span class="g-dot"></span><span class="g-dot"></span>
        <span class="g-file">encrypted_container</span><span class="g-id">&#9612; LOCKED</span>
      </div>
      <div class="g-body">
        <div class="g-stamp">PHASE {phase} // {codename}</div>
        <p class="g-sub">This file is <b>locked</b>. The string below is not the password &mdash; it's the password, <b>encoded</b>. Decode it, type what it says, and you're in. That's the whole test before the test.</p>
        <div class="g-codebox">
          <h3>&#9670; ACCESS CODE &middot; {enc_label}</h3>
          <div class="g-code" id="code">{access_code}</div>
          <button class="g-copy" id="copyBtn" type="button">COPY CODE</button>
        </div>
        <p class="g-hint"><b>How to crack it:</b> {enc_hint}</p>
        <form class="g-form" id="gform">
          <input class="g-input" id="pw" type="text" autocomplete="off" autocapitalize="off" spellcheck="false" placeholder="decoded password">
          <button class="g-btn" type="submit">UNLOCK &#9656;</button>
        </form>
        <div class="g-msg" id="msg"></div>
        <p class="g-parents"><b>Parent?</b> This is a playable demo. The full program guide is <a href="{guide_url}">here</a>. Stuck on the code? Crack it the same way your kid will &mdash; paste it into Claude or ChatGPT and ask what it is.</p>
      </div>
    </main>
    <p class="g-back"><a href="index.html">&#8592; ALL FIELD TESTS</a></p>
  </div>
  <div id="test"></div>
  <p class="g-relock" id="relock" style="display:none"><a id="relockBtn">&#9612; LOCK IT AGAIN</a></p>

<script>
(function(){{
  var HASH="{pw_hash}", KEY="ca_ft_phase{phase}", PAYLOAD="{payload}";
  var gate=document.getElementById("gate"), test=document.getElementById("test"),
      msg=document.getElementById("msg"), relock=document.getElementById("relock");

  function decode(b64){{
    var raw=atob(b64), bytes=new Uint8Array(raw.length);
    for(var i=0;i<raw.length;i++) bytes[i]=raw.charCodeAt(i);
    return new TextDecoder("utf-8").decode(bytes);
  }}
  function sha256(s){{
    return crypto.subtle.digest("SHA-256", new TextEncoder().encode(s)).then(function(buf){{
      return Array.prototype.map.call(new Uint8Array(buf), function(b){{
        return b.toString(16).padStart(2,"0");
      }}).join("");
    }});
  }}
  function open_(){{
    test.innerHTML=decode(PAYLOAD);
    gate.style.display="none";
    test.className="on";
    relock.style.display="block";
    window.scrollTo(0,0);
  }}
  function lock(){{
    try{{localStorage.removeItem(KEY);}}catch(e){{}}
    test.innerHTML=""; test.className="";
    relock.style.display="none"; gate.style.display="";
    msg.className="g-msg"; msg.textContent="";
    document.getElementById("pw").value="";
  }}

  document.getElementById("copyBtn").addEventListener("click",function(){{
    var code=document.getElementById("code").textContent, btn=this;
    function done(){{btn.textContent="COPIED"; setTimeout(function(){{btn.textContent="COPY CODE";}},1400);}}
    if(navigator.clipboard&&navigator.clipboard.writeText){{navigator.clipboard.writeText(code).then(done,done);}}
    else{{var r=document.createRange();r.selectNodeContents(document.getElementById("code"));
      var s=getSelection();s.removeAllRanges();s.addRange(r);done();}}
  }});

  document.getElementById("gform").addEventListener("submit",function(e){{
    e.preventDefault();
    var v=document.getElementById("pw").value.trim().toLowerCase();
    if(!v) return;
    if(!(window.crypto&&crypto.subtle)){{msg.className="g-msg deny";msg.textContent="THIS BROWSER CAN'T RUN THE LOCK. TRY ANOTHER.";return;}}
    sha256(v).then(function(h){{
      if(h===HASH){{
        msg.className="g-msg grant"; msg.textContent="&#9670; ACCESS GRANTED".replace("&#9670;","\\u25c6");
        try{{localStorage.setItem(KEY,"1");}}catch(e){{}}
        setTimeout(open_,650);
      }}else{{
        msg.className="g-msg deny"; msg.textContent="ACCESS DENIED // TRY AGAIN";
      }}
    }});
  }});

  relock.querySelector("a").addEventListener("click",lock);

  try{{if(localStorage.getItem(KEY)==="1") open_();}}catch(e){{}}
}})();
</script>
</body>
</html>
"""


def extract(source_html):
    css = re.search(r"<style>(.*?)</style>", source_html, re.S)
    body = re.search(r"<body>(.*?)</body>", source_html, re.S)
    if not css or not body:
        sys.exit("source file missing <style> or <body> block")
    return css.group(1).strip("\n"), body.group(1).strip("\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--phase", required=True)
    ap.add_argument("--codename", default="FIELD TEST")
    ap.add_argument("--password", required=True)
    ap.add_argument("--encoding", required=True, choices=sorted(ENCODERS))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    enc = ENCODERS[args.encoding]
    source_css, source_body = extract(pathlib.Path(args.source).read_text(encoding="utf-8"))

    page = PAGE_TEMPLATE.format(
        phase=args.phase,
        codename=args.codename,
        source_css=source_css,
        enc_label=enc["label"],
        enc_hint=enc["hint"],
        access_code=enc["encode"](args.password),
        guide_url=PROGRAM_GUIDE_URL,
        pw_hash=hashlib.sha256(args.password.lower().encode("utf-8")).hexdigest(),
        payload=base64.b64encode(source_body.encode("utf-8")).decode("ascii"),
    )
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(f"built {out}  (code: {enc['encode'](args.password)})")


if __name__ == "__main__":
    main()
