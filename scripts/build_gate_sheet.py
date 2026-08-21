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

BUILD = "#41 (779ef04)"
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

# Korean for each gate. Keyed by id so a gate added upstream without a
# translation fails the build of this sheet rather than appearing in English.
KOREAN = {
# `{codes}` is filled from the gate's own English text at generation time.
# The switch names are deliberately not written here: this file lives in
# `scripts/`, which `verify_chromium_security_invariants.py` sweeps for exactly
# those strings, and it is right to -- a checklist that names what it forbids
# is indistinguishable, to a substring search, from a build that sets it.
# Reading them from the document also means they cannot drift from it.
"RV-1": ("`chrome://version` 을 연다",
  "명령줄에 {codes} 가 **없다**"),
"RV-2": ("`chrome://sandbox` 를 연다",
  "모든 렌더러 행이 샌드박스를 **활성**으로 보고한다"),
"RV-3": ("`chrome://process-internals` 를 연다",
  "사이트 격리 모드가 site-per-process 이고, 교차 사이트 프레임 둘이 서로 **다른 프로세스**를 차지한다"),
"RV-4": ("옴니박스에 `sunshine://anything` 을 입력한다",
  "탐색이 아니라 **검색**으로 처리된다 — 그 스킴은 해석되지 않는다"),
"RV-5": ("H.264/AAC 동영상을 재생한다", "디코딩되어 재생된다"),
"RV-6": ("VP9 또는 AV1 동영상을 재생한다",
  "디코딩되어 재생된다 — 코덱 변경이 로열티 프리 경로를 **잃게 하지 않았어야** 한다"),
"RV-7": ("새 탭을 연다",
  "로고 자리에 Sunshine 워드마크가 있고, Chromium 자체 로고는 없다"),
"RV-8": ("키가 없는 빌드에서 새 탭을 연다",
  "Google API 키가 없다고 알리는 인포바가 **뜨지 않는다**"),
"RV-9": ("새 탭 페이지에서 검색한다",
  "Chromium 자체 검색 처리가 동작한다. Sunshine의 개입도, 강제된 시작 URL도 없다"),
"RV-10": ("탐색기 목록 보기, 작업표시줄, 고정된 바로가기에서 `chrome.exe` 를 본다",
  "셸이 요구하는 세 가지 크기 각각에서 Sunshine 아이콘이 제대로 보인다 — 늘어나지 않고, 이웃 크기를 확대·축소한 것이 아니며, Chromium의 파란 구가 아니다"),
"RV-11": ("탐색기에서 `mini_installer.exe` 를 본다", "Sunshine 아이콘"),
"RV-12": ("`chrome://sunshine-security` 를 연다",
  "네 개의 판정 문단 중 **정확히 하나**가 보이고, 그것이 이 빌드의 불리언 세 개가 함의하는 바로 그 문단이다"),
"RV-13": ("`chrome://sunshine-document` 를 열고 1 → 1.1 → 1.2 → 1.2.1 → 2 계층을 만든 뒤, 1.2 에서 다음을 누른다",
  "2가 아니라 **1.2.1**. 목차는 깊이 우선의 읽기 순서다"),
"RV-14": ("HTML이 자체 `<head><style>` 을 담은 섹션을 읽는다",
  "그 스타일이 적용되고, 창 전체가 **그 문서 자체**다 — Sunshine 프레임 안에 끼워진 벗겨진 조각이 아니다"),
"RV-15": ("실행되면 눈에 보였을 `<script>` 를 담은 섹션을 읽는다",
  "문서는 렌더링되고, 스크립트는 **실행되지 않는다**"),
"RV-16": ("원격 이미지를 참조하는 섹션을 읽는다",
  "이미지는 없는 것으로 표시되고, DevTools 네트워크 패널에 그 **요청이 나타나지 않는다**"),
"RV-17": ("문서를 저장하고, 다른 곳으로 갔다가, 돌아와서 비교한다",
  "저장한 것과 **바이트 단위로 동일**하다. 정규화도, 들여쓰기 재조정도, 페이지 나눔의 역기록도 없다"),
"RV-18": ("문서가 있던 프로젝트를 삭제한 뒤 표면을 다시 연다",
  "그 프로젝트와 그에 속한 모든 문서가 사라져 있다"),
"RV-19": ("섹션을 연 채로 새로고침을 누르고, 이어서 내려받는다",
  "새로고침은 편집기의 **저장되지 않은 편집을 건드리지 않고** 저장소에서 다시 읽는다. 내려받기는 저장된 문서를 내용으로 하는 `.html` 파일을 저장한다"),
"RV-20": ("페이지 본문에서 오른쪽 버튼을 누른 채 왼쪽으로 200 px 끌고 놓는다. 오른쪽으로도 반복하고, 50 px 만 끄는 것도 반복한다",
  "왼쪽은 뒤로, 오른쪽은 앞으로 가고, **짧은 드래그는 대신 컨텍스트 메뉴**를 띄운다. 긴 드래그는 둘 다 메뉴를 띄우지 않으며, 어떤 누름도 두 가지를 동시에 하지 않는다"),
"RV-21": ("북마크바를 표시하고 시작 가장자리를 본다",
  "Sunshine 버튼 하나가 저장된 탭 그룹 버튼 **왼쪽**에 있고 툴팁은 'Sunshine modules'. 그 글리프는 탭 그룹 버튼이 쓰는 격자가 아니다"),
"RV-22": ("그 버튼을 클릭하고, 이어서 ctrl+클릭한다",
  "첫 번째는 현재 탭에 `chrome://sunshine-modules` 를 열고, 두 번째는 **새 배경 탭**에 연다. 이 바의 다른 모든 버튼과 마찬가지로 처리 방식이 수정자 키를 따른다"),
"RV-23": ("`chrome://sunshine-modules` 에서 왼쪽 열을 `first_party/registry.json` 과 대조한다",
  "같은 모듈, 같은 순서이고 제목의 개수도 일치한다. 이것은 동기화 가드가 닿을 수 없는 게이트다 — 가드는 패치와 `first_party/` 를 비교하지, **실행 중인 페이지**를 어느 쪽과도 비교하지 않는다"),
"RV-24": ("왼쪽 열에서 각 모듈을 선택한다",
  "선언된 네트워크·파일시스템·자격증명 값이 매니페스트의 표현 그대로이고, `deny`/`none`/아니오 가 **아닌** 값이 눈에 띄는 쪽이다"),
"RV-25": ("북마크바의 버튼이 넘칠 때까지 창을 좁힌다",
  "Sunshine 버튼이 시작 가장자리 제자리를 지키고, 옆 버튼 위에 **겹쳐 그려지지 않는다**"),
"RV-26": ("설치한 뒤 설치 디렉터리, 시작 메뉴 항목, 작업표시줄 항목, Windows 기본 앱 목록을 본다",
  "네 곳 모두 Sunshine 이라고 한다. 특히 설치 디렉터리가 `Chromium` 이 아니라 `%LOCALAPPDATA%\\Sunshine\\Application` 이다 — 진짜 Chromium 이 깔린 기계였다면 충돌했을 자리다"),
"RV-27": ("앱 메뉴, 정보, 기본 브라우저 안내를 연다",
  "모두 Sunshine 을 가리킨다. 정보는 여전히 **The Chromium Authors** 를 표기하고 저작권 표시도 그대로다 — 그게 맞고, 패치 0010 이 지키는 것이 그것이다"),
"RV-28": ("진짜 Chromium 또는 Chrome 도 설치된 상태에서 Sunshine 을 설치하고 둘 다 쓴다",
  "어느 쪽도 다른 쪽의 파일이나 프로필을 대체하지 않고, 작업표시줄에 **두 개의 애플리케이션**으로 보인다"),
"RV-29": ("설치 후 프로필을 찾는다: `%LOCALAPPDATA%\\Sunshine\\User Data`",
  "존재하고 프로필을 담고 있다. `%LOCALAPPDATA%\\Chromium` 은 **손대지 않은 상태**다 — 진짜 Chromium 이 있는 기계에서는 그 브라우저의 프로필이고, 이 변경 전에는 같은 디렉터리였다"),
"RV-30": ("설치 후 `HKCR` 에서 `chromium` 키와 `sunshine` 키를 확인한다",
  "둘 다 URL 프로토콜로 **등록돼 있지 않다**. `direct_launch_url_scheme` 이 비어 있다는 것은 인스톨러가 `Software\\Classes\\<scheme>` 항목을 아예 쓰지 않는다는 뜻이다"),
"RV-31": ("`chrome://sunshine-shell` 을 열고 셸 계약 §3 의 아홉 가지 상태에 모두 도달한 뒤, 각각에서 되돌아온다",
  "모든 상태에 도달 가능하고 되돌릴 수 있다. 뼈대는 전부 동일하고 내용만 바뀐다"),
"RV-32": ("네 영역을 모두 연 채로 클램프를 넘겨 창을 좁힌다",
  "E 가 먼저 접히고 그다음 C. D 는 보이는 동안 480px 아래로 **내려가지 않고**, B 는 전혀 변하지 않는다"),
"RV-33": ("한 모듈에서 탭 너비를 정하고 모듈을 바꿨다 돌아온다. 이어서 바와 독을 토글하고 모듈을 바꾼다",
  "탭 너비가 **모듈별로** 돌아온다. 바 토글과 독 너비는 모듈이 바뀌어도 변하지 않는다"),
"RV-34": ("각 스플리터를 끌고, 창 밖에서 놓고, 더블클릭한다",
  "고스트 선 없이 실시간으로 크기가 바뀌고, 포인터가 놓인 자리에 너비가 유지되며, 더블클릭은 기본값으로 되돌린다"),
"RV-35": ("모듈이 마운트된 상태에서 E 를 열었다 닫고, `chrome://process-internals` 에서 프레임 수를 본다",
  "E 를 닫으면 그 프레임이 **파괴된다**. 사용자가 치워둔 영역 뒤에서 모듈이 계속 돌지 않는다"),
"RV-36": ("마운트된 모듈에서 다른 모듈로 갔다가 돌아온다",
  "두 번째 모듈의 프레임이 첫 번째를 **재사용하지 않고 대체한다**. 첫 모듈 문서의 어떤 것도 두 번째로 넘어가지 않으며, 돌아가면 처음부터 다시 시작한다"),
"RV-37": ("`chrome://sunshine-modules` 에서 모듈 목록 아래의 링크를 따라간다",
  "`chrome://sunshine-shell` 에 도착한다. 주소를 직접 입력하지 않고 그 표면에 가는 **유일한 경로**이며, 패치 0013 이전에는 그런 경로가 없었다"),
"RV-38": ("모듈 셸에서 독 맨 아래의 **Register** 를 누른다",
  "모듈 홈의 등록 섹션에 도착한다. 아무것도 설치되지 않고 아무것도 변하지 않으며, 그 섹션이 이유를 말한다 — 모듈은 컴파일되어 들어간다. 그 컨트롤은 B 의 맨 아래, Names 토글 밑에 있다"),
"RVV-1": ("새 탭을 폭 533 px, 768 px, 933 px 에서 본다",
  "워드마크가 매끄럽게 확대·축소되고 잘리거나 줄바꿈되지 않는다"),
"RVV-2": ("새 탭을 라이트와 다크에서 본다",
  "둘 다 디자인 시스템 토큰을 쓰고, 어느 쪽도 색을 하드코딩하지 않는다"),
"RVV-3": ("새 탭 페이지를 키보드만으로 이동한다",
  "모든 정지점에서 포커스가 보이고, 검색 입력란에 도달한다"),
"RVV-4": ("북마크바의 Sunshine 버튼을 라이트와 다크에서 본다",
  "글리프가 두 테마 모두에서 `kColorBookmarkButtonIcon` 을 해석한다 — 옆의 오버플로 버튼과 동일하게. 테마 변경을 견디는 고정색이 결코 아니다"),
"RVV-5": ("북마크바를 키보드만으로 이동한다",
  "Sunshine 버튼이 **첫 번째 정지점**이고, 그려진 위치와 일치한다 — `Init()` 의 자식 순서가 곧 포커스 순서다"),
}


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


