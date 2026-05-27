from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush

from .models import ProcessBlock, ProcessConnection


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
    units_per_source: int
    total_generated_units: int
    source_count: int
    bottleneck_id: int | None
    bottleneck_throughput: float
    process_flow: list[int]


@dataclass(frozen=True)
class _UnitArrival:
    arrival_time: float
    parent_topo_index: int
    parent_completion_order: int
    source_order: int


@dataclass(frozen=True)
class _UnitCompletion:
    completion_time: float
    completion_order: int


def topological_flow(
    blocks: list[ProcessBlock],
    connections: list[ProcessConnection],
) -> list[int]:
    """Return a stable topological order after validating the process graph."""
    return _validate_and_topological_flow(blocks, connections)


def simulate(
    blocks: list[ProcessBlock],
    connections: list[ProcessConnection],
    units_per_source: int = 10,
) -> SimulationResult:
    _validate_inputs(blocks, units_per_source)
    process_flow = _validate_and_topological_flow(blocks, connections)
    block_by_id = {block.id: block for block in blocks}
    outgoing_by_id = _outgoing_by_id(connections)
    incoming_ids = {connection.to_block for connection in connections}
    source_ids = [block.id for block in blocks if block.id not in incoming_ids]
    total_generated_units = len(source_ids) * units_per_source

    arrivals_by_block: dict[int, list[_UnitArrival]] = {
        block.id: [] for block in blocks
    }
    metrics_by_block: dict[int, dict[str, list[float]]] = {
        block.id: {
            "start_times": [],
            "completion_times": [],
            "waiting_times": [],
        }
        for block in blocks
    }
    topo_index_by_id = {block_id: index for index, block_id in enumerate(process_flow)}

    for source_order, block_id in enumerate(source_ids):
        topo_index = topo_index_by_id[block_id]
        arrivals_by_block[block_id] = [
            _UnitArrival(0, topo_index, unit_index, source_order)
            for unit_index in range(units_per_source)
        ]

    for block_id in process_flow:
        block = block_by_id[block_id]
        arrivals = sorted(
            arrivals_by_block[block_id],
            key=lambda item: (
                item.arrival_time,
                item.parent_topo_index,
                item.parent_completion_order,
                item.source_order,
            ),
        )
        metrics = metrics_by_block[block_id]
        slot_heap = [(0.0, slot_index) for slot_index in range(block.capacity)]
        completions: list[_UnitCompletion] = []

        for completion_order, arrival in enumerate(arrivals):
            available_time, slot_index = heappop(slot_heap)
            start_time = max(arrival.arrival_time, available_time)
            completion_time = start_time + block.process_time
            waiting_time = start_time - arrival.arrival_time

            metrics["start_times"].append(start_time)
            metrics["completion_times"].append(completion_time)
            metrics["waiting_times"].append(waiting_time)
            completions.append(_UnitCompletion(completion_time, completion_order))
            heappush(slot_heap, (completion_time, slot_index))

        completions.sort(key=lambda item: (item.completion_time, item.completion_order))
        _route_completions(
            parent_id=block_id,
            completions=completions,
            outgoing_connections=outgoing_by_id.get(block_id, []),
            block_by_id=block_by_id,
            topo_index_by_id=topo_index_by_id,
            arrivals_by_block=arrivals_by_block,
        )

    timeline = [
        _build_block_result(block_by_id[block_id], metrics_by_block[block_id])
        for block_id in process_flow
    ]
    bottleneck_id, bottleneck_throughput = _analyze_bottleneck(timeline)

    return SimulationResult(
        timeline=timeline,
        total_time=_total_sink_time(timeline, connections),
        units_per_source=units_per_source,
        total_generated_units=total_generated_units,
        source_count=len(source_ids),
        bottleneck_id=bottleneck_id,
        bottleneck_throughput=bottleneck_throughput,
        process_flow=process_flow,
    )


def _validate_inputs(blocks: list[ProcessBlock], units_per_source: int) -> None:
    if units_per_source < 0:
        raise ValueError("시작 공정별 투입 수량(EA)은 0 이상이어야 합니다.")

    block_ids: set[int] = set()
    for block in blocks:
        if block.id in block_ids:
            raise ValueError(f"중복된 블록 ID입니다: {block.id}.")
        block_ids.add(block.id)

        if block.process_time <= 0:
            raise ValueError("처리 시간(분/EA)은 0보다 커야 합니다.")
        if block.capacity <= 0:
            raise ValueError("동시 처리 수량(EA)은 1 이상이어야 합니다.")


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


def _outgoing_by_id(
    connections: list[ProcessConnection],
) -> dict[int, list[ProcessConnection]]:
    outgoing: dict[int, list[ProcessConnection]] = {}
    for connection in connections:
        outgoing.setdefault(connection.from_block, []).append(connection)
    return outgoing


def _route_completions(
    parent_id: int,
    completions: list[_UnitCompletion],
    outgoing_connections: list[ProcessConnection],
    block_by_id: dict[int, ProcessBlock],
    topo_index_by_id: dict[int, int],
    arrivals_by_block: dict[int, list[_UnitArrival]],
) -> None:
    if not outgoing_connections:
        return

    route_pattern = [
        connection.to_block
        for connection in outgoing_connections
        for _ in range(block_by_id[connection.to_block].capacity)
    ]
    parent_topo_index = topo_index_by_id[parent_id]

    for route_index, completion in enumerate(completions):
        child_id = route_pattern[route_index % len(route_pattern)]
        arrivals_by_block[child_id].append(
            _UnitArrival(
                arrival_time=completion.completion_time,
                parent_topo_index=parent_topo_index,
                parent_completion_order=completion.completion_order,
                source_order=route_index,
            )
        )


def _build_block_result(
    block: ProcessBlock,
    metrics: dict[str, list[float]],
) -> BlockResult:
    waiting_times = metrics["waiting_times"]
    start_times = metrics["start_times"]
    completion_times = metrics["completion_times"]
    throughput = block.capacity / block.process_time

    return BlockResult(
        block_id=block.id,
        process_time=float(block.process_time),
        capacity=int(block.capacity),
        start_times=list(start_times),
        completion_times=list(completion_times),
        waiting_times=list(waiting_times),
        throughput=throughput,
        avg_waiting=sum(waiting_times) / len(waiting_times) if waiting_times else 0,
        total_processed=len(completion_times),
    )


def _analyze_bottleneck(timeline: list[BlockResult]) -> tuple[int | None, float]:
    processed = [item for item in timeline if item.total_processed > 0]
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
        item.completion_times[-1]
        for item in timeline
        if item.block_id in sink_ids and item.completion_times
    ]
    return max(sink_completion_times, default=0)
