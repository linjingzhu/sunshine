#!/usr/bin/env python3
"""Build the runtime-gate working sheet from the documents that own it.

`gate-sheet.html` carries all forty-three gates verbatim. A hand-written copy
of that table would be a second list, and this repository's whole objection to
second lists is that they drift from the first one silently -- the same
argument `docs/SIZE_BUDGET.md` makes about `chrome.release`, and the same one
`scripts/measure_shipped_size.py` acts on.

So the sheet is generated. `docs/RUNTIME_VERIFICATION.md` owns each gate's step
and expectation; `docs/RETURN_RUN_SHEET.md` owns which block a gate runs in,
what that block needs, and how long it takes. Neither is transcribed here.

What *is* here, because no document owns it: the Korean block titles and the
short guidance a person reads while working, the three surfaces that have no RV
number yet, and the presentation.

Run it after either document changes:

    python3 scripts/build_gate_sheet.py

Gate text is left in English on purpose. It is contract wording, and a
translation would be a paraphrase of a rule rather than the rule.
"""

from __future__ import annotations

import html
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "gate-sheet.html"

BUILD = "#40 (6b86cc7)"
# Named for the revision, not "pinned": `scripts/verify_no_interposition.py`
# reads a field called `PINNED` as a tab-pinned flag, and it is right to --
# the word means two unrelated things in this project and this one is the
# Chromium revision.
REVISION = "152.0.7977.42"

# Korean titles for the blocks the run sheet names in English, plus the note a
# person reads before starting one. Keyed by the block letter the run sheet
# uses, so a block added there without an entry here fails loudly below.
BLOCK_TITLES = {
    "A": ("실행 전 — 파일과 레지스트리",
          "A가 먼저인 이유: 여기 게이트는 실행이 바꿀 수 없는 파일과 레지스트리 키에 관한 것입니다. "
          "아무것도 돌지 않을 때 답해야 모호하지 않습니다."),
    "B": ("보안 posture — 첫 실행",
          "RV-1·2·3 중 하나라도 실패하면 세션을 중단하십시오. 샌드박스나 격리가 계약과 다른 "
          "브라우저로 아래를 계속 도는 것은 기록할 가치가 없습니다."),
    "C": ("이게 Sunshine인가", ""),
    "D": ("새 탭", ""),
    "E": ("미디어", ""),
    "E2": ("마우스 제스처",
           "빌드 #40에서 처음 컴파일된 패치 0017입니다. 이 인스톨러 또는 이후 것으로만 실행하십시오."),
    "F": ("북마크바와 모듈 홈", ""),
    "G": ("모듈 셸", ""),
    "H": ("문서 표면", ""),
}

STOP_HARD = {"RV-1", "RV-2", "RV-3"}
STOP_BLOCK = {"RV-26", "RV-29", "RV-30"}
CONDITIONAL = {
    "RV-28": "같은 기계에 실제 Chromium 또는 Chrome이 설치돼 있어야 합니다. 없으면 NOT RUN 이 결과입니다.",
}
BLOCKED = {
    "RV-35": "마운트를 선언한 모듈이 없습니다. 열 프레임도, 파괴할 프레임도 없습니다.",
    "RV-36": "같은 원인. 마운트된 모듈 둘을 오가려면 마운트된 모듈이 둘 있어야 합니다.",
}
DONE = {
    "RV-7": "빌드 #12 (커밋 6aa75ff) 에서 PASS 기록됨. 이 시트의 유일한 기존 증거입니다.",
}

