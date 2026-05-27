from __future__ import annotations

from dataclasses import dataclass

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
    total_batches: int
    bottleneck_id: int | None
    bottleneck_throughput: float
    process_flow: list[int]


def topological_flow(
    blocks: list[ProcessBlock],
    connections: list[ProcessConnection],
) -> list[int]:
    """Return the same DFS ordering used by the legacy implementation."""
    if len(connections) == 0:
        return [block.id for block in blocks]

    has_incoming = {connection.to_block for connection in connections}
    start_nodes = [block.id for block in blocks if block.id not in has_incoming]

    if len(start_nodes) == 0:
        return [block.id for block in blocks]

    sorted_nodes: list[int] = []
    visited: set[int] = set()

    def dfs(node_id: int) -> None:
        if node_id in visited:
            return
        visited.add(node_id)

        outgoing = [
            connection.to_block
            for connection in connections
            if connection.from_block == node_id
        ]
        for next_node in outgoing:
            dfs(next_node)

        sorted_nodes.insert(0, node_id)

    for start in start_nodes:
        dfs(start)

    return sorted_nodes


def simulate(
    blocks: list[ProcessBlock],
    connections: list[ProcessConnection],
    total_batches: int = 10,
) -> SimulationResult:
    process_flow = topological_flow(blocks, connections)
    block_by_id = {block.id: block for block in blocks}

    process_info: dict[int, dict[str, object]] = {}
    for block_id in process_flow:
        block = block_by_id.get(block_id)
        if not block:
            continue

        process_info[block_id] = {
            "process_time": block.process_time,
            "capacity": block.capacity,
            "completion_times": [],
            "start_times": [],
            "waiting_times": [],
            "idle_times": 0,
        }

    for batch_num in range(total_batches):
        for idx, block_id in enumerate(process_flow):
            info = process_info[block_id]

            if idx == 0:
                if batch_num == 0:
                    start_time = 0
                else:
                    start_time = info["completion_times"][-1]  # type: ignore[index]
            else:
                prev_block_id = process_flow[idx - 1]
                prev_info = process_info[prev_block_id]

                if batch_num < len(prev_info["completion_times"]):  # type: ignore[arg-type]
                    prev_completion = prev_info["completion_times"][batch_num]  # type: ignore[index]
                else:
                    prev_completion = 0

                if batch_num > 0 and len(info["completion_times"]) > 0:  # type: ignore[arg-type]
                    current_completion = info["completion_times"][-1]  # type: ignore[index]
                    start_time = max(prev_completion, current_completion)
                else:
                    start_time = prev_completion

            if idx > 0 and batch_num > 0:
                prev_block_id = process_flow[idx - 1]
                prev_info = process_info[prev_block_id]
                if batch_num < len(prev_info["completion_times"]):  # type: ignore[arg-type]
                    waiting_time = start_time - prev_info["completion_times"][batch_num]  # type: ignore[index]
                else:
                    waiting_time = 0
            else:
                waiting_time = 0

            info["waiting_times"].append(waiting_time)  # type: ignore[union-attr]
            info["start_times"].append(start_time)  # type: ignore[union-attr]

            completion_time = start_time + info["process_time"]  # type: ignore[operator]
            info["completion_times"].append(completion_time)  # type: ignore[union-attr]

    bottleneck_id, bottleneck_throughput = _analyze_bottleneck(process_info, process_flow)

    timeline: list[BlockResult] = []
    total_time = 0

    for block_id in process_flow:
        info = process_info[block_id]
        waiting_times = list(info["waiting_times"])  # type: ignore[arg-type]
        start_times = list(info["start_times"])  # type: ignore[arg-type]
        completion_times = list(info["completion_times"])  # type: ignore[arg-type]
        process_time = float(info["process_time"])
        capacity = int(info["capacity"])

        avg_waiting = sum(waiting_times) / len(waiting_times) if waiting_times else 0
        throughput = capacity / process_time if process_time > 0 else 0

        timeline.append(
            BlockResult(
                block_id=block_id,
                process_time=process_time,
                capacity=capacity,
                start_times=start_times,
                completion_times=completion_times,
                waiting_times=waiting_times,
                throughput=throughput,
                avg_waiting=avg_waiting,
                total_processed=total_batches * capacity,
            )
        )

        if completion_times:
            total_time = max(total_time, completion_times[-1])

    return SimulationResult(
        timeline=timeline,
        total_time=total_time,
        total_batches=total_batches,
        bottleneck_id=bottleneck_id,
        bottleneck_throughput=bottleneck_throughput,
        process_flow=process_flow,
    )


def _analyze_bottleneck(
    process_info: dict[int, dict[str, object]],
    process_flow: list[int],
) -> tuple[int | None, float]:
    min_throughput = float("inf")
    bottleneck_id = None

    for block_id in process_flow:
        info = process_info[block_id]
        process_time = float(info["process_time"])
        capacity = int(info["capacity"])
        throughput = capacity / process_time if process_time > 0 else float("inf")

        if throughput < min_throughput:
            min_throughput = throughput
            bottleneck_id = block_id

    if bottleneck_id is None:
        return None, 0

    return bottleneck_id, min_throughput
