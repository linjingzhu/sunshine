# Reusable Project Development Dashboard Specification

## 1. 문서 목적

이 문서는 소프트웨어·게임·콘텐츠·연구 프로젝트에서 반복 사용할 수 있는 **개발 진행 대시보드**의 이식형 제품·UX·구현 명세다.

특정 프로젝트의 이름, 일정, 단계, Worker, 저장소 주소를 포함하지 않는다. 새 프로젝트에서는 `Project Configuration` 데이터만 교체하고 공통 UI와 동작은 그대로 재사용한다.

대시보드의 핵심 목적은 다음과 같다.

1. 전체 개발 단계를 한 화면에서 이해한다.
2. 세부 작업을 체크하며 진행률을 자동 계산한다.
3. 각 단계의 결정·문제·다음 행동을 기록한다.
4. Worker 또는 담당 영역의 배분 상태를 확인한다.
5. 주차별 일정과 릴리스 목표를 비교한다.
6. CI 빌드 상태와 최신 실행 제품으로 빠르게 이동한다.

---

## 2. 적용 범위

### 적합한 프로젝트

- 웹·앱·게임 개발
- 사내 도구와 자동화 시스템
- 콘텐츠 제작 파이프라인
- 연구·프로토타입 프로젝트
- 출시 일정이 있는 제품 개발
- 여러 AI Worker 또는 사람 담당자가 나뉘는 프로젝트

### 기본 전제

- 단일 프로젝트를 추적하는 개인용 또는 소규모 팀용 대시보드
- 별도 서버 없이 브라우저 저장소로 개인 진행 기록 보존 가능
- 프로젝트 데이터와 UI 로직을 분리
- 모바일과 데스크톱 모두 지원
- CI와 최신 빌드 URL은 선택 기능

---

## 3. 정보 구조

```text
Project Dashboard
├─ Global Header
│  ├─ Project Identity
│  └─ Save Status
├─ Project Hero
│  ├─ Project Goal
│  ├─ Overall Progress
│  └─ Summary Metrics
├─ Navigation Tabs
│  ├─ Roadmap
│  ├─ Worker Operations
│  ├─ Schedule
│  └─ Test Build Center
├─ Main Content
│  └─ Active Tab Content
└─ Footer
   ├─ Project Tagline
   └─ Local Progress Reset
```

기본 탭은 `Roadmap`이다. 새로고침해도 체크 상태와 메모는 유지하며, 탭 상태는 유지해도 되고 초기 탭으로 돌아가도 된다.

---

## 4. Project Configuration

프로젝트마다 아래 데이터만 교체한다. UI 컴포넌트 내부에 프로젝트 고유 텍스트를 하드코딩하지 않는다.

```ts
type ProjectConfig = {
  id: string;
  name: string;
  dashboardTitle: string;
  tagline: string;
  objective: string;
  targetDuration: string;
  targetRelease: string;
  storageKey: string;
  repositoryUrl?: string;
  workflowUrl?: string;
  latestBuildUrl?: string;
  latestSuccessfulRunUrl?: string;
};
```

예시:

```ts
const project: ProjectConfig = {
  id: "sample-project",
  name: "Sample",
  dashboardTitle: "Development Roadmap",
  tagline: "아이디어를 출시 가능한 제품으로.",
  objective: "핵심 기능을 검증하고 첫 공개 버전을 완성한다.",
  targetDuration: "10주",
  targetRelease: "2027 Q1",
  storageKey: "sample-project-dashboard-v1",
  repositoryUrl: "https://github.com/OWNER/REPOSITORY",
  workflowUrl: "https://github.com/OWNER/REPOSITORY/actions",
  latestBuildUrl: "https://example-build.app",
};
```

`storageKey`에는 프로젝트 ID와 데이터 스키마 버전을 포함한다. 서로 다른 프로젝트가 같은 브라우저 저장값을 공유하지 않도록 한다.

---

## 5. 데이터 모델