# Surfaces that ship in the build and have no RV number. Deliberately not given
# PASS/FAIL controls: marking one PASS would assert a contract that does not
# exist. What a reader writes here is the input to defining a gate.
UNGATED = [
    ("인스톨러 대화창",
     "sunshine-setup.exe 를 실행했을 때 창이 뜨는가. 경로 선택, 바로가기 체크박스, 배너 이미지. "
     "배너는 플레이스홀더이고 비율이 약 7% 눌려 보이는 것이 알려진 상태입니다."),
    ("계정 페이지",
     "chrome://sunshine-account. 이 빌드에는 OAuth 클라이언트가 없으므로 "
     "'이 빌드는 제공하지 않는다'가 정상 동작입니다. 모듈 홈에 줄이 있는지도 함께."),
    ("새 탭 배경",
     "설치 폴더의 chrome.exe 옆(버전 디렉터리 아님)에 newtab-background.png / .jpg / .webp 를 놓고 "
     "새 탭을 여십시오. PNG·JPEG·WebP만 받고, APNG와 애니메이션 WebP도 각각 png·webp로 들어갑니다. "
     "32MB를 넘으면 거부됩니다. "
     "안 나올 경우 이유를 알 방법이 없습니다 — 파일 없음, 크기 초과, 형식 불일치가 모두 같은 결과입니다. "
     "그리고 브라우저를 켠 직후 첫 새 탭은 배경이 없을 수 있습니다(탐지가 프로세스당 한 번, "
     "그리는 스레드 밖에서 돕니다). 두 번째 탭부터 정상이면 그것은 알려진 경합이지 결함이 아닙니다. "
     "파일을 넣기 전에 새 탭을 한 번 열어보시면 대조가 됩니다 — 배경이 없을 때는 프레임 자체가 만들어지지 않습니다."),
]

GATE_ROW = re.compile(r"^\| (RV-\d+|RVV-\d+) \| (.*?) \| (.*?) \|(?: (.*?) \|)?\s*$", re.M)
BLOCK_ROW = re.compile(
    r"^\| \*\*([A-Z]\d?) — [^|]*\*\* \| ([^|]+) \| ([^|]+) \| ([^|]+) \|\s*$", re.M)


def gates(root: Path) -> dict[str, dict[str, str]]:
    text = (root / "docs/RUNTIME_VERIFICATION.md").read_text(encoding="utf-8")
    found = {}
    for match in GATE_ROW.finditer(text):
        found[match.group(1)] = {
            "id": match.group(1),
            "step": match.group(2).strip(),
            "expected": match.group(3).strip(),
            "invariant": (match.group(4) or "").strip(),
        }
    return found


def blocks(root: Path) -> list[tuple[str, list[str], str, str]]:
    text = (root / "docs/RETURN_RUN_SHEET.md").read_text(encoding="utf-8")
    found = []
    for match in BLOCK_ROW.finditer(text):
        letter = match.group(1)
        ids = [part.strip() for part in match.group(2).split(",") if part.strip()]
        needs = re.sub(r"`", "", match.group(3)).strip()
        minutes = match.group(4).strip()
        found.append((letter, ids, needs, minutes))
    return found


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def gate_row(gate: dict[str, str], badge: str = "") -> str:
    inv = f'<span class="inv">{esc(gate["invariant"])}</span>' if gate["invariant"] else ""
    return f"""
      <div class="gate" data-gate="{gate['id']}">
        <div class="stripe" aria-hidden="true"></div>
        <div class="gid"><span class="idtag">{gate['id']}</span>{badge}</div>
        <div class="body">
          <p class="step">{esc(gate['step'])}</p>
          <p class="exp"><span class="explabel">기대</span>{esc(gate['expected'])}</p>
          {inv}
        </div>
        <div class="controls">
          <div class="states" role="group" aria-label="{gate['id']} 결과">
            <button type="button" class="st st-pass" data-state="pass">PASS</button>
            <button type="button" class="st st-fail" data-state="fail">FAIL</button>
            <button type="button" class="st st-na"   data-state="na">NOT RUN</button>
          </div>
          <textarea class="note" rows="1" placeholder="관찰한 것 — 실패면 무엇이 보였는지"></textarea>
        </div>
      </div>"""


def locked_row(gate: dict[str, str], label: str, why: str, kind: str, control: str) -> str:
    return f"""
      <div class="gate is-{kind}" data-gate="{gate['id']}">
        <div class="stripe" aria-hidden="true"></div>
        <div class="gid"><span class="idtag">{gate['id']}</span></div>
        <div class="body">
          <p class="step">{esc(gate['step'])}</p>
          <p class="exp"><span class="explabel">{label}</span>{esc(why)}</p>
        </div>
        <div class="controls">{control}</div>
      </div>"""


