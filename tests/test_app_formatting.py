from app import format_flow_diagram
from engine.models import ProcessConnection


def test_branch_join_flow_diagram_uses_actual_connections():
    connections = [
        ProcessConnection(id=1, from_block=1, to_block=2),
        ProcessConnection(id=2, from_block=1, to_block=3),
        ProcessConnection(id=3, from_block=2, to_block=4),
        ProcessConnection(id=4, from_block=3, to_block=4),
    ]

    diagram = format_flow_diagram(
        process_flow=[1, 2, 3, 4],
        connections=connections,
        block_label=lambda block_id: f"B{block_id}",
    )

    assert diagram.splitlines() == [
        "B1 -> B2",
        "B1 -> B3",
        "B2 -> B4",
        "B3 -> B4",
    ]
    assert "B1 -> B2 -> B3 -> B4" not in diagram


def test_flow_diagram_lists_independent_blocks_without_fake_edges():
    diagram = format_flow_diagram(
        process_flow=[1, 2],
        connections=[],
        block_label=lambda block_id: f"B{block_id}",
    )

    assert diagram.splitlines() == ["B1", "B2"]
