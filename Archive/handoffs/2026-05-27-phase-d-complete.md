# Handoff — FactorySimulation 단계 D 완료 후

## Context

`DongHwanKim-0721/FactorySimulation` repo의 **단계 D 리팩터링**은 구현, push, 이슈 close까지 완료됐다.

- 로컬 작업 디렉터리: `C:\Users\IJMAIL\vscode-python\FactorySimulation`
- 리모트: https://github.com/DongHwanKim-0721/FactorySimulation
- 브랜치: `main`
- 현재 로컬 상태: `main...origin/main`, clean
- 구현 커밋: `e990a03 Implement phase D refactor`
- 기준 문서: `PRD.md`

## What Changed

상세 diff는 커밋 `e990a03`을 참조하고, 여기서는 다음 세션에 필요한 연결 정보만 남긴다.

- 기존 확장자 없는 `WholeCode`는 `WholeCode.py.bak`로 백업 rename됨.
- `engine/` 모듈 추가:
  - `models.py`: `ProcessBlock`, `ProcessConnection`, `Scenario`
  - `simulation.py`: `simulate()`, `topological_flow()`, 결과 dataclass
  - `scenario_io.py`: JSON `save()` / `load()`
- `app.py` 추가:
  - `App`, `PaletteView`, `CanvasView`, `ResultView`
  - `BlockType`, `BLOCK_TYPES`는 GUI 책임으로 분리
- `main.py` 추가: `App().run()` 진입점
- `tests/` 추가:
  - T1/T2 엔진 골든 테스트
  - `Scenario` 무결성 및 JSON 라운드트립 테스트

## GitHub State

다음 이슈는 구현 완료 코멘트를 남기고 `completed`로 닫힘.

- #1 단계 D — 리팩터링: https://github.com/DongHwanKim-0721/FactorySimulation/issues/1
- #2 D1 엔진 분리 + 골든 테스트: https://github.com/DongHwanKim-0721/FactorySimulation/issues/2
- #3 D2 Scenario + 직렬화: https://github.com/DongHwanKim-0721/FactorySimulation/issues/3
- #4 D3 GUI 재작성 + WholeCode 폐기: https://github.com/DongHwanKim-0721/FactorySimulation/issues/4

현재 open issue 없음.

## Verification

완료된 검증:

- `python -B -m pytest` -> 5 passed
- 레거시 비교 스크립트로 기존 `WholeCode` 계산 결과와 새 엔진 결과 일치 확인
- 레거시 비교 스크립트는 D3 조건에 따라 삭제됨
- `app`, `main`, `engine` import 확인
- `engine/` 안에 `BLOCK_TYPES`, `tkinter`, `tk.` 의존성 없음 확인

남은 확인:

- tkinter GUI는 자동화하지 않았다. 필요하면 다음 세션에서 사람이 수동 스모크 테스트를 수행해야 한다.
- 수동 스모크 항목: 블록 추가, 이동, 연결, 삭제, 시뮬레이션 실행/결과 표시, 저장, 불러오기, Free Block 이름 입력.

## Constraints To Preserve

- `capacity` 무력화와 분기/합류 선형화 버그는 단계 D에서 고치지 않았다. 다음 단계 A에서 새 엔진 요구사항으로 다룬다.
- 엔진은 GUI 표시 메타데이터(`BLOCK_TYPES`, 색, 아이콘, 라벨)를 import하지 않아야 한다.
- 식별자는 영어, 사용자에게 보이는 라벨만 한국어로 유지한다.
- 시나리오 JSON은 현 단계에서 버전 필드가 없다.
- `WholeCode.py.bak`는 다음 단계 A 시작 전까지 비교/복구용으로 보존한다.

## Suggested Skills

- `to-prd`: 단계 A(시뮬레이션 엔진 교체)의 새 PRD를 만들 때 사용.
- `to-issues`: 단계 A PRD를 구현 이슈로 쪼갤 때 사용.
- `diagnose`: 새 엔진 도입 중 기존 골든 테스트나 GUI 동작이 깨질 때 사용.
- `handoff`: 다음 세션 종료 시 이 파일을 다시 최신 상태로 갱신할 때 사용.

## Recommended Next Session

1. 필요하면 GUI 수동 스모크 테스트를 먼저 수행한다.
2. 단계 A PRD를 작성한다.
3. 단계 A에서는 `capacity > 1` 의미, 분기/합류 그래프 처리, 새 골든 테스트(T3/T4)를 먼저 정의한다.
4. 새 엔진 교체는 `engine/simulation.py` 내부 교체만으로 끝나도록 현재 분리 경계를 유지한다.
