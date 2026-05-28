from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush
from math import ceil
from typing import Callable

from .models import ProcessBlock, ProcessConnection


@dataclass(frozen=True)
class BundleRecord:
    block_id: int
    bundle_id: int
    product_name: str
    material_name: str
    quantity: int
    source_block_id: int
    arrival_time: float
    start_time: float
    completion_time: float
    transport_trips: int = 0


@dataclass
class BlockResult:
    block_id: int
    operation_time: float
    operation_quantity: int
    start_times: list[float]
    completion_times: list[float]
    waiting_times: list[float]
    throughput: float
    avg_waiting: float
    total_processed: int
    processed_bundle_count: int
    unique_product_count: int
    unique_material_count: int
    transport_trips: int
    bundles: list[BundleRecord]


@dataclass
class SimulationResult:
    timeline: list[BlockResult]
    total_time: float
    total_input_quantity: int
    final_output_quantity: int
    input_quantity_by_product: dict[str, int]
    final_output_quantity_by_product: dict[str, int]
    unique_product_count: int
    bottleneck_id: int | None
    bottleneck_throughput: float
    process_flow: list[int]


@dataclass(frozen=True)
class _Bundle:
    bundle_id: int
    product_name: str
    material_name: str
    quantity: int
    source_block_id: int
    arrival_time: float
    sequence: int


@dataclass(frozen=True)
class _ProcessedBundle:
    bundle: _Bundle
    start_time: float
    completion_time: float
    transport_trips: int = 0


def topological_flow(
    blocks: list[ProcessBlock],
    connections: list[ProcessConnection],
) -> list[int]:
    """Return a stable topological order after validating the process graph."""
    return _validate_and_topological_flow(blocks, connections)


def simulate(
    blocks: list[ProcessBlock],
    connections: list[ProcessConnection],
) -> SimulationResult:
    _validate_block_fields(blocks)
    process_flow = _validate_and_topological_flow(blocks, connections)
    _validate_bundle_graph(blocks, connections)

    if not blocks:
        return SimulationResult(
            timeline=[],
            total_time=0,
            total_input_quantity=0,
            final_output_quantity=0,
            input_quantity_by_product={},
            final_output_quantity_by_product={},
            unique_product_count=0,
            bottleneck_id=None,
            bottleneck_throughput=0,
            process_flow=[],
        )

    block_by_id = {block.id: block for block in blocks}
    outgoing_by_id = _outgoing_by_id(connections)
    arrivals_by_block: dict[int, list[_Bundle]] = {block.id: [] for block in blocks}
    results_by_block: dict[int, BlockResult] = {}
    bundle_sequence = 0
    next_bundle_id = 1

    def next_sequence() -> int:
        nonlocal bundle_sequence
        bundle_sequence += 1
        return bundle_sequence

    def new_bundle_id() -> int:
        nonlocal next_bundle_id
        bundle_id = next_bundle_id
        next_bundle_id += 1
        return bundle_id

    for block_id in process_flow:
        block = block_by_id[block_id]
        if _is_input(block):
            processed = _process_input_block(block, new_bundle_id, next_sequence)
        elif _is_hoist(block):
            processed = _process_hoist_block(block, arrivals_by_block[block_id])
        else:
            processed = _process_work_block(block, arrivals_by_block[block_id])

        results_by_block[block_id] = _build_block_result(block, processed)
        _route_processed_bundles(
            processed=processed,
            outgoing_connections=outgoing_by_id.get(block_id, []),
            block_by_id=block_by_id,
            arrivals_by_block=arrivals_by_block,
            new_bundle_id=new_bundle_id,
            next_sequence=next_sequence,
        )

    timeline = [results_by_block[block_id] for block_id in process_flow]
    bottleneck_id, bottleneck_throughput = _analyze_bottleneck(timeline, block_by_id)
    input_quantity_by_product = _input_quantity_by_product(timeline, block_by_id)
    final_output_quantity_by_product = _final_output_quantity_by_product(
        timeline,
        connections,
    )
    product_names = set(input_quantity_by_product) | set(final_output_quantity_by_product)

    return SimulationResult(
        timeline=timeline,
        total_time=_total_sink_time(timeline, connections),
        total_input_quantity=sum(
            block.input_quantity for block in blocks if _is_input(block)
        ),
        final_output_quantity=_final_output_quantity(timeline, connections),
        input_quantity_by_product=input_quantity_by_product,
        final_output_quantity_by_product=final_output_quantity_by_product,
        unique_product_count=len(product_names),
        bottleneck_id=bottleneck_id,
        bottleneck_throughput=bottleneck_throughput,
        process_flow=process_flow,
    )