### 5.1 Development Stage

```ts
type Stage = {
  id: number;
  phase: string;
  title: string;
  duration: string;
  weeks: string;
  description: string;
  workers: string[];
  tasks: string[];
  milestone: string;
};
```

작성 원칙:

- 한 단계는 하나의 검증 가능한 결과를 만든다.
- 작업 항목은 3~7개를 권장한다.
- `milestone`은 활동이 아니라 완료 판정 기준으로 작성한다.
- `weeks`는 절대 날짜보다 `W1`, `W2–3`처럼 계획상 위치를 우선한다.
- 단계 ID는 화면 순서와 무관한 안정적인 식별자로 사용하는 것이 좋다.

### 5.2 Worker

```ts
type Worker = {
  id: string;
  name: string;
  tone: "coral" | "amber" | "mint" | "blue" | "violet" | "slate";
  scope: string;
};
```

Worker는 AI 세션, 사람, 팀, 전문 영역 모두를 의미할 수 있다. 이름보다 책임 범위가 먼저 드러나야 한다.

### 5.3 Schedule Item

```ts
type ScheduleItem = {
  period: string;
  objective: string;
  workers: string[];
  state?: "planned" | "current" | "completed" | "blocked";
};
```

### 5.4 Release Milestone

```ts
type ReleaseMilestone = {
  period: string;
  title: string;
  description: string;
  primary?: boolean;
};
```

### 5.5 Build Configuration

```ts
type BuildConfig = {
  targetBranch: string;
  workflowUrl?: string;
  latestBuildUrl?: string;
  latestRunUrl?: string;
  checks: Array<{
    state: "success" | "automatic" | "running" | "failed" | "not-configured";
    title: string;
    detail: string;
  }>;
};
```

---

## 6. 화면별 기능 명세

## 6.1 Global Header

항상 표시하는 요소:

- 프로젝트 심볼 또는 짧은 이름
- `Development Roadmap` 등 대시보드 성격
- 자동 저장 상태

권장 동작:

- 스크롤 시 상단 고정
- 반투명 배경과 약한 블러 사용 가능
- 저장 성공 여부를 텍스트와 상태점으로 함께 표시
- 저장 실패 시 성공처럼 표시하지 않는다.

## 6.2 Project Hero

포함 요소:

- 프로젝트 유형 또는 출시 목표를 나타내는 Eyebrow
- 한 문장의 제품 목표
- 전체 진행률 원형 또는 막대 시각화
- 현재 단계
- 완료 단계 수
- 완료 체크리스트 수
- 목표 출시 시점

진행률 계산:

```ts
totalTasks = stages.flatMap(stage => stage.tasks).length;
completedTasks = completedTaskIds.length;
progress = totalTasks === 0
  ? 0
  : Math.round((completedTasks / totalTasks) * 100);
```

완료 단계 계산:

```ts
completedStages = stages.filter(stage =>
  stage.tasks.every((_, index) =>
    completedTaskIds.includes(`${stage.id}-${index}`)
  )
).length;
```

현재 단계는 모든 작업이 완료되지 않은 첫 번째 단계다. 모든 단계가 끝났다면 마지막 단계 또는 `프로젝트 완료` 상태를 표시한다.

## 6.3 Roadmap Tab

각 단계 행의 축약 상태에서 표시:

- 단계 번호
- Phase와 계획 주차
- 단계명
- 한 줄 설명
- 참여 Worker
- 완료 작업 수
- 펼치기 상태

펼친 상태에서 추가 표시:

- 체크 가능한 세부 작업
- 완료 기준
- 단계 메모

체크리스트 동작:

- 체크 즉시 진행률에 반영
- 체크된 항목은 색상과 취소선으로 구분
- 체크박스 전체 영역을 클릭 가능하게 구성
- 키보드로 포커스하고 조작 가능해야 함

단계 메모:

- 결정 사항
- 현재 막힌 점
- 다음 행동
- 검토가 필요한 위험