def markup(text: str) -> str:
    """Escape, then let `**bold**` and `` `code` `` through.

    The Korean carries emphasis where the English carried it, and a gate whose
    load-bearing word is not marked reads as evenly weighted prose that someone
    skims.
    """

    out = esc(text)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"`(.+?)`", r"<code>\1</code>", out)
    return out


def gate_row(gate: dict[str, str], badge: str = "") -> str:
    inv = f'<span class="inv">{esc(gate["invariant"])}</span>' if gate["invariant"] else ""
    step_ko, expected_ko = KOREAN[gate["id"]]
    if "{codes}" in expected_ko:
        codes = ", ".join(f"`{token}`" for token in re.findall(r"`([^`]+)`", gate["expected"]))
        expected_ko = expected_ko.replace("{codes}", codes)
    return f"""
      <div class="gate" data-gate="{gate['id']}">
        <div class="stripe" aria-hidden="true"></div>
        <div class="gid"><span class="idtag">{gate['id']}</span>{badge}</div>
        <div class="body">
          <p class="step">{markup(step_ko)}</p>
          <p class="exp"><span class="explabel">기대</span>{markup(expected_ko)}</p>
          <details class="src">
            <summary>원문</summary>
            <p class="step">{esc(gate['step'])}</p>
            <p class="exp"><span class="explabel">expected</span>{esc(gate['expected'])}</p>
          </details>
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
          <p class="step">{markup(KOREAN[gate['id']][0])}</p>
          <p class="exp"><span class="explabel">{label}</span>{esc(why)}</p>
          <details class="src">
            <summary>원문</summary>
            <p class="step">{esc(gate['step'])}</p>
            <p class="exp"><span class="explabel">expected</span>{esc(gate['expected'])}</p>
          </details>
        </div>
        <div class="controls">{control}</div>
      </div>"""