def _validate_block_fields(blocks: list[ProcessBlock]) -> None:
    block_ids: set[int] = set()
    for block in blocks:
        if block.id in block_ids:
            raise ValueError(f"중복된 블록 ID입니다: {block.id}.")
        block_ids.add(block.id)

        if _is_input(block):
            if not block.product_name.strip():
                raise ValueError(
                    "제품명은 비워둘 수 없습니다."
                )
            if not block.material_name.strip():
                raise ValueError("원자재명은 비워둘 수 없습니다.")
            if block.input_quantity < 0:
                raise ValueError("투입 원자재 수(EA)는 0 이상이어야 합니다.")
            if block.input_time < 0:
                raise ValueError("투입 시간(분)은 0 이상이어야 합니다.")
        elif _is_hoist(block):
            if block.transport_capacity <= 0:
                raise ValueError("1회 운반 수량(EA)은 1 이상이어야 합니다.")
            if block.transport_time <= 0:
                raise ValueError("1회 이동 시간(분)은 0보다 커야 합니다.")
        else:
            if block.process_time_per_ea <= 0:
                raise ValueError("처리 시간(분/EA)은 0보다 커야 합니다.")
            if block.concurrent_capacity <= 0:
                raise ValueError("동시 가공 수량(EA)은 1 이상이어야 합니다.")


def _validate_and_topological_flow(
    blocks: list[ProcessBlock],
    connections: list[ProcessConnection],
) -> list[int]:
    if not blocks:
        return []

    block_order = {block.id: index for index, block in enumerate(blocks)}
    if len(block_order) != len(blocks):
        raise ValueError("블록 ID는 중복될 수 없습니다.")

    seen_edges: set[tuple[int, int]] = set()
    incoming_count = {block.id: 0 for block in blocks}
    outgoing: dict[int, list[int]] = {block.id: [] for block in blocks}

    for connection in connections:
        if (
            connection.from_block not in block_order
            or connection.to_block not in block_order
        ):
            raise ValueError("연결하려는 블록이 시나리오에 있어야 합니다.")
        if connection.from_block == connection.to_block:
            raise ValueError("같은 블록끼리는 연결할 수 없습니다.")

        edge = (connection.from_block, connection.to_block)
        if edge in seen_edges:
            raise ValueError("중복 연결은 허용되지 않습니다.")
        seen_edges.add(edge)

        outgoing[connection.from_block].append(connection.to_block)
        incoming_count[connection.to_block] += 1

    available: list[tuple[int, int]] = []
    for block in blocks:
        if incoming_count[block.id] == 0:
            heappush(available, (block_order[block.id], block.id))

    process_flow: list[int] = []
    while available:
        _, block_id = heappop(available)
        process_flow.append(block_id)

        for child_id in outgoing[block_id]:
            incoming_count[child_id] -= 1
            if incoming_count[child_id] == 0:
                heappush(available, (block_order[child_id], child_id))

    if len(process_flow) != len(blocks):
        raise ValueError("공정 그래프는 DAG여야 합니다. 순환 흐름은 지원하지 않습니다.")

    return process_flow


def _validate_bundle_graph(
    blocks: list[ProcessBlock],
    connections: list[ProcessConnection],
) -> None:
    incoming_count = {block.id: 0 for block in blocks}
    block_by_id = {block.id: block for block in blocks}

    for connection in connections:
        child = block_by_id[connection.to_block]
        if _is_input(child):
            raise ValueError("원자재 투입 블록으로 들어가는 연결은 허용되지 않습니다.")
        incoming_count[connection.to_block] += 1

    for block in blocks:
        if _is_input(block):
            if incoming_count[block.id] > 0:
                raise ValueError("원자재 투입 블록은 입력 연결을 가질 수 없습니다.")
        elif incoming_count[block.id] == 0:
            raise ValueError(
                f"{block.id}번 공정/호이스트 블록은 입력 연결 없이 시작할 수 없습니다."
            )


def _outgoing_by_id(
    connections: list[ProcessConnection],
) -> dict[int, list[ProcessConnection]]:
    outgoing: dict[int, list[ProcessConnection]] = {}
    for connection in connections:
        outgoing.setdefault(connection.from_block, []).append(connection)
    return outgoing


def _process_input_block(
    block: ProcessBlock,
    new_bundle_id: Callable[[], int],
    next_sequence: Callable[[], int],
) -> list[_ProcessedBundle]:
    if block.input_quantity == 0:
        return []

    bundle = _Bundle(
        bundle_id=new_bundle_id(),
        product_name=block.product_name,
        material_name=block.material_name,
        quantity=block.input_quantity,
        source_block_id=block.id,
        arrival_time=0,
        sequence=next_sequence(),
    )
    return [
        _ProcessedBundle(
            bundle=bundle,
            start_time=0,
            completion_time=float(block.input_time),
        )
    ]


