#!/usr/bin/env python3
"""Assemble the downloadable Coach Kit for claudeactually.ai.

Builds a zip containing the full curriculum PDFs, ready-to-run field tests
(locked with the kit's default codes), CODES.txt for the coach, and
mission-config.html -- a fully offline configurator that lets a coach stamp
their kid's codename, their own rewards, and optionally their own passwords
into personalized field-test files, generated entirely in the browser.

The kit's DEFAULT passwords below are public by design: they ship inside a
bundle anyone can download, and the whole point is that a coach can replace
them with Mission Config. They are deliberately different from the site demo
passwords (which stay out of this repo) and from any private family run.

Usage:
  python3 scripts/build_coach_kit.py --out /path/to/dist

Inputs (override with flags if the layout ever moves):
  --curriculum ~/Desktop/claude-actually/curriculum
  scripts/gate_template.html  (shared with build_field_test.py)
"""

import argparse
import base64
import json
import pathlib
import shutil
import sys
import zipfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_field_test import ENCODERS, TEMPLATE, build_tokens, render  # noqa: E402

KIT_NAME = "claude-actually-coach-kit"

# Public-by-design defaults; a coach can mint their own in mission-config.html.
PHASES = [
    {"n": 1, "title": "FIELD TEST", "enc": "hex", "password": "TrustButVerify",
     "site_src": "field-tests/phase1-site.html", "coach_src": "field-tests/phase1-coach.html"},
    {"n": 2, "title": "PROVE THE IDEA", "enc": "rot13", "password": "ProveThePick",
     "site_src": "field-tests/phase2-site.html", "coach_src": "field-tests/phase2-coach.html"},
    {"n": 3, "title": "MAKE IT REAL", "enc": "binary", "password": "MoneyWall",
     "site_src": "field-tests/phase3-site.html", "coach_src": "field-tests/phase3-coach.html"},
    {"n": 4, "title": "DON'T BLEND IN", "enc": "morse", "password": "SHOWDONTTELL",
     "site_src": "field-tests/phase4-site.html", "coach_src": "field-tests/phase4-coach.html"},
    {"n": 5, "title": "SHIP IT LIVE", "enc": "atbash", "password": "StrangerTest",
     "site_src": "field-tests/phase5-site.html", "coach_src": "field-tests/phase5-coach.html"},
    {"n": 6, "title": "GO GET PAID", "enc": "caesar3", "password": "HonestNumbers",
     "site_src": "field-tests/phase6-site.html", "coach_src": "field-tests/phase6-coach.html"},
]

PDFS = [
    "Coach-Runbook.pdf",
    "The-Founder-Guide.pdf",
    "The-Founder-Guide-Adult.pdf",
    "The-Parents-Helper.pdf",
    "Founder-Quest.pdf",
    "Phase-Checks.pdf",
    "Field-Test-Rubrics.pdf",
    "Field-Test-Emails.pdf",
]

COACH_NOTE = ('<p class="g-parents"><b>Coach:</b> the access code and password for every '
              'phase are in your CODES.txt. Keep that file (and the rubrics) away from '
              'your operative. Everything else, let them find.</p>')

README = """CLAUDE, ACTUALLY -- THE COACH KIT
=================================

Everything you need to run the Founder Kit with a kid (or yourself).

START HERE:  Coach-Runbook.pdf
It explains every file in this folder and walks the whole program,
setup to final launch, in a few pages.

THE SHORT VERSION
  1. Read Coach-Runbook.pdf.
  2. Open mission-config.html in your browser and generate field tests
     personalized with your kid's codename and your rewards. (Optional --
     the ready-made ones in field-tests/ work as-is with CODES.txt.)
  3. Hand your founder The-Founder-Guide.pdf and start Phase 1.

KEEP AWAY FROM YOUR OPERATIVE
  CODES.txt, Field-Test-Rubrics.pdf, mission-config.html

Free, no catch, from Claude, Actually -- a program of the AI Actually
Foundation, a California nonprofit.    claudeactually.ai

Love, Claude
"""

CODES_TXT = """CODES.TXT -- COACH EYES ONLY
============================

These unlock the ready-made field tests in the field-tests/ folder.
(If you generate personalized tests with mission-config.html, it will
give you a fresh CODES.txt to replace this one.)

{lines}
How the lock works: your operative sees only the ACCESS CODE. Decoding
it (paste it into an AI and ask what it says) reveals the password.
That decode IS the first test. Don't help.
"""


