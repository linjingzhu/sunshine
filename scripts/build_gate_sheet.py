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

# The build whose binary these gates are about. Every result the sheet exports
# carries it, so a stale value attributes a person's evening to a binary they
# did not run -- which is the same argument the "one stamp" rule below already
# makes, applied to the stamp itself.
#
# It said #47 while #56 was the shipped build, and nothing noticed because
# nothing regenerated the sheet. `check_stamp_is_current` below now refuses a
# stamp older than the newest build docs/RUNTIME_VERIFICATION.md talks about.
# The sha is added once the build exists; before that the number alone is all
# that is known, and claiming more would be the defect this comment describes.
BUILD = "#57"
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
    "F1": ("북마크바 시작 가장자리", "패치 0028 이 기본값을 껐습니다. RV-48 은 **새 프로필**에서만 답이 나옵니다."),
    "F2": ("좌우 분할 화면", ""),
    "F3": ("모듈이 실제로 마운트된 상태",
           "패치 0029 로 처음 생긴 상태입니다. RV-35·RV-36 은 여기서 처음 실행 가능해졌습니다."),
    "G": ("모듈 셸", ""),
    "H": ("문서 표면", ""),
    "A0": ("셋업 창이 뜨는가",
           "빌드 #55 와 #56 이 연달아 창이 안 뜨는 셋업을 냈습니다. 여기서 실패하면 아래 전부가 "
           "실행 불가이니, 추측하지 마시고 종료 코드를 먼저 읽어주십시오."),
}

STOP_HARD = {"RV-1", "RV-2", "RV-3"}
STOP_BLOCK = {"RV-26", "RV-29", "RV-30"}
CONDITIONAL = {
    "RV-28": "같은 기계에 실제 Chromium 또는 Chrome이 설치돼 있어야 합니다. 없으면 NOT RUN 이 결과입니다.",
}
# RV-35 and RV-36 sat here because no module declared a mount, so there was no
# frame to open and none to destroy. Patch 0029 is one, which is exactly the
# condition their entries named -- so they are runnable and back on the sheet.
# RV-36 needs two mounted modules and there is one, which is a NOT RUN with a
# reason rather than a gate this generator should hide.
BLOCKED: dict[str, str] = {}
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
     "100MB를 넘으면 거부됩니다. "
     "안 나올 경우 이유를 알 방법이 없습니다 — 파일 없음, 크기 초과, 형식 불일치가 모두 같은 결과입니다. "
     "그리고 브라우저를 켠 직후 첫 새 탭은 배경이 없을 수 있습니다(탐지가 프로세스당 한 번, "
     "그리는 스레드 밖에서 돕니다). 두 번째 탭부터 정상이면 그것은 알려진 경합이지 결함이 아닙니다. "
     "파일을 넣기 전에 새 탭을 한 번 열어보시면 대조가 됩니다 — 배경이 없을 때는 프레임 자체가 만들어지지 않습니다. "
     "UG-4·UG-5·UG-6 은 이 배경이 들어간 뒤에 보이는 것들입니다."),
    ("포커스 아웃 3초 뒤 — 배경만 남는가",
     "UG-3 으로 배경을 넣으신 뒤 새 탭을 열어두고, 다른 창을 클릭해 Sunshine 창에서 포커스를 뺍니다. "
     "3초 뒤 새 탭의 내용(워드마크·검색창·바로가기)이 사라지고 **배경 사진만 남아야** 합니다. "
     "다시 클릭하면 즉시 돌아옵니다. 그 클릭은 화면을 깨우기만 하고 아무것도 누르지 않습니다. "
     "**배경이 함께 사라져 화면이 통째로 비면 그것이 결함입니다** — 빌드 #44 였다면 그렇게 됐을 자리이고, "
     "이 빌드는 그 수정을 담고 있습니다. 창을 최소화하면 아무 일도 일어나지 않는 것이 정상입니다: "
     "안 보이는 화면은 쉬게 할 것이 없습니다. 배경을 넣지 않으셨다면 이 기능은 동작하지 않습니다."),
    ("우하단 시계",
     "새 탭 오른쪽 아래에 현재 시각이 시:분으로 보여야 합니다. **분이 바뀌는 순간** 함께 바뀌는지 "
     "1분쯤 보고 계시면 확인됩니다. 초는 표시하지 않습니다. "
     "UG-4 의 휴지 상태에서도 **시계는 남아야** 합니다 — 안 보는 화면에서 시계는 볼 이유 그 자체라서 "
     "일부러 남겨둔 것입니다. 배경이 없어도 시계는 보입니다. "
     "시각 오른쪽에 버튼이 하나 보이면 그건 아직 만들지 않은 배경 설정 버튼이고, "
     "**이 빌드에는 없는 것이 정상**입니다."),
    ("검색창 두 상태",
     "새 탭 검색창이 **아무것도 안 할 때는 반투명**해서 뒤 배경이 비쳐야 하고, "
     "**클릭해서 커서가 들어가면 불투명**해져야 합니다. 전환은 즉시입니다(애니메이션 없음). "
     "글자를 입력한 뒤 **페이지 빈 곳을 클릭해 포커스를 빼도 불투명한 채로** 있어야 합니다 — "
     "글자가 남아 있는 동안은 사용 중으로 봅니다. 그 상태에서 글자를 다 지우면 다시 반투명해집니다. "
     "배경이 없으면 차이가 잘 안 보일 수 있으니 UG-3 을 먼저 하십시오. "
     "**반대로 동작하면**(타이핑 중에 비쳐 보이면) 그대로 적어주십시오 — 그것이 이 기능의 유일한 실패 모양입니다."),
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
  "Sunshine 버튼 하나가 거기 있고 툴팁은 'Sunshine modules'. 그리고 **거기 있는 버튼은 그것뿐**이다 — 패치 0028 이 저장된 탭 그룹 버튼을 껐다. 탭 그룹 버튼이 아직 보이면 패치가 먹지 않은 것이고 RV-48 이 이유를 말한다"),
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
"RV-39": ("일반 창을 띄운 채 `Ctrl+Shift+B` 를 누르고, 다시 누른다. 이어서 메뉴로도 같은 것을 한다 — ⋮ → 북마크 및 목록 → 북마크바 표시",
  "**두 경로 모두**로 바가 숨고 나타난다. 메뉴 항목이 흐리게 죽어 있으면 명령 자체가 꺼진 것이고 단축키는 구조상 무효다. 메뉴는 되는데 키가 안 되면 키가 브라우저까지 닿지 않는 것이다"),
"RV-40": ("Sunshine 모듈 홈 버튼이 북마크바에 있는 상태에서 바를 숨긴다",
  "버튼도 바와 함께 사라진다. 그러면 `chrome://sunshine-modules` 로 가는 북마크바 경로가 없어지는데, ADR 0014 §5 는 그것이 의도인지 **말하고 있지 않다**"),
"RV-41": ("북마크바에 폴더가 하나 이상 있는 상태로 표시하고 폴더 아이콘을 본다",
  "바의 모든 폴더가 대표님 이미지(`resource/folder.png`) 를 입고 있다 — 청록 뒷판 위에 반투명 파란 앞판. Chromium 의 외곽선 폴더가 아니다. 버튼 위치는 그대로다: 대체된 벡터 아이콘과 같은 24 dip 로 그린다"),
"RV-42": ("바의 북마크 폴더를 클릭해서 내려온 메뉴 **안쪽**의 폴더 아이콘을 본다",
  "여전히 Chromium 의 단색 외곽선 폴더다. **이것은 결함이 아니라 예상되고 기록된 상태다** — 그 메뉴는 스택이 소유하지 않는 `bookmark_menu_delegate.cc` 가 그리고, ADR 0020 은 그 수정의 값을 29번째 업스트림 파일로 매겼다"),
"RV-43": ("디스플레이 배율을 200% 로 바꾸고 다시 시작한 뒤 바의 폴더 아이콘을 본다",
  "흐릿하게 늘어난 것이 아니라 **선명**하다. 흐리다면 grit 이 `default_200_percent/sunshine/bookmark_folder.png` 를 못 찾고 100% 이미지를 조용히 확대한 것이다"),
"RV-44": ("좌우 분할 화면을 연다(탭 우클릭 → 분할, 또는 탭을 창 가장자리로 끌기). 두 패널 사이의 구분선을 본다",
  "구분선 위, 드래그 손잡이 **위쪽**에 둥근 버튼이 하나 있고, **활성** 패널이 옮겨갈 방향을 가리키는 아이콘이 그려져 있다. 마우스를 올리지 않아도 보인다 — 올려야 보이면 그건 실패다"),