def build(root: Path = ROOT) -> str:
    gate = gates(root)
    if len(gate) != 43:
        raise SystemExit(f"expected 43 gates in RUNTIME_VERIFICATION.md, parsed {len(gate)}")

    sections = []
    scheduled = set()
    for letter, ids, needs, minutes in blocks(root):
        if letter not in BLOCK_TITLES:
            raise SystemExit(f"block {letter} has no Korean title in BLOCK_TITLES")
        title, note = BLOCK_TITLES[letter]
        rows = []
        for gid in ids:
            if gid not in gate:
                raise SystemExit(f"run sheet block {letter} names {gid}, which no gate table defines")
            scheduled.add(gid)
            badge = ""
            if gid in STOP_HARD:
                badge = '<span class="badge stop">중단</span>'
            elif gid in STOP_BLOCK:
                badge = '<span class="badge stopb">블록 후 중단</span>'
            elif gid in CONDITIONAL:
                badge = '<span class="badge cond">조건부</span>'
            rows.append(gate_row(gate[gid], badge))
            if gid in CONDITIONAL:
                rows.append(f'<p class="rowhint">{esc(CONDITIONAL[gid])}</p>')
        note_html = f'<p class="blocknote">{esc(note)}</p>' if note else ""
        sections.append(f"""
    <section class="block" id="block-{letter}">
      <header class="bhead">
        <span class="letter">{letter}</span>
        <div class="bmeta">
          <h2>{esc(title)}</h2>
          <p class="needs"><span class="nlabel">준비</span>{esc(needs)} <span class="dot">·</span> <span class="mins">{esc(minutes)}</span></p>
        </div>
        <span class="bcount" data-block="{letter}">0/{len(ids)}</span>
      </header>
      {note_html}
      <div class="gates">{"".join(rows)}</div>
    </section>""")

    for gid in list(BLOCKED) + list(DONE):
        if gid in scheduled:
            raise SystemExit(f"{gid} is both scheduled by the run sheet and listed as unrunnable here")

    blocked_html = "".join(
        locked_row(gate[gid], "막힌 이유", why, "blocked",
                   '<span class="locknote">실행 불가</span>')
        for gid, why in BLOCKED.items())
    done_html = "".join(
        locked_row(gate[gid], "기록됨", why, "done",
                   '<span class="lockdone">PASS</span>')
        for gid, why in DONE.items())
    ungated_html = "".join(
        f"""
      <div class="gate is-ungated" data-gate="UG-{index}">
        <div class="stripe" aria-hidden="true"></div>
        <div class="gid"><span class="idtag">UG-{index}</span></div>
        <div class="body">
          <p class="step">{esc(title)}</p>
          <p class="exp"><span class="explabel">배경</span>{esc(detail)}</p>
        </div>
        <div class="controls">
          <div class="states" role="group" aria-label="UG-{index} 결과">
            <button type="button" class="st st-pass" data-state="pass">좋음</button>
            <button type="button" class="st st-fail" data-state="fail">문제</button>
            <button type="button" class="st st-na"   data-state="na">안 봄</button>
          </div>
          <textarea class="note" rows="1" placeholder="본 것을 그대로"></textarea>
        </div>
      </div>"""
        for index, (title, detail) in enumerate(UNGATED, start=1))

    return CSS + SHELL.format(
        build=esc(BUILD), revision=esc(REVISION),
        total=len(gate), blocks="".join(sections),
        blocked=blocked_html, done=done_html, ungated=ungated_html,
        ungated_count=len(UNGATED),
    ) + SCRIPT


def main() -> int:
    OUT.write_text(build(), encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}")
    return 0


