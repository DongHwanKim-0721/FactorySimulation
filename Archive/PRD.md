# PRD: 공정 시뮬레이션 프로그램 업그레이드 — 단계 D (리팩터링)

## Problem Statement

현재 공정 시뮬레이션 프로그램은 1200줄짜리 단일 Python 파일(`WholeCode.py`)로, tkinter GUI · 데이터 모델 · 시뮬레이션 로직 · 결과 표시 · 파일 입출력이 한 클래스(`ProcessSimulator`)에 전부 섞여 있다. 이 상태에서는 다음 단계 업그레이드(시뮬레이션 엔진 교체, 도메인 기능 확장, 시각화 강화)를 진행할 때마다 GUI 코드와 시뮬레이션 로직을 동시에 건드려야 하고, 회귀가 발생해도 자동으로 잡을 방법이 없다. 또한 코드를 보면 분명한 결함이 두 가지 있다:

1. `capacity` 필드는 표시되고 처리율 공식에는 들어가지만 실제 스케줄링에서는 무시된다 (capacity=3이어도 한 번에 한 배치씩 처리).
2. 분기·합류 그래프를 만들면 위상정렬 결과를 선형 체인으로 잘못 취급해, 사용자가 그린 다이어그램과 시뮬레이션 결과가 일치하지 않는다.

이 두 결함의 수정은 다음 단계(시뮬레이션 엔진 교체)에서 다룰 것이며, 본 PRD는 그 토대가 되는 **리팩터링과 안전망 확보**에 집중한다.

## Solution

`ProcessSimulator` 단일 클래스를 다음 책임으로 분리한다:

- **데이터 모델** — 블록 · 연결 · 시나리오를 dataclass로 표현하고, 데이터 무결성을 보장하는 최소 연산만 제공
- **시뮬레이션 엔진** — 입력 데이터(블록·연결 리스트)만 받아 결과 dataclass를 반환하는 순수 함수. GUI 메타데이터(색·아이콘·한글 이름)에 의존하지 않음
- **시나리오 직렬화** — JSON 저장/불러오기를 GUI에서 분리
- **GUI 컨트롤러 + 뷰** — 컨트롤러가 데이터·엔진·뷰를 조정. 팔레트·캔버스·결과 패널은 별도 뷰 클래스로 분리하되 하나의 파일 안에 유지
- **진입점** — 짧은 entry script

리팩터링 전에 시뮬레이션 로직의 **현재 동작을 캡처하는 특성화 테스트**를 작성해 회귀 방지 안전망을 확보한다. 단, `capacity`와 분기/합류 시나리오는 현재 동작이 잘못되어 있으므로 골든 테스트에 포함하지 않고, 다음 단계에서 올바른 동작을 새로 테스트한다.

또한 신엔진의 산출이 구코드와 동등한지 직접 비교하는 **레거시 검증 스크립트**를 일회성으로 작성해, 손으로 계산한 골든값의 정확성을 보장한다. D 단계가 끝나면 폐기한다.

## User Stories