def _process_hoist_block(
    block: ProcessBlock,
    arrivals: list[_Bundle],
) -> list[_ProcessedBundle]:
    current_time = 0.0
    processed: list[_ProcessedBundle] = []

    for bundle in _sort_bundles(arrivals):
        start_time = max(current_time, bundle.arrival_time)
        trips = ceil(bundle.quantity / block.transport_capacity)
        completion_time = start_time + trips * block.transport_time
        processed.append(
            _ProcessedBundle(
                bundle=bundle,
                start_time=start_time,
                completion_time=completion_time,
                transport_trips=trips,
            )
        )
        current_time = completion_time

    return processed


def _process_work_block(
    block: ProcessBlock,
    arrivals: list[_Bundle],
) -> list[_ProcessedBundle]:
    current_time = 0.0
    pending = _sort_bundles(arrivals)
    processed: list[_ProcessedBundle] = []

    while pending:
        available = [bundle for bundle in pending if bundle.arrival_time <= current_time]
        if not available:
            current_time = max(current_time, pending[0].arrival_time)
            available = [bundle for bundle in pending if bundle.arrival_time <= current_time]

        material_name = available[0].material_name
        same_material = [
            bundle for bundle in pending if bundle.material_name == material_name
        ]
        same_material_ids = {bundle.bundle_id for bundle in same_material}

        for bundle in same_material:
            start_time = max(current_time, bundle.arrival_time)
            duration = (
                ceil(bundle.quantity / block.concurrent_capacity)
                * block.process_time_per_ea
            )
            completion_time = start_time + duration
            processed.append(
                _ProcessedBundle(
                    bundle=bundle,
                    start_time=start_time,
                    completion_time=completion_time,
                )
            )
            current_time = completion_time

        pending = [
            bundle for bundle in pending if bundle.bundle_id not in same_material_ids
        ]

    return processed


def _route_processed_bundles(
    processed: list[_ProcessedBundle],
    outgoing_connections: list[ProcessConnection],
    block_by_id: dict[int, ProcessBlock],
    arrivals_by_block: dict[int, list[_Bundle]],
    new_bundle_id: Callable[[], int],
    next_sequence: Callable[[], int],
) -> None:
    if not outgoing_connections:
        return

    for processed_bundle in processed:
        bundle = processed_bundle.bundle
        if len(outgoing_connections) == 1:
            child_id = outgoing_connections[0].to_block
            arrivals_by_block[child_id].append(
                _Bundle(
                    bundle_id=bundle.bundle_id,
                    product_name=bundle.product_name,
                    material_name=bundle.material_name,
                    quantity=bundle.quantity,
                    source_block_id=bundle.source_block_id,
                    arrival_time=processed_bundle.completion_time,
                    sequence=next_sequence(),
                )
            )
            continue

        for child_id, quantity in _split_quantity_by_weights(
            bundle.quantity,
            outgoing_connections,
            block_by_id,
        ):
            if quantity <= 0:
                continue
            arrivals_by_block[child_id].append(
                _Bundle(
                    bundle_id=new_bundle_id(),
                    product_name=bundle.product_name,
                    material_name=bundle.material_name,
                    quantity=quantity,
                    source_block_id=bundle.source_block_id,
                    arrival_time=processed_bundle.completion_time,
                    sequence=next_sequence(),
                )
            )


def _split_quantity_by_weights(
    quantity: int,
    outgoing_connections: list[ProcessConnection],
    block_by_id: dict[int, ProcessBlock],
) -> list[tuple[int, int]]:
    pattern = [
        connection.to_block
        for connection in outgoing_connections
        for _ in range(_routing_weight(block_by_id[connection.to_block]))
    ]
    counts = {connection.to_block: 0 for connection in outgoing_connections}
    for index in range(quantity):
        counts[pattern[index % len(pattern)]] += 1
    return [(connection.to_block, counts[connection.to_block]) for connection in outgoing_connections]


def _routing_weight(block: ProcessBlock) -> int:
    if _is_input(block):
        raise ValueError("원자재 투입 블록으로는 분기 라우팅할 수 없습니다.")
    if _is_hoist(block):
        return block.transport_capacity
    return block.concurrent_capacity