# ---------------------------------------------------------------------------
# mission-config.html -- offline configurator. %%DATA%% is replaced with the
# JSON bundle of gate template + tokenized phase sources.
# ---------------------------------------------------------------------------
CONFIG_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MISSION CONFIG // COACH ONLY</title>
<style>
  :root{
    --bg:#05070d; --panel:#0b1020; --ink:#e8f0ff; --dim:#5b6b8c;
    --green:#27f5a0; --amber:#ffb347; --red:#ff6b6b; --line:rgba(39,245,160,.18);
    --mono:"SF Mono","Menlo","Monaco","Consolas",monospace;
    --display:"Avenir Next","Helvetica Neue",sans-serif;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:
      radial-gradient(1200px 600px at 70% -10%, rgba(39,245,160,.10), transparent 60%),
      radial-gradient(900px 500px at 0% 120%, rgba(255,179,71,.08), transparent 55%),
      var(--bg);
    color:var(--ink);font-family:var(--mono);min-height:100vh;
    display:flex;flex-direction:column;align-items:center;padding:24px}
  body::after{content:"";position:fixed;inset:0;pointer-events:none;z-index:50;
    background:repeating-linear-gradient(to bottom, rgba(255,255,255,.025) 0 1px, transparent 1px 3px);
    mix-blend-mode:overlay;opacity:.5}
  .card{width:min(720px,100%);background:linear-gradient(180deg, rgba(11,16,32,.92), rgba(5,7,13,.92));
    border:1px solid var(--line);border-radius:14px;overflow:hidden;
    box-shadow:0 0 0 1px rgba(255,255,255,.02), 0 40px 120px rgba(0,0,0,.6)}
  .bar{display:flex;align-items:center;gap:10px;padding:14px 18px;border-bottom:1px solid var(--line);
    font-size:12px;letter-spacing:.18em;color:var(--dim)}
  .dot{width:11px;height:11px;border-radius:50%;background:#1e2740;border:1px solid rgba(255,255,255,.06)}
  .dot.g{background:var(--green);box-shadow:0 0 12px var(--green)}
  .bar .id{margin-left:auto;color:var(--green);white-space:nowrap;flex:0 0 auto}
  .bar .file{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .body{padding:26px 26px 30px}
  .stamp{font-family:var(--display);font-weight:800;font-size:clamp(24px,5.5vw,38px);line-height:1.05;
    letter-spacing:-.02em;color:var(--green);text-shadow:0 0 30px rgba(39,245,160,.35);margin-bottom:8px}
  .sub{color:var(--dim);font-size:13.5px;line-height:1.65;font-family:var(--display);margin-bottom:22px}
  .sub b{color:var(--ink)}
  fieldset{border:1px solid var(--line);border-radius:10px;padding:16px;margin-bottom:14px;background:rgba(39,245,160,.02)}
  legend{font-size:11px;letter-spacing:.2em;color:var(--green);padding:0 8px}
  label{display:block;font-size:11px;letter-spacing:.16em;color:var(--dim);margin:12px 0 6px}
  label:first-of-type{margin-top:0}
  input[type=text],select{width:100%;font-family:var(--mono);font-size:15px;color:var(--ink);
    background:rgba(255,255,255,.05);border:1px solid var(--line);border-radius:8px;
    padding:10px 12px;outline:none}
  input[type=text]:focus,select:focus{border-color:var(--green);box-shadow:0 0 0 2px rgba(39,245,160,.15)}
  input.err{border-color:var(--red)}
  .row2{display:grid;grid-template-columns:1fr 1fr;gap:12px}
  @media (max-width:520px){.row2{grid-template-columns:1fr}}
  .soon{opacity:.45}
  .soon input{pointer-events:none}
  details{margin-bottom:14px}
  summary{cursor:pointer;font-size:11.5px;letter-spacing:.16em;color:var(--amber);padding:8px 0}
  .btns{display:flex;gap:10px;flex-wrap:wrap;margin-top:8px}
  .btn{font-family:var(--mono);font-size:13px;letter-spacing:.14em;border-radius:8px;
    padding:12px 20px;cursor:pointer;font-weight:700}
  .btn.main{color:#05070d;background:var(--green);border:0}
  .btn.ghost{color:var(--green);background:none;border:1px solid var(--green)}
  .btn:active{transform:translateY(1px)}
  #msg{margin-top:14px;font-size:12.5px;letter-spacing:.08em;min-height:18px;line-height:1.6}
  #msg.ok{color:var(--green)}
  #msg.bad{color:var(--red)}
  .note{margin-top:20px;padding-top:14px;border-top:1px dashed rgba(91,107,140,.3);
    font-family:var(--display);font-size:12.5px;line-height:1.6;color:var(--dim)}
  .note b{color:var(--ink)}
</style>
</head>
<body>
  <main class="card">
    <div class="bar">
      <span class="dot g"></span><span class="dot"></span><span class="dot"></span>
      <span class="file">mission_config.exe</span><span class="id">COACH ONLY</span>
    </div>
    <div class="body">
      <div class="stamp">MISSION CONFIG</div>
      <p class="sub">Stamp <b>your family's structure</b> into the field tests: codename, rewards, and (optionally) your own passwords. Everything happens on this computer &mdash; nothing is uploaded, no account, no internet needed. Click <b>GENERATE</b> and you'll get personalized field-test files for your operative, a fresh <b>CODES.txt</b> for you, and a <b>family file</b> you can load here later to make changes.</p>

      <fieldset>
        <legend>THE OPERATIVE</legend>
        <div class="row2">
          <div>
            <label for="codename">CODENAME</label>
            <input type="text" id="codename" autocomplete="off" placeholder="AGENT BLUEBIRD">
          </div>
          <div>
            <label for="budget">BUDGET DIAL</label>
            <select id="budget">
              <option value="NEAR-FREE">NEAR-FREE (under $200)</option>
              <option value="LEAN">LEAN ($200 to $2,000)</option>
              <option value="FULL">FULL ($2,000+)</option>
            </select>
          </div>
        </div>
      </fieldset>

      <fieldset>
        <legend>REWARDS &middot; ONE PER PHASE</legend>
        <div class="row2">
          <div>
            <label for="reward1">PHASE 1 &middot; PROVE THE SETUP</label>
            <input type="text" id="reward1" autocomplete="off" placeholder="$50 and you pick the pizza">
          </div>
          <div>
            <label for="reward2">PHASE 2 &middot; PROVE THE IDEA</label>
            <input type="text" id="reward2" autocomplete="off" placeholder="a camping trip">
          </div>
        </div>
        <div class="row2">
          <div>
            <label for="reward3">PHASE 3 &middot; MAKE IT REAL</label>
            <input type="text" id="reward3" autocomplete="off" placeholder="a new business tool they pick">
          </div>
          <div>
            <label for="reward4">PHASE 4 &middot; DON'T BLEND IN</label>
            <input type="text" id="reward4" autocomplete="off" placeholder="movie night, their pick">
          </div>
        </div>
        <div class="row2">
          <div>
            <label for="reward5">PHASE 5 &middot; SHIP IT LIVE</label>
            <input type="text" id="reward5" autocomplete="off" placeholder="the biggest one, site goes live">
          </div>
          <div>
            <label for="reward6">PHASE 6 &middot; GO GET PAID</label>
            <input type="text" id="reward6" autocomplete="off" placeholder="launch dinner + they keep the revenue">
          </div>
        </div>
      </fieldset>

      <details>
        <summary>&#9656; ADVANCED: SET YOUR OWN PASSWORDS</summary>
        <fieldset>
          <legend>PASSWORDS</legend>
          <p class="sub" style="margin-bottom:4px">The defaults work fine. Set your own and your family's codes exist nowhere else. Letters and numbers only, no spaces; the check ignores capitalization. The cipher ladder escalates on purpose &mdash; every phase is a lock they've never seen.</p>
          <div class="row2">
            <div>
              <label for="pw1">PHASE 1 PASSWORD (HEX)</label>
              <input type="text" id="pw1" autocomplete="off">
            </div>
            <div>
              <label for="pw2">PHASE 2 PASSWORD (ROT13)</label>
              <input type="text" id="pw2" autocomplete="off">
            </div>
          </div>
          <div class="row2">
            <div>
              <label for="pw3">PHASE 3 PASSWORD (BINARY)</label>
              <input type="text" id="pw3" autocomplete="off">
            </div>
            <div>
              <label for="pw4">PHASE 4 PASSWORD (MORSE)</label>
              <input type="text" id="pw4" autocomplete="off">
            </div>
          </div>
          <div class="row2">
            <div>
              <label for="pw5">PHASE 5 PASSWORD (ATBASH)</label>
              <input type="text" id="pw5" autocomplete="off">
            </div>
            <div>
              <label for="pw6">PHASE 6 PASSWORD (CAESAR)</label>
              <input type="text" id="pw6" autocomplete="off">
            </div>
          </div>
        </fieldset>
      </details>

      <div class="btns">
        <button class="btn main" id="gen" type="button">GENERATE KIT &#9656;</button>
        <button class="btn ghost" id="save" type="button">SAVE FAMILY FILE</button>
        <button class="btn ghost" id="load" type="button">LOAD FAMILY FILE</button>
        <input type="file" id="loadFile" accept=".json,application/json" style="display:none">
      </div>
      <div id="msg"></div>

      <p class="note"><b>What you'll download:</b> one locked field-test file per phase (give these to your operative), CODES.txt (yours &mdash; access codes, passwords, rewards), and family-file.json (your save file; load it here anytime). If downloads are blocked, allow multiple downloads when the browser asks.</p>
    </div>
  </main>

<script>
var DATA = %%DATA%%;

(function(){
  var $ = function(id){ return document.getElementById(id); };
  var msg = $("msg");

  function say(kind, text){ msg.className = kind; msg.textContent = text; }
  function esc(s){ return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }
  function b64decode(b64){
    var raw = atob(b64), bytes = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
    return new TextDecoder("utf-8").decode(bytes);
  }
  function b64encode(s){
    var bytes = new TextEncoder().encode(s), raw = "";
    for (var i = 0; i < bytes.length; i++) raw += String.fromCharCode(bytes[i]);
    return btoa(raw);
  }
  function hexEncode(s){
    var bytes = new TextEncoder().encode(s), out = "";
    for (var i = 0; i < bytes.length; i++) out += bytes[i].toString(16).padStart(2, "0");
    return out;
  }
  function rot13(s){
    return s.replace(/[a-zA-Z]/g, function(c){
      var base = c <= "Z" ? 65 : 97;
      return String.fromCharCode((c.charCodeAt(0) - base + 13) % 26 + base);
    });
  }
  function binaryEncode(s){
    var bytes = new TextEncoder().encode(s), out = [];
    for (var i = 0; i < bytes.length; i++) out.push(bytes[i].toString(2).padStart(8, "0"));
    return out.join(" ");
  }
  var MORSE = {A:".-",B:"-...",C:"-.-.",D:"-..",E:".",F:"..-.",G:"--.",H:"....",I:"..",
    J:".---",K:"-.-",L:".-..",M:"--",N:"-.",O:"---",P:".--.",Q:"--.-",R:".-.",S:"...",
    T:"-",U:"..-",V:"...-",W:".--",X:"-..-",Y:"-.--",Z:"--..","0":"-----","1":".----",
    "2":"..---","3":"...--","4":"....-","5":".....","6":"-....","7":"--...","8":"---..","9":"----."};
  function morseEncode(s){
    return s.toUpperCase().split("").map(function(c){ return MORSE[c]; }).join(" ");
  }
  function atbash(s){
    return s.replace(/[a-zA-Z]/g, function(c){
      return c <= "Z" ? String.fromCharCode(90 - (c.charCodeAt(0) - 65))
                      : String.fromCharCode(122 - (c.charCodeAt(0) - 97));
    });
  }
  function caesar3(s){
    return s.replace(/[a-zA-Z]/g, function(c){
      var base = c <= "Z" ? 65 : 97;
      return String.fromCharCode((c.charCodeAt(0) - base + 3) % 26 + base);
    });
  }
  var ENCODE = { hex: hexEncode, rot13: rot13, binary: binaryEncode,
                 morse: morseEncode, atbash: atbash, caesar3: caesar3 };
  function sha256(s){
    return crypto.subtle.digest("SHA-256", new TextEncoder().encode(s)).then(function(buf){
      return Array.prototype.map.call(new Uint8Array(buf), function(b){
        return b.toString(16).padStart(2, "0");
      }).join("");
    });
  }
  function download(name, content, type){
    var blob = new Blob([content], {type: type || "text/plain"});
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a);
    a.click();
    setTimeout(function(){ URL.revokeObjectURL(a.href); a.remove(); }, 2000);
  }

  // prefill default passwords
  DATA.phases.forEach(function(p){ $("pw" + p.n).value = p.defPw; });

  function collect(){
    var f = {
      version: 1,
      program: "founder-kit",
      created: new Date().toISOString().slice(0, 10),
      codename: $("codename").value.trim(),
      budget: $("budget").value,
      rewards: {},
      passwords: {}
    };
    for (var i = 1; i <= 6; i++) f.rewards[i] = $("reward" + i).value.trim();
    DATA.phases.forEach(function(p){ f.passwords[p.n] = $("pw" + p.n).value.trim(); });
    return f;
  }
  function restore(f){
    $("codename").value = f.codename || "";
    if (f.budget) $("budget").value = f.budget;
    for (var i = 1; i <= 6; i++) $("reward" + i).value = (f.rewards && f.rewards[i]) || "";
    DATA.phases.forEach(function(p){
      if (f.passwords && f.passwords[p.n]) $("pw" + p.n).value = f.passwords[p.n];
    });
  }
  function validate(f){
    var bad = [];
    ["codename"].forEach(function(id){ $(id).classList.remove("err"); });
    DATA.phases.forEach(function(p){
      $("reward" + p.n).classList.remove("err");
      $("pw" + p.n).classList.remove("err");
    });
    if (!f.codename){ bad.push("codename"); $("codename").classList.add("err"); }
    DATA.phases.forEach(function(p){
      if (!f.rewards[p.n]){ bad.push("Phase " + p.n + " reward"); $("reward" + p.n).classList.add("err"); }
      if (!/^[A-Za-z0-9]+$/.test(f.passwords[p.n] || "")){
        bad.push("Phase " + p.n + " password (letters and numbers only)"); $("pw" + p.n).classList.add("err");
      }
    });
    return bad;
  }

  function buildPage(p, f){
    var body = b64decode(p.body)
      .split("{{CODENAME}}").join(esc(f.codename))
      .split("{{REWARD}}").join(esc(f.rewards[p.n]));
    var pw = f.passwords[p.n];
    return sha256(pw.toLowerCase()).then(function(hash){
      var page = b64decode(DATA.template);
      var tokens = {
        PHASE: String(p.n),
        TITLE: p.title,
        SOURCE_CSS: b64decode(p.css),
        ENC_LABEL: p.enc.toUpperCase(),
        ENC_HINT: p.hint,
        ACCESS_CODE: ENCODE[p.enc](pw),
        PW_HASH: hash,
        PAYLOAD: b64encode(body),
        LS_KEY: "ca_ft_kit_phase" + p.n,
        PARENTS_NOTE: DATA.coachNote,
        BACK_LINK: ""
      };
      Object.keys(tokens).forEach(function(k){
        page = page.split("@@" + k + "@@").join(tokens[k]);
      });
      return page;
    });
  }

  $("gen").addEventListener("click", function(){
    var f = collect();
    var bad = validate(f);
    if (bad.length){ say("bad", "MISSING: " + bad.join(", ")); return; }
    if (!(window.crypto && crypto.subtle)){ say("bad", "THIS BROWSER CAN'T BUILD THE LOCKS. TRY ANOTHER."); return; }
    say("ok", "GENERATING...");
    Promise.all(DATA.phases.map(function(p){ return buildPage(p, f); })).then(function(pages){
      var codes = "CODES.TXT -- COACH EYES ONLY\n" +
                  "============================\n\n" +
                  "OPERATIVE: " + f.codename + "   BUDGET DIAL: " + f.budget + "\n" +
                  "Generated " + f.created + " by Mission Config. Keep away from your operative.\n\n";
      DATA.phases.forEach(function(p, i){
        codes += "PHASE " + p.n + " (" + p.title + ")\n" +
                 "  access code (" + p.enc.toUpperCase() + "): " + ENCODE[p.enc](f.passwords[p.n]) + "\n" +
                 "  password: " + f.passwords[p.n] + "\n" +
                 "  reward: " + f.rewards[p.n] + "\n\n";
        setTimeout(function(){ download("PHASE-" + p.n + "_FIELD-TEST.html", pages[i], "text/html"); }, i * 300);
      });
      var after = DATA.phases.length * 300;
      setTimeout(function(){ download("CODES.txt", codes); }, after + 300);
      setTimeout(function(){ download("family-file.json", JSON.stringify(f, null, 2), "application/json"); }, after + 600);
      say("ok", "◆ KIT GENERATED. " + DATA.phases.length + " field tests + CODES.txt + family-file.json are downloading. Give the field tests to " + f.codename + ". CODES.txt is yours.");
    }).catch(function(e){ say("bad", "GENERATION FAILED: " + e); });
  });

  $("save").addEventListener("click", function(){
    download("family-file.json", JSON.stringify(collect(), null, 2), "application/json");
    say("ok", "◆ FAMILY FILE SAVED.");
  });

  $("load").addEventListener("click", function(){ $("loadFile").click(); });
  $("loadFile").addEventListener("change", function(){
    var file = this.files[0];
    if (!file) return;
    file.text().then(function(t){
      try { restore(JSON.parse(t)); say("ok", "◆ FAMILY FILE LOADED."); }
      catch(e){ say("bad", "THAT FILE ISN'T A FAMILY FILE."); }
    });
    this.value = "";
  });
})();
</script>
</body>
</html>
"""


def b64(text):
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="dist directory for the kit + zip")
    ap.add_argument("--curriculum",
                    default=str(pathlib.Path.home() / "Desktop/claude-actually/curriculum"))
    args = ap.parse_args()

    curriculum = pathlib.Path(args.curriculum)
    out = pathlib.Path(args.out)
    kit = out / KIT_NAME
    if kit.exists():
        shutil.rmtree(kit)
    (kit / "field-tests").mkdir(parents=True)

    # --- mission-config.html ---
    import re
    data = {"template": b64(TEMPLATE.read_text(encoding="utf-8")),
            "coachNote": COACH_NOTE, "phases": []}
    for p in PHASES:
        src = (curriculum / p["coach_src"]).read_text(encoding="utf-8")
        css = re.search(r"<style>(.*?)</style>", src, re.S).group(1).strip("\n")
        body = re.search(r"<body>(.*?)</body>", src, re.S).group(1).strip("\n")
        data["phases"].append({
            "n": p["n"], "title": p["title"], "enc": p["enc"],
            "defPw": p["password"], "hint": ENCODERS[p["enc"]]["hint"],
            "css": b64(css), "body": b64(body),
        })
    (kit / "mission-config.html").write_text(
        CONFIG_PAGE.replace("%%DATA%%", json.dumps(data)), encoding="utf-8")

    # --- ready-made default field tests (neutral copy, kit default codes) ---
    code_lines = ""
    for p in PHASES:
        src = (curriculum / p["site_src"]).read_text(encoding="utf-8")
        page = render(build_tokens(src, p["n"], p["title"], p["password"], p["enc"],
                                   parents_note=COACH_NOTE, back_link="",
                                   ls_prefix="ca_ft_kit_phase"))
        (kit / "field-tests" / f"PHASE-{p['n']}_FIELD-TEST.html").write_text(page, encoding="utf-8")
        code_lines += (f"PHASE {p['n']} ({p['title']})\n"
                       f"  access code ({p['enc'].upper()}): {ENCODERS[p['enc']]['encode'](p['password'])}\n"
                       f"  password: {p['password']}\n\n")
    (kit / "CODES.txt").write_text(CODES_TXT.format(lines=code_lines), encoding="utf-8")
    (kit / "README.txt").write_text(README, encoding="utf-8")

    # --- PDFs ---
    for name in PDFS:
        src = curriculum / "pdf" / name
        if not src.exists():
            sys.exit(f"missing PDF: {src} (run curriculum/_regen_pdfs.py first)")
        shutil.copy2(src, kit / name)

    # --- zip ---
    zip_path = out / f"{KIT_NAME}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(kit.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(out))
    print(f"kit dir: {kit}")
    print(f"zip:     {zip_path}  ({zip_path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