1. As a 시뮬레이션 도구 사용자, I want 기존 기능(블록 배치·연결·시뮬레이션·결과 표시·시나리오 저장/불러오기)이 리팩터링 후에도 동일하게 동작하기를 원한다, so that 리팩터링이 사용자 경험에 변화 없이 안전하게 끝났음을 확인할 수 있다.
2. As a 시뮬레이션 도구 사용자, I want 새 코드가 기존 시나리오 파일(.json)을 불러오지 못해도 손실되는 데이터가 없기를 원한다, so that 새 포맷으로 전환할 때 손해를 보지 않는다. (현재 저장된 시나리오 파일 없음 — 호환성 미보장.)
3. As a 개발자, I want 시뮬레이션 로직이 GUI 없이 호출 가능한 순수 함수로 분리되기를 원한다, so that GUI를 띄우지 않고도 시뮬레이션 결과를 검증할 수 있다.
4. As a 개발자, I want `simulate()` 함수가 색·아이콘·한글 이름 같은 디스플레이 메타데이터를 입력으로 받지 않고 결과에도 포함하지 않기를 원한다, so that 다음 단계에서 엔진 내부를 교체할 때 외부 의존성에 발목 잡히지 않는다.
5. As a 개발자, I want 데이터 모델(블록·연결·시나리오)이 dataclass로 표현되기를 원한다, so that IDE 자동완성과 타입 검사가 동작하고, 필드 추가/변경 시 영향 범위가 명확해진다.
6. As a 개발자, I want `Scenario` 객체가 블록 추가/삭제 시 연결 cascade 삭제와 같은 무결성을 보장하기를 원한다, so that GUI에서 이 로직을 매번 재구현하지 않아도 된다.
7. As a 개발자, I want 단위 테스트(T1: 단일 블록 10배치, T2: 선형 3블록 10배치)가 작성되어 매 변경 후 회귀를 감지하기를 원한다, so that 리팩터링 중 미묘한 계산 차이가 즉시 드러난다.
8. As a 개발자, I want 신엔진 출력과 구코드 출력의 직접 비교 스크립트가 일회성으로 실행되기를 원한다, so that 손으로 계산한 골든값이 정말 정확한지 알 수 있다.
9. As a 개발자, I want `BLOCK_TYPES`가 GUI 모듈에 살고, 엔진은 이를 import하지 않기를 원한다, so that 엔진의 단위 테스트가 디스플레이 메타데이터 없이도 호출 가능하다.
10. As a 개발자, I want 시뮬레이션 결과에서 병목 공정이 이름(문자열) 대신 블록 ID로 표현되기를 원한다, so that 같은 타입의 블록이 여러 개인 시나리오에서도 정확히 어느 블록인지 알 수 있다.
11. As a 개발자, I want 시나리오 직렬화가 별도 모듈로 분리되기를 원한다, so that GUI 외부에서도 시나리오 파일을 다루는 스크립트를 작성할 수 있다.
12. As a 개발자, I want 팔레트·캔버스·결과 패널이 별도 View 클래스로 분리되기를 원한다, so that 각 영역의 변경이 다른 영역에 영향을 주지 않는다.
13. As a 개발자, I want 컨트롤러(`App`)가 시나리오 상태와 마지막 시뮬레이션 결과를 소유하고, 뷰는 상태를 직접 변경하지 않기를 원한다, so that 데이터 흐름이 단방향이고 추적 가능하다.
14. As a 개발자, I want 식별자가 영어이고 사용자에게 보이는 라벨만 한국어이기를 원한다, so that IDE/디버거/외부 라이브러리 호환성이 유지된다.
15. As a 개발자, I want 기존 `WholeCode.py`가 일정 기간 백업으로 보존되기를 원한다, so that 예상치 못한 문제 발생 시 손으로 비교할 수 있다.
16. As a 개발자, I want 본 단계가 끝난 뒤 다음 단계(시뮬레이션 엔진 교체)에서 엔진 모듈 내부만 교체하면 충분하기를 원한다, so that GUI와 데이터 모델은 손대지 않고도 정확도 향상을 얻을 수 있다.

## Implementation Decisions

### 모듈 분리 (안1 — 평탄 구조)

- **데이터 모델 모듈**: `ProcessBlock`, `ProcessConnection`, `Scenario` dataclass. tkinter 의존 없음.
- **시뮬레이션 엔진 모듈**: 순수 함수 `simulate(blocks, connections, total_batches=10) -> SimulationResult` 및 `topological_flow(blocks, connections) -> list[int]`. dataclass `SimulationResult`, `BlockResult` 반환.
- **시나리오 직렬화 모듈**: `save(scenario, path)`, `load(path) -> Scenario`. JSON 신 포맷만 지원. 구 포맷 호환성 없음.
- **GUI 모듈**: `App` 컨트롤러 + `PaletteView`, `CanvasView`, `ResultView` 클래스. `BlockType` dataclass와 `BLOCK_TYPES` 상수도 여기에 위치.
- **진입점**: `App().run()` 한 줄짜리.
- **테스트 디렉터리**: `tests/test_engine.py`.

GUI는 하위 폴더로 더 쪼개지 않는다(YAGNI). 책임은 같은 파일 안의 클래스로 분리.