CSS = r"""<title>Sunshine 런타임 게이트</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>
:root{
  --ink:#16191F; --ink-2:#454D59; --ink-3:#6B7480;
  --ground:#EEF1F5; --surface:#FFFFFF; --surface-2:#F7F9FB;
  --rule:#D3D9E1; --rule-2:#E4E9EF;
  --accent:#2B5CE6; --accent-soft:#E7EDFD;
  --pass:#136F42; --pass-soft:#DFF1E7;
  --fail:#B3312A; --fail-soft:#FBE5E3;
  --na:#6B7480;  --na-soft:#E9ECF1;
  --warn:#9A6512; --warn-soft:#FAEEDA;
  --shadow:0 1px 2px rgba(22,25,31,.06),0 8px 24px -16px rgba(22,25,31,.28);
}
@media (prefers-color-scheme: dark){ :root:not([data-theme="light"]){
  --ink:#E6EAF1; --ink-2:#A9B2BF; --ink-3:#7F8895;
  --ground:#101318; --surface:#191D24; --surface-2:#1F242C;
  --rule:#2E353F; --rule-2:#252B33;
  --accent:#7CA2FF; --accent-soft:#1B2740;
  --pass:#54C48A; --pass-soft:#14301F;
  --fail:#F27C6B; --fail-soft:#3A1D19;
  --na:#8A93A0;  --na-soft:#22272F;
  --warn:#D9A24E; --warn-soft:#332612;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 8px 24px -16px rgba(0,0,0,.7);
}}
:root[data-theme="dark"]{
  --ink:#E6EAF1; --ink-2:#A9B2BF; --ink-3:#7F8895;
  --ground:#101318; --surface:#191D24; --surface-2:#1F242C;
  --rule:#2E353F; --rule-2:#252B33;
  --accent:#7CA2FF; --accent-soft:#1B2740;
  --pass:#54C48A; --pass-soft:#14301F;
  --fail:#F27C6B; --fail-soft:#3A1D19;
  --na:#8A93A0;  --na-soft:#22272F;
  --warn:#D9A24E; --warn-soft:#332612;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 8px 24px -16px rgba(0,0,0,.7);
}
*{box-sizing:border-box}
body{
  margin:0; background:var(--ground); color:var(--ink);
  font-family:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif;
  font-size:15px; line-height:1.55; -webkit-font-smoothing:antialiased;
}
.wrap{max-width:1080px;margin:0 auto;padding:0 20px 96px}
/* ---- masthead ---- */
.mast{padding:44px 0 24px;border-bottom:2px solid var(--ink)}
.eyebrow{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:11.5px;letter-spacing:.13em;
  text-transform:uppercase;color:var(--ink-3);margin:0 0 10px}
h1{font-family:Archivo,system-ui,sans-serif;font-weight:700;font-size:clamp(28px,4.6vw,44px);
  line-height:1.04;letter-spacing:-.021em;margin:0;text-wrap:balance}
.sub{margin:12px 0 0;max-width:64ch;color:var(--ink-2)}
.sub strong{color:var(--ink);font-weight:600}
/* ---- summary ---- */
.summary{position:sticky;top:0;z-index:30;background:var(--ground);
  border-bottom:1px solid var(--rule);margin:0 -20px;padding:12px 20px}
.srow{display:flex;flex-wrap:wrap;gap:12px;align-items:center;max-width:1080px;margin:0 auto}
.tally{display:flex;gap:6px;flex-wrap:wrap}
.chip{font-family:"IBM Plex Mono",monospace;font-size:12px;font-weight:600;
  padding:5px 9px;border-radius:3px;border:1px solid var(--rule);background:var(--surface);
  font-variant-numeric:tabular-nums;white-space:nowrap}
.chip.c-pass{color:var(--pass);background:var(--pass-soft);border-color:transparent}
.chip.c-fail{color:var(--fail);background:var(--fail-soft);border-color:transparent}
.chip.c-na{color:var(--na);background:var(--na-soft);border-color:transparent}
.chip.c-left{color:var(--ink-2)}
.bar{flex:1 1 180px;min-width:140px;height:6px;border-radius:99px;background:var(--rule-2);
  overflow:hidden;display:flex}
.bar i{display:block;height:100%}
.bar .b-pass{background:var(--pass)} .bar .b-fail{background:var(--fail)} .bar .b-na{background:var(--na)}
.acts{display:flex;gap:8px;margin-left:auto}
button.act{font-family:"IBM Plex Sans",sans-serif;font-size:13px;font-weight:600;cursor:pointer;
  padding:8px 14px;border-radius:4px;border:1px solid var(--rule);background:var(--surface);color:var(--ink)}
button.act:hover{border-color:var(--accent);color:var(--accent)}
button.act.primary{background:var(--accent);border-color:var(--accent);color:#fff}
button.act.primary:hover{filter:brightness(1.08);color:#fff}
button.act:focus-visible,.st:focus-visible,.note:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
/* ---- stop rules ---- */
.rules{margin:28px 0 0;border:1px solid var(--rule);border-left:3px solid var(--warn);
  border-radius:4px;background:var(--surface);padding:16px 18px}
.rules h3{font-family:Archivo,sans-serif;font-size:13px;letter-spacing:.06em;text-transform:uppercase;
  margin:0 0 10px;color:var(--warn)}
.rules dl{margin:0;display:grid;grid-template-columns:auto 1fr;gap:6px 14px;font-size:14px}
.rules dt{font-family:"IBM Plex Mono",monospace;font-weight:600;font-size:12.5px;white-space:nowrap;color:var(--ink)}
.rules dd{margin:0;color:var(--ink-2)}
/* ---- blocks ---- */
.block{margin-top:38px}
.bhead{display:flex;align-items:flex-start;gap:14px;padding-bottom:10px;border-bottom:1px solid var(--ink)}
.letter{font-family:Archivo,sans-serif;font-weight:700;font-size:26px;line-height:1;
  min-width:44px;height:38px;display:flex;align-items:center;justify-content:center;
  background:var(--ink);color:var(--ground);border-radius:3px;letter-spacing:-.02em}
.bmeta{flex:1}
.bmeta h2{font-family:Archivo,sans-serif;font-weight:600;font-size:19px;margin:0;letter-spacing:-.012em}
.needs{margin:3px 0 0;font-size:13px;color:var(--ink-3)}
.nlabel{font-family:"IBM Plex Mono",monospace;font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;
  color:var(--ink-3);margin-right:7px}
.mins{font-variant-numeric:tabular-nums}
.dot{opacity:.5;margin:0 2px}
.bcount{font-family:"IBM Plex Mono",monospace;font-size:12.5px;font-weight:600;color:var(--ink-3);
  font-variant-numeric:tabular-nums;padding-top:9px;white-space:nowrap}
.blocknote{margin:12px 0 0;font-size:13.5px;color:var(--ink-2);border-left:2px solid var(--rule);
  padding-left:12px;max-width:70ch}
.gates{margin-top:14px;display:flex;flex-direction:column;gap:8px}
/* ---- one gate ---- */
.gate{position:relative;display:grid;grid-template-columns:104px minmax(0,1fr) 268px;gap:16px;
  background:var(--surface);border:1px solid var(--rule-2);border-radius:4px;
  padding:14px 16px 14px 19px;box-shadow:var(--shadow);overflow:hidden}
.stripe{position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--rule)}
.gate[data-result="pass"] .stripe{background:var(--pass)}
.gate[data-result="fail"] .stripe{background:var(--fail)}
.gate[data-result="na"]   .stripe{background:var(--na)}
.gate[data-result="fail"]{border-color:var(--fail)}
.gid{display:flex;flex-direction:column;gap:6px;align-items:flex-start}
.idtag{font-family:"IBM Plex Mono",monospace;font-size:13px;font-weight:600;letter-spacing:-.01em}
.badge{font-family:"IBM Plex Mono",monospace;font-size:10px;font-weight:600;letter-spacing:.05em;
  padding:3px 6px;border-radius:3px;white-space:nowrap}
.badge.stop{background:var(--fail-soft);color:var(--fail)}
.badge.stopb{background:var(--warn-soft);color:var(--warn)}
.badge.cond{background:var(--na-soft);color:var(--na)}
.body{min-width:0}
.step{margin:0;font-size:14.5px;line-height:1.5}
.exp{margin:7px 0 0;font-size:13.5px;color:var(--ink-2);line-height:1.5}
.explabel{font-family:"IBM Plex Mono",monospace;font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;
  color:var(--ink-3);margin-right:7px}
.inv{display:inline-block;margin-top:8px;font-family:"IBM Plex Mono",monospace;font-size:11px;
  color:var(--ink-3);background:var(--surface-2);border:1px solid var(--rule-2);
  padding:2px 6px;border-radius:3px}
.controls{display:flex;flex-direction:column;gap:8px}
.states{display:flex;gap:5px}
.st{flex:1;font-family:"IBM Plex Mono",monospace;font-size:11px;font-weight:600;letter-spacing:.03em;
  cursor:pointer;padding:7px 4px;border-radius:3px;border:1px solid var(--rule);
  background:var(--surface);color:var(--ink-3);transition:background .12s,color .12s,border-color .12s}
.st:hover{border-color:var(--ink-3);color:var(--ink)}
.st-pass[aria-pressed="true"]{background:var(--pass);border-color:var(--pass);color:#fff}
.st-fail[aria-pressed="true"]{background:var(--fail);border-color:var(--fail);color:#fff}
.st-na[aria-pressed="true"]{background:var(--na);border-color:var(--na);color:#fff}
.note{width:100%;resize:vertical;min-height:34px;font-family:"IBM Plex Sans",sans-serif;font-size:13px;
  color:var(--ink);background:var(--surface-2);border:1px solid var(--rule-2);border-radius:3px;
  padding:7px 9px;line-height:1.45}
.note::placeholder{color:var(--ink-3)}
.gate[data-result="fail"] .note{border-color:var(--fail);background:var(--fail-soft)}
.rowhint{margin:0 0 0 4px;font-size:12.5px;color:var(--ink-3);border-left:2px solid var(--rule);padding-left:10px}
.locknote,.lockdone{font-family:"IBM Plex Mono",monospace;font-size:11px;font-weight:600;
  padding:7px 9px;border-radius:3px;text-align:center}
.locknote{background:var(--na-soft);color:var(--na)}
.lockdone{background:var(--pass-soft);color:var(--pass)}
.gate.is-blocked,.gate.is-done{opacity:.85}
.gate.is-blocked .stripe{background:var(--na)}
.gate.is-done .stripe{background:var(--pass)}
.gate.is-ungated .stripe{background:var(--accent)}
/* ---- report ---- */
.report{margin-top:44px;border-top:2px solid var(--ink);padding-top:20px}
.report h2{font-family:Archivo,sans-serif;font-size:19px;margin:0 0 6px}
.report p{margin:0 0 14px;color:var(--ink-2);max-width:66ch;font-size:14px}
#out{width:100%;min-height:190px;font-family:"IBM Plex Mono",monospace;font-size:12px;line-height:1.5;
  background:var(--surface);color:var(--ink);border:1px solid var(--rule);border-radius:4px;padding:12px}
.saved{font-family:"IBM Plex Mono",monospace;font-size:11.5px;color:var(--ink-3)}
@media (max-width:860px){
  .gate{grid-template-columns:1fr;gap:12px}
  .gid{flex-direction:row;align-items:center;gap:8px}
  .summary{position:static}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
</style>

"""