메모는 입력할 때마다 자동 저장한다. 서버 저장이 없다면 `이 기기에 저장됨`을 명확히 표시한다.

## 6.4 Worker Operations Tab

Worker 카드에 표시:

- Worker ID
- 역할명
- 책임 범위
- 참여 단계 수
- 전체 단계 중 참여 위치 미니맵

운영 원칙:

- Worker는 구현 또는 전문 검토를 담당한다.
- Manager는 통합 순서, 충돌 방지, 검증과 최종 결정을 담당한다.
- 같은 파일이나 기능에 대한 중복 소유를 최소화한다.
- Worker 수는 고정하지 않고 독립 가능한 업무량에 따라 조절한다.

## 6.5 Schedule Tab

표시 요소:

- 주차 또는 기간
- 그 기간의 핵심 목표
- 참여 Worker
- 현재·완료·차단 상태
- 주요 릴리스 카드

일정은 세부 작업표가 아니라 프로젝트의 시간적 흐름을 빠르게 이해하는 용도로 제한한다. 세부 작업은 Roadmap에 둔다.

## 6.6 Test Build Center

필수 요소:

- 대상 브랜치
- 자동 검사 목록과 상태
- CI 연결 상태
- 최근 성공 또는 실패 정보
- `빌드 실행·결과 보기` 버튼
- `최신 버전 실행` 버튼

버튼 규칙:

### 빌드 실행·결과 보기

- CI workflow 또는 Actions 화면을 새 창에서 연다.
- 실제 빌드 실행 권한은 해당 서비스의 인증과 권한 정책을 따른다.
- 대시보드 버튼 자체가 실행 성공을 보장하는 것처럼 표현하지 않는다.

### 최신 버전 실행

- 현재 테스트 가능한 최신 제품 URL을 새 창에서 연다.
- `latestBuildUrl`이 없으면 버튼을 숨기거나 비활성화하고 `실행 가능한 빌드 없음`을 표시한다.
- CI 성공 여부와 배포 성공 여부를 혼동하지 않는다.
- 가능하면 배포 시점, 버전 또는 Commit 정보를 함께 표시한다.

두 버튼은 데스크톱에서 나란히, 좁은 모바일에서는 같은 너비의 2열 또는 세로 배열로 표시한다.

---

## 7. 상태 저장 명세

기본 저장 구조:

```ts
type DashboardState = {
  schemaVersion: 1;
  completedTaskIds: string[];
  stageNotes: Record<number, string>;
  updatedAt: string;
};
```

저장 예시:

```ts
localStorage.setItem(
  project.storageKey,
  JSON.stringify({
    schemaVersion: 1,
    completedTaskIds,
    stageNotes,
    updatedAt: new Date().toISOString(),
  })
);
```

불러오기 검증:

- JSON 파싱 실패 시 빈 상태로 복구
- 배열과 문자열 타입 검증
- 현재 존재하지 않는 작업 ID는 진행률 계산에서 제외
- 단계 메모가 문자열이 아니면 무시
- 스키마 버전이 바뀌면 migration 또는 안전한 초기화 수행

저장 실패 처리:

- 저장 공간 부족, 개인정보 보호 모드 등 예외를 처리
- 실패 시 `저장 실패`를 사용자에게 표시
- 저장되지 않았는데 `자동 저장됨`으로 표시하지 않음

---

## 8. 초기화 기능

Footer에 `진행 기록 초기화`를 제공한다.

동작:

1. 확인 대화상자 표시
2. 체크 상태 삭제
3. 단계 메모 삭제
4. 해당 프로젝트의 저장 키만 삭제
5. 진행률 재계산
6. 초기 화면으로 복귀

다른 프로젝트나 다른 앱의 브라우저 데이터를 삭제하면 안 된다.

확인 문구 예시:

> 모든 체크와 단계 메모를 초기화할까요? 이 작업은 되돌릴 수 없습니다.

---

## 9. UX 원칙

