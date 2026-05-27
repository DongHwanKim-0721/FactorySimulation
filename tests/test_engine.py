import pytest

from engine.models import ProcessBlock, ProcessConnection
from engine.simulation import simulate, topological_flow


def test_single_input_block_ten_units():
    blocks = [
        ProcessBlock(
            id=1,
            type="INPUT",
            x=0,
            y=0,
            process_time=30,
            capacity=1,
        )
    ]

    result = simulate(blocks, [], units_per_source=10)

    assert result.total_time == 300
    assert result.units_per_source == 10
    assert result.source_count == 1
    assert result.total_generated_units == 10
    assert result.timeline[0].total_processed == 10
    assert result.bottleneck_id == 1


def test_linear_three_block_flow_ten_units():
    blocks = [
        ProcessBlock(id=1, type="INPUT", x=0, y=0, process_time=30, capacity=1),
        ProcessBlock(id=2, type="CUTTING", x=200, y=0, process_time=45, capacity=1),
        ProcessBlock(id=3, type="HEAT", x=400, y=0, process_time=120, capacity=1),
    ]
    connections = [
        ProcessConnection(id=1, from_block=1, to_block=2),
        ProcessConnection(id=2, from_block=2, to_block=3),
    ]

    result = simulate(blocks, connections, units_per_source=10)

    assert result.total_time == 1275
    assert result.bottleneck_id == 3
    assert result.process_flow == [1, 2, 3]
    assert [item.total_processed for item in result.timeline] == [10, 10, 10]


def test_capacity_is_parallel_slot_count():
    blocks = [
        ProcessBlock(id=1, type="INPUT", x=0, y=0, process_time=30, capacity=3)
    ]

    result = simulate(blocks, [], units_per_source=10)

    assert result.total_time == 120
    assert result.timeline[0].start_times == [0, 0, 0, 30, 30, 30, 60, 60, 60, 90]
    assert result.timeline[0].completion_times[-1] == 120
    assert result.timeline[0].total_processed == 10


def test_disconnected_blocks_are_independent_sources_and_sinks():
    blocks = [
        ProcessBlock(id=1, type="INPUT", x=0, y=0, process_time=30, capacity=1),
        ProcessBlock(id=2, type="CUTTING", x=200, y=0, process_time=20, capacity=2),
    ]

    result = simulate(blocks, [], units_per_source=10)

    assert result.source_count == 2
    assert result.total_generated_units == 20
    assert result.total_time == 300
    assert [item.total_processed for item in result.timeline] == [10, 10]


def test_empty_blocks_return_empty_result():
    result = simulate([], [], units_per_source=10)

    assert result.timeline == []
    assert result.process_flow == []
    assert result.total_time == 0
    assert result.source_count == 0
    assert result.total_generated_units == 0
    assert result.bottleneck_id is None


def test_zero_units_per_source_returns_empty_simulation_for_existing_blocks():
    blocks = [
        ProcessBlock(id=1, type="INPUT", x=0, y=0, process_time=30, capacity=1),
        ProcessBlock(id=2, type="CUTTING", x=200, y=0, process_time=45, capacity=1),
    ]
    connections = [ProcessConnection(id=1, from_block=1, to_block=2)]

    result = simulate(blocks, connections, units_per_source=0)

    assert result.total_time == 0
    assert result.total_generated_units == 0
    assert result.bottleneck_id is None
    assert [item.total_processed for item in result.timeline] == [0, 0]
    assert [item.avg_waiting for item in result.timeline] == [0, 0]


def test_engine_rejects_invalid_inputs():
    blocks = [
        ProcessBlock(id=1, type="INPUT", x=0, y=0, process_time=30, capacity=1),
        ProcessBlock(id=2, type="CUTTING", x=200, y=0, process_time=45, capacity=1),
    ]

    with pytest.raises(ValueError):
        simulate(blocks, [], units_per_source=-1)

    with pytest.raises(ValueError):
        simulate(
            [ProcessBlock(id=1, type="INPUT", x=0, y=0, process_time=0, capacity=1)],
            [],
        )

    with pytest.raises(ValueError):
        simulate(
            [ProcessBlock(id=1, type="INPUT", x=0, y=0, process_time=30, capacity=0)],
            [],
        )

    with pytest.raises(ValueError):
        simulate(blocks, [ProcessConnection(id=1, from_block=1, to_block=999)])

    with pytest.raises(ValueError):
        simulate(
            blocks,
            [
                ProcessConnection(id=1, from_block=1, to_block=2),
                ProcessConnection(id=2, from_block=1, to_block=2),
            ],
        )

    with pytest.raises(ValueError):
        simulate(
            blocks,
            [
                ProcessConnection(id=1, from_block=1, to_block=2),
                ProcessConnection(id=2, from_block=2, to_block=1),
            ],
        )


def test_stable_topological_flow_preserves_block_order_for_ready_blocks():
    blocks = [
        ProcessBlock(id=1, type="INPUT", x=0, y=0, process_time=10, capacity=1),
        ProcessBlock(id=3, type="FREE", x=0, y=0, process_time=10, capacity=1),
        ProcessBlock(id=2, type="CUTTING", x=0, y=0, process_time=10, capacity=1),
    ]
    connections = [ProcessConnection(id=1, from_block=1, to_block=2)]

    assert topological_flow(blocks, connections) == [1, 3, 2]

    result = simulate(blocks, connections, units_per_source=1)
    assert result.bottleneck_id == 1


def test_branch_routing_uses_child_capacity_without_copying_units():
    blocks = [
        ProcessBlock(id=1, type="INPUT", x=0, y=0, process_time=10, capacity=1),
        ProcessBlock(id=2, type="CUTTING", x=0, y=0, process_time=100, capacity=4),
        ProcessBlock(id=3, type="HEAT", x=0, y=0, process_time=1, capacity=1),
    ]
    connections = [
        ProcessConnection(id=1, from_block=1, to_block=2),
        ProcessConnection(id=2, from_block=1, to_block=3),
    ]

    result = simulate(blocks, connections, units_per_source=10)
    processed_by_id = {item.block_id: item.total_processed for item in result.timeline}

    assert processed_by_id == {1: 10, 2: 8, 3: 2}


def test_branch_join_fifo_golden_flow():
    blocks = [
        ProcessBlock(id=1, type="INPUT", x=0, y=0, process_time=10, capacity=1),
        ProcessBlock(id=2, type="CUTTING", x=0, y=0, process_time=10, capacity=4),
        ProcessBlock(id=3, type="HEAT", x=0, y=0, process_time=10, capacity=1),
        ProcessBlock(id=4, type="PRESS", x=0, y=0, process_time=10, capacity=1),
    ]
    connections = [
        ProcessConnection(id=1, from_block=1, to_block=2),
        ProcessConnection(id=2, from_block=1, to_block=3),
        ProcessConnection(id=3, from_block=2, to_block=4),
        ProcessConnection(id=4, from_block=3, to_block=4),
    ]

    result = simulate(blocks, connections, units_per_source=10)
    processed_by_id = {item.block_id: item.total_processed for item in result.timeline}
    d_result = next(item for item in result.timeline if item.block_id == 4)

    assert result.process_flow == [1, 2, 3, 4]
    assert processed_by_id == {1: 10, 2: 8, 3: 2, 4: 10}
    assert result.total_time == 120
    assert d_result.start_times == [20, 30, 40, 50, 60, 70, 80, 90, 100, 110]
    assert d_result.waiting_times == [0] * 10