SHELL = """<div class="wrap">
  <header class="mast">
    <p class="eyebrow">Sunshine OS · {revision} · 빌드 {build}</p>
    <h1>런타임 게이트 확인 시트</h1>
    <p class="sub">패치 21개가 컴파일됩니다. 게이트 {total}개 중 <strong>실행된 것은 1개</strong>입니다.
    아래는 <code>docs/RETURN_RUN_SHEET.md</code>의 순서 그대로이고, 각 게이트의 문장은
    <code>docs/RUNTIME_VERIFICATION.md</code>에서 그대로 가져왔습니다 — 계약 문구라 번역하지 않았습니다.</p>
  </header>

  <div class="summary">
    <div class="srow">
      <div class="tally">
        <span class="chip c-pass" id="t-pass">PASS 0</span>
        <span class="chip c-fail" id="t-fail">FAIL 0</span>
        <span class="chip c-na"   id="t-na">NOT RUN 0</span>
        <span class="chip c-left" id="t-left">남음 0</span>
      </div>
      <div class="bar" aria-hidden="true"><i class="b-pass" id="bp"></i><i class="b-fail" id="bf"></i><i class="b-na" id="bn"></i></div>
      <div class="acts">
        <button type="button" class="act" id="reset">비우기</button>
        <button type="button" class="act primary" id="copy">결과 복사</button>
      </div>
    </div>
  </div>

  <section class="rules">
    <h3>중단 규칙</h3>
    <dl>
      <dt>RV-1 · RV-2 · RV-3</dt>
      <dd><strong>세션 중단.</strong> 샌드박스나 격리 posture가 틀렸다면, 그 아래 모든 게이트는 계약이 설명하는 것과 다른 보안 모델의 브라우저에서 도는 것입니다. 기록할 가치가 없습니다.</dd>
      <dt>RV-26 · RV-29 · RV-30</dt>
      <dd>블록 A를 끝내고 중단. 인스톨러 정체성이고 ADR 0015의 주제 전체이며, 실패는 나머지를 돌기 전에 인스톨러를 다시 만들어야 한다는 뜻입니다.</dd>
      <dt>그 외</dt>
      <dd>기록하고 계속. 한 표면의 실패가 다음 표면에 대해 말해주는 것은 없습니다.</dd>
    </dl>
  </section>

  <p class="sub" style="margin-top:26px">읽을 수 없는 게이트는 <strong>PASS가 아니라 NOT RUN</strong>입니다.
  <code>chrome://sandbox</code>와 <code>chrome://process-internals</code>는 업스트림 디버깅 표면이라 핀에서 출력이 달라졌을 수 있습니다. 행을 못 찾으면 그것이 결과입니다.</p>
{blocks}

  <section class="block">
    <header class="bhead">
      <span class="letter" style="background:var(--na)">—</span>
      <div class="bmeta">
        <h2>실행할 수 없는 게이트</h2>
        <p class="needs"><span class="nlabel">이유</span>마운트를 선언한 모듈이 없음 <span class="dot">·</span> 마운트 생명주기는 셸 seam이 존재하는 이유입니다</p>
      </div>
    </header>
    <div class="gates">{blocked}</div>
  </section>

  <section class="block">
    <header class="bhead">
      <span class="letter" style="background:var(--pass)">✓</span>
      <div class="bmeta">
        <h2>이미 증거가 있는 게이트</h2>
        <p class="needs"><span class="nlabel">범위</span>기록된 빌드가 담고 있던 것만 해소합니다</p>
      </div>
    </header>
    <div class="gates">{done}</div>
  </section>

  <section class="block">
    <header class="bhead">
      <span class="letter" style="background:var(--accent)">?</span>
      <div class="bmeta">
        <h2>아직 게이트가 없는 표면</h2>
        <p class="needs"><span class="nlabel">주의</span>계약이 정한 게이트가 아닙니다 — 자유 관찰입니다</p>
      </div>
      <span class="bcount" data-block="UG">0/{ungated_count}</span>
    </header>
    <p class="blocknote">이 셋은 빌드에 들어 있지만 RV 번호가 없습니다. 여기 적어주시는 관찰이 게이트를 정의하는 입력이 됩니다 — 그래서 PASS/FAIL 대신 좋음/문제로 두었습니다.</p>
    <div class="gates">{ungated}</div>
  </section>

  <section class="report">
    <h2>결과 넘기기</h2>
    <p><strong>결과 복사</strong>를 누르면 아래 상자가 채워지고 클립보드에 들어갑니다. 그대로 붙여넣어 주시면 됩니다.
    입력은 이 브라우저에 자동 저장되니 중간에 닫으셔도 됩니다.</p>
    <textarea id="out" readonly placeholder="아직 표시할 결과가 없습니다."></textarea>
    <p class="saved" id="saved" style="margin-top:8px"></p>
  </section>
</div>

"""