def _build_block_result(
    block: ProcessBlock,
    processed: list[_ProcessedBundle],
) -> BlockResult:
    records = [
        BundleRecord(
            block_id=block.id,
            bundle_id=item.bundle.bundle_id,
            product_name=item.bundle.product_name,
            material_name=item.bundle.material_name,
            quantity=item.bundle.quantity,
            source_block_id=item.bundle.source_block_id,
            arrival_time=item.bundle.arrival_time,
            start_time=item.start_time,
            completion_time=item.completion_time,
            transport_trips=item.transport_trips,
        )
        for item in processed
    ]
    waiting_times = [record.start_time - record.arrival_time for record in records]
    start_times = [record.start_time for record in records]
    completion_times = [record.completion_time for record in records]
    transport_trips = sum(record.transport_trips for record in records)

    return BlockResult(
        block_id=block.id,
        operation_time=_operation_time(block),
        operation_quantity=_operation_quantity(block),
        start_times=start_times,
        completion_times=completion_times,
        waiting_times=waiting_times,
        throughput=_throughput(block),
        avg_waiting=sum(waiting_times) / len(waiting_times) if waiting_times else 0,
        total_processed=sum(record.quantity for record in records),
        processed_bundle_count=len(records),
        unique_product_count=len({record.product_name for record in records}),
        unique_material_count=len({record.material_name for record in records}),
        transport_trips=transport_trips,
        bundles=records,
    )


def _analyze_bottleneck(
    timeline: list[BlockResult],
    block_by_id: dict[int, ProcessBlock],
) -> tuple[int | None, float]:
    processed = [
        item
        for item in timeline
        if item.total_processed > 0 and not _is_input(block_by_id[item.block_id])
    ]
    if not processed:
        return None, 0

    bottleneck = min(processed, key=lambda item: item.throughput)
    return bottleneck.block_id, bottleneck.throughput


def _total_sink_time(
    timeline: list[BlockResult],
    connections: list[ProcessConnection],
) -> float:
    if not timeline:
        return 0

    parent_ids = {connection.from_block for connection in connections}
    sink_ids = {item.block_id for item in timeline if item.block_id not in parent_ids}
    sink_completion_times = [
        max(item.completion_times)
        for item in timeline
        if item.block_id in sink_ids and item.completion_times
    ]
    return max(sink_completion_times, default=0)


def _final_output_quantity(
    timeline: list[BlockResult],
    connections: list[ProcessConnection],
) -> int:
    parent_ids = {connection.from_block for connection in connections}
    return sum(
        item.total_processed
        for item in timeline
        if item.block_id not in parent_ids
    )


def _input_quantity_by_product(
    timeline: list[BlockResult],
    block_by_id: dict[int, ProcessBlock],
) -> dict[str, int]:
    quantities: dict[str, int] = {}
    for item in timeline:
        if not _is_input(block_by_id[item.block_id]):
            continue
        for bundle in item.bundles:
            quantities[bundle.product_name] = (
                quantities.get(bundle.product_name, 0) + bundle.quantity
            )
    return quantities


def _final_output_quantity_by_product(
    timeline: list[BlockResult],
    connections: list[ProcessConnection],
) -> dict[str, int]:
    parent_ids = {connection.from_block for connection in connections}
    quantities: dict[str, int] = {}
    for item in timeline:
        if item.block_id in parent_ids:
            continue
        for bundle in item.bundles:
            quantities[bundle.product_name] = (
                quantities.get(bundle.product_name, 0) + bundle.quantity
            )
    return quantities


def _sort_bundles(bundles: list[_Bundle]) -> list[_Bundle]:
    return sorted(
        bundles,
        key=lambda bundle: (
            bundle.arrival_time,
            bundle.sequence,
            bundle.source_block_id,
            bundle.bundle_id,
        ),
    )


def _operation_time(block: ProcessBlock) -> float:
    if _is_input(block):
        return float(block.input_time)
    if _is_hoist(block):
        return float(block.transport_time)
    return float(block.process_time_per_ea)


def _operation_quantity(block: ProcessBlock) -> int:
    if _is_input(block):
        return int(block.input_quantity)
    if _is_hoist(block):
        return int(block.transport_capacity)
    return int(block.concurrent_capacity)


def _throughput(block: ProcessBlock) -> float:
    if _is_input(block):
        if block.input_time == 0:
            return float("inf")
        return block.input_quantity / block.input_time
    if _is_hoist(block):
        return block.transport_capacity / block.transport_time
    return block.concurrent_capacity / block.process_time_per_ea


def _is_input(block: ProcessBlock) -> bool:
    return block.type == "INPUT"


def _is_hoist(block: ProcessBlock) -> bool:
    return block.type == "HOIST"