### 한눈에 이해

- 첫 화면에서 목표, 진행률, 현재 단계, 출시 시점을 이해할 수 있어야 한다.
- 장식보다 상태와 다음 행동을 우선한다.
- 같은 정보의 중복 시각화를 최소화한다.

### Progressive Disclosure

- 전체 단계는 목록으로 비교한다.
- 세부 체크리스트와 메모는 필요한 단계만 펼친다.
- 펼치지 않아도 단계 진행 상태는 보여야 한다.

### 상태의 정직성

- `성공`, `실행 중`, `자동`, `설정 필요`, `실패`를 구분한다.
- 로컬 저장과 서버 저장을 구분한다.
- CI 통과와 실제 제품 배포 완료를 구분한다.

### 프로젝트 고유 콘텐츠와 공통 기능 분리

- 색상, 컴포넌트, 계산, 저장 로직은 공통 계층
- 단계, Worker, 일정, 링크, 카피는 프로젝트 설정 계층

---

## 10. 반응형 규칙

### Desktop

- 최대 콘텐츠 너비 약 1180px
- Hero 목표와 진행률 시각화를 2열 배치
- Build Center를 검사 영역과 연결 상태 영역으로 분할
- Worker 카드는 3열 권장

### Mobile

- 헤더의 보조 문구 축약 가능
- Hero는 단일 열
- 진행률 수치는 유지하되 큰 장식은 생략 가능
- 탭은 가로 스크롤 허용
- Roadmap의 Worker pill과 부가 설명 일부 축약 가능
- 단계 상세는 단일 열
- Worker 카드, 일정, Build Center는 단일 열
- 주요 버튼의 터치 영역은 최소 44×44px

---

## 11. 접근성 요구사항

- 모든 탭은 실제 `button` 요소 사용
- 현재 탭은 시각 상태와 `aria-selected`로 표시
- 단계 펼치기 버튼에 `aria-expanded` 제공
- 체크박스는 연결된 텍스트 라벨 제공
- 진행률에는 텍스트 값 또는 접근 가능한 이름 제공
- 색상만으로 성공·실패·완료를 구분하지 않음
- 모든 버튼과 링크에 `:focus-visible` 스타일 제공
- 본문 대비는 WCAG AA 수준 권장
- 애니메이션은 `prefers-reduced-motion` 존중
- 새 창 링크는 화살표 또는 보조 텍스트로 알림

---

## 12. 컴포넌트 권장 구조

```text
DashboardApp
├─ GlobalHeader
├─ ProjectHero
│  ├─ ProgressVisual
│  └─ SummaryMetrics
├─ DashboardTabs
├─ RoadmapPanel
│  └─ StageRow
│     ├─ TaskChecklist
│     └─ StageNotes
├─ WorkerPanel
│  └─ WorkerCard
├─ SchedulePanel
│  ├─ ScheduleTimeline
│  └─ ReleaseCard
├─ BuildCenter
│  ├─ BuildActions
│  ├─ BuildChecks
│  └─ IntegrationStatus
└─ DashboardFooter
```

초기 버전은 하나의 페이지 컴포넌트로 구현할 수 있다. 재사용 프로젝트가 늘어나면 데이터, 상태 Hook, 패널, 공통 UI 순으로 분리한다.

권장 분리:

```text
src/
├─ config/project.ts
├─ data/stages.ts
├─ data/workers.ts
├─ data/schedule.ts
├─ hooks/useDashboardState.ts
├─ components/dashboard/
│  ├─ ProjectHero.tsx
│  ├─ RoadmapPanel.tsx
│  ├─ WorkerPanel.tsx
│  ├─ SchedulePanel.tsx
│  └─ BuildCenter.tsx
└─ styles/dashboard.css
```

---

## 13. 필수 테스트 시나리오

### 진행 상태