### 엔진 인터페이스 (안II — 순수 분리)

엔진은 다음 dataclass 반환 (그릴링에서 결정된 핵심 모양):

```python
@dataclass
class BlockResult:
    block_id: int
    process_time: float
    capacity: int
    start_times: list[float]
    completion_times: list[float]
    waiting_times: list[float]
    throughput: float
    avg_waiting: float
    total_processed: int

@dataclass
class SimulationResult:
    timeline: list[BlockResult]
    total_time: float
    total_batches: int
    bottleneck_id: int | None
    bottleneck_throughput: float
    process_flow: list[int]
```

- 결과에 `name`, `icon`, `color` 같은 디스플레이 필드는 **포함하지 않음**.
- 병목은 이름이 아닌 **ID로 반환**.
- 엔진 내부 계산 로직은 D 단계에서 변경하지 않음. WholeCode.py에서 복사하면서 시그니처만 다듬는다.

### 상태 소유 (패턴Y)

- `Scenario` 객체가 `blocks`, `connections`와 무결성 보장 메서드(`add_block`, `delete_block`(연결 cascade), `add_connection`(중복/자기참조 거부), `delete_connection`, `next_block_id`, `next_connection_id`)를 가진다.
- `Scenario`는 tkinter를 모르고, 시뮬레이션 호출도 하지 않는다.
- `App` 컨트롤러가 `Scenario`와 마지막 `SimulationResult`를 소유하고, 시뮬레이션 호출과 뷰 갱신을 조정한다.

### 디스플레이 메타데이터의 위치

- `BLOCK_TYPES`(블록 타입별 이름·색·아이콘·기본 처리 시간)는 GUI 모듈 상단에 위치.
- 네 필드 모두 UI 책임이므로 엔진은 import하지 않음.
- `BlockType` dataclass(frozen=True)로 래핑해 점 접근(`BLOCK_TYPES['INPUT'].color`) 가능.

### 마이그레이션 순서 (안나 — TDD 흐름)

1. 디렉터리 구조 생성
2. 특성화 테스트 작성 (T1, T2) — 이 시점 엔진 없음, 실패
3. 데이터 모델(`ProcessBlock`, `ProcessConnection`) dataclass 작성
4. 엔진 로직 이식 (WholeCode.py에서 거의 그대로 복사 + 시그니처만 새 dataclass 사용)
5. 테스트 실행 — 통과 확인
6. 레거시 검증 스크립트 실행 — 구코드와 신엔진 결과 일치 확인
7. `Scenario` 클래스 + 시나리오 직렬화 모듈 작성
8. GUI 재작성 (App + View 클래스 + BlockType)
9. 진입점 작성
10. 수동 스모크 테스트 + 회귀 테스트
11. WholeCode.py를 `.bak`으로 rename, 레거시 검증 스크립트 삭제

엔진 이식(4) 시점에서 내부 계산 로직은 한 줄도 안 건드린다. 이름/시그니처만 다듬는다.

### 시나리오 파일 포맷

- 신 포맷만 지원. 구 WholeCode.py가 저장한 파일과 호환되지 않는다 (현재 사용자에게 저장된 파일 없음).
- 버전 필드는 추가하지 않는다 (YAGNI — 다음 단계에서 필요하면 그때 도입).

### 발견된 결함의 처리

`capacity` 무력화와 분기/합류 선형화는 본 단계에서 **현재 동작을 캡처하지도, 수정하지도 않는다**. 다음 단계(시뮬레이션 엔진 교체)에서 올바른 동작을 새로 정의하고, 그때 새 골든 테스트를 작성한다.

## Testing Decisions

### 좋은 테스트의 기준

- 외부 동작만 단정한다 (`simulate()` 호출 → 결과 dataclass의 특정 필드값).
- 내부 구현 디테일(중간 변수, 메서드 호출 순서, 자료구조)에는 의존하지 않는다.
- 결정적(deterministic)이며 GUI를 띄우지 않는다.

### 테스트 대상 모듈

- **시뮬레이션 엔진 모듈만** D 단계에서 테스트 작성.
- 시나리오 직렬화 모듈, GUI 모듈은 D 단계에서 자동 테스트 없음(수동 스모크 테스트로 검증).

