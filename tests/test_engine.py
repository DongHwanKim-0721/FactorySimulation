from engine.models import ProcessBlock, ProcessConnection
from engine.simulation import simulate


def test_single_input_block_ten_batches():
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

    result = simulate(blocks, [], total_batches=10)

    assert result.total_time == 300
    assert len(result.timeline) == 1
    assert result.bottleneck_id == 1


def test_linear_three_block_flow_ten_batches():
    blocks = [
        ProcessBlock(id=1, type="INPUT", x=0, y=0, process_time=30, capacity=1),
        ProcessBlock(id=2, type="CUTTING", x=200, y=0, process_time=45, capacity=1),
        ProcessBlock(id=3, type="HEAT", x=400, y=0, process_time=120, capacity=1),
    ]
    connections = [
        ProcessConnection(id=1, from_block=1, to_block=2),
        ProcessConnection(id=2, from_block=2, to_block=3),
    ]

    result = simulate(blocks, connections, total_batches=10)

    assert result.total_time == 1275
    assert result.bottleneck_id == 3
    assert result.process_flow == [1, 2, 3]