SCRIPT = r"""<script>
(function(){
  var KEY = "sunshine-gate-sheet-v1";
  var gates = Array.prototype.slice.call(document.querySelectorAll(".gate"));
  var live  = gates.filter(function(g){ return g.querySelector(".states"); });

  function load(){
    try { return JSON.parse(localStorage.getItem(KEY) || "{}"); } catch(e){ return {}; }
  }
  function save(state){
    try {
      localStorage.setItem(KEY, JSON.stringify(state));
      document.getElementById("saved").textContent =
        "이 브라우저에 저장됨 · " + new Date().toLocaleString();
    } catch(e){
      document.getElementById("saved").textContent =
        "저장할 수 없습니다 (비공개 창이거나 사이트 데이터가 차단됨). 창을 닫기 전에 결과를 복사하십시오.";
    }
  }
  var state = load();

  function paint(){
    var n = {pass:0, fail:0, na:0};
    live.forEach(function(g){
      var id = g.dataset.gate, r = (state[id]||{}).r || "";
      if (r) { g.setAttribute("data-result", r); n[r]++; }
      else g.removeAttribute("data-result");
      g.querySelectorAll(".st").forEach(function(b){
        b.setAttribute("aria-pressed", String(b.dataset.state === r));
      });
      var note = g.querySelector(".note");
      if (note && note.value !== ((state[id]||{}).n || "")) note.value = (state[id]||{}).n || "";
    });
    var total = live.length, answered = n.pass + n.fail + n.na;
    document.getElementById("t-pass").textContent = "PASS " + n.pass;
    document.getElementById("t-fail").textContent = "FAIL " + n.fail;
    document.getElementById("t-na").textContent   = "NOT RUN " + n.na;
    document.getElementById("t-left").textContent = "남음 " + (total - answered);
    document.getElementById("bp").style.width = (n.pass/total*100) + "%";
    document.getElementById("bf").style.width = (n.fail/total*100) + "%";
    document.getElementById("bn").style.width = (n.na/total*100)   + "%";
    document.querySelectorAll(".bcount").forEach(function(c){
      var sec = c.closest(".block");
      var rows = sec.querySelectorAll(".gate .states");
      var doneN = 0;
      sec.querySelectorAll(".gate").forEach(function(g){
        if (g.querySelector(".states") && (state[g.dataset.gate]||{}).r) doneN++;
      });
      c.textContent = doneN + "/" + rows.length;
    });
  }

  document.addEventListener("click", function(e){
    var b = e.target.closest(".st");
    if (!b) return;
    var g = b.closest(".gate"), id = g.dataset.gate;
    state[id] = state[id] || {};
    state[id].r = (state[id].r === b.dataset.state) ? "" : b.dataset.state;
    save(state); paint();
  });
  document.addEventListener("input", function(e){
    var t = e.target;
    if (!t.classList || !t.classList.contains("note")) return;
    var id = t.closest(".gate").dataset.gate;
    state[id] = state[id] || {};
    state[id].n = t.value;
    t.style.height = "auto"; t.style.height = (t.scrollHeight + 2) + "px";
    save(state);
  });

  document.getElementById("reset").addEventListener("click", function(){
    if (!confirm("입력한 결과와 메모를 모두 지웁니다. 계속할까요?")) return;
    state = {}; save(state); paint();
    document.getElementById("out").value = "";
  });

  function report(){
    var L = [];
    L.push("# Sunshine 런타임 게이트 결과");
    L.push("");
    L.push("- 빌드: #40 (6b86cc7), 152.0.7977.42");
    L.push("- 작성: " + new Date().toLocaleString());
    var n = {pass:0, fail:0, na:0};
    live.forEach(function(g){ var r=(state[g.dataset.gate]||{}).r; if(r) n[r]++; });
    L.push("- 합계: PASS " + n.pass + " / FAIL " + n.fail + " / NOT RUN " + n.na +
           " / 남음 " + (live.length - n.pass - n.fail - n.na));
    L.push("");
    document.querySelectorAll(".block").forEach(function(sec){
      var rows = Array.prototype.slice.call(sec.querySelectorAll(".gate"))
        .filter(function(g){ return g.querySelector(".states") && (state[g.dataset.gate]||{}).r; });
      if (!rows.length) return;
      var head = sec.querySelector(".letter").textContent.trim() + " — " +
                 sec.querySelector("h2").textContent.trim();
      L.push("## " + head);
      L.push("");
      rows.forEach(function(g){
        var id = g.dataset.gate, s = state[id];
        var mark = s.r === "pass" ? "PASS" : s.r === "fail" ? "FAIL" : "NOT RUN";
        L.push("- **" + id + "** — " + mark);
        if (s.n && s.n.trim()) {
          s.n.trim().split("\n").forEach(function(line){ L.push("  - " + line); });
        }
      });
      L.push("");
    });
    if (n.pass + n.fail + n.na === 0) return "아직 표시할 결과가 없습니다.";
    return L.join("\n");
  }

  document.getElementById("copy").addEventListener("click", function(){
    var text = report(), out = document.getElementById("out");
    out.value = text;
    out.select();
    var ok = false;
    try { ok = document.execCommand("copy"); } catch(e){}
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function(){
        this.textContent = "복사됨";
      }.bind(this)).catch(function(){});
    }
    this.textContent = ok ? "복사됨" : "아래에서 선택해 복사하십시오";
    var btn = this;
    setTimeout(function(){ btn.textContent = "결과 복사"; }, 2200);
  });

  paint();
  live.forEach(function(g){
    var t = g.querySelector(".note");
    if (t && t.value) { t.style.height = "auto"; t.style.height = (t.scrollHeight + 2) + "px"; }
  });
})();
</script>
"""

if __name__ == "__main__":
    raise SystemExit(main())