"RV-45": ("그 버튼을 누른다",
  "두 패널이 자리를 바꾸고, 탭 순서도 함께 바뀌며, 활성 탭은 활성인 채로 남는다. 아이콘은 반대 방향을 가리키게 된다. 구분선 **더블클릭**도 같은 동작인지 함께 확인한다"),
"RV-46": ("구분선을 좌우로 끌어본다. 이어서 Tab 을 눌러 드래그 손잡이에 포커스를 주고 화살표 키를 누른다",
  "두 경로 모두로 크기 조절이 여전히 된다. 버튼이 드래그를 먹으면 안 된다 — **버튼 위**에서 시작한 누름은 크기를 바꾸지 않지만, 구분선의 **다른 곳**은 여전히 바꾼다"),
"RV-47": ("버튼에 마우스를 올려 툴팁을 읽고, 빌드 #47 분할 화면 스크린샷과 간격을 비교한다",
  "툴팁은 'Reverse views' — 메뉴 항목이 쓰던 문자열 그대로이고 새로 만든 문장이 아니다. 구분선이 10px 에서 **20px** 로 넓어졌고 그만큼 패널이 좁아졌다. 이게 '컨트롤이 놓인 구분선' 으로 보이는지 그냥 '벌어진 틈' 으로 보이는지가 ADR 0021 이 남겨둔 질문이다"),
"RV-48": ("**새 프로필**에서 북마크바를 표시한다",
  "저장된 탭 그룹 버튼도, 그 옆 구분선도 없다. 있다면 프로필부터 확인하십시오 — 이 설정은 동기화되고 **한 번이라도 켠 프로필은 자기 값을 유지**하므로, 새 기본값이 틀린 것이 아니다"),
"RV-49": ("북마크바를 우클릭해서 메뉴를 읽는다",
  "**'탭 그룹 표시' 항목이 그대로 있고, 체크는 꺼져 있으며, 눌러보면 동작한다.** 기본값만 움직였을 뿐 업스트림이 사용자에게 준 컨트롤은 손대지 않았다. 눌러도 아무 일 없는 항목이라면 그것이 이 게이트가 잡으려는 결함이다"),
"RV-50": ("`chrome://sunshine-shell` 을 열고 독에서 DevOS 를 고른다",
  "모듈이 그려진다. 헤더는 **DevOS**, C 영역에 **Overview / Repositories / Decisions**, 헤더에 **Refresh** 와 **Details** — 전부 프레임이 마운트될 때 보낸 하나의 `describe` 를 보고 셸이 그린 것이다. **마운트 포트가 메시지를 나른 것은 이번이 처음이다**"),
"RV-51": ("C 영역의 탭을 하나씩 눌러본다",
  "본문이 따라 바뀐다. 그다음 반대 방향이 두 번 그려지지 않는지 확인한다: 모듈은 D 안에 **자기 탭 줄을 전혀 그리지 않고**, 제목도 스위처도 없다. 자기 것을 남겨둔 모듈이라면 모든 게 두 개로 보인다"),
"RV-52": ("헤더의 **Details** 를 누른다",
  "E 영역이 열린다. 모듈은 패널을 직접 연 게 아니라 `request-panel` 로 **요청**했으므로, E 가 안 열리면 메시지가 도착하지 않은 것이다 — 모듈보다 셸의 `child-src` 를 먼저 보십시오"),
"RV-53": ("DevOS 가 마운트된 상태에서 각 탭이 실제로 무엇이라고 쓰여 있는지 읽는다",
  "모든 탭이 무엇을 보여줄 것인지와 **아무것도 읽지 않았다는 것**을 함께 말한다. 숫자도, 0 도, 빈 차트도 없다. 매니페스트가 네트워크를 `deny` 로 선언하고 `connect-src 'none'` 이 그것을 강제하므로, **여기 숫자가 있다면 그것은 지어낸 것**이다"),
"RV-54": ("컴파일러가 깔린 적 없는 기계에서 `sunshine-setup.exe` 를 더블클릭하고 5초 기다린다",
  "**창이 뜬다.** 이 게이트는 그게 전부다. 빌드 #55 와 #56 이 서로 다른 이유로 — C 런타임 누락과 스택 오버플로 — 여기서 실패했고, 밖에서 보기엔 둘이 똑같았다: 더블클릭, 그리고 아무 일 없음. **안 뜨면 추측하지 마시고** PowerShell 에서 `(Start-Process .\sunshine-setup.exe -PassThru -Wait).ExitCode` 를 실행해 숫자를 먼저 읽어주십시오"),
"RV-55": ("그 창에서 **이 PC의 나만** 과 **모든 사용자** 를 오간다. 사이에 위치 상자에 경로를 한 번 입력해본다",
  "상자 아래 위치 설명이 매번 따라 바뀌고, **나만** 에서는 상자가 비면서 흐려지며, 그동안 대화창이 계속 반응한다. `RefreshLocation` 이 이 동작마다 실행되고 매번 자기 자신을 다시 부른다 — 여기서 멈추거나 창이 사라지면 그건 느린 기계가 아니라 IU-18 의 가드가 무너진 것이다"),
}


# What to actually do, and what you should actually see.
#
# The gate text above each of these is the contract's wording: precise for the
# person who wrote the rule and useless to the person holding the mouse. The
# owner could not start from it, which is a defect in this sheet and not in
# them. Each entry is (steps, pass, fail).
HOWTO = {

# --- Block A: before anything is launched ---------------------------------
"RV-11": (["설치 파일이 있는 폴더를 탐색기로 연다",
           "`sunshine-setup.exe` 와 `sunshine-installer-windows-x64.exe` 의 아이콘을 본다"],
  "두 파일 모두 Sunshine 아이콘이 보인다",
  "Chromium 의 파란 구슬 아이콘이거나, 아이콘이 없는 흰 종이 모양이다"),

"RV-26": (["`sunshine-setup.exe` 를 실행해서 설치를 끝낸다",
           "탐색기 주소창에 `%LOCALAPPDATA%` 를 입력하고 Enter",
           "`Sunshine` 폴더가 있는지 본다. 그 안의 `Application` 폴더도",
           "시작 메뉴를 열고 Sunshine 을 찾는다",
           "작업표시줄에 고정하고 이름을 본다",
           "Windows 설정 → 앱 → 기본 앱 목록에서 Sunshine 을 찾는다"],
  "네 곳(설치 폴더·시작 메뉴·작업표시줄·기본 앱) 모두 Sunshine 이라고 쓰여 있다. 설치 폴더는 `%LOCALAPPDATA%\\Sunshine\\Application`",
  "설치 폴더가 `%LOCALAPPDATA%\\Chromium` 이거나, 어느 한 곳이라도 Chromium 이라고 표시된다. **여기서 실패하면 블록 A만 끝내고 중단**"),

"RV-29": (["탐색기 주소창에 `%LOCALAPPDATA%\\Sunshine\\User Data` 를 입력하고 Enter",
           "이어서 주소창에 `%LOCALAPPDATA%\\Chromium` 을 입력하고 Enter"],
  "앞쪽은 존재하고 안에 파일들이 있다. 뒤쪽은 폴더가 없거나(정상), 원래 Chromium 을 쓰고 계셨다면 **날짜가 그대로**다",
  "`Sunshine\\User Data` 가 없거나, `Chromium` 폴더의 내용이 방금 바뀌었다. **실패 시 블록 A 끝내고 중단**"),

"RV-30": (["Win+R → `regedit` 입력 → Enter",
           "왼쪽 트리에서 `HKEY_CLASSES_ROOT` 를 편다",
           "Ctrl+F 로 `sunshine` 을 찾고, 다시 `chromium` 을 찾는다",
           "찾은 키가 있다면 그 안에 `URL Protocol` 이라는 값이 있는지 본다"],
  "`sunshine` 도 `chromium` 도 URL 프로토콜로 등록돼 있지 않다 (키가 아예 없거나, 있어도 `URL Protocol` 값이 없다)",
  "둘 중 하나가 `URL Protocol` 값을 갖고 있다. **실패 시 블록 A 끝내고 중단**"),

"RV-28": (["이 기계에 진짜 Chrome 이나 Chromium 이 설치돼 있는 경우에만 한다",
           "둘 다 실행해서 나란히 띄운다",
           "각각에서 아무 사이트나 열어보고, 작업표시줄을 본다"],
  "서로의 파일이나 프로필을 건드리지 않고, 작업표시줄에 **별개의 두 앱**으로 보인다",
  "한쪽을 설치하니 다른 쪽이 사라졌거나, 작업표시줄에서 하나로 합쳐진다. **Chrome/Chromium 이 없으면 NOT RUN**"),

# --- Block B: security posture --------------------------------------------
"RV-1": (["Sunshine 을 실행한다",
          "주소창에 `chrome://version` 을 입력하고 Enter",
          "페이지에서 **명령줄(Command Line)** 항목을 찾는다"],
  "그 줄에 원문의 세 스위치가 하나도 없다",
  "셋 중 하나라도 보인다. **여기서 실패하면 세션 전체 중단** — 보안 모델이 계약과 다른 브라우저입니다"),

"RV-2": (["주소창에 `chrome://sandbox` 를 입력하고 Enter",
          "표의 각 행을 본다"],
  "렌더러 행마다 샌드박스가 켜져 있다고 표시된다",
  "샌드박스가 꺼져 있다고 표시된 행이 있다. **실패 시 세션 중단**. 페이지 자체가 안 열리면 PASS 가 아니라 **NOT RUN**"),

"RV-3": (["주소창에 `chrome://process-internals` 를 입력하고 Enter",
          "맨 위에서 **Site Isolation mode** 를 찾는다",
          "새 탭에서 다른 사이트의 iframe 이 있는 페이지(예: 유튜브 영상이 박혀 있는 블로그 글)를 연다",
          "`chrome://process-internals` 로 돌아와 그 탭의 프레임 목록을 본다"],
  "격리 모드가 **site-per-process** 이고, 서로 다른 사이트의 프레임이 **다른 프로세스 번호**를 갖는다",
  "모드가 다르거나, 다른 사이트의 프레임이 같은 프로세스에 있다. **실패 시 세션 중단**. 페이지를 못 읽으면 **NOT RUN**"),

"RV-4": (["주소창에 `sunshine://anything` 을 입력하고 Enter"],
  "그 주소로 이동하지 않고 **검색 결과**가 뜬다 (또는 검색 엔진으로 넘어간다)",
  "`sunshine://` 페이지가 열리거나 '해당 주소를 찾을 수 없다'는 식으로 **주소로 취급**된다"),

# --- Block C: is it Sunshine ----------------------------------------------
"RV-10": (["설치 폴더에서 `chrome.exe` 를 탐색기 **자세히/목록** 보기로 본다",
           "작업표시줄에 고정된 Sunshine 아이콘을 본다",
           "바탕화면 바로가기가 있으면 그것도 본다"],
  "세 곳 모두 Sunshine 아이콘이고, 흐릿하거나 늘어나 보이지 않는다",
  "어느 하나가 뭉개져 보이거나, Chromium 의 파란 구슬이다"),

"RV-27": (["오른쪽 위 ⋮ 메뉴를 연다",
           "도움말 → Sunshine 정보 (About) 를 연다",
           "다른 브라우저를 기본으로 해두었다면, Sunshine 을 다시 열어 기본 브라우저 안내가 뜨는지 본다"],
  "메뉴·정보·안내 모두 Sunshine 이라고 한다. **정보 화면에 The Chromium Authors 저작권 표기가 그대로 남아 있는 것이 정상**이고 그게 맞는 동작",
  "어딘가 Chromium 이라고 표시되거나, 반대로 Chromium Authors 저작권 표기가 지워져 있다"),

"RV-12": (["주소창에 `chrome://sunshine-security` 를 입력하고 Enter",
           "화면에 보이는 판정 문단을 센다"],
  "판정 문단이 **정확히 하나**만 보인다",
  "두 개 이상 보이거나, 하나도 안 보인다"),
}

