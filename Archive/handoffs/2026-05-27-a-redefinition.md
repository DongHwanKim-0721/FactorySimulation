# Handoff: FactorySimulation A Redefinition

Updated: 2026-05-27

## Current Context

Repository: `DongHwanKim-0721/FactorySimulation`

Local workspace: `C:\Users\IJMAIL\vscode-python\FactorySimulation`

Remote: `https://github.com/DongHwanKim-0721/FactorySimulation`

Branch: `main`

Current git state at handoff time:

- `main...origin/main`
- Modified: `app.py`
- Untracked: `docs/prd/phase-a-bundle-hoist-redefinition.md`
- Untracked: `tests/test_app_formatting.py`

No secrets or credentials were present in the conversation.

## What Happened

The user is working in the planned order `D -> A -> C -> B`.

Earlier Phase D and the first Phase A implementation were treated as complete, but the user clarified that the original Phase A definition was wrong for the 강관 인발 domain. The previous Phase A model used EA-level push scheduling, where units move to the next process as soon as each EA finishes. The desired model is now bundle/hoist based:

- INPUT blocks generate material bundles.
- Process blocks handle bundles after upstream work completes.
- Hoist blocks explicitly model material movement in batches.
- Material identity matters because tooling/dies differ by material.

Do not treat `handoffs/2026-05-27-phase-a-complete.md` as the current implementation target. It records completion of the old A definition.

## Artifacts Created

Local PRD file:

- `docs/prd/phase-a-bundle-hoist-redefinition.md`

GitHub parent PRD issue:

- #12 `PRD: 단계 A 재정의 - 묶음/호이스트 기반 공정 시뮬레이션`
- URL: `https://github.com/DongHwanKim-0721/FactorySimulation/issues/12`

Implementation issues created from #12:

- #13 `A 재정의 1 - 원자재 투입 블록을 묶음 소스로 전환`
- #14 `A 재정의 2 - 공정 블록을 묶음 누적 처리로 전환`
- #15 `A 재정의 3 - 호이스트 블록과 이동 시간 계산 추가`
- #16 `A 재정의 4 - 묶음 모델용 그래프 연결 제약 적용`
- #17 `A 재정의 5 - 후속 능력치 기반 묶음 분기 라우팅 구현`
- #18 `A 재정의 6 - 묶음 FIFO 합류와 최종 output 수량 계산`
- #19 `A 재정의 7 - 공정 블록 품종 그룹 우선 처리 적용`
- #20 `A 재정의 8 - 묶음 기반 결과 표시와 수동 스모크 정리`

All created issues have the `ready-for-agent` label. Parent issue #12 remains open.

## Key Domain Decisions

Reference #12 and `docs/prd/phase-a-bundle-hoist-redefinition.md` for full detail. Summary only:

- Existing INPUT block remains, but becomes a source block.
- INPUT fields: material name, input quantity EA, input time minutes.
- Global `units_per_source` / `시작 공정별 투입 수량(EA)` is removed.
- Process fields: process time minutes per EA, parallel processing quantity EA.
- Hoist fields: load capacity EA per trip, move time minutes per trip.
- Simulation unit is a bundle, not an individual EA.
- Serial flow waits for the whole bundle to complete before the next block starts.
- Branching is still automatic for this phase, weighted by downstream capability.
- Merge keeps bundles separate and uses bundle FIFO.
- Process blocks additionally apply material-group priority; hoist blocks do not.
- Final output quantity is the sum of completed quantities at sink blocks.
- Existing JSON compatibility can be dropped.

## Existing Uncommitted Code Change

Before the PRD work, a narrow fix was made to the existing GUI result display:

- Added `format_flow_diagram()` in `app.py`.
- Changed result display so branch/join diagrams use actual connections instead of a fake linear chain.
- Added `tests/test_app_formatting.py`.
- Test run after that change: `python -B -m pytest` -> `16 passed`.

This change is not committed. It may be useful, but the new A redefinition will likely replace more of the result model and GUI wording. Decide whether to keep/adapt it when implementing #20.

## Recommended Next Session

Start with #13. It is the first dependency-free implementation issue and should establish the new data contract:

1. Convert INPUT into a bundle source with material fields.
2. Remove global input quantity from GUI/engine contract.
3. Update JSON roundtrip.
4. Add INPUT-only engine tests.

After #13, proceed in dependency order: #14, #15, #16, #17, #18, #19, #20.

Be careful not to continue implementing the old Phase A semantics in `docs/prd/phase-a-simulation-engine.md`; that document is now historical context.

## Suggested Skills

- `diagnose`: use when replacing engine semantics, especially if old tests conflict with new bundle behavior.
- `grill-me`: use if a domain rule becomes ambiguous again, especially around branch quantity or material grouping.
- `to-issues`: use only if #12 needs further splitting after implementation begins.
- `handoff`: use at the end of the next multi-step session to refresh this context.
