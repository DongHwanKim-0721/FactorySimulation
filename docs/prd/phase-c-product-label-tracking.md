# PRD: 단계 C - 제품명 라벨 기반 묶음 추적

Updated: 2026-05-28

Status: implemented

GitHub references:

- Umbrella issue: #21
- Implementation issues: #22, #23, #24, #25

## Problem

기존 묶음 기반 시뮬레이션은 INPUT 블록의 원자재명과 수량을 끝까지 추적했다. 하지만 같은 원자재가 여러 제품에 쓰이거나, 같은 제품 물량이 여러 INPUT 라인으로 나뉘어 들어오는 경우 결과 해석에 제품 단위 라벨이 필요하다.

단계 C의 목적은 시뮬레이션 정밀도 향상이 아니라 추적 라벨 확장이다. 제품명은 처리 시간, 라우팅, 품종 그룹 우선 처리, 수율, BOM, 셋업 시간에 영향을 주지 않는다.

## Scope

- INPUT 블록에 필수 제품명 필드를 추가한다.
- 새 INPUT 블록의 기본 제품명은 `제품`, 기본 원자재명은 `원자재`다.
- 제품명은 INPUT 블록 설정 화면에서만 편집한다.
- INPUT이 생성한 묶음과 모든 결과 묶음 레코드는 제품명과 원자재명을 함께 가진다.
- 분기된 묶음은 제품명과 원자재명을 그대로 복사한다.
- 합류 시 묶음은 병합하지 않고 bundle ID 단위로 유지한다.
- 엔진 결과는 제품별 투입 EA와 최종 output EA를 직접 제공한다.
- GUI 결과는 제품 라벨 수, 제품별 투입/output EA, 블록별 제품/원자재 수, 묶음별 제품명/원자재명/수량/시간을 표시한다.
- JSON 저장/불러오기는 `product_name`을 지원하고, 구 파일은 기본값 `제품`으로 불러온다.

## Out Of Scope

- 명시적 OUTPUT 블록
- 제품별 라우팅
- 제품별 처리 시간
- 제품별 수율, 불량률, 폐기
- 제품별 BOM 또는 조립 규칙
- 금형 교체 시간 또는 셋업 시간 계산
- 제품명이 품종 그룹 우선 처리 기준에 참여하는 기능
- 제품명 중복 방지 또는 제품 마스터 관리

## Implementation Notes

- `ProcessBlock.product_name`이 INPUT 라벨 계약을 담당한다.
- `BundleRecord.product_name`이 엔진 결과의 제품 추적 표면이다.
- `SimulationResult.input_quantity_by_product`는 INPUT 묶음 기준 집계다.
- `SimulationResult.final_output_quantity_by_product`는 출력 간선이 없는 sink 블록의 완료 묶음 기준 집계다.
- 품종 그룹 우선 처리는 계속 `_process_work_block()`의 `material_name` 기준 그룹핑을 사용한다.

## Verification

Automated tests cover:

- INPUT 제품명 기본값과 필수 검증
- INPUT-only 제품명 보존
- 분기/합류 후 제품명과 원자재명 보존
- 같은 제품/원자재 라벨 묶음의 비병합
- 제품별 투입/output EA 집계
- 제품명이 달라도 원자재명이 같으면 같은 품종 그룹으로 처리되는 동작
- 새 JSON 저장 라운드트립
- 구 JSON의 `product_name` 기본값 처리

Manual GUI checks are listed in `docs/manual-smoke-checklist.md`.