HOWTO.update({
# --- Block D: new tab ------------------------------------------------------
"RV-8": (["Ctrl+T 로 새 탭을 연다", "화면 위쪽에 노란 띠 같은 알림 막대가 있는지 본다"],
  "'Google API 키가 없다'는 알림 막대가 **뜨지 않는다**",
  "그런 알림 막대가 뜬다"),
"RV-9": (["새 탭의 검색창에 아무 단어나 입력하고 Enter"],
  "평범하게 검색 결과로 넘어간다",
  "엉뚱한 페이지로 가거나, 검색이 아니라 정해진 주소로 끌려간다"),
"RVV-1": (["새 탭을 연 상태에서 창을 아주 좁게 → 중간 → 넓게 세 번 크기를 바꾼다",
           "가운데 SUNSHINE 글자를 본다"],
  "글자 크기가 창에 따라 부드럽게 변하고, 잘리거나 두 줄로 넘어가지 않는다",
  "글자가 잘리거나 줄바꿈되거나, 크기가 끊기듯 튄다"),
"RVV-2": (["Windows 설정에서 앱 모드를 밝게/어둡게 바꿔가며 새 탭을 본다"],
  "두 모드 모두 글자와 배경이 제대로 보인다",
  "한쪽에서 글자가 배경에 묻혀 안 보인다"),
"RVV-3": (["새 탭에서 마우스를 쓰지 않고 Tab 키만 눌러 이동한다"],
  "지금 어디에 있는지 **테두리로 표시**되고, 계속 누르면 검색창에 도달한다",
  "어디에 있는지 안 보이거나, 검색창에 도달하지 못한다"),

# --- Block E: media --------------------------------------------------------
"RV-5": (["유튜브 같은 곳에서 일반 동영상을 재생한다"],
  "정상 재생된다", "재생이 안 되거나 검은 화면에 소리만 난다"),
"RV-6": (["같은 사이트에서 다른 영상을 몇 개 더 재생한다 (요즘 유튜브는 대부분 VP9/AV1)"],
  "정상 재생된다", "일부 영상만 재생이 안 된다"),

# --- E2: mouse gestures ----------------------------------------------------
"RV-20": (["아무 사이트에서 링크를 두어 번 눌러 **뒤로 갈 기록**을 만든다",
           "페이지 빈 곳에서 **오른쪽 버튼을 누른 채** 왼쪽으로 화면 폭의 1/5 쯤 끌고 놓는다",
           "같은 방식으로 오른쪽으로 끌고 놓는다",
           "이번엔 아주 짧게(1cm 정도) 끌고 놓는다"],
  "왼쪽 = 뒤로, 오른쪽 = 앞으로. **짧게 끌면 오른쪽 클릭 메뉴가 뜬다.** 길게 끌었을 때는 메뉴가 뜨지 않는다",
  "이동이 안 되거나, 길게 끌었는데 메뉴까지 같이 뜬다"),

# --- Block F: bookmark bar and module home ---------------------------------
"RV-21": (["Ctrl+Shift+B 로 북마크바를 켠다", "북마크바 **맨 왼쪽**을 본다", "그 버튼에 마우스를 올려 툴팁을 읽는다"],
  "맨 왼쪽에 버튼이 하나 있고 툴팁이 'Sunshine modules'. 모양이 격자(바둑판) 모양은 아니다",
  "버튼이 없거나, 다른 자리에 있거나, 격자 모양이다"),
"RV-22": (["그 버튼을 그냥 클릭한다", "뒤로 온 뒤, 이번엔 Ctrl 을 누른 채 클릭한다"],
  "그냥 클릭 = 지금 탭에서 열림. Ctrl+클릭 = **뒤쪽 새 탭**에서 열림",
  "둘 다 같게 동작하거나, Ctrl+클릭이 지금 탭을 바꿔버린다"),
"RV-23": (["그 버튼으로 모듈 홈을 연다", "왼쪽 목록의 항목 이름과 순서를 적어둔다",
           "제목에 적힌 개수도 본다"],
  "목록과 개수가 서로 맞는다 (저장소의 `first_party/registry.json` 과 대조하는 게 원칙이지만, **개수와 목록이 어긋나지 않으면 합격**으로 두셔도 됩니다)",
  "제목의 개수와 실제 항목 수가 다르다"),
"RV-24": (["왼쪽 목록에서 항목을 하나씩 눌러본다", "오른쪽에 나오는 네트워크·파일·자격증명 값을 본다"],
  "대부분 `deny` / `none` / 아니오 로 표시되고, 그렇지 않은 값이 있으면 **눈에 띈다**",
  "값이 안 보이거나, 무엇이 허용됐는지 알아볼 수 없다"),
"RV-25": (["북마크바를 켠 채로 창을 아주 좁게 줄인다"],
  "Sunshine 버튼이 맨 왼쪽 자리를 지키고, 옆 버튼과 **겹치지 않는다**",
  "버튼이 사라지거나 다른 버튼 위에 겹쳐 그려진다"),
"RV-37": (["모듈 홈에서 목록 **아래쪽**의 링크를 찾아 누른다"],
  "모듈 셸 화면으로 이동한다",
  "링크가 없거나 눌러도 아무 일이 없다"),
"RVV-4": (["밝게/어둡게 모드를 바꿔가며 북마크바의 Sunshine 버튼을 본다"],
  "두 모드 모두 옆 버튼들과 **같은 색감**으로 보인다",
  "한쪽 모드에서 혼자 색이 튀거나 안 보인다"),
"RVV-5": (["북마크바를 켜고, 주소창에서 Tab 키로 이동해 북마크바에 들어간다"],
  "북마크바 안에서 **Sunshine 버튼이 첫 번째**로 선택된다",
  "다른 버튼이 먼저 선택된다"),

# --- Block G: module shell -------------------------------------------------
"RV-31": (["주소창에 `chrome://sunshine-shell` 을 입력하고 Enter",
           "화면의 각 영역(왼쪽 바, 목록, 본문, 오른쪽 패널)을 **열고 닫아가며** 가능한 조합을 만들어 본다",
           "각 조합에서 다시 원래대로 되돌려 본다"],
  "어떤 조합이든 만들 수 있고 **되돌릴 수 있다**. 틀(뼈대)은 그대로고 내용만 바뀐다",
  "어떤 조합에서 빠져나올 수 없거나, 화면 틀 자체가 깨진다"),
"RV-32": (["네 영역을 모두 연 채로 창을 계속 좁힌다"],
  "오른쪽 패널이 **먼저** 접히고, 그다음 목록이 접힌다. 본문은 일정 폭 아래로 안 줄고, 왼쪽 바는 변하지 않는다",
  "본문이 계속 찌그러지거나, 왼쪽 바가 같이 줄어든다"),
"RV-33": (["한 모듈에서 목록 폭을 드래그로 바꾼다", "다른 모듈로 갔다가 돌아온다",
           "왼쪽 바와 오른쪽 독을 토글해보고 다시 모듈을 바꾼다"],
  "폭이 **모듈마다 따로** 기억된다. 바 토글과 독 폭은 모듈을 바꿔도 그대로",
  "폭이 초기화되거나, 모든 모듈이 같은 폭을 공유한다"),
"RV-34": (["영역 사이 경계선을 잡고 드래그한다", "창 밖까지 끌고 놓아본다", "경계선을 더블클릭한다"],
  "끄는 대로 즉시 크기가 변하고, 놓은 자리에 유지되며, 더블클릭하면 기본 폭으로 돌아온다",
  "회색 선만 움직이다 튀거나, 더블클릭이 아무 일도 안 한다"),
"RV-38": (["모듈 셸에서 오른쪽 독 **맨 아래**의 Register 를 누른다"],
  "모듈 홈의 등록 안내로 이동하고, **아무것도 설치되지 않는다.** 왜 그런지 설명이 적혀 있다",
  "버튼이 없거나, 눌렀더니 뭔가 설치·변경된다"),

# --- Block H: document surface ---------------------------------------------
"RV-13": (["주소창에 `chrome://sunshine-document` 를 입력하고 Enter",
           "항목을 1 → 1.1 → 1.2 → 1.2.1 → 2 순서로 만든다 (들여쓰기로 하위 항목)",
           "1.2 를 열어둔 채 **다음** 을 누른다"],
  "2 가 아니라 **1.2.1** 로 간다",
  "2 로 건너뛴다"),
"RV-14": (["`<style>` 이 들어 있는 HTML 을 섹션 내용으로 붙여넣는다", "그 섹션을 읽기로 연다"],
  "그 스타일이 그대로 적용되고, 화면 전체가 그 문서로 보인다",
  "스타일이 벗겨지거나, Sunshine 틀 안에 작게 끼워져 보인다"),
"RV-15": (["`<script>alert(1)</script>` 처럼 실행되면 티가 나는 것을 섹션에 넣는다", "읽기로 연다"],
  "문서는 보이고 스크립트는 **실행되지 않는다**",
  "경고창이 뜨는 등 스크립트가 실행된다"),
"RV-16": (["인터넷 주소의 이미지를 참조하는 `<img>` 를 섹션에 넣는다",
           "F12 로 개발자도구를 열고 Network 탭을 켠 뒤 섹션을 연다"],
  "이미지는 안 보이고, Network 탭에 **그 요청이 없다**",
  "이미지가 보이거나, Network 탭에 요청이 나타난다"),
"RV-17": (["문서를 저장한다", "다른 화면으로 갔다가 돌아온다", "내용을 원래와 비교한다"],
  "글자 하나까지 저장한 그대로다",
  "들여쓰기나 줄바꿈이 임의로 바뀌어 있다"),
"RV-18": (["문서가 들어 있는 프로젝트를 삭제한다", "화면을 닫았다 다시 연다"],
  "그 프로젝트와 문서가 모두 사라져 있다",
  "일부가 남아 있다"),
"RV-19": (["섹션을 열고 내용을 조금 고친다 (저장하지 말 것)", "새로고침을 누른다", "이어서 내려받기를 누른다"],
  "새로고침이 **고치던 내용을 날리지 않고**, 내려받으면 저장된 내용의 `.html` 파일이 생긴다",
  "새로고침이 편집 중인 내용을 지우거나, 내려받은 파일 내용이 다르다"),
})


