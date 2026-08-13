# Formal Development Reporting

The Manager reports once per meaningful run. Worker logs are internal unless requested.

## Status vocabulary

- `COMPLETED`
- `COMPLETED_WITH_NOTES`
- `ACTION_REQUIRED`
- `FAILED`

## Chat report

Keep the user-facing report compact and formal:

```text
DEVELOPMENT REPORT

Status:
Repository:
Repository Mode:
Integration:

Executive Summary
<what was delivered and overall result>

Delivered
- ...

Verification
- Compile:
- Tests:
- Windows Build:
- Runtime/Visual:
- Adversarial Review:
- Cross-Agent Review:
- Git Conflicts:

Problems Found & Automatically Fixed
- severity — problem → resolution

Remaining Risks
- ...

Efficiency / Meta Evaluation
- workers / mission packs
- conflict/rework observations
- token/time metrics only when reliably available
- strategy lesson, if any

Recommended Next Actions
1. ...
2. ...
3. ...
```

Do not list actions the AI could have safely completed itself.

## Persistent detailed report

When a run is substantial or creates useful engineering history, write a detailed report under:

```text
.ai/reports/YYYY-MM-DD-<short-run-name>.md
```

Keep persistent reports factual and concise.

## Truthfulness

Never claim:
- a build passed if it was not run;
- runtime/visual verification passed if the UI was not observed;
- cross-agent validation happened if only one agent family reviewed;
- exact token/cost numbers if they were not measured.

Use `NOT RUN`, `NOT AVAILABLE`, or `FALLBACK REVIEW` explicitly.