### 골든 시나리오

- **T1: 단일 INPUT 블록**, `process_time=30`, `capacity=1`, 10배치.
  단정: `total_time == 300`, `len(timeline) == 1`, `bottleneck_id == 1`.
- **T2: 선형 3블록** (INPUT 30 → CUTTING 45 → HEAT 120), 각 `capacity=1`, 10배치.
  단정: `total_time == 1275`, 병목은 HEAT(`bottleneck_id`는 HEAT의 id).

### 일회성 레거시 검증

- 별도 검증 스크립트가 `WholeCode.py`의 `ProcessSimulator`를 GUI 없이 인스턴스화하고, 동일 시나리오로 `run_batch_simulation` 호출 결과를 신엔진의 `simulate(...)` 결과와 비교 (`total_time`, 배치별 `start_times`, `completion_times`).
- 불일치 발견 시 골든을 수정하거나 이식 코드를 점검.
- D 단계 종료 시 스크립트 삭제.

### 프레임워크 및 환경

- pytest 9.x (이미 `.venv`에 설치되어 있음).
- Python 3.14.

### 자동화 테스트 미적용 영역

- tkinter GUI: 자동화가 까다로움. 수동 스모크 테스트로 대체 (블록 추가/이동/연결/삭제/시뮬레이션/저장/불러오기/Free Block 이름).
- 시나리오 JSON 라운드트립: D 단계에서는 수동으로 한 번 확인. 다음 단계에서 자동 테스트 도입 검토.

## Out of Scope

본 PRD는 **단계 D(리팩터링)** 만 다룬다. 다음 단계들은 별도 PRD에서 다룬다:

- **단계 A — 시뮬레이션 엔진 교체**: SimPy/이산사건 시뮬레이션 도입 여부, 확률적 처리 시간, `capacity > 1`의 진짜 의미(병렬 vs 배치 사이즈), 분기/합류 그래프의 올바른 처리, T3/T4 골든 테스트 추가.
- **단계 C — 도메인 기능 확장**: 재작업 루프, 작업자 자원, 셋업 시간, 불량률, WIP/버퍼 한계, 다품종, 시나리오 비교(What-if).
- **단계 B — 시각화/UX 강화**: 진짜 간트 차트, matplotlib/Plotly 그래프, 애니메이션 재생, 결과 비교 모드.

다음의 변경도 본 PRD 범위 밖이다:

- 도메인 글로사리(CONTEXT.md) 작성
- ADR 작성
- 이슈 트래커 설정 (`/setup-matt-pocock-skills` 실행)
- `pyproject.toml`/패키지화/`.exe` 빌드 (단계 D4)
- 시나리오 파일 포맷 버저닝
- tkinter GUI 자동화 테스트
- `next_block_id` 재사용 버그 수정 (블록 삭제 후 새로 만들면 ID 충돌 가능 — 알려진 이슈, 다음 단계에서 처리)

## Further Notes

- **레거시 비교 스크립트는 일회성**이지만, 그 결과가 골든값을 확정한다. 손계산 골든(T1=300, T2=1275)과 다르면 신엔진이 아닌 손계산을 수정한다 (신엔진은 구코드의 동작을 충실히 옮긴 것이 D 단계의 정의).
- **WholeCode.py 백업 보존 기간**: 다음 단계(A)가 시작되기 전까지. A에서 엔진을 교체하면 어차피 동작이 달라지므로 그 시점에서 비교 가치가 사라진다.
- **D3 깊이의 선택**: 더 가벼운 D1(파일 분리만)은 A 단계에서 엔진 교체 시 GUI 코드까지 건드려야 하는 문제가 그대로 남는다. 더 무거운 D4(패키징·exe)는 누가 어떻게 배포할지 불명확한 단계에서 미리 결정할 가치가 없다.
- **그릴링 결과로부터의 PRD**: 본 문서는 to-prd 스킬을 통해 그릴링 대화를 종합한 것이다. 결정 사항의 근거(왜 안가가 아니라 안나, 왜 안Z가 아니라 안Y 등)는 원 대화에 더 상세히 남아 있다.