# Gates a person has already answered on build #41, and the answer.
#
# Kept here rather than in a document because the sheet is generated: a gate
# that has been settled must stop appearing, and the only honest way to do that
# is to name it and its result where the generator can see it.
VERIFIED = {
 "RV-11":"pass","RV-28":"pass","RV-1":"pass","RV-2":"pass","RV-3":"pass","RV-4":"pass",
 "RV-10":"pass","RV-27":"pass","RV-12":"pass","RV-8":"pass","RV-9":"pass",
 "RVV-1":"pass","RVV-2":"pass","RVV-3":"pass","RV-5":"pass","RV-6":"pass",
 "RV-21":"pass","RV-22":"pass","RV-24":"pass","RV-25":"pass","RV-37":"pass",
 "RVV-4":"pass","RV-32":"pass","RV-33":"pass","RV-34":"pass","RV-38":"pass",
}

# Better instructions for the seventeen that are left. The first pass at these
# was written from the contract rather than from the screen -- the document
# surface entries described indentation the page does not have -- which is why
# five of them were left blank rather than answered.
RETEST_HOWTO = {

"RV-26": (["**먼저 답해주실 것: 설치할 때 '내 계정' 과 '전체 사용자' 중 무엇을 고르셨습니까?**",
  "탐색기 주소창에 `%LOCALAPPDATA%\\Sunshine\\Application` 을 넣고 Enter — 폴더가 있으면 **내 계정** 설치입니다",
  "없다면 `C:\\Program Files\\Sunshine\\Application` 을 넣고 Enter — 있으면 **전체 사용자** 설치입니다",
  "둘 중 찾은 쪽 경로를 메모에 적어주십시오",
  "시작 메뉴에서 Sunshine 을 찾아 이름을 본다",
  "Windows 설정 → 앱 → 기본 앱 에서 Sunshine 을 찾는다"],
  "설치 폴더가 **위 둘 중 하나**이고(어느 쪽이든 정상입니다), 시작 메뉴와 기본 앱 목록이 Sunshine 이라고 한다",
  "둘 다 아닌 곳에 설치됐거나, 어딘가 **Chromium** 이라고 표시된다. 지난번 실패가 '전체 사용자로 설치했는데 제 설명이 내 계정 경로만 적어둔 것' 이라면 **제 잘못이고 합격입니다**"),

"RV-29": (["탐색기 주소창에 `%LOCALAPPDATA%\\Sunshine\\User Data` 를 넣고 Enter",
  "폴더가 열리면 안에 `Default` 같은 폴더나 파일이 있는지 본다",
  "**설치 위치와 무관하게 이 경로여야 합니다** — 전체 사용자로 설치하셨어도 프로필은 여기입니다",
  "이어서 주소창에 `%LOCALAPPDATA%\\Chromium` 을 넣고 Enter"],
  "앞쪽이 존재하고 안에 내용이 있다. 뒤쪽은 **폴더가 없거나**, 원래 Chromium 을 쓰셨다면 그대로 남아 있다",
  "`Sunshine\\User Data` 가 없다 → 프로필이 어디에 생겼는지 메모에 적어주십시오. 또는 `Chromium` 폴더가 방금 새로 생겼다"),

"RV-30": (["Win+R 를 누르고 `regedit` 입력 후 Enter (관리자 확인이 뜨면 예)",
  "**왼쪽 트리 맨 위**의 `HKEY_CLASSES_ROOT` 를 한 번 클릭해 선택한다",
  "Ctrl+F 를 누르고 `sunshine` 을 입력, **'키' 만 체크**하고 '다음 찾기'",
  "찾은 항목이 있으면 그 안에 `URL Protocol` 이라는 값이 있는지 오른쪽 목록에서 본다",
  "F3 으로 몇 번 더 찾아본 뒤, 같은 방법으로 `chromium` 도 찾는다"],
  "`sunshine` 이나 `chromium` 이라는 **키가 아예 없거나**, 있어도 그 안에 `URL Protocol` 값이 **없다**",
  "어느 한쪽에 `URL Protocol` 값이 있다. 레지스트리 편집기를 못 여시겠으면 **NOT RUN** 으로 두십시오"),

"RV-23": (["북마크바 맨 왼쪽 Sunshine 버튼을 눌러 모듈 홈을 연다",
  "왼쪽 목록의 항목이 **몇 개**인지 센다",
  "그 목록 위 제목에 적힌 **숫자**를 본다"],
  "센 개수와 제목의 숫자가 **같다**",
  "둘이 다르다. (원래 계약은 저장소 파일과 대조하는 것인데 그 파일이 대표님 화면에 없어서, 실제로 하실 수 있는 확인으로 낮춰 적었습니다)"),

"RV-20": (["아무 사이트를 열고 링크를 **두세 번** 눌러 페이지를 이동한다 (뒤로 갈 곳을 만드는 것)",
  "글자나 이미지가 없는 **빈 여백**에 마우스를 둔다",
  "**오른쪽 버튼을 누른 채로** 왼쪽으로 화면 폭의 1/5 정도(대략 5cm) 끌고, 버튼을 놓는다",
  "같은 방식으로 오른쪽으로 끌고 놓는다",
  "마지막으로 **아주 짧게**(1cm 정도) 끌고 놓는다"],
  "왼쪽 = 뒤로 감, 오른쪽 = 앞으로 감. **짧게 끌면 오른쪽 클릭 메뉴가 뜬다**",
  "아무 반응이 없거나, 길게 끌었는데 메뉴가 같이 뜬다. **어떤 일이 일어났는지 메모에 적어주십시오** — '아무 일도 안 일어남' 도 중요한 답입니다"),

"RVV-5": (["Ctrl+Shift+B 로 북마크바를 켠다",
  "주소창을 클릭해 커서를 둔다",
  "**Tab 키를 여러 번** 눌러 초점이 북마크바로 넘어갈 때까지 이동한다",
  "북마크바에 들어간 **첫 순간** 어느 버튼에 테두리가 생기는지 본다"],
  "북마크바에서 **가장 먼저** 테두리가 생기는 것이 맨 왼쪽 Sunshine 버튼이다",
  "다른 버튼이 먼저 선택된다. 어느 것이 먼저였는지 메모에 적어주십시오"),

"RV-31": (["주소창에 `chrome://sunshine-shell` 을 넣고 Enter",
  "화면에 세로로 나뉜 영역들이 보입니다. 각 영역을 **접었다 폈다** 해본다 (경계선이나 토글 버튼)",
  "가능한 조합을 몇 가지 만들어 보고, **매번 원래대로 되돌아오는지** 확인한다"],
  "어떤 조합을 만들어도 **되돌릴 수 있고**, 화면 틀이 깨지지 않는다",
  "어떤 상태에서 빠져나올 수 없거나 화면이 깨진다. **무엇이 안 됐는지 메모에 적어주십시오** — 계약상 '아홉 가지 상태'가 있지만 그걸 다 세실 필요는 없습니다. 되돌릴 수 없는 상태가 하나라도 있으면 불합격입니다"),

# --- 문서 표면: 화면 구조부터 --------------------------------------------
"RV-13": (["주소창에 `chrome://sunshine-document` 를 넣고 Enter",
  "화면은 왼쪽부터 **Projects / Contents / Source / Reading** 네 칸입니다",
  "왼쪽 **Projects** 의 `New project` 칸에 아무 이름이나 넣고 `+ New` 를 누른다",
  "가운데 **Contents** 로 갑니다. `New section` 에 `1` 을 넣고 `+ Node` — 이때 `Inside` 는 비워둡니다",
  "`New section` 에 `1.1` 을 넣고, **`Inside` 에서 방금 만든 `1` 을 고른 뒤** `+ Node`",
  "같은 방식으로 `1.2` 도 `Inside = 1` 로 만든다",
  "`1.2.1` 은 **`Inside = 1.2`** 로 만든다",
  "`2` 는 `Inside` 를 비우고 만든다",
  "목록에서 `1.2` 를 클릭해 선택한 뒤 `Next` 를 누른다"],
  "`2` 가 아니라 **`1.2.1`** 이 선택된다",
  "`2` 로 건너뛴다. 화면 구조가 위 설명과 다르면 **NOT RUN** 으로 두고 무엇이 달랐는지 적어주십시오"),

"RV-14": (["RV-13 에서 만든 섹션을 하나 선택한다",
  "**Source** 칸(`HTML for the selected section`)에 아래를 붙여넣는다",
  "`<style>body{background:#fee;font-size:28px}</style><p>테스트</p>`",
  "`Save document` 를 누른다",
  "맨 오른쪽 **Reading** 칸을 본다"],
  "Reading 칸의 배경이 **연분홍색**이 되고 글자가 크게 보인다 — 즉 붙여넣은 스타일이 적용된다",
  "스타일이 무시되고 평범한 글자로만 보인다"),

"RV-15": (["같은 섹션의 **Source** 칸 내용을 아래로 바꾼다",
  "`<p>보이는 글</p><script>document.body.innerHTML='스크립트가 실행됨'</script>`",
  "`Save document` 를 누르고 **Reading** 칸을 본다"],
  "Reading 칸에 **'보이는 글'** 이 그대로 보인다 (스크립트가 실행되지 않음)",
  "'스크립트가 실행됨' 으로 바뀐다 → 스크립트가 실행된 것이고 **불합격**"),

"RV-16": (["같은 섹션의 Source 를 `<img src='https://picsum.photos/200'>` 로 바꾸고 `Save document`",
  "**F12** 를 눌러 개발자도구를 연다",
  "위쪽 탭에서 **Network** 를 고른다",
  "`Ctrl+R` 로 페이지를 새로고침한 뒤, Network 목록에서 `picsum` 을 찾는다"],
  "Reading 칸에 이미지가 **안 보이고**, Network 목록에 `picsum` 요청이 **없다**",
  "이미지가 보이거나 Network 에 그 요청이 나타난다. 개발자도구를 못 여시겠으면 **NOT RUN**"),

"RV-17": (["섹션의 Source 칸에 줄바꿈과 공백이 섞인 HTML 을 넣는다 (예: 들여쓰기를 일부러 넣은 여러 줄)",
  "`Save document` 를 누른다",
  "다른 섹션을 클릭했다가 **다시 돌아온다**",
  "Source 칸의 내용을 처음 넣은 것과 비교한다"],
  "**글자 하나, 공백 하나까지 그대로**다",
  "들여쓰기나 줄바꿈이 임의로 정리돼 있다"),

"RV-18": (["Projects 칸에서 방금 만든 프로젝트가 선택된 상태인지 확인한다",
  "`Delete project` 를 누른다",
  "브라우저 탭을 닫았다가 `chrome://sunshine-document` 를 다시 연다"],
  "그 프로젝트와 그 안의 섹션들이 **모두 사라져 있다**",
  "프로젝트나 섹션 일부가 남아 있다"),

"RV-19": (["섹션을 하나 열고 Source 칸의 내용을 **조금 고친다. 저장하지 마십시오**",
  "**Reading 칸 위/아래의 새로고침 버튼**(refresh)을 누른다",
  "Source 칸의 고치던 내용이 남아 있는지 본다",
  "이어서 **다운로드 버튼**을 누른다",
  "받아진 `.html` 파일을 메모장으로 열어본다"],
  "새로고침이 **고치던 내용을 지우지 않고**, 받은 파일 내용이 **저장돼 있던 내용**과 같다",
  "새로고침이 편집 중인 내용을 날리거나, 받은 파일이 비어 있다"),

# --- 게이트가 없는 세 표면 -------------------------------------------------
"UG-1": (["설치할 때 쓰신 `sunshine-setup.exe` 를 **다시 실행**한다 (설치를 끝까지 하실 필요는 없습니다)",
  "창이 뜨는지 본다",
  "맨 위 **가로 띠 이미지**를 본다",
  "설치 위치 선택(내 계정 / 전체 사용자)과 바로가기 체크박스들이 보이는지 본다",
  "확인만 하고 **취소**로 닫으셔도 됩니다"],
  "창이 뜨고, 위쪽에 띠 이미지가 있고, 선택 항목들이 보인다",
  "창이 안 뜨거나(그냥 설치가 시작되면 엔진 쪽 파일을 실행하신 것입니다), 화면이 깨져 보인다. **띠 이미지가 'PLACEHOLDER BANNER' 라고 적힌 임시 이미지인 것은 정상입니다**"),

"UG-2": (["주소창에 `chrome://sunshine-account` 를 넣고 Enter",
  "맨 위 문장을 읽는다",
  "이어서 모듈 홈(`chrome://sunshine-modules`)을 열고 `Google account` 줄이 있는지 본다"],
  "계정 페이지가 열리고 **'이 빌드는 Google 계정 연결을 제공하지 않는다'** 는 취지의 문장이 보인다. **이게 정상입니다** — 아직 클라이언트 ID가 없습니다",
  "페이지가 안 열리거나, 눌러도 아무 일 없는 연결 버튼이 보인다"),

"UG-3": (["**먼저 파일을 넣기 전에** 새 탭(Ctrl+T)을 열어 지금 배경이 어떤지 봐둔다",
  "아무 사진 파일 하나를 `newtab-background.png` 로 이름을 바꾼다 (원래 PNG 여야 합니다. JPG 면 `newtab-background.jpg`)",
  "그 파일을 **`chrome.exe` 가 있는 폴더**에 넣는다 (RV-26 에서 찾으신 그 폴더입니다)",
  "Sunshine 을 **완전히 껐다가 다시 켠다**",
  "새 탭을 **두 번** 열어본다"],
  "새 탭 배경에 그 사진이 보인다. **첫 번째 탭에 안 보이고 두 번째부터 보이는 것은 알려진 동작**이고 결함이 아닙니다",
  "두 번 다 안 보인다 → 파일 이름·위치·형식 중 하나가 어긋난 것인데 **화면은 그 이유를 알려주지 않습니다.** 넣으신 파일 이름과 정확한 폴더 경로를 메모에 적어주십시오"),
# --- Block F: the bookmark bar, its folders, and module home ---------------
"RV-39": (["일반 창(시크릿 아님)을 하나 띄우고 페이지를 아무거나 연다",
  "`Ctrl+Shift+B` 를 누른다. 이어서 한 번 더 누른다",
  "이번엔 오른쪽 위 ⋮ → 북마크 및 목록 → **북마크바 표시** 를 눌러본다. 다시 눌러 되돌린다"],
  "두 경로 모두로 바가 숨었다 나타난다",
  "**메뉴 항목이 흐리게 죽어 있다** → 명령 자체가 꺼진 것이고 단축키도 구조상 안 됩니다. **메뉴는 되는데 키만 안 된다** → 키가 브라우저까지 안 닿는 것입니다. 둘 중 어느 쪽인지 꼭 적어주십시오 — 아래 F 블록 전부가 여기에 달려 있습니다"),

"RV-40": (["북마크바를 켜고 시작 가장자리의 Sunshine 버튼을 확인한다",
  "`Ctrl+Shift+B` 로 바를 숨긴다"],
  "버튼도 바와 함께 사라진다",
  "바를 숨겼는데 버튼이 남아 있다. (참고: 사라지는 게 정상 동작이고, 그게 의도인지는 ADR 0014 가 답하지 않았습니다 — 느끼신 바가 있으면 메모에 적어주십시오)"),

"RV-41": (["북마크바에 **폴더**가 하나도 없으면 하나 만든다: 바를 우클릭 → 폴더 추가",
  "바의 폴더 아이콘을 본다",
  "빌드 #47 이전 스크린샷이 있으면 나란히 놓고 본다"],
  "폴더가 대표님이 올리신 이미지다 — 청록 뒷판 위에 반투명 파란 앞판. 버튼 위치와 간격은 그대로",
  "**Chromium 의 회색 외곽선 폴더 그대로다** → 패치 0026 이나 오버레이가 안 들어간 것입니다. 또는 아이콘 때문에 버튼이 커지거나 밀렸다"),

"RV-42": (["RV-41 에서 본 그 폴더를 **클릭**해서 메뉴를 내린다",
  "메뉴 **안쪽** 항목들의 폴더 아이콘을 본다"],
  "안쪽은 여전히 Chromium 의 단색 외곽선 폴더다. **이게 정상이고 예상된 결과입니다**",
  "(이 게이트는 사실상 실패할 수 없습니다. 안쪽까지 새 아이콘이면 오히려 적어주십시오 — 제 설명이 틀린 것입니다)"),

"RV-43": (["Windows 설정 → 시스템 → 디스플레이 → 배율을 **200%** 로 바꾼다",
  "안내대로 로그아웃했다가 다시 로그인하거나, 최소한 Sunshine 을 완전히 껐다 켠다",
  "북마크바의 폴더 아이콘을 확대해서 본다",
  "확인이 끝나면 배율을 원래대로 돌려놓는다"],
  "아이콘이 선명하다. 가장자리가 뭉개지거나 번지지 않는다",
  "**흐릿하게 확대된 것처럼 보인다** → 200% 이미지를 못 찾고 100% 짜리를 늘린 것입니다. 이건 빌드 문제이니 그대로 적어주십시오"),

# --- Block F1: what the leading edge no longer has -------------------------
"RV-48": (["**새 프로필**을 만든다: 오른쪽 위 프로필 아이콘 → 추가 → (로그인 없이) 계속",
  "새로 열린 창에서 `Ctrl+Shift+B` 로 북마크바를 켠다",
  "바의 **시작(왼쪽) 가장자리**를 본다"],
  "Sunshine 버튼 하나만 있고, 저장된 탭 그룹 격자 버튼도 그 옆 구분선도 없다",
  "탭 그룹 버튼이 아직 있다 → **먼저 새 프로필이 맞는지 확인해주십시오.** 이 설정은 동기화되고 한 번이라도 켠 프로필은 자기 값을 유지하므로, 기존 프로필에서는 남아 있는 것이 정상입니다"),

"RV-49": (["북마크바의 빈 곳을 **우클릭**한다",
  "메뉴에서 '탭 그룹 표시' 를 찾는다",
  "눌러서 켜고, 바를 본다. 다시 눌러 끈다"],
  "항목이 그대로 있고 체크는 꺼져 있으며, **켜면 탭 그룹 버튼이 돌아오고 끄면 사라진다**",
  "항목이 메뉴에서 아예 없어졌거나, 눌러도 아무 변화가 없다. 둘 다 결함입니다 — 기본값만 바꿨지 컨트롤을 없앤 게 아닙니다"),

# --- Block F2: split view --------------------------------------------------
"RV-44": (["탭 두 개를 연다",
  "한쪽 탭을 우클릭 → **분할 화면**(또는 탭을 창 오른쪽 가장자리로 끈다)",
  "두 패널 **사이의 구분선**을 본다. 마우스는 올리지 않는다"],
  "구분선 위, 드래그 손잡이보다 **위쪽**에 둥근 버튼이 하나 보인다. 마우스를 안 올려도 보인다",
  "**마우스를 올려야만 보인다** → 실패입니다(그게 이 기능의 전부입니다). 아예 없다 → 패치 0027 이 안 들어간 것"),

"RV-45": (["두 패널의 내용을 구분할 수 있게 서로 다른 페이지를 띄운다",
  "어느 쪽이 **활성**인지 기억해둔다(탭 줄에서 진하게 보이는 쪽)",
  "그 버튼을 누른다",
  "이어서 구분선을 **더블클릭**해본다"],
  "두 패널이 자리를 바꾸고, 탭 순서도 같이 바뀌며, 활성 탭은 활성 그대로. 아이콘이 반대를 가리키게 된다. **더블클릭도 똑같이 동작한다**",
  "내용만 바뀌고 탭 순서는 그대로이거나, 활성 탭이 바뀌거나, 버튼과 더블클릭의 결과가 서로 다르다"),

"RV-46": (["구분선의 **버튼이 아닌 곳**을 잡고 좌우로 끌어본다",
  "이번엔 **버튼 위**에서 누른 채 끌어본다",
  "Tab 을 여러 번 눌러 드래그 손잡이에 포커스가 갈 때까지 간 뒤 ← → 키를 눌러본다"],
  "버튼이 아닌 곳으로는 크기가 바뀌고, **버튼 위에서 시작한 누름은 크기를 바꾸지 않으며**, 화살표 키로도 조절된다",
  "구분선 어디를 잡아도 안 끌리거나(버튼이 드래그를 먹은 것), 반대로 버튼을 눌렀는데 크기가 바뀐다(스왑이 안 될 것)"),

"RV-47": (["버튼에 마우스를 **올린 채** 잠시 기다려 툴팁을 읽는다",
  "빌드 #47 의 분할 화면 스크린샷을 옆에 띄운다(없으면 이 항목은 눈대중으로)",
  "두 패널 사이 간격을 비교한다"],
  "툴팁은 **Reverse views**. 구분선이 이전보다 약 두 배(10px → 20px) 넓고 패널이 그만큼 좁다",
  "툴팁 문구가 다르거나 안 뜬다. **간격에 대한 판단은 실패가 아니라 의견입니다** — '컨트롤이 놓인 구분선'으로 보이는지 '그냥 벌어진 틈'으로 보이는지 한 줄 적어주시면 그게 ADR 0021 의 답이 됩니다"),

# --- Block F3: a module actually mounted -----------------------------------
"RV-50": (["주소창에 `chrome://sunshine-shell` 을 넣고 Enter",
  "왼쪽 독(세로 목록)에서 **DevOS** 를 고른다",
  "헤더와 그 아래 탭 줄을 본다"],
  "헤더에 **DevOS**, 그 아래 **Overview / Repositories / Decisions** 세 탭, 헤더 오른쪽에 **Refresh** 와 **Details**",
  "빈 화면이거나 '모듈을 불러올 수 없다'는 식의 문구. 독에 DevOS 가 아예 없으면 그것도 적어주십시오"),

"RV-51": (["세 탭을 하나씩 눌러본다",
  "본문(가운데 큰 영역) 안쪽에 **또 다른 탭 줄이나 제목이 있는지** 본다"],
  "탭을 누르면 본문이 바뀐다. 그리고 본문 **안에는** 탭 줄도, 모듈 제목도, 모듈 스위처도 없다",
  "본문 안에 탭 줄이 하나 더 있어 **모든 게 두 개로 보인다** → 모듈이 자기 것을 안 지운 것입니다"),

"RV-52": (["헤더 오른쪽의 **Details** 를 누른다"],
  "오른쪽에 패널(E 영역)이 열린다",
  "아무 일도 안 일어난다 → 모듈의 요청이 셸에 도착하지 않은 것입니다. 그대로 적어주십시오"),

"RV-53": (["세 탭을 하나씩 열어 **쓰여 있는 문장을 읽는다**",
  "숫자·0·빈 차트·'0개의 저장소' 같은 표현이 하나라도 있는지 본다"],
  "탭마다 '무엇을 보여줄 것인가' 와 **'아직 아무것도 읽지 않았다'** 를 말한다. 숫자가 하나도 없다",
  "**숫자나 0 이나 빈 차트가 보인다 → 그것은 지어낸 값입니다.** 이 모듈은 네트워크가 막혀 있어 읽을 수가 없습니다. 무엇이 보였는지 그대로 적어주십시오"),

"RV-35": (["DevOS 가 마운트된 상태에서 **Details** 로 E 영역을 연다",
  "두 번째 탭에 `chrome://process-internals` 를 열고 프레임 수를 적어둔다",
  "첫 탭으로 돌아가 E 영역을 **닫는다**",
  "`chrome://process-internals` 를 새로고침하고 다시 센다"],
  "E 를 닫으면 프레임이 **하나 줄어든다** — 치워둔 영역 뒤에서 모듈이 계속 돌지 않는다",
  "프레임 수가 그대로다 → 숨겼을 뿐 살아 있는 것입니다"),

"RV-36": (["독에서 DevOS 를 고른다. 어떤 탭에 있었는지 기억해둔다",
  "다른 모듈로 갔다가 DevOS 로 돌아온다",
  "**마운트를 선언한 모듈이 DevOS 하나뿐이면 여기까지가 한계입니다 — NOT RUN 으로 적어주십시오**"],
  "돌아왔을 때 DevOS 가 **처음부터 다시 시작**한다. 이전 상태가 남아 있지 않다",
  "이전 탭·스크롤 위치가 그대로 남아 있다 → 프레임이 재사용된 것입니다"),

# --- Block A0: the setup window -------------------------------------------
"RV-54": (["`sunshine-setup.exe` 가 있는 폴더를 연다",
  "**더블클릭하고 5초 센다**",
  "**창이 안 뜨면 여기서 멈추십시오.** PowerShell 을 열고 그 폴더로 이동한 뒤 아래를 그대로 실행합니다",
  "`(Start-Process .\\sunshine-setup.exe -PassThru -Wait).ExitCode`",
  "화면에 나온 **숫자를 그대로** 메모에 적어주십시오"],
  "설치 창이 뜬다",
  "**아무것도 안 뜬다** → 위 숫자가 원인을 말해줍니다. `-1073741571` 이면 스택 오버플로(#56 과 같은 것), `-1073741515` 면 DLL 누락(#55 와 같은 것)입니다. 숫자 없이 '안 됩니다' 만으로는 두 개를 구분할 수 없습니다"),

"RV-55": (["뜬 창에서 **모든 사용자** 를 고른다",
  "위치 상자에 아무 경로나 입력해본다 (예: `D:\\Test`)",
  "**이 PC의 나만** 으로 바꾼다",
  "다시 **모든 사용자** 로 바꾼다",
  "이걸 서너 번 빠르게 반복한다"],
  "상자 아래 설명 문장이 매번 따라 바뀌고, **나만** 에서는 상자가 비면서 흐려진다. 창이 계속 반응한다",
  "**창이 멈추거나 사라진다** → 느린 게 아니라 결함입니다. 어느 동작에서 그랬는지 적어주십시오. 이게 빌드 #56 이 아예 안 뜬 바로 그 원인입니다"),
}