- 작업 체크 시 완료 항목과 전체 진행률이 함께 증가한다.
- 체크 해제 시 값이 정상 감소한다.
- 한 단계의 모든 작업 완료 시 완료 단계 수가 증가한다.
- 모든 단계 완료 시 완료 상태를 표시한다.

### 저장과 복구

- 체크와 메모 후 새로고침해도 유지된다.
- 잘못된 JSON 저장값이 있어도 화면이 열린다.
- 존재하지 않는 작업 ID가 진행률을 왜곡하지 않는다.
- 저장 실패 시 실패 상태가 표시된다.

### Roadmap

- 단계별 펼치기와 접기가 독립적으로 동작한다.
- 체크박스를 키보드로 조작할 수 있다.
- 메모 입력 중 다른 단계로 이동해도 내용이 보존된다.

### Build Center

- 빌드 결과 버튼이 올바른 CI 주소를 연다.
- 최신 버전 실행 버튼이 올바른 배포 주소를 연다.
- 최신 빌드 URL이 없을 때 오동작하는 링크가 노출되지 않는다.

### 초기화

- 취소하면 기존 데이터가 유지된다.
- 확인하면 해당 프로젝트 데이터만 삭제된다.
- 초기화 후 진행률, 현재 단계, 체크, 메모가 즉시 갱신된다.

### 반응형·접근성

- 360px 너비에서 가로 넘침이 없다.
- 모든 주요 버튼이 44px 이상이다.
- 탭, 단계, 체크박스, 링크를 키보드만으로 사용할 수 있다.
- 포커스 위치가 항상 보인다.

---

## 14. 프로젝트 이식 절차

1. 이 문서를 새 저장소의 `docs/PROJECT_DASHBOARD_SPEC.md`로 복사한다.
2. 프로젝트 이름, 목표, 기간, 출시 목표를 정의한다.
3. `ProjectConfig`를 작성한다.
4. 개발 단계를 6~12개 수준으로 작성한다.
5. 각 단계에 3~7개의 검증 가능한 작업과 완료 기준을 넣는다.
6. Worker 또는 담당 영역을 정의하고 단계에 연결한다.
7. 주차별 일정과 릴리스 마일스톤을 입력한다.
8. 저장소, CI workflow, 최신 빌드 URL을 연결한다.
9. 고유한 `storageKey`를 지정한다.
10. 필수 테스트 시나리오를 통과한다.

AI 개발 도구에 전달할 때는 다음과 같이 요청한다.

> `docs/PROJECT_DASHBOARD_SPEC.md`를 기준으로 현재 프로젝트용 개발 대시보드를 구현해 주세요. 공통 기능과 UX 계약은 유지하되, 프로젝트 데이터는 현재 저장소의 제품 스펙과 개발 계획에서 추출해 `ProjectConfig`, `Stage`, `Worker`, `ScheduleItem`, `BuildConfig`로 분리하세요. 구현 후 진행률, 로컬 저장, 초기화, 모바일, 키보드 접근성, 빌드 링크와 최신 버전 실행 링크를 검증하세요.

---

## 15. 완료 정의

다음 조건을 모두 만족하면 대시보드 이식이 완료된 것으로 본다.

- 프로젝트 목표와 현재 단계가 첫 화면에서 이해된다.
- 단계 체크와 진행률 계산이 일치한다.
- 메모와 체크 상태가 안전하게 저장·복구된다.
- Worker 책임과 참여 단계가 보인다.
- 일정과 릴리스 목표가 연결된다.
- CI 결과와 최신 실행 제품에 접근할 수 있다.
- 초기화가 확인 절차와 함께 동작한다.
- 모바일과 키보드로 핵심 기능을 사용할 수 있다.
- 프로젝트 고유 데이터가 공통 UI 로직과 분리되어 있다.

이 문서는 특정 기술 스택을 강제하지 않는다. React, Vue, Svelte, 정적 HTML 등 어떤 방식으로 구현하더라도 위의 정보 구조, 상태 계약, UX 원칙과 완료 조건을 유지한다.