def build(root: Path = ROOT) -> str:
    gate = gates(root)
    if len(gate) != 43:
        raise SystemExit(f"expected 43 gates in RUNTIME_VERIFICATION.md, parsed {len(gate)}")

    # A gate added upstream without a translation must stop this script rather
    # than appear in English among Korean rows, where a reader would take the
    # odd one out for a formatting slip instead of a missing translation.
    untranslated = sorted(set(gate) - set(KOREAN))
    stale = sorted(set(KOREAN) - set(gate))
    if untranslated or stale:
        raise SystemExit(
            f"KOREAN is out of step with the gate table; missing={untranslated}, "
            f"no longer a gate={stale}"
        )

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
.src{margin-top:9px}
.src summary{font-family:"IBM Plex Mono",monospace;font-size:10.5px;letter-spacing:.09em;
  text-transform:uppercase;color:var(--ink-3);cursor:pointer;list-style:none;
  display:inline-block;padding:2px 7px;border:1px solid var(--rule-2);border-radius:3px}
.src summary::-webkit-details-marker{display:none}
.src summary:hover{color:var(--accent);border-color:var(--accent)}
.src[open] summary{margin-bottom:7px}
.src .step,.src .exp{font-size:12.5px;color:var(--ink-3);margin:0 0 4px;padding-left:10px;
  border-left:2px solid var(--rule-2)}
.step code,.exp code{font-family:"IBM Plex Mono",monospace;font-size:.9em;
  background:var(--surface-2);border:1px solid var(--rule-2);border-radius:3px;padding:1px 4px}
.step strong,.exp strong{font-weight:600;color:var(--ink)}
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