HOWTO.update(RETEST_HOWTO)

GATE_ROW = re.compile(r"^\| (RV-\d+|RVV-\d+) \| (.*?) \| (.*?) \|(?: (.*?) \|)?\s*$", re.M)
BLOCK_ROW = re.compile(
    r"^\| \*\*([A-Z]\d?) — [^|]*\*\* \| ([^|]+) \| ([^|]+) \| ([^|]+) \|\s*$", re.M)


def check_stamp_is_current(root: Path) -> None:
    """Refuse a BUILD stamp older than the newest build the document discusses.

    `docs/RUNTIME_VERIFICATION.md` names builds as it records what each one
    did, so the highest number in it is a lower bound on what has been built.
    A stamp below that is not merely old -- it is a claim about which binary a
    result describes, and it would be wrong.
    """

    text = (root / "docs/RUNTIME_VERIFICATION.md").read_text(encoding="utf-8")
    cited = [int(n) for n in re.findall(r"#(\d\d)\b", text)]
    stamped = re.match(r"#(\d+)", BUILD)
    if not stamped:
        raise SystemExit(f"BUILD does not start with a build number: {BUILD!r}")
    if cited and int(stamped.group(1)) < max(cited):
        raise SystemExit(
            f"BUILD says {BUILD}, but docs/RUNTIME_VERIFICATION.md already "
            f"discusses build #{max(cited)}. Every exported result carries this "
            "stamp, so a stale one attributes the run to the wrong binary"
        )


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
        # The cell is written for a person: "**RV-39 first**, then RV-41, ...,
        # RV-43 last". Splitting on commas handed those decorations through as
        # gate ids and every one of them failed the lookup below. The order in
        # the cell is still the order that is kept; only the prose is dropped.
        ids = re.findall(r"RVV?-\d+", match.group(2))
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
    do, ok, no = HOWTO[gate["id"]]
    steps = "".join(f"<li>{markup(item)}</li>" for item in do)
    if "{codes}" in expected_ko:
        codes = ", ".join(f"`{token}`" for token in re.findall(r"`([^`]+)`", gate["expected"]))
        expected_ko = expected_ko.replace("{codes}", codes)
    return f"""
      <div class="gate" data-gate="{gate['id']}">
        <div class="stripe" aria-hidden="true"></div>
        <div class="gid"><span class="idtag">{gate['id']}</span>{badge}</div>
        <div class="body">
          <p class="step">{markup(step_ko)}</p>
          <ol class="do">{steps}</ol>
          <p class="verdict ok"><span class="vlabel">합격</span>{markup(ok)}</p>
          <p class="verdict no"><span class="vlabel">불합격</span>{markup(no)}</p>
          <p class="exp"><span class="explabel">계약 문구</span>{markup(expected_ko)}</p>
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
    # The stamp used to exist twice -- once in the header, once inside the
    # export text -- and the second copy went two builds stale without anything
    # noticing. A result that names the wrong build is a result about an unknown
    # binary, so there is now one stamp and nothing else may spell one.
    check_stamp_is_current(root)

    hardcoded = re.findall(r"#\d\d\b", SCRIPT + SHELL)
    if hardcoded:
        raise SystemExit(
            f"a build number is written into the page instead of coming from "
            f"BUILD: {hardcoded}"
        )

    gate = gates(root)
    # There was a bare `len(gate) != 43` here, and it is gone rather than
    # raised to 60. It was a second place to write a number that the two checks
    # below already decide exactly: KOREAN must be a bijection with the gate
    # table, so a gate added or removed upstream fails there, by name, saying
    # which. The count said only that something had moved -- and because
    # nothing in CI ran this script, what it actually did for fifteen gates and
    # three releases was refuse to generate the sheet at all, silently, while
    # the owner went on using a stale one.

    # A gate added upstream without a translation must stop this script rather
    # than appear in English among Korean rows, where a reader would take the
    # odd one out for a formatting slip instead of a missing translation.
    runnable = set(gate) - set(BLOCKED) - set(DONE) - set(VERIFIED)
    unwalked = sorted(runnable - set(HOWTO))
    if unwalked:
        raise SystemExit(
            f"these gates have no walkthrough and a reader cannot start from "
            f"the contract's wording alone: {unwalked}"
        )
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
        ids = [gid for gid in ids if gid not in VERIFIED]
        if not ids:
            continue
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

    # RV-35/36 cannot run and RV-7 already has evidence; neither belongs on a
    # sheet whose only purpose now is the seventeen still open.
    blocked_html = ""
    done_html = ""
    _unused = "".join(
        locked_row(gate[gid], "막힌 이유", why, "blocked",
                   '<span class="locknote">실행 불가</span>')
        for gid, why in BLOCKED.items())
    _unused2 = "".join(
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
    ) + SCRIPT.replace("__BUILD_STAMP__", esc(f"{BUILD}, {REVISION}"))


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
.start{margin:28px 0 0;border:1px solid var(--rule);border-left:3px solid var(--accent);
  border-radius:4px;background:var(--surface);padding:18px 20px}
.start h3{font-family:Archivo,sans-serif;font-size:13px;letter-spacing:.06em;text-transform:uppercase;
  margin:0 0 10px;color:var(--accent)}
.start p{margin:0 0 10px;font-size:14px;line-height:1.6;max-width:70ch}
.start ul{margin:0 0 10px;padding-left:20px;font-size:14px;line-height:1.6;max-width:70ch}
.start li{margin-bottom:5px}
.start em{font-style:normal;font-family:"IBM Plex Mono",monospace;font-size:12px;
  background:var(--surface-2);border:1px solid var(--rule-2);border-radius:3px;padding:1px 5px}
.startnote{color:var(--ink-3);font-size:13px}
.rules{margin:20px 0 0;border:1px solid var(--rule);border-left:3px solid var(--warn);
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
.do{margin:9px 0 0;padding-left:20px;font-size:13.5px;line-height:1.6;color:var(--ink)}
.do li{margin-bottom:3px}
.do li::marker{color:var(--ink-3);font-family:"IBM Plex Mono",monospace;font-size:11px}
.verdict{margin:8px 0 0;font-size:13.5px;line-height:1.5;padding-left:10px;border-left:3px solid}
.verdict.ok{border-color:var(--pass)}
.verdict.no{border-color:var(--fail)}
.vlabel{font-family:"IBM Plex Mono",monospace;font-size:10.5px;letter-spacing:.09em;
  font-weight:600;margin-right:8px}
.verdict.ok .vlabel{color:var(--pass)}
.verdict.no .vlabel{color:var(--fail)}
.exp{margin-top:10px}
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
    <h1>다시 볼 열일곱 가지</h1>
    <p class="sub"><strong>통과한 26개는 지웠습니다.</strong> 남은 것은 실패했거나, 화면을 못 찾으셨거나,
    제 설명이 부실해서 손대지 못하신 항목들입니다.
    문서 표면(<code>chrome://sunshine-document</code>) 설명은 <strong>제가 계약서만 보고 지어낸 것</strong>이라
    실제 화면과 달랐습니다. 실제 화면을 확인하고 다시 썼습니다.</p>
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
    <h3>지난 결과 — 중단 규칙은 걸리지 않았습니다</h3>
    <p style="margin:0 0 12px;font-size:14px;color:var(--ink-2);max-width:70ch">
    <strong>RV-1 · RV-2 · RV-3 · RV-4 가 모두 통과했습니다.</strong> 샌드박스도, 사이트 격리도,
    스킴 미등록도 계약대로입니다. 세션을 중단시킬 실패는 없었고, 이건 오늘 나온 것 중 가장 큰 결과입니다.
    아래는 참고용으로 남겨둔 원래 규칙입니다.</p>
    <dl>
      <dt>RV-1 · RV-2 · RV-3</dt>
      <dd><strong>세션 중단.</strong> 샌드박스나 격리 posture가 틀렸다면, 그 아래 모든 게이트는 계약이 설명하는 것과 다른 보안 모델의 브라우저에서 도는 것입니다. 기록할 가치가 없습니다.</dd>
      <dt>RV-26 · RV-29 · RV-30</dt>
      <dd>블록 A를 끝내고 중단. 인스톨러 정체성이고 ADR 0015의 주제 전체이며, 실패는 나머지를 돌기 전에 인스톨러를 다시 만들어야 한다는 뜻입니다.</dd>
      <dt>그 외</dt>
      <dd>기록하고 계속. 한 표면의 실패가 다음 표면에 대해 말해주는 것은 없습니다.</dd>
    </dl>
  </section>

  <section class="start">
    <h3>읽어주십시오</h3>
    <p><strong>가장 먼저 답해주실 것 하나:</strong> 설치할 때 <strong>내 계정</strong>과 <strong>전체 사용자</strong> 중
    무엇을 고르셨습니까? RV-26 의 첫 줄입니다. 전체 사용자를 고르셨다면 설치 폴더가 Program Files 이고,
    그건 <strong>정상</strong>인데 제가 지난 설명에 <code>%LOCALAPPDATA%</code> 만 적어놨습니다.
    그 한 가지로 지난번 실패 두 개가 설명될 수 있습니다.</p>
    <ul>
      <li><strong>모르겠거나 화면을 못 찾으면 NOT RUN 입니다.</strong> 추측해서 PASS 를 누르지 마십시오 —
      모른다는 것도 결과이고, 그게 제일 쓸모 있는 답입니다.</li>
      <li><strong>메모칸이 이번에는 중요합니다.</strong> 실패한 항목은 <em>무엇이 보였는지</em> 한 줄만 적어주십시오.
      지난번에는 결과만 있고 관찰이 없어서 원인을 좁힐 수 없었습니다.</li>
      <li><strong>순서는 아무래도 괜찮습니다.</strong> 다만 <strong>RV-13 을 먼저</strong> 하시면 그 뒤 다섯 개
      (RV-14~19)가 거기서 만든 것을 이어서 씁니다.</li>
      <li><strong>페이지를 저장해서 보내지 마십시오.</strong> 저장하면 선택은 남지만 <strong>메모가 사라집니다</strong>.
      맨 아래 <strong>결과 복사</strong> 버튼을 쓰시면 둘 다 담깁니다.</li>
    </ul>
    <p class="startnote">항목마다 <em>계약 문구</em>와 <em>원문</em>이 접혀 있습니다. 읽지 않으셔도 됩니다 —
    번역이 원문과 어긋났을 때 그 자리에서 보이라고 남겨둔 것입니다.</p>
  </section>
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
    <p><strong>답하지 않은 항목도 함께 나옵니다.</strong> 설명이 부족해서 못 하신 것이라면 비워둔 채로 복사해 주십시오 —
    그 목록이 제가 다시 써야 할 항목입니다. 페이지를 저장해서 보내주시는 것보다 이 버튼이 확실합니다
    (저장한 페이지에는 입력하신 내용이 함께 담기지 않습니다).</p>
    <textarea id="out" readonly placeholder="아직 표시할 결과가 없습니다."></textarea>
    <p class="saved" id="saved" style="margin-top:8px"></p>
  </section>
</div>

"""

SCRIPT = r"""<script>
(function(){
  var KEY = "sunshine-gate-sheet-retest-v1";
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
    L.push("# Sunshine 재테스트 결과 (17개)");
    L.push("");
    L.push("- 빌드: __BUILD_STAMP__");
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
    // The unanswered gates, by name. This is the half of the report that
    // matters most: the owner's first pass through the sheet left rows blank
    // because they could not tell what to do, and a report that listed only
    // answers made that invisible -- I could see what worked and not what was
    // unusable, which is the thing I need to fix.
    var blank = live.filter(function(g){ return !(state[g.dataset.gate]||{}).r; })
                    .map(function(g){ return g.dataset.gate; });
    if (blank.length) {
      L.push("## 따라 하지 못한 항목");
      L.push("");
      L.push("아래는 답하지 않은 항목입니다. 설명이 부족해서 못 하신 것이라면 그대로 두시면 됩니다 — 이 목록이 다시 쓸 대상입니다.");
      L.push("");
      L.push(blank.join(", "));
      L.push("");
    }
    if (n.pass + n.fail + n.na === 0 && !blank.length) return "아직 표시할 결과가 없습니다.";
    if (n.pass + n.fail + n.na === 0) return L.join("\n");
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
